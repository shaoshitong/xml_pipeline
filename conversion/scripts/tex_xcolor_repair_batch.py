"""Restore xcolor-loading failures with audited source-preserving compile wrappers."""
import argparse,concurrent.futures,hashlib,json,os,shutil,sqlite3,time
from pathlib import Path
from native_worker import R,W,now
from durable_sqlite import begin,commit
from tex_xcolor_forwarding import Unsupported
from tex_xcolor_compile import compile_source,pymupdf
from tikz_binary_capture_repair import serializable

STATE='tikz_xcolor_rendering'
def promote_ready_provenance(db):
    promoted=0
    rows=db.execute('select j.id,j.state,j.output_record,t.record from jobs j join tikz_renders t on t.id=j.id join tikz_xcolor_repairs x on x.id=j.id where x.state="compiled" and j.worker_pid is NULL and j.output_record is not NULL and j.state!="accepted"').fetchall()
    for id,state,raw,execution_raw in rows:
        r=json.loads(raw);execution=json.loads(execution_raw);proof=execution['source_preparation']
        if r.get('source_preparation')==proof:continue
        assert r['source_code_sha256']==proof['original_code_sha256']
        if r.get('source_render_pdf_sha256')!=execution['pdf_sha256']:continue
        for key,digest in [('wrapper_file','wrapper_sha256'),('original_source_file','original_code_sha256')]:
            p=R/proof[key];assert p.resolve().is_relative_to(R/'clean');assert hashlib.sha256(p.read_bytes()).hexdigest()==proof[digest]
        p=R/proof['proof_file'];assert p.resolve().is_relative_to(R/'clean');saved=json.loads(p.read_text());assert saved['wrapper_sha256']==proof['wrapper_sha256'] and saved['original_code_sha256']==proof['original_code_sha256']
        for key,hkey in [('code_file','code_sha256'),('image_file','image_sha256')]:
            p=R/r[key];assert p.resolve().is_relative_to(R/'clean');assert hashlib.sha256(p.read_bytes()).hexdigest()==r[hkey]
        updated=json.dumps({**r,'source_preparation':proof},ensure_ascii=False)
        begin(db)
        if db.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()!=(state,raw,None):db.rollback();continue
        meta=(R/r['code_file']).parent/'conversion.json';tmp=meta.with_suffix('.xcolor.tmp');tmp.write_text(updated+'\n');tmp.replace(meta)
        db.execute('update jobs set output_record=?,updated_at=? where id=?',(updated,now(),id));commit(db);promoted+=1
    return promoted

def initialize(db):
    begin(db);db.execute('create table if not exists tikz_xcolor_repairs (id TEXT PRIMARY KEY,state TEXT,prior_error TEXT,record TEXT,updated_at TEXT)');commit(db)

def claim(db,id,expected,pid):
    begin(db)
    row=db.execute('select state,error,input_record,input_manifest,output_record,worker_pid from jobs where id=?',(id,)).fetchone()
    if row!=expected or row[0]!='needs_fallback' or row[-1] is not None or 'Option clash for package xcolor' not in (row[1] or '') or db.execute('select 1 from tikz_xcolor_repairs where id=?',(id,)).fetchone():db.rollback();return False
    db.execute('insert into tikz_xcolor_repairs values (?,"running",?,NULL,?)',(id,row[1],now()))
    db.execute('update jobs set state=?,worker_pid=?,attempts=attempts+1,updated_at=? where id=?',(STATE,pid,now(),id));commit(db);return True

def publish(db,id,expected,pid,record,error,repair_state):
    begin(db)
    row=db.execute('select state,worker_pid,input_record,input_manifest,output_record from jobs where id=?',(id,)).fetchone()
    assert row==(STATE,pid,expected[2],expected[3],expected[4]),'Changed repair ownership or source revision'
    state='tikz_source_rendered' if record else 'needs_fallback'
    db.execute('update jobs set state=?,worker_pid=NULL,error=?,updated_at=? where id=?',(state,error,now(),id))
    if record:db.execute('insert or replace into tikz_renders values (?,?,?,?,?)',(id,state,json.dumps(record,ensure_ascii=False),None,now()))
    db.execute('update tikz_xcolor_repairs set state=?,record=?,updated_at=? where id=?',(repair_state,json.dumps({'execution':record,'error':error},ensure_ascii=False),now(),id));commit(db)

def capture(id,source,inp,prior_error):
    data=(R/inp['source_code']).read_bytes();assert hashlib.sha256(data).hexdigest()==source['code_sha256'];assert not inp.get('panel_assets'),'Explicit asset mapping required'
    directory=W/'tikz_xcolor_render'/id[:2]/id;proof=compile_source(directory,data);pdf=directory/'source.pdf';captures=[];binaries=[]
    with pymupdf.open(pdf) as doc:
        for i,page in enumerate(doc):
            svg=directory/f'page{i}.svg';svg.write_text(page.get_svg_image(text_as_path=False));meta=serializable(page.get_text('dict'),directory/'pdf_binary_metadata',binaries);(directory/f'page{i}_text.json').write_text(json.dumps(meta,ensure_ascii=False));png=directory/f'page{i}.png';page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).save(png)
            captures.append({'page':i,'width_pt':page.rect.width,'height_pt':page.rect.height,'text_characters':len(page.get_text()),'drawing_paths':len(page.get_drawings()),'svg_file':str(svg.relative_to(R)),'svg_sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),'pdf_render_png':str(png.relative_to(R))})
    support=R/'clean/drawio_unified'/id[:2]/id/'compile_support/xcolor_v1';support.mkdir(parents=True,exist_ok=True)
    for filename in ('source.tex','original_source.tex'):shutil.copyfile(directory/'build'/filename,support/filename)
    assert hashlib.sha256((support/'original_source.tex').read_bytes()).hexdigest()==source['code_sha256']
    assert hashlib.sha256((support/'source.tex').read_bytes()).hexdigest()==proof['wrapper_sha256']
    (support/'forwarding_proof.json').write_text(json.dumps(proof,indent=2)+'\n');warnings=(directory/'stderr.log').read_text()
    record={'id':id,'source':source['source'],'source_code_sha256':source['code_sha256'],'directory':str(directory.relative_to(R)),'pdf_file':str(pdf.relative_to(R)),'pdf_sha256':proof['pdf_sha256'],'captures':captures,'pages':len(captures),'compile_returncode':0,'compile_attempts':proof['compile_attempts'],'compile_warnings':[x for x in warnings.splitlines() if 'warning' in x.lower()],'native_drawio_conversion_complete':False,'sandbox':proof['sandbox'],'captured_at_utc':now(),'recovered_from_error':prior_error,'binary_metadata_payloads':binaries,'source_preparation':{'method':proof['version'],'options':proof['options'],'original_code_sha256':source['code_sha256'],'wrapper_file':str((support/'source.tex').relative_to(R)),'wrapper_sha256':proof['wrapper_sha256'],'original_source_file':str((support/'original_source.tex').relative_to(R)),'proof_file':str((support/'forwarding_proof.json').relative_to(R))}}
    (directory/'preparation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');return record

def producer_live():
    try:
        owner=json.loads((W/'tikz_render_owner.json').read_text());p=Path('/proc')/str(owner['pid'])/'cmdline';return p.exists() and b'tikz_render_batch.py' in p.read_bytes()
    except (OSError,ValueError):return False

def worker(index,limit,selected):
    db=sqlite3.connect(W/'jobs.sqlite',timeout=2);n=0;counts={}
    while not limit or n<limit:
        promoted=promote_ready_provenance(db)
        if promoted:print(json.dumps({'worker':index,'source_provenance_promoted':promoted,'at':now()}),flush=True)
        sql='select id,state,error,input_record,input_manifest,output_record,worker_pid from jobs where format="tikz" and state="needs_fallback" and worker_pid is NULL and error like "%Option clash for package xcolor%" and id not in (select id from tikz_xcolor_repairs)';params=[]
        if selected:sql+=' and id in ('+','.join('?' for _ in selected)+')';params+=selected
        row=db.execute(sql+' order by id limit 1',params).fetchone()
        if not row:
            if limit or selected or not producer_live():break
            time.sleep(30);continue
        id,*rest=row;expected=tuple(rest)
        if not claim(db,id,expected,os.getpid()):continue
        record=None;error=None;repair_state='compiled'
        try:record=capture(id,json.loads(expected[2]),json.loads(expected[3]),expected[1])
        except Unsupported as exc:repair_state='requires_source_review';error=expected[1]+'\nxcolor forwarding not applied: '+str(exc)
        except Exception as exc:repair_state='compile_failed';error=type(exc).__name__+': '+str(exc)[:2600]
        checkpoint=W/'tikz_xcolor_render'/id[:2]/id;checkpoint.mkdir(parents=True,exist_ok=True);result={'id':id,'repair_state':repair_state,'execution':record,'error':error,'at':now()};(checkpoint/'publication_checkpoint.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        publish(db,id,expected,os.getpid(),record,error,repair_state);n+=1;counts[repair_state]=counts.get(repair_state,0)+1
        print(json.dumps({'id':id,'worker':index,'state':repair_state,'error':error,'at':now()}),flush=True)
    return {'worker':index,'processed':n,'counts':counts}

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids-file');a=p.parse_args();selected=json.loads(Path(a.ids_file).read_text()) if a.ids_file else []
    db=sqlite3.connect(W/'jobs.sqlite',timeout=2);initialize(db);db.close();owner={'pid':os.getpid(),'workers':a.workers,'limit_per_worker':a.limit,'selected':selected,'at':now()};(W/'tikz_xcolor_owner.json').write_text(json.dumps(owner)+'\n')
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:result=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[selected]*a.workers))
    (W/('tikz_xcolor_smoke_summary.json' if a.limit or selected else 'tikz_xcolor_summary.json')).write_text(json.dumps({'at':now(),'result':result,'goal_complete':False},indent=2)+'\n')
if __name__=='__main__':main()
