"""Keep complete source pages while repairing small real native overflows; never accept quality."""
import argparse,concurrent.futures,hashlib,io,json,os,shutil,sqlite3,time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from durable_sqlite import begin,commit
from native_page_padding import shift
from native_padding_proof import render,verify_cells,plan_from_pixels,exact_pixel_proof
from strict_canvas_gate import require_declared_page
from svg_batch import metric
from harness_source_provenance import validate_source_record
sha=lambda b:hashlib.sha256(b).hexdigest()
STATE='native_page_padding_repairing'

def source_render(r,w,h,work):
    assert r['source_format']=='tikz';svg=(R/r['source_render_svg']).read_bytes();assert sha(svg)==r['source_render_svg_sha256'];blocked=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
        ctx=browser.new_context(java_script_enabled=False,viewport={'width':w,'height':h},service_workers='block');ctx.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=ctx.new_page();page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode());page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[w,h]);page.evaluate('document.fonts.ready');png=page.screenshot();browser.close()
    assert not blocked,'Unresolved source SVG resources';(work/'source_render.png').write_bytes(png);return png

def repair(id,raw):
    r=json.loads(raw);xml=(R/r['code_file']).read_text();oldpng=(R/r['image_file']).read_bytes();reference=(R/r['original_reference']).read_bytes();assert sha(xml.encode())==r['code_sha256'] and sha(oldpng)==r['image_sha256'];assert sha(reference)==r['source_image_sha256'];source_checks=validate_source_record(r)
    work=W/'native_page_padding'/id/r['code_sha256'];work.mkdir(parents=True,exist_ok=True);(work/'before_record.json').write_text(raw);w,h=Image.open(io.BytesIO(reference)).size
    baseline,oldinfo=render(xml,w,h,work/'baseline');assert oldinfo['canvas']==[w,h],'Source/declared canvas registration requires review';assert oldinfo['selected_image']=='complete_tight_graph','Not a real overflow in current renderer'
    canvas=plan_from_pixels((work/'baseline/render.padded.png').read_bytes(),oldinfo);nw,nh=canvas['width'],canvas['height'];new,geometry=shift(xml,canvas['dx'],canvas['dy'],nw,nh);verify_cells(xml,new,geometry)
    png,newinfo=render(new,nw,nh,work/'candidate');require_declared_page(newinfo,nw,nh);exact=exact_pixel_proof(work/'baseline',work/'candidate',oldinfo,newinfo,canvas)
    before=metric(reference,oldpng);after=metric(reference,png);assert after>before,'Reference fidelity did not improve'
    sourcepng=source_render(r,w,h,work);metrics={**r.get('metrics',{}),'original_reference_ssim_512':after,'original_source_render_ssim_512':metric(reference,sourcepng),'source_render_vs_drawio_ssim_512':metric(sourcepng,png)}
    if 'exact_reference_pixels' in metrics:metrics['exact_reference_pixels']=False
    issues=[x for x in r.get('unresolved_issues',[]) if x.get('reason')!='native_content_outside_source_canvas']
    if min(metrics[k] for k in ('original_reference_ssim_512','original_source_render_ssim_512','source_render_vs_drawio_ssim_512'))>=.9:issues=[x for x in issues if x.get('reason')!='source_or_native_fidelity_below_review_threshold']
    archive=W/'harness_sessions'/('native_page_padding_'+id+'_'+r['code_sha256'])/'baseline';archive.mkdir(parents=True,exist_ok=True);(archive/'conversion.json').write_text(raw);(archive/'diagram.drawio').write_text(xml);(archive/'image.png').write_bytes(oldpng)
    proof={'at':now(),'method':'bounded_integer_page_padding_with_exact_native_paint_v1','old_code_sha256':r['code_sha256'],'old_image_sha256':r['image_sha256'],'new_code_sha256':sha(new.encode()),'new_image_sha256':sha(png),'geometry':geometry,'canvas_plan':canvas,'exact_pixel_proof':exact,'old_outside_page_pixels':oldinfo['outside_page_pixel_audit']['nonwhite_outside_pixels'],'new_outside_page_pixels':newinfo['outside_page_pixel_audit']['nonwhite_outside_pixels'],'reference_ssim_before':before,'reference_ssim_after':after,'source_hash_checks':source_checks,'audit':str((work/'report.json').relative_to(R)),'accepted':False}
    out={**r,'code_sha256':proof['new_code_sha256'],'image_sha256':proof['new_image_sha256'],'render':newinfo,'metrics':metrics,'unresolved_issues':issues,'native_page_padding':proof,'previous_candidate_archive':str(archive.relative_to(R)),'quality_state':'pending_source_semantic_and_visual_validation'}
    (work/'candidate.drawio').write_text(new);(work/'candidate.png').write_bytes(png);(work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(work/'report.json').write_text(json.dumps(proof,indent=2)+'\n');return work,out,proof

def worker(index,limit,selected):
    db=sqlite3.connect(W/'jobs.sqlite',timeout=2);n=0;counts={}
    while not limit or n<limit:
        sql='select id,state,output_record from jobs j where format="tikz" and state in ("rendered","needs_quality_repair") and worker_pid is NULL and json_extract(output_record,"$.render.selected_image")="complete_tight_graph" and not exists(select 1 from native_page_padding_repairs p where p.id=j.id and p.input_hash=json_extract(j.output_record,"$.code_sha256"))';args=[]
        if selected:sql+=' and id in ('+','.join('?' for _ in selected)+')';args+=selected
        row=db.execute(sql+' order by id limit 1',args).fetchone()
        if not row:
            if limit or selected:break
            time.sleep(30);continue
        id,state,raw=row;old=json.loads(raw);hash=old['code_sha256'];begin(db)
        if db.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()!=(state,raw,None) or db.execute('select 1 from native_page_padding_repairs where id=? and input_hash=?',(id,hash)).fetchone():db.rollback();continue
        db.execute('insert into native_page_padding_repairs values (?, ?,"running",NULL,?)',(id,hash,now()));db.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(STATE,os.getpid(),now(),id));commit(db);out=None;work=None
        try:work,out,report=repair(id,raw)
        except Exception as exc:report={'id':id,'at':now(),'input_code_sha256':hash,'error':repr(exc),'canonical_changed':False,'accepted':False}
        begin(db);assert db.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==(STATE,os.getpid(),raw),'Ownership changed'
        if out:
            for a,b in [(work/'candidate.drawio',R/out['code_file']),(work/'candidate.png',R/out['image_file']),(work/'candidate_record.json',(R/out['code_file']).parent/'conversion.json')]:
                tmp=b.with_suffix(b.suffix+'.pagepadding.tmp');shutil.copyfile(a,tmp);tmp.replace(b)
        db.execute('update jobs set state=?,worker_pid=NULL,output_record=?,updated_at=? where id=?',(state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));stage='published' if out else 'retained_prior_candidate';db.execute('update native_page_padding_repairs set state=?,record=?,updated_at=? where id=? and input_hash=?',(stage,json.dumps(report),now(),id,hash));commit(db)
        if out:(work/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256']}))
        n+=1;counts[stage]=counts.get(stage,0)+1;print(json.dumps({'at':now(),'id':id,'stage':stage,'worker':index,'error':report.get('error')}),flush=True)
    return {'worker':index,'processed':n,'counts':counts}

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);p.add_argument('--ids-file');a=p.parse_args();selected=json.loads(Path(a.ids_file).read_text()) if a.ids_file else []
    d=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(d);d.execute('create table if not exists native_page_padding_repairs (id TEXT,input_hash TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_hash))');commit(d);d.close();(W/'native_page_padding_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'limit':a.limit,'selected':selected,'at':now()}))
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers,[selected]*a.workers))
    (W/('native_page_padding_smoke_summary.json' if a.limit or selected else 'native_page_padding_summary.json')).write_text(json.dumps({'at':now(),'results':results,'goal_complete':False},indent=2)+'\n')
if __name__=='__main__':main()
