"""Development-only actual paint-support evidence; never changes any QA gate.
Original SVG text elements are atomic paint units. Marker heads share the source
owner's original paint element. No tspan, geometry, content or membership edits.
"""
from __future__ import annotations
import argparse,datetime,hashlib,io,json,uuid,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
R=Path('/backup/shaoshitong/img2code_20261029');JS=Path(__file__).with_suffix('.js')
POLICY='read_only_actual_source_native_alpha_support_commutation_evidence_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def pixels(blob):
 with Image.open(io.BytesIO(blob)) as im:return np.asarray(im.convert('RGBA')).copy()
def white_pixels(blob):
 with Image.open(io.BytesIO(blob)) as im:
  rgba=im.convert('RGBA');white=Image.new('RGBA',rgba.size,'white');white.alpha_composite(rgba);return np.asarray(white).copy()
def require(ok,why):
 if not ok:raise ValueError(why)
def _save(path,blob):
 path.parent.mkdir(parents=True,exist_ok=True);require(not path.exists() or path.read_bytes()==blob,'immutable_diagnostic_artifact_changed');path.write_bytes(blob);return {'file':str(path),'sha256':sha(blob),'bytes':len(blob)}
def _json(path,z):return _save(path,(json.dumps(z,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode())
def compare_masks(a,b):
 pa,pb=pixels(a),pixels(b);require(pa.shape==pb.shape,'paint_mask_canvas_changed');aa,ab=pa[:,:,3]>0,pb[:,:,3]>0;both=aa&ab;overlap=int(np.count_nonzero(both));diff=np.max(np.abs(pa[:,:,:3].astype(np.int16)-pb[:,:,:3].astype(np.int16)),axis=2);maxdiff=int(diff[both].max()) if overlap else 0;unequal=int(np.count_nonzero(both&(diff!=0)));ys,xs=np.where(both)
 return {'left_alpha_support_pixels':int(np.count_nonzero(aa)),'right_alpha_support_pixels':int(np.count_nonzero(ab)),'overlap_alpha_support_pixels':overlap,'overlap_bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if overlap else None,'max_unpremultiplied_RGB_difference_on_overlap':maxdiff,'overlap_pixels_with_different_RGB':unequal,'sampled_source_over_order_commutes':overlap==0 or maxdiff==0,'basis':'actual isolated browser RGBA, normal source-over: alphaA*alphaB*(CA-CB)=0; no SSIM or reference score used'}
def capture_masks(page,script,units,work,baseline):
 transparent=page.evaluate(script,{'action':'transparent'});full=page.screenshot(type='png',omit_background=True);require(np.array_equal(white_pixels(full),pixels(baseline)),'transparent_infrastructure_backdrop_changed_full_white_composite');fullmeta=_save(work/'full_transparent.png',full);masks={};events=[]
 for u in units:
  event=page.evaluate(script,{'action':'isolate','key':u['key']});blob=page.screenshot(type='png',omit_background=True);masks[u['key']]=blob;event['mask']=_save(work/(u['key'].replace(':','_')+'.png'),blob);event['alpha_support_pixels']=int(np.count_nonzero(pixels(blob)[:,:,3]));events.append(event)
 restored=page.evaluate(script,{'action':'restore'});after=page.screenshot(type='png');_save(work/'restored.png',after);restored['actual_full_bitmap_exactly_restored']=bool(np.array_equal(pixels(after),pixels(baseline)));return masks,{'transparent_infrastructure_only':transparent,'whole_white_composite_exact':True,'full_transparent':fullmeta,'isolations':events,'restore':restored}
def diagnose(record_path,quality_path,cairo_fonts_path,*,work=None):
 import compiler_svg_raster_panel_frontend_v1 as frontend
 from native_worker import native
 from playwright.sync_api import sync_playwright
 record_path=Path(record_path);record=json.loads(record_path.read_bytes());quality_path=Path(quality_path);q=json.loads(quality_path.read_bytes());order=q['checks']['source']['evidence']['checks']['actual_source_overlap_paint_order'];pairs=order['failures'];require(pairs,'no_existing_overlap_failures');xmlpath=R/record['code_file'];codepath=R/record['original_source_code'];imagepath=R/record['image_file'];xml=xmlpath.read_text();code=codepath.read_bytes();require(sha(xml.encode())==record['code_sha256'] and sha(code)==record['source_code_sha256'] and sha(imagepath.read_bytes())==record['image_sha256'],'latest_development_asset_identity_changed');size=[int(record['source_record']['width']),int(record['source_record']['height'])];work=Path(work or R/'clean/svg_source_native_paint_overlap_probe_v1'/uuid.uuid4().hex);require(work.resolve().is_relative_to(R/'clean'),'paint_diagnostic_media_must_remain_clean');work.mkdir(parents=True,exist_ok=False);script=JS.read_text();domain_data={};source_masks={};units=[];mapped_pairs=[]
 def observer(page,context,dom,positions,faces,anchors):
  nonlocal source_masks,units,mapped_pairs
  init=page.evaluate(script,{'action':'source_init','dom':dom,'pairs':pairs});units=init['units'];mapped_pairs=init['pairs'];baseline=frontend._screenshot(page);_save(work/'source/baseline.png',baseline);source_masks,proof=capture_masks(page,script,units,work/'source',baseline);domain_data['source']={'initialization':init,**proof,'baseline_pixel_sha256':sha(pixels(baseline).tobytes())};_json(work/'source/isolation_evidence.json',domain_data['source']);require(proof['restore']['actual_full_bitmap_exactly_restored'],'source_isolation_actual_bitmap_not_restored');return {'paint_overlap_evidence_file':str(work/'source/isolation_evidence.json')}
 # Replay the latest actual Cairo face observations; never regenerate a source
 # figure, rebuild a candidate, execute author code, or touch original ledgers.
 scratch=R/'conversion'/frontend.VERSION/'paint_overlap_diag'/uuid.uuid4().hex;scratch.mkdir(parents=True,exist_ok=False);observation=json.loads(Path(cairo_fonts_path).read_text());capture=frontend._capture(code,size,scratch,observation,diagnostic_observer=observer);sourcepng=capture['png'];expected=record['compiler_svg_raster_panel_frontend_v1']['sourceproof']['source_browser_png_sha256'];domain_data['source']['latest_saved_browser_source_png_sha256']=expected;domain_data['source']['fresh_browser_png_sha256']=sha(sourcepng);domain_data['source']['fresh_source_matches_latest_development_browser_pixels']=sha(sourcepng)==expected
 require(domain_data['source']['fresh_source_matches_latest_development_browser_pixels'],'fresh_source_domain_differs_from_latest_development_bitmap')
 viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';manifest=json.loads((R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_text());require(sha(viewer.read_bytes())==manifest['viewer_bundle_sha256'],'official_native_runtime_changed');native_masks={}
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=frontend.CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   page=browser.new_page(viewport={'width':size[0],'height':size[1]},device_scale_factor=1);page.route('**/*',lambda route:route.abort());page.set_content('<html><body style="margin:0;background:white"></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer));init=page.evaluate(script,{'action':'native_init','xml':xml,'size':size,'units':units});baseline=page.screenshot(type='png');_save(work/'native/baseline.png',baseline);same=bool(np.array_equal(pixels(baseline),pixels(imagepath.read_bytes())));domain_data['native']={'initialization':init,'fresh_whole_bitmap_matches_latest_candidate_exact':same,'baseline_pixel_sha256':sha(pixels(baseline).tobytes())};_json(work/'native/replay_evidence.json',domain_data['native']);require(same,'fresh_native_domain_differs_from_latest_candidate_bitmap');native_masks,proof=capture_masks(page,script,units,work/'native',baseline);domain_data['native'].update(proof);_json(work/'native/isolation_evidence.json',domain_data['native'])
  finally:browser.close()
 decisions=[];cache={}
 for pair in mapped_pairs:
  key=(pair['left'],pair['right'])
  if key not in cache:
   sr=compare_masks(source_masks[key[0]],source_masks[key[1]]);nr=compare_masks(native_masks[key[0]],native_masks[key[1]]);commute=sr['sampled_source_over_order_commutes'] and nr['sampled_source_over_order_commutes'];cache[key]={'source':sr,'native':nr,'both_actual_domains_order_commute_at_captured_pixel_resolution':commute,'decision':'order_commutation_evidence_only_requires_root_policy_review' if commute else 'actual_distinct_color_paint_overlap_retains_order_failure'}
  decisions.append({**pair,**cache[key]})
 result={'schema':POLICY,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'id':record['id'],'candidate_code_sha256':record['code_sha256'],'candidate_image_sha256':record['image_sha256'],'source_code_sha256':record['source_code_sha256'],'quality_report':{'file':str(quality_path),'sha256':sha(quality_path.read_bytes())},'runtime_sha256':manifest['viewer_bundle_sha256'],'producer_pins':{str(p):sha(p.read_bytes()) for p in (Path(__file__),JS,Path(frontend.__file__),viewer)},'source_and_native':domain_data,'original_failures':len(pairs),'unique_atomic_unit_pairs':len(cache),'unit_groups':units,'pair_evidence':decisions,'all_failed_pairs_have_both_domain_commutation_evidence':all(x['both_actual_domains_order_commute_at_captured_pixel_resolution'] for x in decisions),'accepted':False,'qa_gates_changed':False,'canonical_mutations':0,'normal_conversions':0,'model_calls':0,'limitation':'Bounded development diagnostics at exact browser pixel resolution; no candidate qualification or frozen guard relaxation.'};_json(work/'report.json',result);return result,work
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--record',required=True);p.add_argument('--quality',required=True);p.add_argument('--cairo-fonts',required=True);p.add_argument('--work');a=p.parse_args()
 try:
  result,work=diagnose(a.record,a.quality,a.cairo_fonts,work=a.work);print(json.dumps({'report':str(work/'report.json'),'original_failures':result['original_failures'],'unique_atomic_pairs':result['unique_atomic_unit_pairs'],'all_commute_evidence':result['all_failed_pairs_have_both_domain_commutation_evidence'],'pair_summary':[{'before':x['source_before'],'after':x['source_after'],'source_overlap':x['source']['overlap_alpha_support_pixels'],'native_overlap':x['native']['overlap_alpha_support_pixels'],'source_maxRGB':x['source']['max_unpremultiplied_RGB_difference_on_overlap'],'native_maxRGB':x['native']['max_unpremultiplied_RGB_difference_on_overlap'],'decision':x['decision']} for x in result['pair_evidence']]}))
 except Exception as e:
  print(json.dumps({'accepted':False,'diagnostic_failed':True,'error_type':type(e).__name__,'reason':str(e),'work':a.work}));raise
