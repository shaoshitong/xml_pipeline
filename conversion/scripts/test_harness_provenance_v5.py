import copy,json,sqlite3,uuid
from native_worker import R,W,native,now
from harness_context_v5 import build_context,compact_xml,hydrate,verify_source_fullname_faces
from harness_source_provenance import attach,validate_frozen,resolve
from harness_graphviz_gate import check
from strict_canvas_gate import require_declared_page
from PIL import Image
ids=['00c975522ec4d80ed17b33637be20d9adc5271a1207763bc5073c591bfcd1ed2','0001e9de3d46dda67b0e749c8376d7138f91e3673273930bccfb3f33599a7c79'];D=sqlite3.connect(W/'jobs.sqlite',timeout=60);B=W/'harness_sessions'/('provenance_preflight_'+uuid.uuid4().hex[:10]);B.mkdir();results=[]
for id in ids:
 inp,prepared,raw=D.execute('select input_record,input_manifest,output_record from jobs where id=?',(id,)).fetchone();r=json.loads(raw);source=json.loads(inp);prepared=json.loads(prepared);folder=B/id;folder.mkdir();ctx=build_context(source,prepared,r,folder);proof=ctx['source_provenance'];verified=validate_frozen(proof);xml=(R/r['code_file']).read_text();new,used=hydrate(compact_xml(xml,ctx),ctx);w,h=Image.open(R/r['original_reference']).size;before=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');after=native.native_job(new,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert before['ok'] and after['ok'] and before['png']==after['png'];require_declared_page(after['native_render'],w,h);faces=verify_source_fullname_faces(verified,after['native_render']);assert faces['ok'];assert check(verified,new)['ok'];(folder/'before.png').write_bytes(before['png']);(folder/'after.png').write_bytes(after['png']);(folder/'before.drawio').write_text(xml);(folder/'after.drawio').write_text(new)
 stripped={k:v for k,v in r.items() if k not in ('native_source_font_repair','native_embedded_fonts','native_font_validation','source_font_recovery_archive','source_render_svg','source_render_svg_sha256','source_render_dot')};stripped['fonts']=[{k:v for k,v in f.items() if k!='bytes'} for f in ctx['fonts'].values()];published=attach(stripped,ctx);nextwork=folder/'next_generation';nextwork.mkdir();nextctx=build_context(source,prepared,published,nextwork);nextproof=validate_frozen(nextctx['source_provenance']);assert nextproof.get('native_source_font_repair')==verified.get('native_source_font_repair');assert set(ctx['fonts'])==set(nextctx['fonts']);again,_=hydrate(compact_xml(new,nextctx),nextctx);assert again==new,'Second model generation font roundtrip changed XML';neg=[]
 bad=copy.deepcopy(proof);bad['identity']['id']='wrong-source'
 try:validate_frozen(bad)
 except AssertionError:neg.append('wrong_source_identity')
 else:raise AssertionError('Wrong source identity accepted')
 bad=copy.deepcopy(proof);bad['record_sha256']='0'*64
 try:validate_frozen(bad)
 except AssertionError:neg.append('modified_frozen_record')
 else:raise AssertionError('Altered record digest accepted')
 bad=copy.deepcopy(proof);bad['archive']='raw'
 try:validate_frozen(bad)
 except AssertionError:neg.append('external_archive')
 else:raise AssertionError('External archive accepted')
 bad=copy.deepcopy(stripped);bad['source_image_sha256']='0'*64
 try:attach(bad,ctx)
 except AssertionError:neg.append('publication_source_identity_changed')
 else:raise AssertionError('Changed target reference accepted')
 results.append({'id':id,'archive':proof['archive'],'fonts':len(ctx['fonts']),'assets_used':len(used),'source_font_proof_applicable':bool(verified.get('native_source_font_repair')),'fresh_native_png_identical':True,'declared_canvas_passed':True,'source_fullname_faces':faces,'second_generation_provenance_preserved':True,'second_generation_font_roundtrip_xml_identical':True,'negative_tests_rejected':neg})
out={'at':now(),'ok':True,'work':str(B.relative_to(R)),'results':results};(W/'harness_provenance_v5_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
