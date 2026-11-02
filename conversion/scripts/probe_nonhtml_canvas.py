import json,sqlite3,hashlib
from pathlib import Path
from PIL import Image
from native_worker import R,W,native,now
from svg_pilot import metrics
D=sqlite3.connect(W/'jobs.sqlite');results=[]
for id in ['00c975522ec4d80ed17b33637be20d9adc5271a1207763bc5073c591bfcd1ed2','004d04208982b2501ea670c77cd454f814ba1ba37dd08b643f1fbb78ea699039']:
 old=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);P=W/'native_font_embedding_v4'/id/old['code_sha256'];B=W/'nonhtml_canvas_probe'/id;B.mkdir(parents=True,exist_ok=True);w,h=Image.open(R/old['original_reference']).size;record={'id':id,'input_hash':old['code_sha256'],'old_size':old['render']['output_size'],'reference_size':[w,h]}
 try:
  xml=(R/old['code_file']).read_text();candidate=(P/'original_flags_native_stack.drawio').read_text();baseline=native.native_job(xml,w,h,120,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');after=native.native_job(candidate,w,h,120,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert baseline['ok'] and after['ok'];(B/'before.png').write_bytes((R/old['image_file']).read_bytes());(B/'baseline.png').write_bytes(baseline['png']);(B/'after.png').write_bytes(after['png']);(B/'baseline_render.json').write_text(json.dumps(baseline['native_render'],indent=2));(B/'after_render.json').write_text(json.dumps(after['native_render'],indent=2));ref=(R/old['original_reference']).read_bytes();record.update(baseline_equals_embedded=baseline['png']==after['png'],new_selection=after['native_render']['selected_image'],new_size=after['native_render']['output_size'],bounds=after['native_render'].get('outside_page_pixel_audit'),before_reference_ssim=metrics(ref,(B/'before.png').read_bytes())['ssim_512'],after_reference_ssim=metrics(ref,after['png'])['ssim_512'])
 except Exception as e:record['error']=repr(e)
 (B/'report.json').write_text(json.dumps(record,indent=2));results.append(record);print(json.dumps(record),flush=True)
(W/'nonhtml_canvas_probe.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
