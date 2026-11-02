"""Actual native image editing with one unconditional full-paint protocol.

Initialization, every movement, and every restoration always use the same
upstream Graph.refresh/view.validate/two-frame paint. This is not a retry after
an incremental-paint failure. Restore model, all live edge/vertex states, paint
owner order, and actual full-canvas RGBA must be exact: no tolerance or SSIM.
Original v1 remains unchanged as historical incremental-paint failure evidence.
"""
from __future__ import annotations
import hashlib,io,json,math,uuid,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
import svg_raster_panel_image_ir_v1 as ir
R=Path('/backup/shaoshitong/img2code_20261029');JS=Path(__file__).with_suffix('.js')
PROFILE='actual_upstream_source_asset_image_owner_unconditional_full_paint_v2'
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(z):return (json.dumps(z,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def _save(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);ir.require(not p.exists() or p.read_bytes()==b,'native_image_v2_immutable_evidence_changed')
 if not p.exists():p.write_bytes(b)
 return {'file':str(p),'sha256':sha(b),'bytes':len(b)}
def _pixels(b):
 with Image.open(io.BytesIO(b)) as im:return np.asarray(im.convert('RGBA')).copy()
def _difference(a,b):
 x,y=_pixels(a),_pixels(b);ir.require(x.shape==y.shape,'native_image_v2_canvas_changed');d=np.abs(x.astype(np.int16)-y.astype(np.int16));mask=np.any(d!=0,axis=2);ys,xs=np.where(mask);return {'changed_pixels':int(np.count_nonzero(mask)),'maximum_channel_difference':int(d.max()),'difference_bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if mask.any() else None,'exact_RGBA_equal':not bool(mask.any())}
def _snapshot(page,script,path):
 z=page.evaluate(script,{'action':'snapshot'});files={'model':_save(path/'model.xml',z['model'].encode()),'all_live_states':_save(path/'all_live_states.json',raw(z['states'])),'actual_paint_DOM':_save(path/'paint.svg',z['svgOuterHTML'].encode()),'actual_DOM_membership_and_order':_save(path/'DOM.json',raw({'nodes':z['dom'],'paintOrder':z['paintOrder']}))};return z,files

def audit(xml,dom,*,data_root=R,work=None):
 from native_worker import native
 from playwright.sync_api import sync_playwright
 root=Path(data_root).resolve();ir.require(root==R.resolve(),'native_image_v2_registered_root_required');work=Path(work or root/'clean/native_image_edit_probe_v2'/uuid.uuid4().hex).resolve();ir.require(work.is_relative_to(root/'clean'),'native_image_v2_media_must_stay_clean');work.mkdir(parents=True,exist_ok=True);phase='independent_source_asset_mapping';report={'ok':False,'profile':PROFILE,'candidate_code_sha256':sha(xml.encode() if isinstance(xml,str) else xml),'model_calls':0,'normal_conversions':0,'canonical_mutations':0,'interventions':[],'full_scene_reference_fidelity_assessed':False,'interior_editability':'source_asset_unit_only','paint_protocol':'unconditional Graph.refresh(); view.validate(); document.fonts.ready; two RAF at initialization/move/restore; never retry','RGBA_restore_tolerance':0,'report_file':str(work/'image_edit_probe.json')};pins={};browser=None
 try:
  proof=ir.verify_dom_candidate(dom,xml);expected=proof['images'];ir.require(bool(expected),'native_image_v2_requires_original_source_asset_owners');report['source_asset_mapping']=proof
  model=next(ET.fromstring(xml).iter('mxGraphModel'));width=math.ceil(max(float(model.get('pageWidth','0')),max(x['paint_rect']['x']+x['paint_rect']['w'] for x in expected))+64);height=math.ceil(max(float(model.get('pageHeight','0')),max(x['paint_rect']['y']+x['paint_rect']['h'] for x in expected))+64);ir.require(0<width<=8192 and 0<height<=8192 and width*height<=64_000_000,'native_image_v2_resource_bound');report['viewport']=[width,height]
  viewer=native.renderer_path(root).parent/'assets/viewer-static.min.js';manifest=json.loads((root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_bytes());ir.require(sha(viewer.read_bytes())==manifest['viewer_bundle_sha256'],'native_image_v2_official_runtime_hash_changed');pins={str(p):sha(p.read_bytes()) for p in (Path(__file__),JS,Path(ir.__file__),viewer)};report['pins']=pins;report['official_viewer_sha256']=manifest['viewer_bundle_sha256'];_save(work/'probe_configuration.json',raw({k:report[k] for k in ('profile','candidate_code_sha256','pins','official_viewer_sha256','viewport','paint_protocol','RGBA_restore_tolerance','interior_editability')}));script=JS.read_text()
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
   try:
    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1);blocked=[];page.route('**/*',lambda r:(blocked.append(r.request.url),r.abort())[1]);page.set_content('<html><body style="margin:0;background:white"></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer));phase='initial_actual_full_paint';observed=page.evaluate(script,{'action':'init','xml':xml,'width':width,'height':height,'expected':expected})
    for row,wanted in zip(observed['images'],expected):
     asset=ir.decode_asset_uri(row.pop('actual_image_uri'),native=True);ir.require(asset['source_asset_sha256']==wanted['source_asset_sha256'],'native_image_v2_actual_painter_asset_hash_changed');row['actual_source_asset_sha256']=asset['source_asset_sha256'];row['actual_source_asset_bytes_verified']=True
    report['actual_painter_observations']=observed['images'];report['native_runtime_version']=observed['runtime_version'];baseline=page.screenshot(type='png');report['baseline_png']=_save(work/'baseline.png',baseline);base,basefiles=_snapshot(page,script,work/'baseline');report['baseline_frame']=basefiles;report['baseline_RGBA_sha256']=sha(_pixels(baseline).tobytes());report['blocked_network_requests']=len(blocked)
    for wanted in expected:
     cid=wanted['native_cell_id'];directory=work/cid;event={'native_cell_id':cid,'source_asset_sha256':wanted['source_asset_sha256'],'offset':{'x':17,'y':11},'before_png':_save(directory/'before.png',baseline),'before_frame':basefiles};report['interventions'].append(event)
     phase=cid+':move_actual_full_paint';event['movement']=page.evaluate(script,{'action':'move','id':cid});moved=page.screenshot(type='png');event['moved_png']=_save(directory/'moved.png',moved);_,event['moved_frame']=_snapshot(page,script,directory/'moved');event['movement_pixels']=_difference(baseline,moved);ir.require(event['movement_pixels']['changed_pixels']>0,'native_image_v2_actual_bitmap_did_not_change:'+cid);event['actual_native_paint_changed']=True
     phase=cid+':restore_actual_full_paint';event['restoration']=page.evaluate(script,{'action':'restore','id':cid});restored=page.screenshot(type='png');event['restored_png']=_save(directory/'restored.png',restored);after,event['restored_frame']=_snapshot(page,script,directory/'restored');event['restoration_pixels']=_difference(baseline,restored);event['model_exactly_restored']=base['model']==after['model'];event['all_live_states_including_edge_points_exactly_restored']=base['states']==after['states'];event['actual_paint_DOM_exactly_restored']=base['svgOuterHTML']==after['svgOuterHTML'];event['actual_paint_owner_sequence_exactly_restored']=[(n['owner'],n['tag']) for n in base['paintOrder']]==[(n['owner'],n['tag']) for n in after['paintOrder']];event['actual_native_paint_restored_exactly']=event['restoration_pixels']['exact_RGBA_equal'];_save(directory/'phase_evidence.json',raw(event));ir.require(event['model_exactly_restored'] and event['all_live_states_including_edge_points_exactly_restored'] and event['actual_paint_owner_sequence_exactly_restored'],'native_image_v2_actual_model_states_or_paint_order_not_restored:'+cid);ir.require(event['actual_native_paint_restored_exactly'],'native_image_v2_actual_RGBA_not_restored:'+cid)
    page.evaluate(script,{'action':'dispose'});report.update(ok=True,source_image_owners=len(expected),all_source_asset_owners_individually_moved=len(report['interventions'])==len(expected),model_and_all_live_states_restored=True,actual_bitmap_restored_exactly=True,all_actual_paint_owner_sequences_restored=True)
   except Exception:
    # Preserve the exact failed phase before closing Chromium. No second
    # mutation, refresh or screenshot-based retry is attempted.
    try:
     report['failed_phase_current_png']=_save(work/'failed_phase_current.png',page.screenshot(type='png'))
     _,report['failed_phase_current_frame']=_snapshot(page,script,work/'failed_phase_current_frame')
    except Exception as capture_error:report['failed_phase_capture_error']={'type':type(capture_error).__name__,'reason':str(capture_error)}
    raise
   finally:browser.close();browser=None
  ir.require(all(sha(Path(k).read_bytes())==v for k,v in pins.items()),'native_image_v2_implementation_changed');report['implementation_unchanged']=True;_save(work/'image_edit_probe.json',raw(report));return report
 except Exception as error:
  report.update(ok=False,typed_failure={'phase':phase,'error_type':type(error).__name__,'reason':str(error)},implementation_unchanged=all(sha(Path(k).read_bytes())==v for k,v in pins.items()));_save(work/'image_edit_probe.json',raw(report));raise ValueError('native_image_v2_typed_failure:'+str(error)+':evidence='+str(work/'image_edit_probe.json')) from error

if __name__=='__main__':
 import base64
 from PIL import Image
 b=io.BytesIO();Image.new('RGB',(4,2),'#e05040').save(b,format='PNG');png='data:image/png;base64,'+base64.b64encode(b.getvalue()).decode();svg='data:image/svg+xml;base64,'+base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 2"><rect width="4" height="2" fill="#386fd0"/></svg>').decode();objects=[];source='<svg xmlns="http://www.w3.org/2000/svg">';cells='<mxCell id="0"/><mxCell id="1" parent="0"/>'
 for i,uri in enumerate((png,svg)):
  x,y=20+150*i,20;sid='src'+str(i);cid='v'+str(i);objects.append({'id':cid,'type':'image','sourceId':sid,'href':uri,'matrix':[1,0,0,1,0,0],'style':{'opacity':1},'sceneImage':{'documentIndex':i,'originalInstance':True,'attrs':{'x':x,'y':y,'width':100,'height':100},'preserveAspectRatio':'xMidYMid meet','matrix':[1,0,0,1,0,0],'viewportBBox':{'x':x,'y':y,'w':100,'h':100}}});source+='<image id="'+sid+'" href="'+uri+'"/>'
 dom={'objects':objects,'issues':[]};ir.apply_to_dom(dom,(source+'</svg>').encode());ir.require(dom['raster_panel_ir']['ok'],'native_image_v2_control_IR_failed')
 for o in objects:
  r=o['bbox'];uri=ir.decode_asset_uri(o['href'])['canonical_native_uri'];cells+='<mxCell id="'+o['id']+'" vertex="1" parent="1" style="shape=image;imageAspect=0;image='+uri+';"><mxGeometry x="'+ir.num(r['x'])+'" y="'+ir.num(r['y'])+'" width="'+ir.num(r['w'])+'" height="'+ir.num(r['h'])+'" as="geometry"/></mxCell>'
 xml='<mxfile><diagram><mxGraphModel pageWidth="400" pageHeight="180"><root>'+cells+'</root></mxGraphModel></diagram></mxfile>';r=audit(xml,dom,work=R/'clean/native_image_edit_probe_v2_controls'/uuid.uuid4().hex);print(json.dumps({'ok':r['ok'],'source_image_owners':r['source_image_owners'],'all_restore_RGBA_exact':r['actual_bitmap_restored_exactly'],'report_file':r['report_file'],'pins':r['pins']}))
