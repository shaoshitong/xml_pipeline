import json,sqlite3,uuid
from PIL import Image
from native_worker import R,W,native,now,sha
from mermaid_native_v2 import build,check_backgrounds
from mermaid_semantic_v4 import check as semantic
from mermaid_geometry_coverage import check as geometry
from svg_source_coverage_v2 import audit as coverage
from harness_context_v5 import build_context,compact_xml,hydrate
from strict_canvas_gate import require_declared_page

from playwright.sync_api import sync_playwright
from portable_native_fonts import ready_page
from native_move_audit import SCRIPT as MOVE
from mermaid_native_v2 import MOVE_SCRIPT as BG_MOVE
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);results=[]
for id,expected in [('0b4d8f904638e102675cf373b09496594eab6c9bfd948e01a460c56fb405a785','e8ea8798398b06a643dda7f7aa78e15196d34f5ae087189283516dfd2097db13'),('0b8e6086486b77fdc223c81e902f2927af8f9a3be730f9f2133c68479b637fdb','743ffc5ceaa21bd2777ed555c0bca13c88dc8b318d6cf4d86a22ebfcc6ce9b97')]:
 state,current,source,inp=D.execute('select state,output_record,input_record,input_manifest from jobs where id=?',(id,)).fetchone();snapshot=W/'root_candidate_snapshots'/id/expected;r=json.loads((snapshot/'record.json').read_text());xml=(snapshot/'diagram.drawio').read_text();png=(snapshot/'native.png').read_bytes();assert sha(xml.encode())==expected==r['code_sha256'] and sha(png)==r['image_sha256'];w,h=Image.open(R/r['original_reference']).size
 for k,hk in [('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_png','source_render_png_sha256')]:
  p=R/r[k];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==r[hk]
 files=r['native_source_geometry_repair']['files']
 for x in files.values():assert (R/x['file']).resolve().is_relative_to(R/'clean') and sha((R/x['file']).read_bytes())==x['sha256']
 assert isinstance(r['native_embedded_fonts'],list)
 for f in r['native_embedded_fonts']:
  for k,hk in [('file','sha256'),('original_file','original_sha256')]:assert (R/f[k]).resolve().is_relative_to(R/'clean') and sha((R/f[k]).read_bytes())==f[hk]
 dom=json.loads((R/files['source_dom.json']['file']).read_text());ast=json.loads((R/files['source_ast.json']['file']).read_text());md=json.loads((R/files['source_geometry.json']['file']).read_text());_,stats,processed=build(dom,w,h,md)
 cov=coverage(processed,xml,stats);geo=geometry(ast,xml,md);sem=semantic(ast,xml);assert cov['ok'] and geo['ok'] and sem['status']=='node_edge_text_match';check_backgrounds(xml,stats['native_html_label_backgrounds'])
 immutable=(R/r['code_file']).parent/'review_candidates'/expected;immutable.mkdir(parents=True,exist_ok=True)
 for name,data in [('diagram.drawio',xml.encode()),('image.png',png)]:
  dest=immutable/name
  if dest.exists():assert dest.read_bytes()==data
  else:dest.write_bytes(data)
 r['code_file']=str((immutable/'diagram.drawio').relative_to(R));r['image_file']=str((immutable/'image.png').relative_to(R))
 B=W/'harness_sessions'/('compound_node_audit_'+id+'_'+uuid.uuid4().hex[:8]);B.mkdir();ctx=build_context(json.loads(source),json.loads(inp),r,B);roundtrip,_=hydrate(compact_xml(xml,ctx),ctx);fresh=native.native_job(roundtrip,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==png;require_declared_page(fresh['native_render'],w,h)
 usage=fresh['native_render']['actual_platform_font_usage'];assert usage
 for row in usage:
  assert row['fonts'] and all(f['isCustomFont'] for f in row['fonts'] if f['glyphCount'])
 report=json.loads((R/r['native_source_geometry_repair']['audit']).read_text());assert report['native_html_backgrounds']['pixel_audit']['ok'];assert report['actual_endpoint_moves']==geo['source_edges']*2
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser);moves=page.evaluate(MOVE,xml);bgmoves=page.evaluate(BG_MOVE,{'xml':xml,'bindings':stats['native_html_label_backgrounds']});browser.close()
 assert len(moves['moves'])==2*geo['source_edges']
 for m in moves['moves']:assert abs(m['delta']['x']-17)<1e-5 and abs(m['delta']['y']-11)<1e-5
 for m in bgmoves:assert all(abs(m['background_delta'][k]-m['label_delta'][k])<1e-5 for k in ['x','y'])
 (B/'actual_moves.json').write_text(json.dumps({'endpoints':moves,'backgrounds':bgmoves},indent=2));anchor=json.loads((R/files['anchor_fit.json']['file']).read_text());assert anchor['component_count']>anchor['node_count'];assert r['source_renderer']['font_override'] is None

 results.append({'id':id,'code_sha256':r['code_sha256'],'actual_render_after_harness_roundtrip_identical':True,'source_coverage':cov['ok'],'source_semantic':sem['status'],'source_nodes':geo['source_nodes'],'source_edges':geo['source_edges'],'endpoint_moves':len(moves['moves']),'background_moves':len(bgmoves),'actual_move_audit':str((B/'actual_moves.json').relative_to(R)),'component_anchor_count':anchor['component_count'],'snapshot':str(snapshot.relative_to(R)),'immutable_candidate':str(immutable.relative_to(R)),'state_at_start':state,'current_code_at_end':json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0])['code_sha256'],'actual_embedded_font_text_cells':len(usage),'backgrounds':len(stats['native_html_label_backgrounds']),'background_pixel_audit':report['native_html_backgrounds']['pixel_audit'],'all_payload_dependencies_clean':True,'accepted':False})
out={'at':now(),'ok':True,'results':results,'scope':'Independent fresh source and renderer roundtrip audit; original-reference visual fidelity remains required.'};(W/'mermaid_compound_node_release_audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
