"""Independent native fidelity in the original physical Source SVG domain.

The original PDF/reference global, tile and foreground gates remain mandatory.
Every Source text primitive is tested at the existing 0.55 local threshold in
one fixed Chromium source projection, with unchanged 0.03px glyph/font proof.
No reference pixels select source geometry, offsets, parameters or regions.
"""
import copy,io,json,math,xml.etree.ElementTree as ET
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
FIELD='compiler_tikz_node_paint_viewport_v2'
POLICY='complete_actual_PDF_Source_SVG_native_render_domain_v1'


def require(value,reason):
 if not value:raise ValueError(reason)


def retained_visual(original,domain):
 failures=[value for value in original.get('failures',[])if value!='local_text_line_ssim_below_0.55']
 if domain.get('ok')is not True:failures.append('independent_actual_PDF_source_render_domain_failed')
 return {**original,'ok':not failures,'failures':failures,'original_reference_visual':original,'cross_renderer_local_text_is_diagnostic':True,'source_replay_visual':domain.get('visual'),'source_render_domain_policy':POLICY,'scope':'Original global/tile/foreground thresholds plus complete same-browser Source paint and all-primitive local fidelity at unchanged thresholds; complete actual Source glyph/font geometry remains mandatory.'}


def verify(record,xml,png,native_info,profile,reference,work):
 from auto_quality_common_v4 import checked,image_quality
 from compiler_language_capture_v1 import screenshot
 from playwright.sync_api import sync_playwright
 from PIL import Image
 from tikz_pdf_glyph_layout_v1 import validate,source_positions
 from tikz_node_paint_export_contract_v4 import registration
 from compiler_tikz_node_paint_viewport_v2 import sha,raw,CHROME
 work=Path(work);require(not work.exists(),'source_domain_evidence_must_be_new');work.mkdir(parents=True)
 require(profile.get('ok')is True and profile.get('supported')is True and profile.get('profile')==FIELD,'source_domain_requires_full_fresh_source_frontend')
 evidence=profile['evidence'];require(evidence.get('complete_source_coverage')is True and evidence.get('source_label_driver_ownership_complete')is True and evidence.get('actual_original_PDF_paint_inventory',{}).get('complete_actual_PDF_paint_inventory')is True,'source_domain_missing_complete_PDF_and_PGF_ownership')
 require(evidence['candidate_code_sha256']==record['code_sha256']==sha(xml.encode()),'source_domain_candidate_XML_changed')
 require(evidence.get('actual_native_PDF_source_glyphs',{}).get('ok')is True,'source_domain_requires_actual_native_PDF_glyph_proof')
 p=record[FIELD];files=p['files'];source_svg=checked(R,files['source_svg']['file'],files['source_svg']['sha256']);expected_blob=checked(R,files['source_glyph_positions']['file'],files['source_glyph_positions']['sha256']);expected=json.loads(expected_blob)
 frame=p['frame'];width,height=frame['reference_viewport'];require(frame['crop']is False and frame['parameter_search']is False and frame['individual_object_changes']is False and frame['translation']==[0,0],'source_domain_requires_original_fixed_physical_frame')
 root=ET.fromstring(source_svg);require([float(root.get(key))for key in ('width','height')]==[width,height] and list(map(float,root.get('viewBox').split()))==[0,0,width,height],'source_domain_original_PDF_device_canvas_changed')
 blocked=[]
 with sync_playwright()as playwright:
  browser=playwright.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text'])
  try:
   context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=context.new_page();page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+source_svg.decode());page.evaluate('document.fonts.ready');source_png=screenshot(page)
   matrix=page.evaluate('()=>{const m=document.querySelector("g[data-tikz-physical-pdf-frame]").getScreenCTM();return[m.a,m.b,m.c,m.d,m.e,m.f]}')
   require(max(abs(a-b)for a,b in zip(matrix,[frame['scale'],0,0,frame['scale'],0,0]))<.00001,'source_domain_physical_unit_projection_changed')
   dom=page.evaluate((W/'scripts/svg_dom_pdf_v2.js').read_text());observed=source_positions(page,dom);require(raw(observed)==expected_blob,'source_domain_fresh_Source_glyph_or_font_inventory_changed');require(screenshot(page)==source_png and not blocked,'source_domain_observation_changed_paint_or_external_resources')
  finally:browser.close()
 registered,contract=registration(record,reference,xml,R);source=copy.deepcopy(observed);dx,dy=contract['original_page_offset']
 for row in source.values():
  for char in row['chars']:char['x']+=dx;char['y']+=dy
 glyphs=validate(source,native_info)
 visual=image_quality(source_png,png,registered,native_info.get('actual_text_positions'))
 require(visual.get('text_regions_checked')==sum(len([run for run in row['runs']if any(c.get('text','').strip()and c.get('width',0)>0 and c.get('height',0)>0 for c in run.get('chars',[]))])for row in native_info.get('actual_text_positions',[])),'source_domain_incomplete_native_text_region_coverage')
 (work/'source_browser.png').write_bytes(source_png);result=dict(ok=visual.get('ok')is True,policy=POLICY,visual=visual,source_glyphs=glyphs,source_SVG_sha256=sha(source_svg),source_browser_png_sha256=sha(source_png),candidate_fresh_png_sha256=sha(png),source_frame=frame,source_matrix=matrix,source_text_objects=len(observed),every_source_text_primitive_checked=True,original_reference_pixels_used_for_alignment=False,model_calls=0)
 (work/'report.json').write_bytes(raw(result));return result
