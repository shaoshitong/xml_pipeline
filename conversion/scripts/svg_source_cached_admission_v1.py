"""Hash-verified source-only reuse; current semantics, never candidate outcomes.

All 2365 target inputs and old unsupported/error decisions remain preserved.
Only previously source-admitted observations enter current semantic replay.
Actual candidate QA must still capture the authoritative source afresh.
"""
from pathlib import Path
import argparse
import collections
import concurrent.futures
import datetime
import hashlib
import inspect
import json
import os
import sqlite3
import sys
import time

R=Path('/backup/shaoshitong/img2code_20261029')
S=R/'conversion/scripts'
sys.path.insert(0,str(S))
OLD=R/'conversion/source_semantic_admission_audit_v1/e430695f8e8042d3bf1b4426ca99b423'
PARENT=R/'release/compiler_iterations/source_pools/svg_complex_symbol_viewport_unseen100_20261102_v7'


def raw(v):return (json.dumps(v,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()))
def read(p):return json.loads(p.read_bytes())
def rows(p):return [json.loads(x)for x in p.read_bytes().splitlines()if x]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,v):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_bytes(raw(v));os.replace(tmp,p)


def case(prior):
    import compiler_svg_scene_frontend_v15 as observer
    import compiler_svg_general_guard_v14 as core
    from svg_source_semantic_admission_audit_v1 import leaf_alpha_source_supported
    from PIL import Image
    started=time.monotonic()
    result={**prior,'source_observation_fresh_for_current_core':False,
            'source_observation_reused_from_frozen_v15':True,
            'normal_conversion_calls':0,'candidate_emissions':0,'QA_calls':0,'model_calls':0}
    try:
        with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
            db.row_factory=sqlite3.Row;job=dict(db.execute('select*from jobs where id=?',(prior['id'],)).fetchone())
        source,code,reference=observer._inputs(job)
        assert (sha(code),sha(reference))==(prior['source_code_sha256'],prior['source_image_sha256'])
        work=Path(prior['source_observation_work']).resolve(strict=True)
        assert work.is_relative_to(R/'conversion/compiler_svg_scene_frontend_v15/source')
        proof=read(work/'sourceproof.json');dom=read(work/'dom.json');positions=read(work/'positions.json')
        assert proof['source_code_sha256']==sha(code)and proof['source_image_sha256']==sha(reference)
        assert proof['source_metadata_sha256']==sha(observer.raw(source))
        assert proof['fresh_source_dom_sha256']==sha(observer.raw(dom))
        assert proof['source_engine_png_sha256']==sha((work/'cairosvg_source.png').read_bytes())
        assert proof['source_browser_png_sha256']==sha((work/'browser_source.png').read_bytes())
        assert proof['source_reference']['ok']and proof['cairo_browser_physical_font_equivalence']['ok']
        assert proof['candidate_independent']and proof['source_dom_extraction_preserved_all_pixels']
        assert proof['parameter_search']is False and proof['relayout']is False
        assert sorted(positions)==proof['required_text_cell_ids']
        size=Image.open(work/'browser_source.png').size
        assert size==Image.open(__import__('io').BytesIO(reference)).size
        assert observer._expected_text_regions(positions,size)==proof['source_reference_raster_regions_checked']
        fonts=read(work/'cairo_fonts/cairo_physical_fonts.json')
        meta=dict(faces={key:{k:v for k,v in f.items()if k!='file'}for key,f in fonts['faces'].items()},paint=fonts['paint'])
        assert sha(observer.raw(meta))==proof['cairo_browser_physical_font_equivalence']['metadata_sha256']
        for face in fonts['faces'].values():
            f=Path(face['file']).resolve(strict=True)
            assert f.is_relative_to(work/'cairo_fonts')and sha(f.read_bytes())==face['sha256']
        features=core.source_features(dom,size)
        allowed={o['id']for o in dom['objects']if leaf_alpha_source_supported(o,dom)}
        failures=[v for v in features['failures']if not(v.get('reason')=='source_element_or_ancestor_opacity_requires_compositing_frontend'and v.get('id')in allowed)]
        result.update(status='unsupported'if failures else'admitted',
            reason=failures[0]['reason']if failures else'source_semantic_admission_passed',
            current_source_semantics_recomputed=True,source_feature_failures=failures,
            cached_proof=asset(work/'sourceproof.json'),cached_DOM=asset(work/'dom.json'),
            cached_positions=asset(work/'positions.json'),cached_Cairo_fonts=asset(work/'cairo_fonts/cairo_physical_fonts.json'))
        with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
            db.row_factory=sqlite3.Row;assert dict(db.execute('select*from jobs where id=?',(prior['id'],)).fetchone())==job
    except Exception as error:
        result.update(status='error',reason='source_cache_or_current_semantics_replay_failed:'+str(error),error_type=type(error).__name__)
    result.update(elapsed_seconds=time.monotonic()-started,finished_at=now())
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--workers',type=int,default=8);args=parser.parse_args()
    root=args.work.resolve();assert root.is_relative_to(R/'conversion/source_cached_admission_v1')and 1<=args.workers<=12
    root.mkdir(parents=True,exist_ok=True)
    with(root/'owner.json').open('x')as f:json.dump(dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]),f)
    import compiler_svg_scene_frontend_v15 as old
    import compiler_svg_scene_frontend_v18 as new
    import compiler_svg_general_guard_v14 as core
    plan=read(OLD/'plan.json');old_cfg=read(OLD/'configuration.json');old_summary=read(OLD/'summary.json')
    assert old_summary['finished']and old_summary['completed']==old_summary['total']==2365
    assert plan['configuration']==old_cfg
    assert sha((S/'svg_source_semantic_admission_audit_v1.py').read_bytes())==plan['producer_sha256']
    for path,digest in old_cfg['pins'].items():assert sha(Path(path).read_bytes())==digest,path
    allowed_changes={'configuration','_apply_offsets','_semantics','structure_checks','convert','validate_source','audit_editing','_marker_contours'}
    changed=[];identical={}
    for name,fn in vars(old).items():
        if inspect.isfunction(fn)and fn.__module__==old.__name__:
            a=inspect.getsource(fn);b=inspect.getsource(getattr(new,name))
            if a!=b:changed.append(name)
            else:identical[name]=sha(a.encode())
    assert set(changed)<=allowed_changes,changed
    for name in ['CHROME','PYTHON','SOURCE_RUNTIME','SOURCE_PACKAGES','_CAIRO','_RUN_ROWS_JS']:assert getattr(old,name)==getattr(new,name),name
    for ref in old_summary['files'].values():assert asset(R/ref['file'])==ref
    body=(PARENT/'supported_population.jsonl').read_bytes();assert sha(body)==plan['input_sha256']==sha((OLD/'input.jsonl').read_bytes())
    candidates=rows(OLD/'admitted.jsonl');retained=rows(OLD/'unsupported.jsonl')+rows(OLD/'error.jsonl')
    assert len(candidates)==785 and len(retained)==1580
    config=core.configuration();(root/'configuration.json').write_bytes(raw(config));(root/'input.jsonl').write_bytes(body)
    method=dict(identical_source_observation_functions=identical,changed_functions=changed,
        source_observation_constants_unchanged=True,all_prior_implementation_pins_revalidated=True,
        parent_admission_summary=asset(OLD/'summary.json'),parent_plan=asset(OLD/'plan.json'))
    (root/'plan.json').write_bytes(raw(dict(configuration=config,input_sha256=sha(body),producer_sha256=sha(Path(__file__).read_bytes()),method=method,
        source_only_policy='Reuse only original hash-bound source observations; recompute current semantics for the prior 785 source-admitted rows. Preserve all other original decisions with their prior-core provenance. Candidate results and QA are never read. Fresh candidate QA remains mandatory.')))
    db=sqlite3.connect(root/'status.sqlite');db.execute('create table sources(seq integer primary key,id text unique,status text,result text)')
    for i,row in enumerate(candidates):db.execute('insert into sources values(?,?,?,null)',(i,row['id'],'queued'))
    for i,row in enumerate(retained,len(candidates)):
        row={**row,'retained_prior_source_decision':True,'current_source_semantics_recomputed':False,'retained_prior_admission_summary':asset(OLD/'summary.json')}
        db.execute('insert into sources values(?,?,?,?)',(i,row['id'],row['status'],json.dumps(row)))
    db.commit();start=time.monotonic()
    def progress(finished=False):
        counts=dict(db.execute('select status,count(*)from sources group by status'));done=2365-counts.get('queued',0)-counts.get('running',0)
        v=dict(at_utc=now(),total=2365,completed=done,recomputed_current_semantics=done-1580,retained_prior_source_decisions=1580,
            counts=counts,finished=finished,elapsed_seconds=time.monotonic()-start,normal_conversion_calls=0,candidate_emissions=0,QA_calls=0,model_calls=0,browser_source_recaptures=0,goal_complete=False)
        atomic(root/'summary.json',v);return v
    progress();queue=iter(candidates);pending={}
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers)as pool:
        def dispatch():
            while len(pending)<args.workers:
                row=next(queue,None)
                if row is None:break
                db.execute("update sources set status='running'where id=?",(row['id'],));db.commit();pending[pool.submit(case,row)]=row['id']
        dispatch()
        while pending:
            done,_=concurrent.futures.wait(pending,timeout=5,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                identifier=pending.pop(future)
                try:value=future.result()
                except Exception as error:value=dict(id=identifier,status='error',reason='source_cache_worker_error:'+str(error),normal_conversion_calls=0,candidate_emissions=0,QA_calls=0,model_calls=0)
                db.execute('update sources set status=?,result=?where id=?',(value['status'],json.dumps(value),identifier));db.commit()
            dispatch();progress()
    assert config==core.configuration()
    files={}
    for state in ['admitted','unsupported','error']:
        p=root/(state+'.jsonl');p.write_bytes(b''.join(json.dumps(json.loads(x[0]),sort_keys=True).encode()+b'\n'for x in db.execute('select result from sources where status=? order by seq',(state,))));p.chmod(0o444);files[p.name]=asset(p)
    final=progress();final.update(finished=True,files=files);atomic(root/'summary.json',final);db.close();print(json.dumps(final),flush=True)


if __name__=='__main__':main()
