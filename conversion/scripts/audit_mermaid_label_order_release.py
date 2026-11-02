import json,sqlite3,uuid
from PIL import Image
from native_worker import R,W,native,now,sha
from mermaid_native_v2 import build,check_backgrounds
from mermaid_semantic_v4 import check as semantic
from mermaid_geometry_coverage import check as geometry
from svg_source_coverage_v2 import audit as coverage
from harness_context_v5 import build_context,compact_xml,hydrate
from strict_canvas_gate import require_declared_page

D=sqlite3.connect(W/'jobs.sqlite',timeout=60);results=[]
for id in ['02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce','047acd3596838a3e998ae96081f3d778bdec3210a6eb1e0ced7e4aafbe81733f']:
 state,raw,source,inp=D.execute('select state,output_record,input_record,input_manifest from jobs where id=?',(id,)).fetchone();r=json.loads(raw);assert state=='needs_quality_repair';xml=(R/r['code_file']).read_text();png=(R/r['image_file']).read_bytes();w,h=Image.open(R/r['original_reference']).size
 for k,hk in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_png','source_render_png_sha256')]:
  p=R/r[k];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==r[hk]
 files=r['native_source_geometry_repair']['files']
 for x in files.values():assert (R/x['file']).resolve().is_relative_to(R/'clean') and sha((R/x['file']).read_bytes())==x['sha256']
 assert isinstance(r['native_embedded_fonts'],list)
 for f in r['native_embedded_fonts']:
  for k,hk in [('file','sha256'),('original_file','original_sha256')]:assert (R/f[k]).resolve().is_relative_to(R/'clean') and sha((R/f[k]).read_bytes())==f[hk]
 dom=json.loads((R/files['source_dom.json']['file']).read_text());ast=json.loads((R/files['source_ast.json']['file']).read_text());md=json.loads((R/files['source_geometry.json']['file']).read_text());_,stats,processed=build(dom,w,h,md)
 cov=coverage(processed,xml,stats);geo=geometry(ast,xml,md);sem=semantic(ast,xml);assert cov['ok'] and geo['ok'] and sem['status']=='node_edge_text_match';check_backgrounds(xml,stats['native_html_label_backgrounds'])
 B=W/'harness_sessions'/('label_order_audit_'+id+'_'+uuid.uuid4().hex[:8]);B.mkdir();ctx=build_context(json.loads(source),json.loads(inp),r,B);roundtrip,_=hydrate(compact_xml(xml,ctx),ctx);fresh=native.native_job(roundtrip,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==png;require_declared_page(fresh['native_render'],w,h)
 usage=fresh['native_render']['actual_platform_font_usage'];assert usage
 for row in usage:
  assert row['fonts'] and all(f['isCustomFont'] for f in row['fonts'] if f['glyphCount'])
 report=json.loads((R/r['native_source_geometry_repair']['audit']).read_text());assert report['native_html_backgrounds']['pixel_audit']['ok'];assert report['actual_endpoint_moves']==geo['source_edges']*2
 assert r['source_renderer']['font_override'] is None,'Expected source-faithful default font for these two reviewed cases'
 results.append({'id':id,'code_sha256':r['code_sha256'],'actual_render_after_harness_roundtrip_identical':True,'source_coverage':cov['ok'],'source_semantic':sem['status'],'source_nodes':geo['source_nodes'],'source_edges':geo['source_edges'],'endpoint_moves':report['actual_endpoint_moves'],'actual_embedded_font_text_cells':len(usage),'backgrounds':len(stats['native_html_label_backgrounds']),'background_pixel_audit':report['native_html_backgrounds']['pixel_audit'],'all_payload_dependencies_clean':True,'accepted':False})
out={'at':now(),'ok':True,'results':results,'scope':'Independent fresh source and renderer roundtrip audit; original-reference visual fidelity remains required.'};(W/'mermaid_label_order_release_audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
