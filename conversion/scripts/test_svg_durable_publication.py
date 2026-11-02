"""Real SQLite writer contention and real native rendering in an isolated test namespace."""
import json,sqlite3,threading,time,uuid,hashlib
from pathlib import Path
from PIL import Image,ImageDraw
import svg_batch_durable as m
from durable_sqlite import begin as real_begin
from native_worker import R,W,native,now

root=W/'runtime_tests'/('svg_durable_'+uuid.uuid4().hex[:12]);root.mkdir(parents=True);work=root/'conversion';work.mkdir();(work/'scripts').symlink_to(W/'scripts',target_is_directory=True);(work/'rendering').symlink_to(W/'rendering',target_is_directory=True);(root/'evaluation').symlink_to(R/'evaluation',target_is_directory=True)
source='<svg xmlns="http://www.w3.org/2000/svg" width="320" height="160" viewBox="0 0 320 160"><rect x="20" y="20" width="280" height="120" fill="#d5e8d4" stroke="#82b366" stroke-width="2"/><text x="160" y="90" text-anchor="middle" font-family="Arial" font-size="24">Durable SVG</text></svg>'
(root/'source.svg').write_text(source);im=Image.new('RGB',(320,160),'white');ImageDraw.Draw(im).rectangle((20,20,300,140),fill='#d5e8d4',outline='#82b366',width=2);im.save(root/'reference.png');digest=lambda b:hashlib.sha256(b).hexdigest();id=digest(source.encode());src={'source':'isolated_svg_publication_test','category':'scientific_diagram','image_sha256':digest((root/'reference.png').read_bytes()),'code_sha256':digest(source.encode())};inp={'source_code':'source.svg','reference_image':'reference.png'}
db=sqlite3.connect(work/'jobs.sqlite');db.execute('create table jobs(id TEXT PRIMARY KEY,state TEXT,route TEXT,input_record TEXT,input_manifest TEXT,output_record TEXT,attempts INTEGER,worker_pid INTEGER,updated_at TEXT,error TEXT)');db.execute('insert into jobs values(?,"queued","svg_v2",?,?,NULL,0,NULL,NULL,NULL)',(id,json.dumps(src),json.dumps(inp)));db.commit();db.close()
counts=[]
def contended_begin(db):
 ready=threading.Event()
 def hold():
  other=sqlite3.connect(work/'jobs.sqlite',timeout=10);other.execute('begin immediate');ready.set();time.sleep(.4);other.commit();other.close()
 thread=threading.Thread(target=hold);thread.start();assert ready.wait(5);n=real_begin(db,seconds=10);thread.join();counts.append(n);return n
m.R=root;m.W=work;m.connect=lambda:sqlite3.connect(work/'jobs.sqlite',timeout=.02);m.begin=contended_begin
result=m.worker(0,1);db=sqlite3.connect(work/'jobs.sqlite');state,raw,attempts,pid=db.execute('select state,output_record,attempts,worker_pid from jobs').fetchone();r=json.loads(raw);assert state in ['rendered','needs_quality_repair'] and attempts==1 and pid is None
for k,hk in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:assert digest((root/r[k]).read_bytes())==r[hk]
assert json.loads(((root/r['code_file']).parent/'conversion.json').read_text())==r;checkpoint=json.loads((work/'svg_durable_publication'/id/'committed.json').read_text());assert checkpoint['writer_retry_count']>0 and len(counts)==2 and all(x>0 for x in counts)
fresh=native.native_job((root/r['code_file']).read_text(),320,160,120,W/'rendering/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==(root/r['image_file']).read_bytes()
out={'at':now(),'isolated_directory':str(root),'real_database_untouched':True,'actual_sqlite_contention_retry_counts':counts,'processed_exactly_once':result['processed']==1,'db_metadata_payload_hashes_consistent':True,'fresh_native_png_identical':True,'state':state,'accepted':False,'ok':True};(W/'svg_durable_publication_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
