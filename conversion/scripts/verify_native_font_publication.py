import json,sqlite3,hashlib,base64,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from mermaid_geometry_coverage import check
D=sqlite3.connect(W/'jobs.sqlite');ids=json.loads((W/'native_font_embedding_owner.json').read_text())['ids'];assert len(ids)==2;results=[]
for id in ids:
 r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);xml=(R/r['code_file']).read_text();png=(R/r['image_file']).read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(xml.encode())==r['code_sha256']==r['native_font_validation']['output_code_sha256'];assert sha(png)==r['image_sha256'];root=E.fromstring(xml);urls=dict(x.split('^',1) for x in root.find('.//mxGraphModel').get('extFonts').split('|'))
 for f in r['native_embedded_fonts']:
  for pathkey,h in [('file','sha256'),('original_file','original_sha256')]:
   p=R/f[pathkey];assert p.resolve().is_relative_to(R/'clean');assert sha(p.read_bytes())==f[h]
  assert sha(base64.b64decode(urls[f['family']].split(',',1)[1]))==f['sha256']
 w,h=Image.open(R/r['image_file']).size;fresh=native.native_job(xml,w,h,90,W/'rendering_fontproof/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==png;usage=fresh['native_render']['actual_platform_font_usage'];assert all(row['fonts'] and all(f['isCustomFont'] for f in row['fonts'] if f['glyphCount']) for row in usage);ast=json.loads((R/r['source_ast_file']).read_text());coverage=check(ast,xml,r['svg_conversion']['mermaid_source_metadata']);assert coverage['ok'];results.append({'id':id,'fonts':len(r['native_embedded_fonts']),'native_text_cells':len(usage),'font_asset_hashes_and_embedded_payloads_match':True,'fresh_actual_native_png_identical':True,'actual_custom_fonts_used':True,'source_ast_coverage':coverage,'accepted':False})
report={'at':now(),'ok':True,'results':results};(W/'native_font_publication_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
