"""One consumed development source, one new frozen core attempt, then full QA."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,sqlite3,subprocess,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S));RAW='d33bf4c3f050929ae2907cf8c94f46be081fbe626e11d747d933c2e938982c5b'
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def work(root):
 import priority_datikz_source_viewport_v4 as core
 import priority_datikz_source_replay_quality_v5 as quality
 freeze=json.loads((root/'freeze.json').read_bytes());assert core.configuration()==freeze['configuration'];task=freeze['task'];source=task['source'];identifier=source['pair_sha256'];key=sha(raw(freeze['configuration']));claim=R/'conversion'/core.VERSION/'normal_once'/key/(RAW+'.json');claim.parent.mkdir(parents=True,exist_ok=True)
 with claim.open('xb')as f:f.write(raw(dict(raw_id=RAW,source_code_sha256=source['code_sha256'],work=str(root),source_core_sha256=key,claim_before_normal=True)))
 with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:canonical=db.execute('select*from jobs where id=?',(RAW,)).fetchone()
 started=time.monotonic();result=dict(raw_id=RAW,id=identifier,source_core_sha256=key,normal_calls=1,claim=str(claim),new_model_calls=0,goal_complete=False,development_only=True,fresh_unseen_validation_claimed=False)
 try:
  seed=dict(id=identifier,source_record=source,original_source_code=task['code']['file'],original_reference=task['image']['file']);native=R/'conversion'/core.VERSION/'program_runs'/root.name/RAW;attempt=core.convert(seed,None,native);(root/'frontend_result.json').write_bytes(raw(attempt));result.update(conversion_ok=attempt.get('ok'),reason=attempt.get('reason'),detail=attempt.get('detail'))
  if attempt.get('ok'):
   candidate=Path(attempt['record_file']);before=candidate.read_bytes();database=root/'quality_identity.sqlite'
   with sqlite3.connect(database)as db:
    db.execute('create table jobs(id text primary key,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)');manifest=dict(source_code=task['code']['file'],reference_image=task['image']['file']);db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(identifier,'scientific_diagram','tikz',source['source'],json.dumps(source),'quality_review','DaTikZ_text_terminal_development',0,datetime.datetime.now(datetime.timezone.utc).isoformat(),None,None,json.dumps(manifest),None))
   qa=R/'conversion/prototype/candidate_quality_ro_v1'/('DaTikZ_text_terminal_v4_'+uuid.uuid4().hex);report=quality.verify(identifier,candidate,R,Path(core.__file__),qa,database=database);assert candidate.read_bytes()==before;result.update(candidate=str(candidate),quality_ok=report['ok'],quality_failures=report.get('failures'),quality_report=str(qa/'report.json'),checks=list(report.get('checks',{})),qualified_not_published=report['ok'])
 except Exception as e:result.update(exception=type(e).__name__,reason=str(e))
 with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:assert db.execute('select*from jobs where id=?',(RAW,)).fetchone()==canonical
 assert core.configuration()==freeze['configuration'];result.update(canonical_unchanged=True,elapsed_seconds=time.monotonic()-started);(root/'summary.json').write_bytes(raw(result));print(json.dumps(result))
def launch():
 import priority_datikz_source_viewport_v4 as core
 proof=R/'conversion/datikz_source_ownership_development_v1'
 old=R/'conversion/priority_datikz_native_pilot_v1/bdda92b0e0ae42058f682bdb55efa270/freeze.json';document=json.loads(old.read_bytes());task=next(r for r in document['tasks']if r['raw_id']==RAW)
 seen=R/'release/compiler_iterations/development_seen_v1/priority_datikz_actual_native_attempts_20261102_v1.jsonl';payload=''.join(json.dumps(dict(id=r['raw_id'],source_code_sha256=r['source']['code_sha256'],source_image_sha256=r['source']['original_provider_image_sha256'],reason='Actual prior DaTikZ native development attempt; never reuse as unseen.'),sort_keys=True)+'\n'for r in document['tasks'])
 if seen.exists():assert seen.read_text()==payload
 else:seen.write_text(payload);seen.chmod(0o444)
 for name in ['priority_datikz_source_viewport_v4.py','priority_datikz_source_replay_quality_v5.py','priority_datikz_execution_binding_v6.py','priority_datikz_execution_binding_v5.py','datikz_source_node_glyph_prefix_v1.py','datikz_source_frame_ownership_v1.py','datikz_text_terminal_normal_v1.py']:(S/name).chmod(0o444)
 cfg=core.configuration();key=sha(raw(cfg));claim=R/'conversion'/core.VERSION/'normal_once'/key/(RAW+'.json');assert not claim.exists(),'Consumed source/core must never be restarted'
 root=R/'conversion/datikz_text_terminal_normal_v1'/uuid.uuid4().hex;root.mkdir(parents=True);(root/'freeze.json').write_bytes(raw(dict(configuration=cfg,task=task,source_core_sha256=key,known_source=True,normal_calls_planned=1)));(root/'freeze.json').chmod(0o444)
 with(root/'output.log').open('wb')as log:p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'work','--root',str(root)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
 birth=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19];receipt=dict(root=str(root),pid=p.pid,birth_ticks=birth,source_core_sha256=key,normal_calls_planned=1,known_development_case=True,model_calls=0,goal_complete=False);(root/'launch.json').write_bytes(raw(receipt));print(json.dumps(receipt))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('launch','work'));p.add_argument('--root',type=Path);a=p.parse_args();launch()if a.action=='launch'else work(a.root)
