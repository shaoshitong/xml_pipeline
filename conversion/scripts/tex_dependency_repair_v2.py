"""Retry exact failed revisions after all explicitly missing bundle files are available."""
import argparse,fcntl,hashlib,json,os,sqlite3,time
from pathlib import Path
from native_worker import W,now
from durable_sqlite import begin,commit
from tex_missing_v2 import missing_files
from tectonic_compile import fetch

TABLE='tikz_dependency_repairs_v2'
def initialize(db):
    begin(db)
    db.execute(f'create table if not exists {TABLE} (id TEXT,error_sha256 TEXT,dependency_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,error_sha256,dependency_sha256))')
    commit(db)

def publish(db,item,files):
    id,error,raw,prepared=item
    names=missing_files(error or '')
    assert names and sorted(r['name'] for r in files)==names
    h=hashlib.sha256(error.encode()).hexdigest()
    fingerprint=hashlib.sha256(json.dumps([(r['name'],r['ok']) for r in files],sort_keys=True).encode()).hexdigest()
    begin(db)
    current=db.execute('select state,error,input_record,input_manifest,worker_pid from jobs where id=?',(id,)).fetchone()
    if current!=('needs_fallback',error,raw,prepared,None):db.rollback();return 'stale_or_busy'
    if db.execute(f'select 1 from {TABLE} where id=? and error_sha256=? and (dependency_sha256=? or state="requeued")',(id,h,fingerprint)).fetchone():db.rollback();return 'already_recorded'
    state='requeued' if all(r['ok'] for r in files) else 'dependency_unavailable'
    record={'files':files,'prior_error':error,'input_record_sha256':hashlib.sha256(raw.encode()).hexdigest(),'input_manifest_sha256':hashlib.sha256(prepared.encode()).hexdigest(),'reason':'All explicitly named missing dependencies fetched from configured official bundle' if state=='requeued' else 'Preserve failed job; named dependency unavailable','new_quality_acceptance':False}
    db.execute(f'insert into {TABLE} values (?,?,?,?,?,?)',(id,h,fingerprint,state,json.dumps(record),now()))
    if state=='requeued':
        changed=db.execute('update jobs set state="queued",error=NULL,updated_at=? where id=? and state="needs_fallback" and error=? and worker_pid is NULL',(now(),id,error)).rowcount
        assert changed==1
    commit(db);return state

def producer_live():
    try:
        owner=json.loads((W/'tikz_render_owner.json').read_text());p=Path('/proc')/str(owner['pid'])/'cmdline'
        return p.exists() and b'tikz_render_batch.py' in p.read_bytes()
    except (OSError,ValueError):return False

def main():
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');a=p.parse_args()
    lock=(W/'tex_dependency_v2.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=sqlite3.connect(W/'jobs.sqlite',timeout=2);initialize(db)
    (W/'tex_dependency_v2_owner.json').write_text(json.dumps({'pid':os.getpid(),'started_at_utc':now(),'watch':a.watch})+'\n')
    while True:
        counts={};fetched={};rows=db.execute('select id,error,input_record,input_manifest from jobs where format="tikz" and state="needs_fallback" and worker_pid is NULL order by id').fetchall()
        for item in rows:
            names=missing_files(item[1] or '')
            if not names:continue
            results=[]
            for name in names:
                if name not in fetched:
                    try:fetched[name]=fetch(name)
                    except Exception as exc:fetched[name]={'name':name,'ok':False,'error':str(exc)[:500]}
                results.append(fetched[name])
            state=publish(db,item,results);counts[state]=counts.get(state,0)+1
        report={'at':now(),'counts':counts,'rows_examined':len(rows),'dependencies_seen':len(fetched),'total_repair_states':dict(db.execute(f'select state,count(*) from {TABLE} group by state')),'goal_complete':False}
        temp=W/'tex_dependency_v2_latest.tmp';temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(W/'tex_dependency_v2_latest.json');print(json.dumps(report),flush=True)
        if not a.watch or not producer_live():break
        time.sleep(30)

if __name__=='__main__':main()
