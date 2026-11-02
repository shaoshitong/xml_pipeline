"""Invoke draw.io's unmodified built-in PDF importer on destination PDFs.

This is an import harness, not a PDF-to-vector or custom PDF conversion engine.
PDF content never leaves HKUST. Unsuccessful inputs receive a typed record.
"""
from pathlib import Path
import argparse, base64, concurrent.futures, datetime, fcntl, hashlib, json
import os, re, shutil, subprocess, time, urllib.parse, xml.etree.ElementTree as ET, zipfile, zlib

R = Path('/backup/shaoshitong/img2code_20261029')
ROOT = R/'clean/arxiv_research_figures_v1'
ACQ = ROOT/'acquisition_pilot_v1'
D = ROOT/'drawio_builtin_import_v1'
S = D/'official_importer'
sha = lambda b: hashlib.sha256(b).hexdigest()
now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()

NODE_ADAPTER = r'''const fs=require('fs'),vm=require('vm');
const [root,input,output]=process.argv.slice(2);
const c={Editor:{},mxClient:{IS_SF:false},window:{},atob:s=>Buffer.from(s,'base64').toString('latin1')};
c.window.atob=c.atob;c.Base64={decode:c.atob};
vm.createContext(c);
vm.runInContext(fs.readFileSync(root+'/pako.min.js','utf8'),c,{timeout:2000});
vm.runInContext('var Graph={stringToArrayBuffer:function(s){var a=new Uint8Array(s.length);for(var i=0;i<s.length;i++)a[i]=s.charCodeAt(i);return a;}};',c);
vm.runInContext(fs.readFileSync(root+'/official_pdf_functions.js','utf8'),c,{timeout:2000});
c.pdfInput='data:application/pdf;base64,'+fs.readFileSync(input).toString('base64');
const result=vm.runInContext('Editor.extractGraphModelFromPdf(pdfInput)',c,{timeout:20000});
if(result==null){process.stdout.write(JSON.stringify({status:'no_embedded_diagram',official_function:'Editor.extractGraphModelFromPdf'}));}
else if(typeof result!=='string'||Buffer.byteLength(result)>64*1024*1024){throw Error('official_import_result_invalid_or_too_large');}
else{fs.writeFileSync(output,result,{flag:'wx'});process.stdout.write(JSON.stringify({status:'xml_extracted',xml_bytes:Buffer.byteLength(result),official_function:'Editor.extractGraphModelFromPdf'}));}
'''

def write_once(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(b,str):b=b.encode()
    if p.exists():
        if p.read_bytes()!=b:raise ValueError('immutable_importer_content_mismatch:'+str(p))
    else:
        with p.open('xb') as f:f.write(b)

def setup():
    war=R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war'
    with zipfile.ZipFile(war) as z:
        editor=z.read('js/diagramly/Editor.js').decode()
        parts=[]
        for name in ['extractGraphModelFromPdf','extractGraphModelFromXref']:
            m=re.search(r'Editor\.'+name+r' = function\b[\s\S]*?\n\t};',editor)
            if not m:raise ValueError('official_function_missing:'+name)
            parts.append(m.group(0))
        body='\n\n'.join(parts)+'\n'
        pako=z.read('js/deflate/pako.min.js')
        write_once(S/'official_pdf_functions.js',body)
        write_once(S/'pako.min.js',pako)
        write_once(S/'node_adapter.cjs',NODE_ADAPTER)
    manifest={'schema':'official_drawio_pdf_importer_pin_v1','official_archive':str(war.relative_to(R)),
      'archive_sha256':sha(war.read_bytes()),'source_editor_js_sha256':sha(editor.encode()),
      'official_functions_sha256':sha(body.encode()),'pako_sha256':sha(pako),'adapter_sha256':sha(NODE_ADAPTER.encode()),
      'functions_unmodified':True,'functions':['Editor.extractGraphModelFromPdf','Editor.extractGraphModelFromXref'],
      'adapter_role':'Node browser-platform shims only; no PDF geometry reconstruction',
      'source_url':'https://github.com/jgraph/drawio/blob/dev/src/main/webapp/js/diagramly/Editor.js',
      'custom_pdf_converter_used':False}
    write_once(S/'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return manifest

def xml_stats(text):
    root=ET.fromstring(text);models=[]
    if root.tag=='mxGraphModel':models=[root]
    elif root.tag=='mxfile':
        for p in root.findall('diagram'):
            m=p.find('mxGraphModel')
            if m is None:
                s=(p.text or '').strip()
                if s.startswith('<'):m=ET.fromstring(s)
                else:
                    dec=zlib.decompressobj(-15);data=dec.decompress(base64.b64decode(s),64*1024*1024+1)
                    if len(data)>64*1024*1024 or dec.unconsumed_tail:raise ValueError('decompressed_xml_above_limit')
                    m=ET.fromstring(urllib.parse.unquote(data.decode()))
            models.append(m)
    else:raise ValueError('imported_xml_not_drawio')
    cells=[c for m in models for c in m.iter('mxCell')];vertices=[c for c in cells if c.get('vertex')=='1'];edges=[c for c in cells if c.get('edge')=='1']
    images=[c for c in vertices if re.search(r'(?:^|;)shape=image(?:;|$)',c.get('style',''))]
    texts=[c for c in cells if c.get('value','').strip()]
    return {'pages':len(models),'vertices':len(vertices),'edges':len(edges),'image_cells':len(images),'labeled_cells':len(texts),
      'label_characters':sum(len(re.sub('<[^>]*>',' ',c.get('value',''))) for c in texts),
      'all_image_wrapper':bool(vertices) and len(images)==len(vertices)}

def run_one(p):
    started=time.monotonic();b=p.read_bytes();ident=sha(b);case=D/'cases'/ident
    case.mkdir(parents=True,exist_ok=True)
    rec={'id':ident,'pdf_file':str(p.relative_to(R)),'pdf_sha256':ident,'pdf_bytes':len(b),
      'source_role':'paper_document_diagnostic' if p.name=='paper.pdf' else 'source_figure_asset',
      'started_at_utc':now(),'custom_pdf_converter_used':False,'model_calls':0,'status':'error'}
    try:
        if len(b)>64*1024*1024:raise ValueError('pdf_above_64MiB_probe_limit')
        if not b.startswith(b'%PDF-'):raise ValueError('source_not_pdf')
        out=case/'imported.drawio'
        if out.exists():raise ValueError('unexpected_existing_unrecorded_import')
        result=subprocess.run([shutil.which('node'),'--max-old-space-size=768',str(S/'node_adapter.cjs'),str(S),str(p),str(out)],capture_output=True,text=True,timeout=35)
        if result.returncode:raise RuntimeError('official_import_execution_failed:'+result.stderr[-1200:])
        result=json.loads(result.stdout);rec['builtin_result']=result
        if result['status']=='no_embedded_diagram':
            rec.update(status='unsupported_builtin_import',reason='drawio_builtin_import_returned_no_embedded_diagram')
        else:
            raw=out.read_bytes();stats=xml_stats(raw.decode());rec.update(status='editable_xml_candidate',code_file=str(out.relative_to(R)),code_sha256=sha(raw),structure=stats)
            if not stats['vertices'] or stats['all_image_wrapper']:
                rec.update(status='rejected_noneditable_or_empty',reason='empty_graph_or_whole_image_wrapper')
            else:
                rec['remaining_validation']='complexity, independent official PNG rendering, PDF alignment and editing probe required before qualified publication'
    except subprocess.TimeoutExpired:rec.update(status='failed',reason='official_import_timeout_35s')
    except Exception as e:rec.update(status='failed',reason=type(e).__name__+':'+str(e)[:1800])
    rec['seconds']=round(time.monotonic()-started,3);rec['finished_at_utc']=now()
    write_once(case/'record.json',json.dumps(rec,ensure_ascii=False,indent=2)+'\n')
    return rec

def main(wait):
    D.mkdir(parents=True,exist_ok=True)
    lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest=setup();seen={}
    for p in (D/'cases').glob('*/record.json'):
        r=json.loads(p.read_text());seen[r['id']]=r
    events=(D/'events.jsonl').open('a',buffering=1)
    idle=0
    while True:
        paths=sorted(ACQ.glob('**/*.pdf'));todo=[];hashes=set(seen)
        for p in paths:
            h=sha(p.read_bytes())
            if h not in hashes:todo.append(p);hashes.add(h)
        if todo:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                for rec in pool.map(run_one,todo):
                    seen[rec['id']]=rec;events.write(json.dumps(rec,ensure_ascii=False)+'\n')
                    print(json.dumps({k:rec[k] for k in ['id','pdf_file','status','seconds']},ensure_ascii=False),flush=True)
            idle=0
        counts={s:sum(r['status']==s for r in seen.values()) for s in sorted({r['status'] for r in seen.values()})}
        acquisition_terminal=False
        p=ACQ/'manifest.json'
        if p.exists():acquisition_terminal=json.loads(p.read_text()).get('finished',False)
        summary={'schema':'drawio_builtin_pdf_import_progress_v1','at_utc':now(),'tested_unique_pdfs':len(seen),'states':counts,
          'acquisition_finished':acquisition_terminal,'finished':acquisition_terminal or not wait,'official_importer':manifest,
          'qualified_pairs':0,'qualification_note':'Successful built-in extraction is a candidate until rendering/editability/fidelity checks finish.',
          'data_on_HKUST_only':True,'custom_pdf_converter_used':False,'model_calls':0}
        temp=D/'summary.tmp.json';temp.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');os.replace(temp,D/'summary.json')
        if not wait or acquisition_terminal:break
        receipt=json.loads((ACQ/'launch.json').read_text());proc=Path('/proc',str(receipt['pid']))
        live=proc.exists() and proc.joinpath('stat').read_text().split(') ',1)[1].split()[19]==receipt['birth_ticks']
        if not live:
            print(json.dumps({'event':'acquisition_process_terminal_without_finished_manifest','at_utc':now()}),flush=True);break
        idle+=1
        if idle>360:raise TimeoutError('bounded_builtin_import_acquisition_wait_2h_exceeded')
        time.sleep(20)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wait-for-acquisition',action='store_true');a=p.parse_args();main(a.wait_for_acquisition)
