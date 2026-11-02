"""Private metadata-only stress benchmark of frozen v1 transaction placement."""
import sys,json,sqlite3,time,uuid,copy,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import mermaid_page_metadata_batch_v1 as v1
from mermaid_page_metadata_candidate_v1 import canonical
sha=lambda b:hashlib.sha256(b).hexdigest();source=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);audit=json.loads((W/'mermaid_canvas_metadata_audit_v1.json').read_text());policy,files=v1.implementation();target=None
for item in audit['records'][::-1]:
 try:
  context=v1.context(source,item['id']);old=context[3]
  if (old['code_sha256'],old['image_sha256'])==(item['code_sha256'],item['image_sha256']):target=item['id'];before=context[:3];break
 except (ValueError,KeyError,TypeError):pass
assert target;scope=W/'prototype/mermaid_page_metadata_v1b_lock_benchmark'/uuid.uuid4().hex;scope.mkdir(parents=True);database=scope/'jobs.sqlite';db=sqlite3.connect(database,isolation_level=None,timeout=0);ids=[r['id'] for r in audit['records']];db.execute('BEGIN')
for table in ('jobs','processing_outcomes_v2','harness_queue','harness_queue_v2','harness_queue_v3',v1.TABLE,v1.HISTORY,'auto_quality_dirty_v2'):
 schema=source.execute("select sql from sqlite_master where type='table' and name=?",(table,)).fetchone()
 if not schema:continue
 db.execute(schema[0])
 for id in ids:
  for row in source.execute('select * from '+table+' where id=?',(id,)).fetchall():db.execute('insert into '+table+' values('+','.join('?' for _ in row)+')',row)
for (sql,) in source.execute("select sql from sqlite_master where type='trigger' and tbl_name='jobs'").fetchall():db.execute(sql)
db.commit()
db.execute('pragma journal_mode=WAL');v1.initialize(db);db.execute("update processing_outcomes_v2 set status='qualified',record='{}' where id!=?",(target,));events=[]
def trace(sql):
 head=sql.lstrip().split(None,1)[0].upper();events.append((head,time.monotonic()))
db.set_trace_callback(trace);current=v1.claim(db,audit,policy,files,root=R,publish=True);assert current['id']==target;claim_events=list(events);events.clear();observations=[]
def fake_files(current,out,proof,work,root):
 observations.append({'artifact_callback_inside_transaction':db.in_transaction,'injected_io_seconds':.20});time.sleep(.20);return out
old=json.loads(dict(zip(current['prior_job']['columns'],current['prior_job']['rows'][0]))['output_record']);out={**old,'quality_state':'pending_private_lock_benchmark'};proof={'candidate_checks_passed':True,'accepted':False,'output_code_sha256':old['code_sha256'],'output_image_sha256':old['image_sha256']};v1.finish(db,current,out,proof,scope,True,R,artifact_writer=fake_files);finish_events=list(events);db.set_trace_callback(None);db.close();after=v1.context(source,target)[:3];source.close();assert before==after,'Canonical target changed during private-only benchmark'
def elapsed(events):
 begin=next(t for op,t in events if op=='BEGIN');commit=next(t for op,t in events if op=='COMMIT');return commit-begin
result={'at':v1.now(),'scope':str(scope),'private_database':str(database),'audit_count':len(audit['records']),'stress_condition':'Other audit IDs privately marked qualified, forcing frozen BEGIN-time selector to traverse to final eligible ID. This is a bounded worst-case placement benchmark, not a claim about current average service rate.','target':target,'claim_writer_transaction_seconds':elapsed(claim_events),'claim_select_or_pragma_events':sum(op in ('SELECT','PRAGMA') for op,t in claim_events),'finish_writer_transaction_seconds':elapsed(finish_events),'artifact_observations':observations,'canonical_job_outcome_queues_unchanged':True,'actual_candidate_rendering_claimed':False,'production_changes':0,'model_calls':0};(scope/'receipt.json').write_bytes(canonical(result));print(json.dumps(result),flush=True)
