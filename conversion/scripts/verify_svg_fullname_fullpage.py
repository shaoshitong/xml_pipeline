import argparse,base64,hashlib,json,sqlite3,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_fullname_fonts import patch_native,verify_patch,verify_render_fonts
from source_fullname_capture_retry import capture_source
from source_svg_snapshot import auxiliary_hashes
from strict_canvas_gate import require_declared_page
sha=lambda b:hashlib.sha256(b).hexdigest()

def verify(id):
 D=sqlite3.connect(W/'jobs.sqlite');state,raw=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();r=json.loads(raw);assert state!='accepted';proof=r['native_source_font_repair'];B=(R/proof['audit']).parent;old=json.loads((B/'before_record.json').read_text());xml=(R/r['code_file']).read_text();png=(R/r['image_file']).read_bytes();assert sha(xml.encode())==r['code_sha256']==r['native_font_validation']['output_code_sha256'];assert sha(png)==r['image_sha256'];assert sha((B/'before.drawio').read_bytes())==old['code_sha256'];assert sha((B/'before.png').read_bytes())==old['image_sha256'];changes=json.loads((B/'changes.json').read_text());verify_patch((B/'before.drawio').read_text(),xml,changes)
 for k in old:
  if k not in ['code_sha256','image_sha256','render','native_embedded_fonts','native_font_validation','metrics','native_canvas_refresh']:assert old[k]==r[k],k
 for key,digest in [('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:assert (R/r[key]).resolve().is_relative_to(R/'clean') and sha((R/r[key]).read_bytes())==r[digest]
 assert auxiliary_hashes(r)==proof['source_auxiliary_hashes'];model=E.fromstring(xml).find('.//mxGraphModel');urls=dict(s.split('^',1) for s in model.get('extFonts').split('|'))
 for f in r['native_embedded_fonts']:
  for key,digest in [('file','sha256'),('original_file','original_sha256')]:assert (R/f[key]).resolve().is_relative_to(R/'clean') and sha((R/f[key]).read_bytes())==f[digest]
  assert sha(base64.b64decode(urls[f['family']].split(',',1)[1]))==f['sha256']
 for key,hkey in [('source_before_dom_file','source_before_dom_sha256'),('source_after_dom_file','source_after_dom_sha256')]:assert (R/proof[key]).resolve().is_relative_to(R/'clean') and sha((R/proof[key]).read_bytes())==proof[hkey]
 w,h=Image.open(R/r['original_reference']).size;V=W/'svg_fullname_fullpage_verification'/id;V.mkdir(exist_ok=True,parents=True)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:before,after,bp,ap,fonts,source_changes=capture_source(browser,old,V,w,h)
  finally:browser.close()
 assert before==json.loads((R/proof['source_before_dom_file']).read_text());assert after==json.loads((R/proof['source_after_dom_file']).read_text());rebuilt,rebuilt_changes=patch_native((B/'before.drawio').read_text(),old,before,after,fonts,w,h);assert rebuilt==xml and rebuilt_changes==changes,'Fresh source reconstruction differs from published native text';baseline=native.native_job((B/'before.drawio').read_text(),w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');fresh=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert baseline['ok'] and baseline['png']==(B/'before.png').read_bytes();assert fresh['ok'] and fresh['png']==png;require_declared_page(baseline['native_render'],w,h);require_declared_page(fresh['native_render'],w,h);verify_render_fonts(baseline['native_render'],fresh['native_render'],changes,source_changes);out={'at':now(),'id':id,'ok':True,'changed_text_objects':len(changes),'fresh_source_font_and_text_geometry_reconstruction_identical':True,'all_source_code_image_data_and_font_payload_hashes_verified':True,'all_final_font_and_dom_assets_under_clean':True,'fresh_native_png_identical':True,'requested_physical_faces_and_source_glyph_counts_match':True,'unchanged_text_positions_and_nontext_graph_preserved':True,'reference_ssim_before':proof['reference_ssim_before'],'reference_ssim_after':proof['reference_ssim_after'],'accepted':False};(V/'report.json').write_text(json.dumps(out,indent=2));D.close();return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('ids',nargs='*');a=p.parse_args();D=sqlite3.connect(W/'jobs.sqlite');tables=[r[0] for r in D.execute("select name from sqlite_master where name in ('svg_fullname_font_repairs','svg_fullname_font_repairs_v2')")];ids=a.ids or sorted({r[0] for table in tables for r in D.execute('select id from '+table+" where state='published'")});results=[]
 for id in ids:
  try:r=verify(id)
  except Exception as e:r={'id':id,'ok':False,'error':repr(e)}
  results.append(r);print(json.dumps(r),flush=True)
 out={'at':now(),'ok':bool(results) and all(r['ok'] for r in results),'results':results};(W/'svg_fullname_fullpage_verification.json').write_text(json.dumps(out,indent=2));assert out['ok'],out
