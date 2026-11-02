import json,sqlite3,tempfile
from pathlib import Path
import auto_quality_batch_v2 as m
from auto_quality_common import sha

def run(mode):
 with tempfile.TemporaryDirectory() as t:
  m.R=Path(t);m.W=m.R/'conversion';m.W.mkdir();dest=m.R/'clean/pair';dest.mkdir(parents=True)
  xml=b'<mxfile/>';oldpng=b'old-png';newpng=b'fresh-png';(dest/'diagram.drawio').write_bytes(xml);(dest/'image.png').write_bytes(oldpng)
  r={'id':'one','code_file':'clean/pair/diagram.drawio','image_file':'clean/pair/image.png','code_sha256':sha(xml),'image_sha256':sha(oldpng)};raw=json.dumps(r);item=('one','rendered',raw,'{}','native')
  report={'id':'one','state':'qualified','accepted':False};out={**r,'image_file':'clean/pair/image.native.test.png','image_sha256':sha(newpng)}
  work=m.W/'proof';work.mkdir();(work/'fresh.png').write_bytes(newpng)
  d=sqlite3.connect(':memory:');d.execute('create table jobs(id primary key,state,output_record,worker_pid,updated_at,error,input_manifest)');d.execute('insert into jobs values(?,?,?,?,?,?,?)',('one','rendered',raw,None,'old','error','{}'))
  d.execute('create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at,primary key(id,code_hash,image_hash,policy))')
  # Exact schema used by the live v5/v6 queue, intentionally no updated_at.
  d.execute('create table auto_quality_exceptions_v1(id,code_hash,image_hash,policy,route,state,reason,updated_at,primary key(id,code_hash,image_hash,policy))');m.initialize_dispatch(d)
  d.execute('create table harness_queue_v3(id primary key,state,attempts,priority,worker_pid,started_at,heartbeat,session_dir,error)');d.execute('insert into harness_queue_v3 values(?,?,?,?,?,?,?,?,?)',('one','queued',0,0,None,None,None,None,'old'))
  if mode=='busy':d.execute('update jobs set worker_pid=123 where id="one"')
  if mode=='revised':d.execute('update jobs set output_record=? where id="one"',(json.dumps({**r,'revision_note':'new metadata'}),))
  if mode=='accepted':d.execute('update jobs set state="accepted" where id="one"')
  d.commit();m.publish(d,item,report,out,work,True)
  assert (dest/'image.png').read_bytes()==oldpng,'Prior image was overwritten'
  if mode=='idle':
   assert report['accepted'];assert d.execute('select state from jobs').fetchone()[0]=='accepted';assert (dest/'image.native.test.png').read_bytes()==newpng
   assert d.execute('select state from harness_queue_v3').fetchone()[0]=='resolved';assert json.loads((dest/'conversion.json').read_text())['image_sha256']==sha(newpng)
  else:
   assert report['state']=='stale_revision' and not report['accepted'];assert not (dest/'image.native.test.png').exists();assert d.execute('select state from harness_queue_v3').fetchone()[0]=='queued'
for mode in ('idle','busy','revised','accepted'):run(mode)
with tempfile.TemporaryDirectory() as t:
 m.R=Path(t);m.W=m.R/'conversion';m.W.mkdir();dest=m.R/'clean/pair';dest.mkdir(parents=True)
 xml=b'<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="n" parent="1" vertex="1" value="source"><mxGeometry width="50" height="30" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'
 (dest/'diagram.drawio').write_bytes(xml);(dest/'image.png').write_bytes(b'unchanged')
 r={'id':'one','source_pair_sha256':'one','source_code_sha256':'a'*64,'source_image_sha256':'b'*64,'code_file':'clean/pair/diagram.drawio','code_sha256':sha(xml),'image_file':'clean/pair/image.png','image_sha256':sha(b'unchanged')};raw=json.dumps(r)
 d=sqlite3.connect(':memory:');d.execute('create table jobs(id primary key,state,output_record,worker_pid,updated_at,error,input_manifest)');d.execute('insert into jobs values(?,?,?,?,?,?,?)',('one','harness_review_pending',raw,None,'old',None,'{}'))
 d.execute('create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at,primary key(id,code_hash,image_hash,policy))');d.execute('create table auto_quality_exceptions_v1(id,code_hash,image_hash,policy,route,state,reason,updated_at,primary key(id,code_hash,image_hash,policy))');m.initialize_dispatch(d)
 d.execute('create table harness_queue_v3(id primary key,state,attempts,priority,worker_pid,started_at,heartbeat,session_dir,error)');d.execute('insert into harness_queue_v3 values(?,?,?,?,?,?,?,?,?)',('one','held_for_quality_v2',2,9,None,'old','old','preserved','history'));d.commit()
 report={'id':'one','state':'repair_required','accepted':False,'failures':['raster_anomaly: local_text_line_ssim_below_0.55'],'checks':{'source':{'supported':True,'ok':True},'visual':{'ok':False,'failures':['local_text_line_ssim_below_0.55']}}};work=m.W/'failure';work.mkdir()
 m.publish(d,('one','harness_review_pending',raw,'{}','graph'),report,None,work,True)
 state,updated=d.execute('select state,output_record from jobs').fetchone();assert state=='needs_quality_repair';assert json.loads(updated)['root_review']['automatic_quality']['source']=='automatic_quality'
 assert d.execute('select state,attempts,priority,session_dir,error from harness_queue_v3').fetchone()==('held_for_source_v5',2,9,'preserved','history')
 assert (dest/'diagram.drawio').read_bytes()==xml and (dest/'image.png').read_bytes()==b'unchanged'
print(json.dumps({'ok':True,'fixtures':4,'live_queue_schema':True,'previous_payloads_preserved':True,'cas_ownership_protection':True}))
