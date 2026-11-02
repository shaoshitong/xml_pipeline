import hashlib,json,sqlite3
from PIL import Image
from native_worker import R,W,native,now
from strict_canvas_gate import require_declared_page
sha=lambda b:hashlib.sha256(b).hexdigest()
previous=json.loads((W/'svg_fullname_fullpage_verification.json').read_text());assert previous['ok'];D=sqlite3.connect(W/'jobs.sqlite');results=[]
for case in previous['results']:
 id=case['id'];V=W/'svg_fullname_paint_bounds_verification'/id;V.mkdir(parents=True,exist_ok=True)
 try:
  r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);xml=(R/r['code_file']).read_text();assert sha(xml.encode())==r['code_sha256'];stored=(R/r['image_file']).read_bytes();assert sha(stored)==r['image_sha256'];w,h=Image.open(R/r['original_reference']).size;fresh=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');(V/'render.json').write_text(json.dumps({k:v for k,v in fresh.items() if k!='png'},indent=2));assert fresh['ok'],fresh.get('reason');assert fresh['png']==stored;info=fresh['native_render'];require_declared_page(info,w,h);assert info['probe_includes_actual_dom_paint_bounds'] and not info['actual_dom_paint_bounds']['unsupported'];out={'at':now(),'id':id,'ok':True,'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256'],'fresh_native_png_identical':True,'paint_bounds':info['actual_dom_paint_bounds'],'outside_page_pixel_audit':info['outside_page_pixel_audit'],'accepted':False}
 except Exception as e:out={'id':id,'ok':False,'error':repr(e)}
 (V/'report.json').write_text(json.dumps(out,indent=2));results.append(out);print(json.dumps(out),flush=True)
out={'at':now(),'ok':all(r['ok'] for r in results),'results':results};(W/'svg_fullname_paint_bounds_verification.json').write_text(json.dumps(out,indent=2));assert out['ok']
