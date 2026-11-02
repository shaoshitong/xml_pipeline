import json,sqlite3,hashlib
from PIL import Image
from native_worker import R,W,native,now
D=sqlite3.connect(W/'jobs.sqlite');summary=json.loads((W/'tikz_durable_smoke_summary.json').read_text());assert sum(x['processed'] for x in summary['results'])==2;events=[json.loads(s) for s in (W/'tikz_durable_events.jsonl').read_text().splitlines() if s];assert len(events)==2;results=[]
for e in events:
 id=e['id'];state,raw,pid=D.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone();assert state!='tikz_converting';r=json.loads(raw) if raw else None;cp=W/'tikz_durable_publication'/id
 if not (cp/'committed.json').exists():
  assert state=='needs_fallback' and e['error'];results.append({'id':id,'failure_preserved':True,'error':e['error']});continue
 j=json.loads((cp/'committed.json').read_text());assert j['code_sha256']==r['code_sha256'] and j['image_sha256']==r['image_sha256'];xml=(R/r['code_file']).read_text();png=(R/r['image_file']).read_bytes();assert hashlib.sha256(xml.encode()).hexdigest()==r['code_sha256'];assert hashlib.sha256(png).hexdigest()==r['image_sha256'];w,h=Image.open(R/r['original_reference']).size;fresh=native.native_job(xml,w,h,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==png;results.append({'id':id,'hashes_match_db_and_checkpoint':True,'fresh_actual_native_png_identical':True,'state':state,'accepted':False})
assert any(r.get('fresh_actual_native_png_identical') for r in results);report={'at':now(),'ok':True,'results':results};(W/'tikz_durable_smoke_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
