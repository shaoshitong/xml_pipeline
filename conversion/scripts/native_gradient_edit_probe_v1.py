"""Actual pinned Graph linear-gradient painter inspection and edit/restore."""
from pathlib import Path
import hashlib,io,json,uuid,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
import svg_linear_gradient_ir_v1 as ir
R=Path('/backup/shaoshitong/img2code_20261029');JS=Path(__file__).with_suffix('.js');BASE_JS=JS.with_name('native_image_edit_probe_v2.js')
sha=lambda b:hashlib.sha256(b).hexdigest()
def pixels(b):
 with Image.open(io.BytesIO(b))as im:return np.asarray(im.convert('RGBA')).copy()
def save(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b)
 return dict(file=str(p),sha256=sha(b),bytes=len(b))
def raw(x):return(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def audit(xml,dom,*,data_root=R,work=None):
 from native_worker import native
 from native_svg_screen_offset_v1 import observe,transform
 from playwright.sync_api import sync_playwright
 ir.require(Path(data_root).resolve()==R,'gradient_probe_registered_root_required');frame=observe(xml);canonical=transform(xml,frame['offsets'],1);source=ir.verify_dom_candidate(dom,canonical);expected=source['gradients']
 strokes=(dom.get('source_text_stroke_ir')or{}).get('strokes',[]);alphas=(dom.get('source_single_paint_alpha_ir')or{}).get('paints',[])
 if not expected and not strokes and not alphas:return dict(ok=True,policy=ir.POLICY,candidate_code_sha256=sha(xml.encode()),source_code_sha256=source['source_code_sha256'],source_gradient_instances=0,not_applicable=True,reason='fresh_original_source_and_native_inventory_both_have_zero_gradient_paint',gradient_editing_positive_claimed=False,new_raster_assets=0,model_calls=0,canonical_mutations=0)
 work=Path(work or R/'clean/native_gradient_edit_probe_v1'/uuid.uuid4().hex).resolve();ir.require(work.is_relative_to(R/'clean'),'gradient_proof_must_be_clean');work.mkdir(parents=True,exist_ok=False)
 model=next(E.fromstring(xml).iter('mxGraphModel'));width=int(model.get('pageWidth'))+64;height=int(model.get('pageHeight'))+64;ir.require(width<=8192 and height<=8192 and width*height<=64_000_000,'gradient_actual_probe_resource_bound')
 viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';runtime=json.loads((R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_bytes());ir.require(sha(viewer.read_bytes())==runtime['viewer_bundle_sha256'],'gradient_official_runtime_changed')
 pins={str(p):sha(p.read_bytes())for p in(Path(__file__),JS,BASE_JS,Path(ir.__file__),viewer)};report=dict(ok=False,policy=ir.POLICY,candidate_code_sha256=sha(xml.encode()),source_code_sha256=source['source_code_sha256'],pins=pins,source_gradient_instances=len(expected),source_stroked_text_objects=len(strokes),new_raster_assets=0,model_calls=0,canonical_mutations=0,interventions=[],source_text_stroke_interventions=[],RGBA_restore_tolerance=0)
 try:
  with sync_playwright()as pw:
   browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
   try:
    page=browser.new_page(viewport=dict(width=width,height=height),device_scale_factor=1);blocked=[];page.route('**/*',lambda r:(blocked.append(r.request.url),r.abort())[1]);page.set_content('<body style="margin:0;background:white"></body>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer))
    basejs=BASE_JS.read_text();script=JS.read_text();page.evaluate(basejs,dict(action='init',xml=xml,width=width,height=height,expected=[]));report['actual_official_source_gradient_painters']=page.evaluate(script,dict(action='inspect',expected=expected,expected_strokes=strokes,expected_alpha=alphas));baseline=page.screenshot(type='png');base=page.evaluate(basejs,dict(action='snapshot'));report['baseline_png']=save(work/'baseline.png',baseline);save(work/'baseline_actual_SVG.svg',base['svgOuterHTML'].encode());report['baseline_model_sha256']=sha(base['model'].encode())
    for e in expected:
     cid=e['native_cell_id'];folder=work/cid;mutation=page.evaluate(script,dict(action='edit',id=cid));edited=page.screenshot(type='png');a,b=pixels(baseline),pixels(edited);changed=int(np.count_nonzero(np.any(a!=b,axis=2)));ir.require(changed>0,'gradient_actual_color_edit_did_not_change_visible_pixels:'+cid)
     restored=page.evaluate(script,dict(action='restore',id=cid));after=page.screenshot(type='png');state=page.evaluate(basejs,dict(action='snapshot'));exact=bool(np.array_equal(a,pixels(after)));ir.require(exact and base['model']==state['model']and base['states']==state['states']and base['svgOuterHTML']==state['svgOuterHTML'],'gradient_actual_model_SVG_or_pixels_not_exactly_restored:'+cid)
     row=dict(native_cell_id=cid,actual_gradient_color_edit=mutation,actual_changed_pixels=changed,restore=restored,actual_RGBA_restored_exactly=exact,whole_model_and_all_states_restored_exactly=True,actual_native_SVG_restored_exactly=True,edited_png=save(folder/'edited.png',edited),restored_png=save(folder/'restored.png',after));report['interventions'].append(row)
    for e in strokes:
     cid=e['native_cell_id'];folder=work/('text_'+cid);mutation=page.evaluate(script,dict(action='edit_stroke',id=cid));edited=page.screenshot(type='png');a,b=pixels(baseline),pixels(edited);changed=int(np.count_nonzero(np.any(a!=b,axis=2)));ir.require(changed>0 and mutation['original_Unicode_unchanged'],'actual_source_text_stroke_edit_did_not_change_pixels_or_preserve_text')
     restored=page.evaluate(script,dict(action='restore_stroke',id=cid));after=page.screenshot(type='png');state=page.evaluate(basejs,dict(action='snapshot'));exact=bool(np.array_equal(a,pixels(after)));ir.require(exact and base['model']==state['model']and base['states']==state['states']and base['svgOuterHTML']==state['svgOuterHTML'],'actual_source_text_stroke_model_SVG_or_RGBA_not_exactly_restored')
     report['source_text_stroke_interventions'].append(dict(native_cell_id=cid,actual_paint_mutation=mutation,actual_changed_pixels=changed,restore=restored,actual_RGBA_restored_exactly=exact,actual_native_SVG_restored_exactly=True,edited_png=save(folder/'edited.png',edited),restored_png=save(folder/'restored.png',after)))
    report['single_paint_alpha_interventions']=[]
    for e in alphas:
     cid=e['native_cell_id'];folder=work/('alpha_'+cid);mutation=page.evaluate(script,dict(action='edit_alpha',id=cid));edited=page.screenshot(type='png');a,b=pixels(baseline),pixels(edited);changed=int(np.count_nonzero(np.any(a!=b,axis=2)));ir.require(changed>0,'single_paint_alpha_edit_has_no_actual_pixel_effect');restored=page.evaluate(script,dict(action='restore_alpha',id=cid));after=page.screenshot(type='png');state=page.evaluate(basejs,dict(action='snapshot'));exact=bool(np.array_equal(a,pixels(after)));ir.require(exact and base['model']==state['model']and base['states']==state['states']and base['svgOuterHTML']==state['svgOuterHTML'],'single_paint_alpha_model_SVG_or_RGBA_not_restored');report['single_paint_alpha_interventions'].append(dict(native_cell_id=cid,mutation=mutation,actual_changed_pixels=changed,restored=restored,actual_RGBA_restored_exactly=exact,actual_native_SVG_restored_exactly=True,edited_png=save(folder/'edited.png',edited),restored_png=save(folder/'restored.png',after)))
    page.evaluate(basejs,dict(action='dispose'));ir.require(not blocked,'gradient_probe_external_resource_blocked');report.update(ok=True,every_original_gradient_owner_actually_color_edited_and_restored=True,whole_actual_native_pixels_restored_exactly=True)
   finally:browser.close()
  ir.require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()),'gradient_probe_implementation_changed');report['implementation_unchanged']=True;save(work/'proof.json',raw(report));return report
 except Exception as e:
  report['typed_failure']=str(e);save(work/'proof.json',raw(report));raise ValueError('actual_gradient_paint_edit_failed:'+str(e)+':evidence='+str(work/'proof.json'))from e
