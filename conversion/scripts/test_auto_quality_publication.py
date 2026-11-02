import json,sqlite3,tempfile
from pathlib import Path
import auto_quality_batch as m
from auto_quality_common import sha

def run(mode):
 with tempfile.TemporaryDirectory() as t:
  m.R=Path(t);m.W=m.R/'conversion';m.W.mkdir();dest=m.R/'clean/pair';dest.mkdir(parents=True)
  xml=b'<mxfile/>';oldpng=b'old-png';newpng=b'fresh-png';(dest/'diagram.drawio').write_bytes(xml);(dest/'image.png').write_bytes(oldpng)
  r={'id':'one','code_file':'clean/pair/diagram.drawio','image_file':'clean/pair/image.png','code_sha256':sha(xml),'image_sha256':sha(oldpng)};raw=json.dumps(r);item=('one','rendered',raw,'{}','native')
  report={'id':'one','state':'qualified','accepted':False};out={**r,'image_file':'clean/pair/image.native.test.png','image_sha256':sha(newpng)}
  work=m.W/'proof';work.mkdir();(work/'fresh.png').write_bytes(newpng)
  d=sqlite3.connect(':memory:');d.execute('create table jobs(id primary key,state,output_record,worker_pid,updated_at,error)');d.execute('insert into jobs values(?,?,?,?,?,?)',('one','rendered',raw,None,'old','error'))
  d.execute('create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at,primary key(id,code_hash,image_hash,policy))')
  # Exact schema used by the live v5/v6 queue, intentionally no updated_at.
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
print(json.dumps({'ok':True,'fixtures':4,'live_queue_schema':True,'previous_payloads_preserved':True,'cas_ownership_protection':True}))
