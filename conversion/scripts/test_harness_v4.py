import copy,json,sqlite3,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from harness_context_v4 import build_context,compact_xml,hydrate,structure,sha,verify_source_fullname_faces,validate_font_resources
from harness_graphviz_gate import check
from harness_pool_v4 import passed,REQUIRED
from strict_canvas_gate import require_declared_page
D=sqlite3.connect(W/'jobs.sqlite');B=W/'harness_v4_preflight';B.mkdir(exist_ok=True);results=[]
ids=['00c975522ec4d80ed17b33637be20d9adc5271a1207763bc5073c591bfcd1ed2']
row=D.execute("select id from jobs where format='html' and state in ('rendered','needs_quality_repair') and json_extract(output_record,'$.native_font_validation.output_code_sha256')=json_extract(output_record,'$.code_sha256') and json_array_length(json_extract(output_record,'$.native_embedded_fonts'))>0 order by id limit 1").fetchone();assert row;ids.append(row[0])
for id in ids:
 source,inp,raw=D.execute('select input_record,input_manifest,output_record from jobs where id=?',(id,)).fetchone();old=json.loads(raw);V=B/id;V.mkdir(exist_ok=True)
 if id==ids[0]:archive=R/old['previous_candidate_archive'];old=json.loads((archive/'conversion.json').read_text());xml=(archive/'diagram.drawio').read_text();png=(archive/'image.png').read_bytes()
 else:xml=(R/old['code_file']).read_text();png=(R/old['image_file']).read_bytes()
 assert sha(xml.encode())==old['code_sha256'] and sha(png)==old['image_sha256'];ctx=build_context(json.loads(source),json.loads(inp),old,V);prior=old.get('native_embedded_fonts',[]);assert prior and all(f['family'] in ctx['fonts'] and ctx['fonts'][f['family']]['sha256']==f['sha256'] for f in prior);compact=compact_xml(xml,ctx);restored,used=hydrate(compact,ctx);assert set(validate_font_resources(restored,ctx))==set(ctx['fonts']);assert structure(restored,ctx)['ok'];w,h=Image.open(R/old['original_reference']).size;r=native.native_job(restored,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert r['ok'],{k:v for k,v in r.items() if k!='png'};(V/'roundtrip_candidate.png').write_bytes(r['png']);(V/'roundtrip_before.png').write_bytes(png);(V/'roundtrip_candidate.drawio').write_text(restored);(V/'roundtrip_before.drawio').write_text(xml);(V/'roundtrip_render.json').write_text(json.dumps(r['native_render'],indent=2));baseline=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert baseline['ok'];assert r['png']==baseline['png'],{'id':id,'reason':'font roundtrip changes fresh official native pixels','prior_fonts':len(prior)};canvas_ok=True
 try:require_declared_page(r['native_render'],w,h)
 except AssertionError:
  canvas_ok=False;assert id=='0001c7fc6c8af5cb3c7b28e7e33e9f5f2abe1d782448c2240b6612a3fc8ffe0a';assert r['native_render']['outside_page_pixel_audit']['nonwhite_outside_pixels']==baseline['native_render']['outside_page_pixel_audit']['nonwhite_outside_pixels']>0
 faces=verify_source_fullname_faces(old,r['native_render']);(V/'restored.drawio').write_text(restored);(V/'restored.png').write_bytes(r['png']);(V/'render.json').write_text(json.dumps(r['native_render'],indent=2));(V/'before_record.json').write_text(json.dumps(old,indent=2));edit=check(old,restored)
 if id==ids[0]:
  assert not edit['ok'] and len(edit['requirements'])==14;bad=copy.deepcopy(r['native_render']);cid=faces['checked'][0]['cell'];next(x for x in bad['actual_platform_font_usage'] if x['cell']==cid)['fonts'][0]['postScriptName']='Wrong-Face'
  try:verify_source_fullname_faces(old,bad)
  except AssertionError:pass
  else:raise AssertionError('Wrong physical face accepted')
  fake={'structure':{'ok':True,'edges':14},'judge':{'pass':True,'material_errors':[],'expected_semantic_connector_count':14,**{k:True for k in REQUIRED}},'source_coverage':{'status':'independent_source_coverage_pending'},'fidelity_diagnostic':{'regression_guard_pass':True},'source_editability':edit,'source_fullname_face_validation':faces};assert not passed(fake),'Perfect critic score bypassed arrow gate'
  c=copy.deepcopy(ctx);c['fonts'].pop(next(iter(c['fonts'])))
  try:compact_xml(xml,c)
  except AssertionError:pass
  else:raise AssertionError('Undeclared font silently stripped')
 results.append({'id':id,'prior_native_font_files':len(prior),'registry_fonts':len(ctx['fonts']),'font_payload_roundtrip_verified':True,'actual_roundtrip_png_identical':True,'fresh_native_baseline_matches_stored':baseline['png']==png,'eligible_for_declared_canvas':canvas_ok,'outside_pixels':r['native_render']['outside_page_pixel_audit']['nonwhite_outside_pixels'],'source_fullname_faces':faces,'source_editability_gate':edit})
out={'at':now(),'ok':True,'results':results,'negative_tests':['unknown font registry entry rejected before compaction','wrong physical source fullname face rejected','perfect critic score cannot bypass 14 detached source arrows']};(W/'harness_v4_preflight.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
