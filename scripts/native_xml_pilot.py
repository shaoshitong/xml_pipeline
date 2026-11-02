#!/usr/bin/env python3
"""Read-only Starvector SVG scan plus at most ten offline native-XML pilots.
Writes only evaluation/native_xml_pilot; does not modify raw, catalog or derived DB.
"""
import argparse, base64, collections, concurrent.futures, hashlib, html, json, re, time, urllib.parse, xml.etree.ElementTree as ET, zlib
from pathlib import Path
import curate_derived as derived

MARKER=re.compile(r'mxfile|mxGraphModel',re.I)
CONTENT=re.compile(r'\b(?:content|data-content|data-mxgraph|mxfile)\s*=',re.I)
CONTENT_KEYS={'content','data-content','data-mxgraph','mxfile'}


def unpack_outer_base64(value):
    """Adapt uncommon outer encodings; renderer and native XML parser are reused."""
    for _ in range(3):
        decoded=html.unescape(value)
        if re.search(r'%[0-9A-Fa-f]{2}',decoded):decoded=urllib.parse.unquote(decoded)
        if decoded==value:break
        value=decoded
    if value.startswith('data:') and ',' in value:value=value.split(',',1)[1]
    if len(value)<16 or len(value)>derived.MAX_XML or not re.fullmatch(r'[A-Za-z0-9+/=\s]+',value):return None,None
    try:raw=base64.b64decode(re.sub(r'\s+','',value),validate=True)
    except Exception:return None,None
    possibilities=[(raw,'base64_outer_xml')]
    for bits,name in [(-15,'base64_raw_deflate_outer_xml'),(15,'base64_zlib_outer_xml'),(31,'base64_gzip_outer_xml')]:
        try:
            decoder=zlib.decompressobj(bits);data=decoder.decompress(raw,derived.MAX_XML+1)
            if len(data)<=derived.MAX_XML and not decoder.unconsumed_tail and decoder.eof:possibilities.append((data,name))
        except zlib.error:pass
    for data,name in possibilities:
        try:text=urllib.parse.unquote(data.decode())
        except UnicodeError:continue
        if len(text.encode())<=derived.MAX_XML and MARKER.search(text) and re.search(r'<(?:mxfile|mxGraphModel)\b',text):return text,name
    return None,None


def native_document(root):
    native=derived.extract_native(root)
    if native:return native,'standard_content_xml_or_inner_diagram_encoding'
    # Some exporters wrap the complete mxfile in base64, not only its diagram.
    # Changes here affect metadata parsing only. Rendering still uses original SVG.
    for node in root.iter():
        for key,value in list(node.attrib.items()):
            if key.rsplit('}',1)[-1].casefold() not in CONTENT_KEYS:continue
            values=[value]
            try:
                obj=json.loads(value)
                if isinstance(obj,dict):values.extend(v for v in obj.values() if isinstance(v,str))
            except Exception:pass
            decoded=encoding=None
            for candidate in values:
                decoded,encoding=unpack_outer_base64(candidate)
                if decoded:break
            if decoded:
                original=node.attrib[key];node.attrib[key]=decoded
                try:native=derived.extract_native(root)
                finally:node.attrib[key]=original
                if native:return native,encoding
    return None,None


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.replace(path)


def run(args):
    import pyarrow.parquet as pq
    root=args.root.resolve();source=root/'raw'/'starvector--svg-diagrams';out=root/'evaluation'/'native_xml_pilot';out.mkdir(parents=True,exist_ok=True)
    counts=collections.Counter();reasons=collections.Counter();categories=collections.Counter();encodings=collections.Counter();files=[];examples=[];pending={};started=time.monotonic();attempts=min(max(args.max_examples,0),10)
    summary={'source_repo':'starvector/svg-diagrams','raw_directory':str(source),'output_directory':str(out),'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'counts':{},'rejections':{},'categories':{},'encodings':{},'files':files,'examples':examples,'limits':{'maximum_render_attempts':attempts,'render_workers':min(max(args.workers,1),4),'per_image_timeout_seconds':30,'maximum_expanded_xml_bytes':derived.MAX_XML},'scope':'Read-only all-row SVG scan; only first qualified native documents are rendered. No training catalog or derived-state DB writes.','hash_definition':'source_svg_sha256 hashes the exact Parquet SVG string encoded UTF-8; original_xml_sha256 hashes the extracted mxfile/mxGraphModel element before normalization (XML prolog excluded); normalized_xml_sha256 hashes saved native.drawio.','limitations':['Qualification is deterministic metadata/text/graph and asset validation, not human semantic confirmation.','PNG is rendered from the supplied original SVG. Native XML is extracted from its embedded exporter state; original authorship and pixel equivalence between native XML and SVG are not guaranteed.','Ten examples are the first qualified rows, not a statistically representative quality sample.','Provided-image/code pairs and these SVG-derived pilots are separate; pilot outputs are not added to the dataset catalog.']}
    def save_summary(finished=False):
        summary.update({'counts':dict(counts),'rejections':dict(reasons),'categories':dict(categories),'encodings':dict(encodings),'elapsed_seconds':round(time.monotonic()-started,2)})
        if finished:summary['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        write_json(out/'summary.json',summary)
    def collect_ready(wait=False):
        done=set(pending) if wait else {future for future in pending if future.done()}
        for future in done:
            record=pending.pop(future)
            try:result=future.result()
            except Exception as e:result={'ok':False,'reason':'pilot_renderer_exception','error':type(e).__name__+':'+str(e)[:250]}
            record['render_status']='success' if result.get('ok') else 'failed';record['render_seconds']=result.get('seconds');record['render_error']=result.get('error',result.get('reason'))
            case=out/record['example_id']
            if result.get('ok'):
                png=result['png'];(case/'source_render.png').write_bytes(png);record['image_sha256']=hashlib.sha256(png).hexdigest();record['image_bytes']=len(png);record['png_file']=str((case/'source_render.png').relative_to(root));counts['pilot_render_success']+=1
            else:counts['pilot_render_failed']+=1
            write_json(case/'case.json',record)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max(args.workers,1),4)) as pool,(out/'candidate_inventory.jsonl').open('w') as audit:
        if not source.is_dir():summary['error']='raw_source_directory_missing';save_summary(True);return
        for file in sorted(source.rglob('*.parquet')):
            rel=str(file.relative_to(source));stats={'raw_file':rel,'rows':0,'native_xml_extracted':0,'qualified_native_candidates':0};files.append(stats)
            try:
                reader=pq.ParquetFile(file);names=reader.schema_arrow.names
                if not any(name in names for name in ('svg','Svg','SVG','source_svg','code')):raise ValueError('no_supported_svg_column')
                columns=[name for name in names if name in ('svg','Svg','SVG','source_svg','code','filename','Filename','caption','description','category','metadata','source')]
                batches=reader.iter_batches(batch_size=32,columns=columns)
                for batch in batches:
                    for row in batch.to_pylist():
                        index=stats['rows'];stats['rows']+=1;counts['raw_rows']+=1;svg,key=derived.source_svg(row)
                        if not svg:counts['rows_without_svg']+=1;continue
                        counts['svg_rows']+=1;marker=bool(MARKER.search(svg));content=bool(CONTENT.search(svg))
                        if marker:counts['rows_with_literal_native_marker']+=1
                        if content:counts['rows_with_content_metadata_attribute']+=1
                        if not marker and not content:counts['rows_without_native_candidate_marker_or_content']+=1;continue
                        counts['native_marker_or_content_candidates']+=1;record={'source_repo':'starvector/svg-diagrams','raw_file':rel,'raw_row':index,'svg_key':key,'source_filename':str(row.get('Filename',row.get('filename','')))}
                        try:
                            tree=derived.parse_svg(svg);native,encoding=native_document(tree)
                            if native is None:raise ValueError('no_extractable_native_xml_in_content')
                            counts['native_xml_extracted']+=1;stats['native_xml_extracted']+=1;encodings[encoding]+=1;record.update({'original_xml_sha256':native['original_sha256'],'normalized_xml_sha256':hashlib.sha256(native['code'].encode()).hexdigest(),'encoding':encoding,'inner_diagram_decompressed':native['expanded_compressed_diagram']})
                            domain_text=native['code']+' '+record['source_filename']
                            if re.search(r'mxgraph\.mockup|wireframe|landing.?page|login.?page|login.?form|navigation.?bar|navbar|shopping.?cart|checkout',domain_text,re.I):raise ValueError('web_ui_or_wireframe_domain')
                            issue=derived.native_asset_issue(native)
                            if issue:raise ValueError(issue)
                            width,height,original_width,original_height=derived.canvas(tree,args.max_side);elements,raster=derived.asset_and_raster_check(tree,original_width,original_height);category,basis,structure=derived.classify(row,rel,tree,native,elements)
                            if category is None:raise ValueError(basis)
                            counts['qualified_native_candidates']+=1;stats['qualified_native_candidates']+=1;categories[category]+=1;source_sha=hashlib.sha256(svg.encode()).hexdigest();record.update({'qualified':True,'source_svg_sha256':source_sha,'category':category,'semantic_basis':basis,'structure':structure,'raster_image_elements':raster,'width':width,'height':height})
                            if len(examples)<attempts:
                                example_id=f'case_{len(examples)+1:02d}';case=out/example_id;case.mkdir(exist_ok=True);(case/'source.svg').write_text(svg);(case/'native.drawio').write_text(native['code']);backend='chromium' if elements['foreignObject'] else 'cairosvg';example={**record,'example_id':example_id,'source_svg_file':str((case/'source.svg').relative_to(root)),'native_xml_file':str((case/'native.drawio').relative_to(root)),'image_provenance':'rendered_from_source_svg','code_provenance':'embedded_original_drawio','render_backend':backend,'render_status':'pending','native_xml_vs_svg_pixel_equivalence_verified':False};examples.append(example);write_json(case/'case.json',example);future=pool.submit(derived.job,svg,width,height,backend,30);pending[future]=example;counts['pilot_render_attempts']+=1
                        except Exception as e:
                            reason=str(e)[:180] if isinstance(e,ValueError) else type(e).__name__;reasons[reason]+=1;record.update({'qualified':False,'reason':reason})
                        audit.write(json.dumps(record,ensure_ascii=False)+'\n')
                    collect_ready()
                    if counts['raw_rows']%4096<32:
                        save_summary();print(json.dumps({'event':'native_xml_scan_progress','rows':counts['raw_rows'],'native_extracted':counts['native_xml_extracted'],'qualified':counts['qualified_native_candidates'],'pilot_success':counts['pilot_render_success']}),flush=True)
            except Exception as e:stats['error']=type(e).__name__+':'+str(e)[:250];counts['parquet_scan_failures']+=1
            collect_ready();save_summary();print(json.dumps({'event':'native_xml_file_complete',**stats}),flush=True)
        collect_ready(wait=True)
    summary['scan_complete']=not bool(counts['parquet_scan_failures']);save_summary(True);print(json.dumps({'ok':summary['scan_complete'],'summary':str(out/'summary.json'),'raw_rows':counts['raw_rows'],'native_xml_extracted':counts['native_xml_extracted'],'qualified_native_candidates':counts['qualified_native_candidates'],'pilot_render_attempts':counts['pilot_render_attempts'],'pilot_render_success':counts['pilot_render_success']}),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--max-examples',type=int,default=10);p.add_argument('--workers',type=int,default=4);p.add_argument('--max-side',type=int,default=3072);args=p.parse_args();run(args)

if __name__=='__main__':main()
