"""Promote staged source dependencies to clean, preserving payload bytes and live ownership."""
import argparse,hashlib,json,os,sqlite3,time,traceback,re
from pathlib import Path
from PIL import Image
from native_worker import R,W,now
from durable_sqlite import begin,commit
sha=lambda b:hashlib.sha256(b).hexdigest()
FIELDS={'original_reference':'source_image_sha256','original_source_code':'source_code_sha256','original_source_data':'source_data_sha256','source_render_svg':'source_render_svg_sha256','source_render_pdf':'source_render_pdf_sha256'}
IDLE=('rendered','needs_quality_repair','needs_fallback','harness_review_pending')

def plan(r):
 assert re.fullmatch(r"[0-9a-f]{64}",r["id"]),"Invalid sample ID"
 changes={};directory=R/'clean/drawio_unified'/r['id'][:2]/r['id']/'original_inputs'
 for key,hkey in FIELDS.items():
  if not r.get(key):continue
  src=(R/r[key]).resolve()
  if src.is_relative_to(R/'clean'):continue
  assert src.is_relative_to(W/'inputs'),'Not an owned staged source: '+key
  data=src.read_bytes();digest=sha(data);assert digest==r[hkey],'Staged source hash mismatch: '+key
  if key=='original_reference':
   with Image.open(src) as im:ext='.'+im.format.lower()
  else:ext={'original_source_code':'.txt','original_source_data':src.suffix or '.bin','source_render_svg':'.svg','source_render_pdf':'.pdf'}[key]
  dest=directory/(key+'_'+digest+ext)
  if dest.exists():assert dest.is_file() and not dest.is_symlink() and sha(dest.read_bytes())==digest
  changes[key]={'from':r[key],'to':str(dest.relative_to(R)),'sha256':digest,'bytes':len(data)}
 return changes

def materialize_sources(r):
 """Used by new publications before writing their record, as well as repair tooling."""
 out=dict(r);changes=plan(r)
 for key,x in changes.items():
  src=R/x['from'];dest=R/x['to'];dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():
   try:os.link(src,dest)
   except FileExistsError:pass
  assert not dest.is_symlink() and sha(dest.read_bytes())==x['sha256']
  out[key]=x['to']
 if changes:out['source_payload_promotion']={'at':now(),'changes':changes,'method':'same-filesystem hard links to immutable staged source bytes; staging retained for active workers'}
 return out

def run(limit,ids):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists source_payload_promotions (id TEXT,record_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,record_sha256))');commit(D)
 (W/'source_payload_promotion_owner.json').write_text(json.dumps({'pid':os.getpid(),'at':now(),'limit':limit,'ids':ids}))
 count=0
 while not limit or count<limit:
  rows=D.execute("select id,state,output_record from jobs where state in ('rendered','needs_quality_repair','needs_fallback','harness_review_pending') and (json_extract(output_record,'$.original_reference') like 'conversion/inputs/%' or json_extract(output_record,'$.original_source_code') like 'conversion/inputs/%') order by case when error like '%Source resource outside clean%' then 0 else 1 end,id").fetchall()
  if ids:rows=[x for x in rows if x[0] in ids]
  rows=[x for x in rows if not D.execute('select 1 from source_payload_promotions where id=? and record_sha256=?',(x[0],sha(x[2].encode()))).fetchone()]
  if not rows:break
  for id,state,raw in rows:
   if limit and count>=limit:break
   digest=sha(raw.encode());r=json.loads(raw);report={'id':id,'at':now(),'input_record_sha256':digest,'payloads_unchanged':True};status='failed';changed=False
   try:
    changes=plan(r);assert changes
    # Hash checks include current XML/PNG; this operation must never convert or accept a case.
    for k,hk in [('code_file','code_sha256'),('image_file','image_sha256')]:assert sha((R/r[k]).read_bytes())==r[hk],k
    out=dict(r)
    for key,x in changes.items():
     src=R/x['from'];dest=R/x['to'];dest.parent.mkdir(parents=True,exist_ok=True)
     if not dest.exists():
      try:os.link(src,dest)
      except FileExistsError:pass
     assert not dest.is_symlink() and sha(dest.read_bytes())==x['sha256']
     out[key]=x['to']
    out['source_payload_promotion']={'at':now(),'input_record_sha256':digest,'changes':changes,'method':'same-filesystem hard links to immutable staged source bytes; staging retained for active workers'}
    # Only update the exact idle version observed. Workers claim through the same SQLite lock.
    begin(D);current=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()
    if current!=(state,raw):D.rollback();continue
    q=D.execute('select state,error,session_dir from harness_queue_v3 where id=?',(id,)).fetchone()
    assert not q or q[0]!='running','Harness owns current source'
    path=(R/r['code_file']).parent/'conversion.json'
    assert json.loads(path.read_text())==r,'Published metadata differs from database'
    requeue=bool(q and q[0]=='attempt_finished' and q[1]=='AssertionError: Source resource outside clean')
    if requeue:
     # Infrastructure failure was before model calls; retain session and attempt history in this audit.
     session=R/q[2];assert not list(session.glob('*/call.json')),'Unexpected paid call before infrastructure failure'
     D.execute('update harness_queue_v3 set state="held_for_source_v5",worker_pid=NULL,error=NULL where id=? and state="attempt_finished"',(id,))
    body=json.dumps(out,ensure_ascii=False,indent=2);tmp=path.with_suffix('.source-promotion.tmp');tmp.write_text(body);tmp.replace(path)
    D.execute('update jobs set output_record=?,error=?,updated_at=? where id=?',(json.dumps(out,ensure_ascii=False),None if requeue else D.execute('select error from jobs where id=?',(id,)).fetchone()[0],now(),id))
    report.update(changes=changes,prior_queue=q,requeued_after_pre_model_failure=requeue,output_record_sha256=sha(json.dumps(out,ensure_ascii=False).encode()),code_sha256=r['code_sha256'],image_sha256=r['image_sha256']);status='promoted';changed=True
    D.execute('insert into source_payload_promotions values (?,?,?,?,?)',(id,digest,status,json.dumps(report),now()));commit(D)
   except Exception as e:
    D.rollback();report['error']=repr(e);report['traceback']=traceback.format_exc();begin(D);D.execute('insert or ignore into source_payload_promotions values (?,?,?,?,?)',(id,digest,status,json.dumps(report),now()));commit(D)
   count+=1
   if status=='failed' or count%100==0:print(json.dumps({'at':now(),'processed':count,'id':id,'state':status,'error':report.get('error')}),flush=True)
 result={'at':now(),'processed':count,'states':dict(D.execute('select state,count(*) from source_payload_promotions group by state')),'remaining_by_state':D.execute("select state,count(*) from jobs where json_extract(output_record,'$.original_reference') like 'conversion/inputs/%' group by state").fetchall()}
 (W/'source_payload_promotion_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=0);p.add_argument('--ids',nargs='*',default=[]);a=p.parse_args();run(a.limit,a.ids)
