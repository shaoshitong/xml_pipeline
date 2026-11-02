import json,sqlite3,hashlib,base64,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from fontmix_validation import verify_graph,verify_fonts
D=sqlite3.connect(W/'jobs.sqlite');ids=[r[0] for r in D.execute("select f.id from native_font_embeddings_v3 f join jobs j on j.id=f.id where f.state='published' and json_extract(j.output_record,'$.native_font_validation.method')='physical_font_runs_with_exact_native_pixels_v3'")];assert ids;results=[];sha=lambda b:hashlib.sha256(b).hexdigest()
for id in ids:
 row=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();state,raw=row;r=json.loads(raw);proof=r['native_font_validation'];assert proof['method']=='physical_font_runs_with_exact_native_pixels_v3';audit=R/proof['audit'];work=audit.parent;old=json.loads((work/'before_record.json').read_text());xml=(R/r['code_file']).read_text();png=(R/r['image_file']).read_bytes();assert sha(xml.encode())==r['code_sha256']==proof['output_code_sha256'];assert sha(png)==r['image_sha256']==old['image_sha256'];assert state!='accepted';details=json.loads((work/'font_details.json').read_text());observed=json.loads((work/'observed_fonts.json').read_text());verify_graph((work/'before.drawio').read_text(),xml,details)
 for k in old:
  if k not in ['code_sha256','render','native_embedded_fonts','native_font_validation','validation_pending']:assert old[k]==r[k],k
 root=E.fromstring(xml);urls=dict(x.split('^',1) for x in root.find('.//mxGraphModel').get('extFonts').split('|'))
 for f in r['native_embedded_fonts']:
  for key,h in [('file','sha256'),('original_file','original_sha256')]:
   p=R/f[key];assert p.resolve().is_relative_to(R/'clean');assert sha(p.read_bytes())==f[h]
  assert sha(base64.b64decode(urls[f['family']].split(',',1)[1]))==f['sha256']
 for key,h in [('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:
  p=R/r[key];assert p.resolve().is_relative_to(R/'clean');assert sha(p.read_bytes())==r[h],key
 w,h=Image.open(R/r['image_file']).size;fresh=native.native_job(xml,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==png;verify_fonts(observed,fresh['native_render'],details);results.append({'id':id,'fonts':len(r['native_embedded_fonts']),'mixed_text_cells':details['mixed_text_cells'],'all_text_cells':len(details['changes']),'original_source_and_image_hashes_preserved':True,'font_file_and_embedded_payload_hashes_match':True,'fresh_actual_native_png_identical':True,'editable_text_and_graph_preserved':True,'physical_font_glyph_counts_preserved':True,'accepted':False})
report={'at':now(),'ok':True,'results':results};(W/'native_font_v3_publication_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
