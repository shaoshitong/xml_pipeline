import base64,hashlib,json,sqlite3,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from native_text_clip import verify_graph,verify_positions,pixel_clip_proof,plain
sha=lambda b:hashlib.sha256(b).hexdigest()
def verify(id):
 D=sqlite3.connect(W/'jobs.sqlite');state,raw=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert state!='accepted';out=json.loads(raw);clip=out['native_text_clipping'];work=(R/clip['audit']).parent;old=json.loads((work/'before_record.json').read_text());details=json.loads((work/'clip_details.json').read_text());xml=(R/out['code_file']).read_text();png=(R/out['image_file']).read_bytes();assert sha(xml.encode())==out['code_sha256']==out['native_font_validation']['output_code_sha256'];assert sha(png)==out['image_sha256'];assert sha((R/clip['source_dom_file']).read_bytes())==clip['source_dom_sha256'];assert (R/clip['source_dom_file']).resolve().is_relative_to(R/'clean');verify_graph((work/'before.drawio').read_text(),xml,details)
 for k in old:
  if k not in ['code_sha256','image_sha256','render','native_font_validation','metrics','native_canvas_refresh']:assert old[k]==out[k],k
 for key,digest in [('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:assert sha((R/out[key]).read_bytes())==out[digest]
 urls=dict(x.split('^',1) for x in E.fromstring(xml).find('.//mxGraphModel').get('extFonts').split('|'))
 for f in out['native_embedded_fonts']:
  for key,digest in [('file','sha256'),('original_file','original_sha256')]:p=R/f[key];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==f[digest]
  assert sha(base64.b64decode(urls[f['family']].split(',',1)[1]))==f['sha256']
 for a in out['source_assets']:
  if a['source']!='embedded_original_html_asset':assert sha((R/a['source']).read_bytes())==a['source_sha256']
 w,h=Image.open(R/out['image_file']).size;fresh=native.native_job(xml,w,h,120,W/'rendering_textproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==png;before=json.loads((work/'before_render.json').read_text());verify_positions(before['actual_text_positions'],fresh['native_render']['actual_text_positions']);usage=lambda x:{r['cell']:r['fonts'] for r in x['actual_platform_font_usage']};assert usage(before)==usage(fresh['native_render']);assert all(f['isCustomFont'] for fs in usage(fresh['native_render']).values() for f in fs if f['glyphCount']);proof=pixel_clip_proof((work/'before.png').read_bytes(),png,(work/'background.png').read_bytes(),details);assert proof['ok'];report={'at':now(),'id':id,'ok':True,'accepted':False,'editable_source_text_objects_verified':clip['source_text_objects_verified'],'source_rectangular_text_clips_restored':clip['clipped_text_objects'],'original_source_image_code_and_assets_hashes_preserved':True,'font_active_file_and_embedded_payload_hashes_verified':True,'all_actual_fonts_custom_and_physical_glyph_counts_preserved':True,'all_native_character_bounds_unchanged':True,'fresh_actual_native_png_identical':True,'source_dom_metadata_under_clean':True,'pixel_proof':proof};D.close();return report
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('ids',nargs='*');a=p.parse_args();D=sqlite3.connect(W/'jobs.sqlite');ids=a.ids or [r[0] for r in D.execute("select id from native_text_clip_repairs where state='published' and json_extract(record,'$.implementation')='source_text_clip_batch_v2'")];results=[]
 for id in ids:
  try:r=verify(id)
  except Exception as e:r={'id':id,'ok':False,'error':repr(e)}
  results.append(r);print(json.dumps(r),flush=True)
 out={'at':now(),'ok':bool(results) and all(r['ok'] for r in results),'results':results};(W/'native_text_clip_batch_verification.json').write_text(json.dumps(out,indent=2));assert out['ok'],out
