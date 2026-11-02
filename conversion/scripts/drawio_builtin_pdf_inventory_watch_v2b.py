"""Inventory real acquired PDFs and invoke the pinned official importer once.

Counts of text/images/vector paths are read-only evidence, never PDF geometry
conversion. Downloaded code is not executed. Original v1 records are retained.
"""
from pathlib import Path
import argparse, collections, datetime, fcntl, hashlib, importlib.util, json, os, subprocess, sys, time

R=Path('/backup/shaoshitong/img2code_20261029')
A=R/'clean/arxiv_research_figures_v1/acquisition_pilot_v1'
V1=R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1'
D=R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v2b'
PDF_RUNTIME=R/'evaluation/assets/pdf_inventory_python_v1'
sys.path.insert(0,str(PDF_RUNTIME))
S=V1/'official_importer'
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda b:hashlib.sha256(b).hexdigest()
def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def once(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def atomic(p,obj):
    temp=p.with_name(p.name+'.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');os.replace(temp,p)
spec=importlib.util.spec_from_file_location('official_probe_v1',R/'conversion/scripts/drawio_builtin_pdf_import_probe_v1.py')
official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)

def inventory(path,ident):
    import fitz
    doc=fitz.open(path);pages=[]
    try:
        for p in doc:
            text=p.get_text('text');words=p.get_text('words');blocks=p.get_text('blocks');drawings=p.get_drawings()
            pages.append({'page':p.number+1,'width_points':round(p.rect.width,3),'height_points':round(p.rect.height,3),
              'text_characters':len(text.strip()),'text_words':len(words),'text_blocks':sum(len(b)>6 and b[6]==0 for b in blocks),
              'image_occurrences':len(p.get_images(full=True)),'vector_path_objects':len(drawings),'vector_path_segments':sum(len(d.get('items',[])) for d in drawings)})
        totals={k:sum(p[k] for p in pages) for k in ['text_characters','text_words','text_blocks','image_occurrences','vector_path_objects','vector_path_segments']}
        rel=path.relative_to(A);parts=[x.lower() for x in rel.parts];stem=path.stem.lower();basis=[]
        if path.name=='paper.pdf':purpose='whole_paper';basis=['Acquisition paper.pdf document locator; not an isolated figure.']
        elif 'logo' in parts or 'logos' in parts or 'logo' in stem:purpose='logo_asset';basis=['Source directory/stem explicitly labels logo; vector density cannot promote a logo to research figure.']
        elif len(pages)<=4 and ('figures' in parts or 'figure' in parts or 'figs' in parts) and ((totals['text_characters']>=120 and totals['text_words']>=20 and totals['vector_path_objects']>=10) or (totals['image_occurrences']>=2 and totals['text_characters']>=80)):
            purpose='complex_figure_candidate';basis=['Explicit source figure asset, at most4pages, with measured text plus multiple vector/image objects; semantic value still needs review.']
        else:purpose='figure_candidate_unknown';basis=['Source PDF not proven to be a complex figure by the conservative measured rule.']
        return {'schema':'readonly_pdf_source_inventory_v2b','id':ident,'path':str(path.relative_to(R)),'pdf_bytes':path.stat().st_size,'page_count':len(pages),'purpose':purpose,'purpose_basis':basis,'pages':pages,'totals':totals,
          'pdf_metadata_title':doc.metadata.get('title',''),'read_only_fitz':True,'geometry_conversion':False,'path_counts_are_not_logical_nodes':True,'text_content_not_exported':True}
    finally:doc.close()

def import_once(path,ident):
    case=D/'cases'/ident;case.mkdir(parents=True,exist_ok=True)
    rec={'schema':'drawio_builtin_pdf_inventory_import_case_v2b','id':ident,'pdf_file':str(path.relative_to(R)),'pdf_sha256':ident,'at_utc':now(),
      'official_function':'Editor.extractGraphModelFromPdf','official_runtime':str(S/'manifest.json'),'custom_pdf_converter_used':False,'model_calls':0,'qualified':False,'official_extract_calls':0}
    started=time.monotonic()
    try:
        inv=inventory(path,ident);once(case/'inventory.json',inv);rec['inventory_file']=str((case/'inventory.json').relative_to(R));rec['purpose']=inv['purpose'];rec['structure']=inv['totals']
        old=V1/'cases'/ident/'record.json'
        if old.exists():
            prior=json.loads(old.read_text());assert prior['pdf_sha256']==ident
            rec.update(status=prior['status'],reason=prior.get('reason'),reused_official_result=str(old.relative_to(R)),reused_official_result_sha256=sha(old.read_bytes()),builtin_result=prior.get('builtin_result'))
        else:
            out=case/'imported.drawio';journal=case/'official_import_started.json'
            if journal.exists():
                rec.update(status='interrupted_official_import_no_retry',reason='Once ledger already records an attempted official import; no second invocation.')
            else:
                once(journal,{'at_utc':now(),'pdf_file':str(path.relative_to(R)),'pdf_sha256':ident,'official_function':'Editor.extractGraphModelFromPdf','no_automatic_second_call':True})
                if path.stat().st_size>64*1024**2:rec.update(status='typed_skip_pdf_above_limit',reason='64MiB importer bound')
                else:
                    rec['official_extract_calls']=1
                    result=subprocess.run(['/usr/bin/node','--max-old-space-size=768',str(S/'node_adapter.cjs'),str(S),str(path),str(out)],capture_output=True,text=True,timeout=35)
                    if result.returncode:raise RuntimeError('official_import_execution_failed:'+result.stderr[-1500:])
                    parsed=json.loads(result.stdout);rec['builtin_result']=parsed
                    if parsed['status']=='no_embedded_diagram':rec.update(status='unsupported_builtin_import',reason='drawio_builtin_import_returned_no_embedded_diagram')
                    else:
                        raw=out.read_bytes();stats=official.xml_stats(raw.decode());rec.update(status='editable_xml_candidate',code_file=str(out.relative_to(R)),code_sha256=sha(raw),xml_structure=stats)
                        if not stats['vertices'] or stats['all_image_wrapper']:rec.update(status='rejected_noneditable_or_empty',reason='empty_graph_or_whole_image_wrapper')
                        else:rec['remaining_validation']=['Research-figure structural and semantic complexity review','Independent official PNG rendering','Source PDF visual alignment','Editability probe'];rec['qualified']=False
    except subprocess.TimeoutExpired:rec.update(status='failed_builtin_timeout',reason='Official importer35second bound')
    except Exception as e:rec.update(status='failed_inventory_or_import',reason=type(e).__name__+':'+str(e)[:2000])
    rec['seconds']=round(time.monotonic()-started,3);once(case/'record.json',rec);return rec

def acquisition_state():
    receipt=json.loads((A/'launch.json').read_text());proc=Path('/proc',str(receipt['pid']))
    live=False
    if proc.exists():
        parts=proc.joinpath('stat').read_text().split(') ',1)[1].split();live=parts[0]!='Z' and parts[19]==receipt['birth_ticks']
    manifest=A/'manifest.json';finished=manifest.exists() and json.loads(manifest.read_text()).get('finished',False)
    return {'pid':receipt['pid'],'birth_ticks':receipt['birth_ticks'],'same_process_live':live,'manifest_finished':finished}

def discover():
    paths=[]
    for paper in sorted(A.iterdir()):
        if not paper.is_dir():continue
        if (paper/'paper.pdf').is_file():paths.append(paper/'paper.pdf')
        # source_index is written only after safe extraction and static indexing.
        if (paper/'source_index.json').exists():paths.extend(sorted((paper/'source').rglob('*.pdf')))
    return [p for p in paths if p.is_file() and not p.is_symlink()]

def main(wait):
    import fitz
    assert fitz.VersionBind=='1.26.7','Pinned PDF inventory runtime mismatch'
    D.mkdir(parents=True,exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    importer_manifest=official.setup();seen={r['id']:r for p in (D/'cases').glob('*/record.json') for r in [json.loads(p.read_text())]}
    aliases={}
    if (D/'aliases.jsonl').exists():aliases={r['pdf_file']:r for r in map(json.loads,(D/'aliases.jsonl').read_text().splitlines())}
    events=(D/'events.jsonl').open('a',buffering=1);alias_out=(D/'aliases.jsonl').open('a',buffering=1);started=time.monotonic();scan=0
    while True:
        scan+=1
        for path in discover():
            locator=str(path.relative_to(R))
            if locator in aliases:continue
            ident=sha(path.read_bytes())
            if ident not in seen:
                rec=import_once(path,ident);seen[ident]=rec;events.write(enc(rec)+'\n');print(enc({'event':'case','id':ident,'pdf_file':locator,'purpose':rec.get('purpose'),'status':rec['status'],'official_extract_calls':rec['official_extract_calls']}),flush=True)
            alias={'pdf_file':locator,'pdf_sha256':ident,'case_file':str((D/'cases'/ident/'record.json').relative_to(R)),'first_seen_at_utc':now()};aliases[locator]=alias;alias_out.write(enc(alias)+'\n')
        state=acquisition_state();finished=state['manifest_finished'] or not state['same_process_live'] or not wait
        summary={'schema':'drawio_builtin_pdf_inventory_watch_v2b','at_utc':now(),'scan_count':scan,'unique_pdfs':len(seen),'pdf_path_aliases':len(aliases),'states':dict(collections.Counter(r['status'] for r in seen.values())),
          'purposes':dict(collections.Counter(r.get('purpose','inventory_failed') for r in seen.values())),'official_extract_calls_v2':sum(r['official_extract_calls'] for r in seen.values()),'reused_v1_results':sum('reused_official_result' in r for r in seen.values()),
          'acquisition':state,'finished':finished,'elapsed_seconds':round(time.monotonic()-started,1),'official_importer':importer_manifest,'qualified_pairs':0,'custom_pdf_converter_used':False,'model_calls':0,'geometry_conversion':False,'all_data_remains_HKUST':True,'inventory_runtime':{'pymupdf_version':fitz.VersionBind,'runtime_path':str(PDF_RUNTIME)},'supersedes_infrastructure_only_run':str(R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v2'),
          'qualification_policy':'Official embeddedXML extraction alone is a candidate. Complexity, independent official rendering, PDF alignment and editing probe are required.'}
        atomic(D/'summary.json',summary)
        if finished:print(enc(summary),flush=True);break
        if time.monotonic()-started>2*3600:raise TimeoutError('bounded_acquisition_watch_2h_exceeded')
        time.sleep(20)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--wait-for-acquisition',action='store_true');args=parser.parse_args();main(args.wait_for_acquisition)
