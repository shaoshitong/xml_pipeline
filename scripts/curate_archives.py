#!/usr/bin/env python3
"""Safely unpack and pair native chart archives/files on HKUST without executing code.
Targets ChartMimic, TencentARC/Plot2Code, CSU-JPG/Chart2Code, RealChart2Code.
Raw archives are never modified; complete resources remain under extracted/.
"""
import argparse, collections, csv, hashlib, io, json, os, re, shutil, sqlite3, tarfile, time, urllib.parse, zipfile
from pathlib import Path
import curate_pairs as core

IMAGE_EXTS={'.png','.jpg','.jpeg','.webp','.gif'}
CODE_EXTS={'.py': 'python','.r':'r','.tex':'tikz','.asy':'asymptote','.svg':'svg','.drawio':'drawio','.xml':'drawio','.mmd':'mermaid','.puml':'plantuml','.html':'html'}


def signature(paths):return [{'name':p.name,'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in paths]

def volume_number(path):
    suffix=path.suffix[1:]
    if suffix.isdigit():return int(suffix)
    if suffix.isalpha() and suffix.islower():
        number=0
        for char in suffix:number=number*26+ord(char)-ord('a')
        return number
    raise ValueError('unrecognized_multipart_archive_volume')

def volume_base(path):return re.sub(r'\.(?:\d+|[a-z]{2,})$','',str(path))

def expected_volume_paths(source,name):
    root=source.parent.parent;expected=set()
    inventories=[root/'download_inventory.json']+list((root/'runs').glob('*/download_inventory.json'))
    for inventory in inventories:
        if not inventory.is_file():continue
        for repo in json.loads(inventory.read_text()):
            if repo.get('repo_id','').replace('/','--')!=source.name:continue
            for record in repo.get('files',[]):
                relative=record['path']
                if volume_base(relative)==name and re.search(r'\.tar\.gz\.(?:\d+|[a-z]{2,})$',relative):expected.add(source/relative)
    return expected


class PartReader(io.RawIOBase):
    def __init__(self,paths):self.paths=iter(paths);self.stream=None;self._done=False
    def readable(self):return True
    def readinto(self,target):
        target=memoryview(target);total=0
        while total<len(target):
            if self.stream is None:
                try:self.stream=next(self.paths).open('rb')
                except StopIteration:break
            n=self.stream.readinto(target[total:])
            if n:total+=n
            else:self.stream.close();self.stream=None
        return total
    def close(self):
        if self.stream:self.stream.close()
        super().close()


def safe_target(destination,name):
    p=Path(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name:return None
    out=(destination/p).resolve()
    return out if core.within(out,destination.resolve()) else None


def extract_archive(paths,destination):
    destination.mkdir(parents=True,exist_ok=True);marker=destination/'.extraction_complete.json';sig=signature(paths)
    if marker.is_file():
        try:
            if json.loads(marker.read_text()).get('parts')==sig:return {'status':'already_complete','destination':str(destination)}
        except Exception:pass
    files=0;bytes_out=0;skipped=collections.Counter()
    if len(paths)==1 and paths[0].suffix.lower()=='.zip':
        with zipfile.ZipFile(paths[0]) as z:
            for member in z.infolist():
                target=safe_target(destination,member.filename)
                if target is None or (member.external_attr>>16)&0o170000==0o120000:skipped['unsafe_member']+=1;continue
                if member.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(member) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
                files+=1;bytes_out+=member.file_size
    else:
        if len(paths)>1:
            nums=[volume_number(p) for p in paths]
            alphabetic=not paths[0].suffix[1:].isdigit()
            if nums[0] not in (0,1) or (alphabetic and nums[0]!=0) or nums!=list(range(nums[0],nums[-1]+1)):raise ValueError('missing_multipart_archive_volume')
            stream=io.BufferedReader(PartReader(paths),buffer_size=1024*1024);tf=tarfile.open(fileobj=stream,mode='r|gz')
        else:stream=None;tf=tarfile.open(paths[0],mode='r:*')
        try:
            for member in tf:
                target=safe_target(destination,member.name)
                if target is None or member.issym() or member.islnk() or not(member.isdir() or member.isfile()):skipped['unsafe_member']+=1;continue
                if member.isdir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True)
                src=tf.extractfile(member)
                if src is None:skipped['unreadable_member']+=1;continue
                with src,target.open('wb') as dst:shutil.copyfileobj(src,dst,1024*1024)
                files+=1;bytes_out+=member.size
        finally:
            tf.close()
            if stream:stream.close()
    receipt={'parts':sig,'files':files,'extracted_bytes':bytes_out,'skipped':dict(skipped),'destination':str(destination),'status':'complete'};core.write_json(marker,receipt);return receipt


def unpack_source(source,destination):
    receipts=[];groups=collections.defaultdict(list)
    for p in sorted(source.rglob('*')):
        if not p.is_file():continue
        if re.search(r'\.tar\.gz\.(?:\d+|[a-z]{2,})$',p.name):groups[volume_base(p.relative_to(source))].append(p)
        elif p.name.endswith(('.tar.gz','.tgz','.tar','.zip')):groups[str(p.relative_to(source))]=[p]
    for name,paths in sorted(groups.items()):
        paths=sorted(paths,key=lambda p:volume_number(p) if re.search(r'\.tar\.gz\.(?:\d+|[a-z]{2,})$',p.name) else 0)
        folder=destination/re.sub(r'[^A-Za-z0-9._-]','_',re.sub(r'\.(?:tar\.gz|tgz|tar|zip)$','',name))
        try:
            expected=expected_volume_paths(source,name)
            if expected and set(paths)!=expected:raise ValueError('selected_multipart_volumes_not_all_downloaded')
            receipt=extract_archive(paths,folder)
        except Exception as e:receipt={'status':'failed','parts':[str(x) for x in paths],'error':type(e).__name__+':'+str(e)[:150]}
        receipts.append(receipt);print(json.dumps({'event':'extract',**receipt}),flush=True)
    return receipts


def iter_json_records(path):
    if path.suffix.lower()=='.tsv':
        csv.field_size_limit(64*1024*1024)
        with path.open() as stream:
            for i,row in enumerate(csv.DictReader(stream,delimiter='\t')):yield i,row
        return
    if path.suffix.lower()=='.jsonl':
        with path.open() as stream:
            for i,line in enumerate(stream):
                if line.strip():
                    try:yield i,json.loads(line)
                    except json.JSONDecodeError:continue
        return
    # Most source manifests are small; large arrays are decoded incrementally.
    if path.stat().st_size<128*1024*1024:
        try:obj=json.loads(path.read_text())
        except Exception:return
        if isinstance(obj,list):
            for i,row in enumerate(obj):yield i,row
        elif isinstance(obj,dict):
            rows=next((obj[k] for k in ('data','examples','samples','records','dataset') if isinstance(obj.get(k),list)),None)
            if rows is not None:
                for i,row in enumerate(rows):yield i,row
            elif any(k in obj for k in ('code','image','InputFigure','GroundTruthFigure','conversations','messages')):yield 0,obj
            else:
                for k,v in obj.items():
                    if isinstance(v,dict):yield k,v
        return
    decoder=json.JSONDecoder();buffer='';offset=0;index=0;started=False
    with path.open() as stream:
        while True:
            chunk=stream.read(1024*1024);buffer+=chunk
            if not started:
                buffer=buffer.lstrip()
                if not buffer:return
                if not buffer.startswith('['):return
                buffer=buffer[1:];started=True
            while True:
                buffer=buffer.lstrip(' \r\n\t,')
                if buffer.startswith(']'):return
                try:obj,n=decoder.raw_decode(buffer)
                except json.JSONDecodeError:break
                yield index,obj;index+=1;buffer=buffer[n:]
            if not chunk:return


def index_assets(roots):
    by_name=collections.defaultdict(list);images=[];scripts=[];jsons=[]
    for root in roots:
        for p in root.rglob('*'):
            if not p.is_file():continue
            by_name[p.name].append(p)
            if p.suffix.lower() in IMAGE_EXTS:images.append(p)
            elif p.suffix.lower() in CODE_EXTS:scripts.append(p)
            elif p.suffix.lower() in ('.json','.jsonl','.tsv') and not p.name.startswith(('.', 'dataset_summary','download_','MANIFEST')):jsons.append(p)
    return by_name,images,scripts,jsons


def resolve_asset(value,base,roots,index):
    if isinstance(value,list):value=value[0] if len(value)==1 else None
    if isinstance(value,dict):value=value.get('path',value.get('file',value.get('image')))
    if not isinstance(value,str) or not value or len(value)>4096 or '://' in value:return None
    value=value.replace('\\','/');path=Path(value)
    candidates=[]
    if not path.is_absolute():
        candidates.extend([base/path]+[r/path for r in roots])
        for parent in list(base.parents)[:5]:
            if any(core.within(parent,r.resolve()) for r in roots):candidates.append(parent/path)
    for candidate in candidates:
        c=candidate.resolve()
        if c.is_file() and any(core.within(c,r.resolve()) for r in roots):return c
    matches=index.get(path.name,[])
    if len(matches)==1:return matches[0]
    suffix_matches=[p for p in matches if str(p).endswith(value)]
    if len(suffix_matches)==1:return suffix_matches[0]
    return None


def same_stem_image(code,index):
    # Exact generated stem is preferred to the input/reference stem for edit tasks.
    for ext in ('.png','.jpg','.jpeg','.webp'):
        own=code.with_suffix(ext)
        if own.is_file():return own
    for ext in ('.png','.jpg','.jpeg','.webp'):
        found=index.get(code.stem+ext,[])
        if len(found)==1:return found[0]
    return None


def omni_scope(row):
    kind=str(row.get('code_type','')).casefold();figure=re.sub(r'[^a-z0-9]+',' ',str(row.get('figure_type','')).casefold())
    if re.search(r'html|smiles|molfile',kind) or re.search(r'molecul|chemical structure|web ?page|website|wireframe|icon|logo|table|matrix|commutative|geometr|circuit',figure):return None,'omni_out_of_scope_web_chemical_icon_math_table'
    if re.search(r'chart|plot|scatter|treemap|box chart|histogram|heatmap|line|bar|pie|area|contour|density|violin|radar|quiver|wordcloud|error|bubble',figure):return 'chart',None
    if re.search(r'flow|pipeline|architecture|diagram|network|graph|tree|framework',figure):return 'scientific_diagram',None
    return None,'omni_figure_domain_not_established'


def candidate_pairs(roots,index,scripts,jsons,require_tsv_join=False,require_before_revision=False,require_realchart_pairs=False):
    if require_realchart_pairs:
        # RealChart2Code documents generated_code_* with generated_plot_*.
        # Refined outputs stay within their own refinement directory and variant.
        # Never use a basename lookup across samples or substitute an earlier image.
        for code in sorted(scripts):
            match=re.fullmatch(r'(generated|refined)_code_(\w+)\.py',code.name)
            base=code.parent.parent if re.fullmatch(r'refine_version_\d+',code.parent.name) else code.parent
            metadata_file=base/'complete_metadata.json'
            common={'code_path':code,'metadata':{'source_code_name':code.name,'sample_directory':base.name,'generation_stage':match[1] if match else None,'variant':match[2] if match else None},'manifest':metadata_file if metadata_file.is_file() else None,'row_index':0,'pairing_evidence':'realchart_same_directory_stage_variant_code_plot','category':'chart','pair_side':f'{match[1]}:{match[2]}' if match else None}
            if not match:
                yield {**common,'skip_reason':'unrecognized_realchart_code_filename'};continue
            image=code.with_name(f'{match[1]}_plot_{match[2]}.png')
            if not image.is_file() or image.resolve().parent!=code.parent.resolve():
                yield {**common,'skip_reason':'missing_same_directory_same_variant_plot'};continue
            yield {**common,'image_path':image}
        return
    if require_before_revision:
        folders={p.parent for p in scripts if p.name=='input.svg'}|{p.parent for p in jsons if p.name=='sample.json'}
        for folder in sorted(folders):
            svg=folder/'input.svg';image=folder/'input.png';metadata_file=folder/'sample.json';metadata={}
            if metadata_file.is_file():
                try:metadata=json.loads(metadata_file.read_text())
                except (OSError,json.JSONDecodeError):pass
            common={'metadata':metadata,'manifest':metadata_file if metadata_file.is_file() else None,'row_index':0,'pairing_evidence':'same_sample_before_input_svg_and_input_png','category':'scientific_diagram'}
            if not svg.is_file():yield {**common,'skip_reason':'revision_input_svg_missing'};continue
            # Never use target.png or a basename match in another sample folder.
            if not image.is_file():yield {**common,'skip_reason':'revision_input_png_missing'};continue
            yield {**common,'image_path':image,'code_path':svg}
        return
    # Native script/image pairs are the least ambiguous, even in editing datasets.
    for code in scripts:
        if require_tsv_join:continue
        image=same_stem_image(code,index)
        if image:yield {'image_path':image,'code_path':code,'metadata':{},'pairing_evidence':'matching_stem_script_and_render'}
    for manifest in jsons:
        if require_tsv_join and manifest.suffix.lower()!='.tsv':continue
        for row_index,row in iter_json_records(manifest):
            if not isinstance(row,dict):continue
            if require_tsv_join:
                metadata={k:v for k,v in row.items() if k!='image'}
                category,scope_error=omni_scope(row)
                common={'metadata':metadata,'manifest':manifest,'row_index':row_index,'pairing_evidence':'tsv_answer_unique_gt_filename_join','category':category}
                if scope_error:yield {**common,'skip_reason':scope_error};continue
                code=resolve_asset(row.get('answer'),manifest.parent,roots,index)
                if code is None or code.suffix.lower() not in CODE_EXTS:yield {**common,'skip_reason':'omni_answer_gt_code_not_found_or_ambiguous'};continue
                data=core.image_bytes(row.get('image'),roots[0]);info=core.image_info(data) if data else None
                if not info:yield {**common,'skip_reason':'omni_missing_or_invalid_base64_image'};continue
                folder=roots[1]/'tsv_images';folder.mkdir(parents=True,exist_ok=True);suffix={"JPEG":'.jpg',"PNG":'.png',"WEBP":'.webp'}.get(info['format'],'.img');image=folder/(hashlib.sha256(data).hexdigest()+suffix)
                if not image.is_file():image.write_bytes(data)
                yield {**common,'image_path':image,'code_path':code,'metadata_image_provenance':'base64_image_column_in_source_tsv'}
                continue
            # ChartMimic explicitly supplies input and ground-truth code-image pairs.
            if 'InputFigure' in row or 'GroundTruthFigure' in row:
                for label in ('Input','GroundTruth'):
                    image=resolve_asset(row.get(label+'Figure'),manifest.parent,roots,index);code=resolve_asset(row.get(label+'FigureCode'),manifest.parent,roots,index)
                    if image and code:yield {'image_path':image,'code_path':code,'metadata':row,'manifest':manifest,'row_index':row_index,'pair_side':label,'pairing_evidence':'explicit_same_side_manifest_fields'}
                continue
            value,key=core.code_value(row);code=core.unwrap_code(value)
            code_path=None
            for k in ('code_file','code_path','python_file','GroundTruthFigureCode','script','file_path','hf_drawio'):
                code_path=resolve_asset(row.get(k),manifest.parent,roots,index)
                if code_path:break
            if not code_path and isinstance(value,str) and Path(value).suffix.lower() in CODE_EXTS:
                code_path=resolve_asset(value,manifest.parent,roots,index)
                if code_path:code=''
            if not code and not code_path:continue
            image=None
            for k in ('image','image_path','image_file','img','figure','png','filename','file_name','target_image','ground_truth_image','images','hf_image'):
                image=resolve_asset(row.get(k),manifest.parent,roots,index)
                if image and image.suffix.lower() in IMAGE_EXTS:break
                image=None
            # Conversations may carry image names in the user message.
            if image is None:
                m=json.dumps(row.get('conversations',row.get('messages',[])),ensure_ascii=False)
                refs=re.findall(r'[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|webp)',m)
                unique={str(p):p for ref in refs if (p:=resolve_asset(ref,manifest.parent,roots,index))}
                if len(unique)==1:image=next(iter(unique.values()))
            if image:yield {'image_path':image,'code_path':code_path,'inline_code':code,'metadata':row,'manifest':manifest,'row_index':row_index,'code_key':key,'pairing_evidence':'explicit_image_and_code_fields'}


def dependencies(code,code_file,roots,index,strict_relative=False):
    assets=[];missing=[];base=code_file.parent if code_file else roots[0]
    patterns=[r'(?:read\.csv|read\.table|readRDS|read_csv|read_excel|read_json|read_parquet|loadtxt|genfromtxt|imread|Image\.open|np\.load|open)\(\s*[\'"]([^\'"\n]+)',r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}']
    for pattern in patterns:
        for value in re.findall(pattern,code):
            if value.startswith(('data:','#')):continue
            if '://' in value:missing.append({'reference':value,'reason':'external_data_dependency'});continue
            if value.lower().endswith(('.png','.jpg','.jpeg','.pdf','.csv','.xlsx','.json','.npy','.npz','.parquet','.tsv','.txt','.ttf','.otf','.woff','.woff2')):
                p=(base/value).resolve() if strict_relative else resolve_asset(value,base,roots,index)
                if strict_relative and (not core.within(p,base.resolve()) or not p.is_file()):p=None
                if p:assets.append({'reference':value,'path':str(p)})
                else:missing.append({'reference':value,'reason':'missing_data_or_asset'})
    # Local SVG resources must be retained, and their declared paths verified.
    svg_references=re.findall(r'<(?:image|img|use|feImage)\b[^>]*\b(?:(?:xlink:)?href|src)=[\'"]([^\'"]+)',code,re.I)
    if '<svg' in code:svg_references+=re.findall(r'url\(\s*[\'"]?([^\s)\'";]+)',code,re.I)
    for value in svg_references:
        if value.startswith(('data:','#')):continue
        if '://' in value or value.startswith('//'):missing.append({'reference':value,'reason':'external_data_dependency'});continue
        relative=urllib.parse.unquote(value).split('?',1)[0].split('#',1)[0]
        p=(base/relative).resolve() if strict_relative else resolve_asset(relative,base,roots,index)
        if strict_relative and (not core.within(p,base.resolve()) or not p.is_file()):p=None
        if p:assets.append({'reference':value,'path':str(p)})
        else:missing.append({'reference':value,'reason':'missing_data_or_asset'})
    # matplotlib package sample-data resources are packaged runtime dependencies,
    # distinct from a missing user data CSV; record the names for reproduction.
    packaged=re.findall(r'get_sample_data\(\s*[\'"]([^\'"\n]+)',code)
    return assets,missing,packaged


def validate_r(code):
    return None if re.search(r'ggplot|plotly|plot\(|ggplot2|geom_',code) else 'unrecognized_r_plot_code'


def curate_source(root,source,db,base_db,only_extract=False):
    is_dwt='dwt_drawio' in source.name.casefold()
    is_official='jgraph--drawio-templates' in source.name.casefold()
    is_omni='omni-i2c' in source.name.casefold()
    is_revision='scidiagramrevision' in source.name.casefold()
    is_realchart=source.name.casefold()=='zjj1233--realchart2code'
    category='scientific_diagram' if is_dwt else 'chart'
    extracted=root/'extracted'/source.name;extracted.mkdir(parents=True,exist_ok=True)
    stats={'source':source.name,'raw_candidates':0,'paired_image_code':0,'rejected':0,'reasons':collections.Counter(),'formats':collections.Counter(),'archives':unpack_source(source,extracted)}
    if any(x.get('status') not in ('complete','already_complete') for x in stats['archives']):
        stats['error']='one_or_more_selected_archives_not_completely_extracted'
    if only_extract:return stats
    if stats.get('error'):
        # Never pair files left by an interrupted tar/zip extraction.
        (root/'manifests'/(source.name+'.archives.jsonl')).write_text('')
        for stale in (root/'clean'/source.name/'native').glob('part*.parquet'):stale.unlink()
        return stats
    roots=[source,extracted];index,images,scripts,jsons=index_assets(roots)
    stats['inventory']={'images':len(images),'scripts':len(scripts),'metadata_files':len(jsons)}
    manifest_path=root/'manifests'/(source.name+'.archives.jsonl');reject_path=root/'manifests'/(source.name+'.archives.rejected.jsonl');out=root/'clean'/source.name/'native';out.mkdir(parents=True,exist_ok=True)
    for stale in out.glob('part*.parquet'):stale.unlink()
    rows_for_parquet=[];part=0
    def flush_rows():
        nonlocal part
        if not rows_for_parquet:return
        import pyarrow as pa,pyarrow.parquet as pq
        pq.write_table(pa.Table.from_pylist(rows_for_parquet),out/f'part{part:05d}.parquet',compression='zstd');part+=1;rows_for_parquet.clear()
    with manifest_path.open('w') as mf,reject_path.open('w') as rf:
        for candidate in candidate_pairs(roots,index,scripts,jsons,require_tsv_join=is_omni,require_before_revision=is_revision,require_realchart_pairs=is_realchart):
            if candidate.get('skip_reason'):
                stats['raw_candidates']+=1;stats['rejected']+=1;stats['reasons'][candidate['skip_reason']]+=1;rf.write(json.dumps({'source':source.name,'reason':candidate['skip_reason'],'metadata_file':str(candidate['manifest'].relative_to(root)) if candidate.get('manifest') else None,'metadata_row':candidate['row_index'],'metadata':candidate['metadata']},ensure_ascii=False)+'\n');continue
            if is_omni or is_revision:category=candidate['category']
            stats['raw_candidates']+=1;image=candidate['image_path'];code_path=candidate.get('code_path');code=candidate.get('inline_code','')
            reason=None
            if is_official:
                scope=str(code_path or image).replace('\\','/').lower()
                if re.search(r'(^|/)charts/',scope):category='chart'
                elif re.search(r'(^|/)flowcharts/',scope):category='scientific_diagram'
                else:reason='official_template_out_of_requested_chart_flowchart_scope'
            if code_path:
                try:code=code_path.read_text().strip()
                except (OSError,UnicodeError):reason='unreadable_code'
            fmt=CODE_EXTS.get(code_path.suffix.lower()) if code_path else core.infer_format(code)
            if not code_path and re.search(r'(?m)^\s*(?:library\(|require\(|[A-Za-z_.][A-Za-z0-9_.]*\s*<-)',code):
                fmt='r'
            if fmt=='python' and code_path and code_path.suffix.lower()=='.py':pass
            if not fmt or fmt=='unknown':
                fmt='r' if re.search(r'(?m)^\s*library\(|ggplot\(|geom_\w+\(|(?:plot_ly|plotlyOutput)\(',code) else core.infer_format(code)
            assets,missing,packaged=dependencies(code,code_path,roots,index,strict_relative=is_revision or is_realchart)
            allowed_svg_assets={str(Path(urllib.parse.unquote(a['reference']).split('?',1)[0].split('#',1)[0])) for a in assets}
            if fmt=='r':reason=reason or validate_r(code)
            else:reason=reason or core.validate_code(code,fmt,allowed_svg_assets if fmt=='svg' else None)
            try:data=image.read_bytes();info=core.image_info(data)
            except OSError:data=None;info=None
            if not reason and not info:reason='invalid_image'
            if not reason and missing:reason=missing[0]['reason']
            meta=candidate['metadata']
            if not reason and fmt=='python':
                reason=core.python_dependency_issue(code,meta if isinstance(meta,dict) else {},code_path.parent if code_path else roots[0],
                    available_assets={asset['reference']:asset['path'] for asset in assets})
            if not reason and fmt=='tikz':reason=core.tex_dependency_issue(code,code_path.parent if code_path else roots[0])
            if not reason and fmt=='asymptote':reason=core.asymptote_support().dependency_issue(code,code_path.parent if code_path else roots[0],available_assets={asset['reference']:asset['path'] for asset in assets})
            if not reason and fmt=='asymptote' and not core.actual_chart_evidence(code,fmt):reason='chart_content_not_established'
            if not reason and fmt not in ('python','r','vegalite','html','svg','tikz','asymptote','mermaid','drawio'):reason='non_plot_code'
            # These selected sources contain visual charts; guard asset/demo images.
            plot_primitives=r'\.(?:plot|plot_surface|plot_wireframe|plot_trisurf|plot3D|scatter3D|loglog|semilogx|semilogy|scatter|bar|barh|broken_barh|hist|hist2d|hexbin|imshow|matshow|contour|contourf|pcolormesh|pcolor|boxplot|violinplot|pie|errorbar|fill_between|stackplot|stem|step|quiver|streamplot|eventplot|add_trace|add_traces|addplot|heatmap|line|area|density|kdeplot|jointplot|pairplot|regplot|displot|clustermap)\s*\(|(?m:^\s*plot\()|draw_networkx|nx\.draw|ggplot\(|geom_|plot_ly\(|graph_objects|go\.(?:Scatter|Bar|Heatmap|Surface)|\\begin\{axis\}|vega|echarts'
            if not reason and (is_dwt or is_official) and fmt!='drawio':reason='native_source_requires_drawio'
            if not reason and not is_dwt and not is_official and not is_omni and not is_revision and not re.search(plot_primitives,code,re.I) and not (fmt=='asymptote' and core.actual_chart_evidence(code,fmt)):reason='chart_content_not_established'
            image_sha=hashlib.sha256(data).hexdigest() if data else None;code_sha=hashlib.sha256(code.encode()).hexdigest();pair_sha=hashlib.sha256((str(image_sha)+code_sha).encode()).hexdigest()
            if not reason:
                if base_db and base_db.execute('SELECT 1 FROM pairs WHERE pair_sha=?',(pair_sha,)).fetchone():reason='duplicate_existing_parquet_pair'
                else:
                    try:db.execute('INSERT INTO pairs VALUES (?)',(pair_sha,))
                    except sqlite3.IntegrityError:reason='duplicate_exact_pair'
            record={'source':source.name,'image_file':str(image.relative_to(root)),'code_file':str(code_path.relative_to(root)) if code_path else None,'format':fmt,'category':category,'pairing_evidence':candidate['pairing_evidence'],'pair_side':candidate.get('pair_side'),'metadata_file':str(candidate['manifest'].relative_to(root)) if candidate.get('manifest') else None,'metadata_row':candidate.get('row_index'),'dependencies':assets,'packaged_runtime_sample_data':packaged,'missing_dependencies':missing}
            if reason:
                stats['rejected']+=1;stats['reasons'][reason]+=1;record['reason']=reason;rf.write(json.dumps(record,ensure_ascii=False)+'\n');continue
            record.update({'image_sha256':image_sha,'code_sha256':code_sha,'image_info':info,'image_provenance':'dataset_provided_reference_figure' if is_dwt else ('official_template_preview_png' if is_official else ('dataset_provided_reference_figure' if is_omni else ('dataset_provided_before_edit_render' if is_revision else 'dataset_provided_plot_render'))),'gold_code_provenance':'reconstructed_codex_subagent' if is_dwt else ('official_drawio_template' if is_official else ('official_benchmark_gt_filename_join' if is_omni else ('dataset_input_svg_before_edit' if is_revision else 'dataset_provided_plot_source'))),'structurally_complete':True,'code_execution_checked':False,'clean_file':str((out/f'part{part:05d}.parquet').relative_to(root)),'clean_row':len(rows_for_parquet),'image_key':'image','code_key':'code'})
            if is_revision:record.update({'alignment_role':'before_edit_input','asset_root':str(code_path.parent.relative_to(root)),'source_svg_file':str(code_path.relative_to(root))})
            if is_realchart:record.update({'alignment_role':'same_stage_variant_plot','asset_root':str(code_path.parent.relative_to(root)),'image_provenance':'synthetic_render_provided_by_dataset','gold_code_provenance':'dataset_generated_or_refined_plot_source'})
            stats['paired_image_code']+=1;stats['formats'][fmt]+=1;mf.write(json.dumps(record,ensure_ascii=False)+'\n')
            rows_for_parquet.append({'source':source.name,'category':category,'format':fmt,'image_file':record['image_file'],'image':{'bytes':data,'path':image.name},'code':code,'source_code_file':record['code_file'],'source_metadata_file':record['metadata_file'],'source_metadata_json':json.dumps(meta,ensure_ascii=False),'dependencies_json':json.dumps(assets,ensure_ascii=False),'pairing_evidence':record['pairing_evidence'],'pair_side':record['pair_side']})
            if len(rows_for_parquet)>=64:flush_rows();db.commit()
        flush_rows();db.commit()
    stats['reasons']=dict(stats['reasons']);stats['formats']=dict(stats['formats']);return stats


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--only',nargs='*');p.add_argument('--extract-only',action='store_true');a=p.parse_args();root=a.root.resolve();(root/'manifests').mkdir(exist_ok=True);(root/'reports').mkdir(exist_ok=True)
    db=sqlite3.connect(root/'manifests'/'native_dedup.sqlite');db.execute('CREATE TABLE IF NOT EXISTS pairs(pair_sha TEXT PRIMARY KEY)');db.execute('DELETE FROM pairs');db.commit()
    original=root/'manifests'/'dedup.sqlite';base_db=sqlite3.connect('file:'+str(original)+'?mode=ro',uri=True) if original.is_file() else None
    summary={'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sources':{},'paired_image_code':0,'validation':'image decode, code syntax, explicit/same-stem pairing, dependency existence; dataset code is never executed'}
    for source in sorted((root/'raw').iterdir()):
        if not source.is_dir():continue
        if a.only:
            if not any(x.lower() in source.name.lower() for x in a.only):continue
        elif not any(x in source.name.lower() for x in ('chartmimic','tencentarc--plot2code','csu-jpg--chart2code','realchart','dwt_drawio','jgraph--drawio-templates','omni-i2c','scidiagramrevision')):continue
        try:stats=curate_source(root,source,db,base_db,a.extract_only)
        except Exception as e:stats={'source':source.name,'error':type(e).__name__+':'+str(e)[:200],'paired_image_code':0}
        summary['sources'][source.name]=stats;summary['paired_image_code']+=stats['paired_image_code'];core.write_json(root/'reports'/'archive_summary.json',summary);print(json.dumps(stats,ensure_ascii=False),flush=True)
    summary['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());core.write_json(root/'reports'/'archive_summary.json',summary)
    db.close()
    if base_db:base_db.close()

if __name__=='__main__':main()
