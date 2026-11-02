import json,sqlite3,hashlib
from PIL import Image
from native_worker import R,W,native,now
D=sqlite3.connect(W/'jobs.sqlite');rows=[]
for id in ['0001784b9f3b28598732c2dc034369bd2dc5274e31e8a2a945bb3bc4a6fb15c2','0001e9de3d46dda67b0e749c8376d7138f91e3673273930bccfb3f33599a7c79']:
 state,raw=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert state=='accepted';record=json.loads(raw);xml=(R/record['code_file']).read_text();png=(R/record['image_file']).read_bytes();assert hashlib.sha256(xml.encode()).hexdigest()==record['code_sha256'];w,h=Image.open(R/record['image_file']).size;out=native.native_job(xml,w,h,120,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert out['ok'];result={'id':id,'format':record['source_format'],'fresh_strict_native_png_identical':out['png']==png,'outside_page_pixel_audit':out['native_render'].get('outside_page_pixel_audit'),'content_outside_declared_canvas':out['native_render']['content_outside_declared_canvas']};rows.append(result);print(json.dumps(result),flush=True)
report={'at':now(),'results':rows,'scope':'Two accepted font/canvas pilots only, not a corpus-wide strict release audit.','ok':all(x['fresh_strict_native_png_identical'] for x in rows)};(W/'accepted_strict_canvas_pilots.json').write_text(json.dumps(report,indent=2));assert report['ok']
