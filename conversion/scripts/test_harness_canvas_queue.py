import json,sqlite3,tempfile
from pathlib import Path
import harness_pool_v6 as pool
from native_worker import W,now
with tempfile.TemporaryDirectory(prefix='canvas-queue-',dir=W) as temp:
    file=Path(temp)/'jobs.sqlite';db=sqlite3.connect(file)
    db.executescript('create table jobs(id TEXT PRIMARY KEY,state TEXT,worker_pid INT,output_record TEXT,updated_at TEXT); create table harness_queue_v3(id TEXT PRIMARY KEY,state TEXT,priority INT);')
    cases=[('eligible','needs_quality_repair',None,'held_for_source_v5','h','h'),('finished','rendered',None,'attempt_finished','h','h'),('busy','repair_running',123,'running','h','h'),('accepted','accepted',None,'held_for_source_v5','h','h'),('stale','rendered',None,'held_for_source_v5','new','old'),('ordinary','needs_quality_repair',None,'held_for_source_v5','h',None)]
    for id,state,pid,q,current,proven in cases:
        r={'code_sha256':current,'native_page_padding':{'new_code_sha256':proven}}
        db.execute('insert into jobs values (?,?,?,?,?)',(id,state,pid,json.dumps(r),now()));db.execute('insert into harness_queue_v3 values (?,?,0)',(id,q))
    db.commit();pool.conn=lambda:sqlite3.connect(file,timeout=60);pool.init()
    assert pool.reserve()==2 and pool.reserve()==0
    states=dict(db.execute('select id,state from harness_queue_v3'))
    assert states=={'eligible':'held_for_canvas_v6','finished':'held_for_canvas_v6','busy':'running','accepted':'held_for_source_v5','stale':'held_for_source_v5','ordinary':'held_for_source_v5'}
    assert db.execute('select count(*) from harness_canvas_revisions').fetchone()[0]==2
    report={'at':now(),'ok':True,'eligible_revision_reserved':True,'failed_prior_harness_revision_reserved':True,'live_model_job_not_reassigned':True,'accepted_and_ordinary_and_stale_revisions_untouched':True,'repeat_reservation_does_not_duplicate':True,'production_db_mutated':False}
(W/'harness_canvas_queue_tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
