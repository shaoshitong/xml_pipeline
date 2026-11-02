"""Actual upstream native image-owner geometry and bitmap intervention proof.

One original asset unit is moved (+17,+11), then both full model and bitmap are
restored exactly. This proves per-image editing; full scene/font/reference
fidelity remains the caller's separate mandatory validation.
"""
from __future__ import annotations
import hashlib,io,json,math,uuid,xml.etree.ElementTree as ET
from pathlib import Path
import svg_raster_panel_image_ir_v1 as ir
R=Path('/backup/shaoshitong/img2code_20261029')
JS=Path(__file__).with_suffix('.js')
PROFILE='actual_upstream_source_asset_image_owner_and_bitmap_intervention_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def _pixels(blob):
 from PIL import Image
 with Image.open(io.BytesIO(blob)) as im:
  im=im.convert('RGBA');return im.size,im.tobytes()
def _changed(a,b):
 from PIL import Image,ImageChops
 with Image.open(io.BytesIO(a)) as x,Image.open(io.BytesIO(b)) as y:
  x=x.convert('RGB');y=y.convert('RGB');ir.require(x.size==y.size,'native_image_probe_canvas_changed');z=ImageChops.difference(x,y);box=z.getbbox();n=sum(p!=(0,0,0) for p in z.getdata()) if box else 0;return {'changed_pixels':n,'difference_bbox':list(box) if box else None}
def audit(xml,dom,*,data_root=R,work=None):
 from native_worker import native
 from playwright.sync_api import sync_playwright
 root=Path(data_root).resolve();ir.require(root==R.resolve(),'native_image_probe_registered_root_required');proof=ir.verify_dom_candidate(dom,xml);expected=proof['images'];ir.require(bool(expected),'native_image_probe_requires_source_asset_owners')
 parsed=ET.fromstring(xml);model=next(parsed.iter('mxGraphModel'));width=float(model.get('pageWidth','0'));height=float(model.get('pageHeight','0'));width=max(width,max(x['paint_rect']['x']+x['paint_rect']['w'] for x in expected))+64;height=max(height,max(x['paint_rect']['y']+x['paint_rect']['h'] for x in expected))+64;width,height=math.ceil(width),math.ceil(height);ir.require(0<width<=8192 and 0<height<=8192 and width*height<=64_000_000,'native_image_probe_resource_bound')
 viewer=native.renderer_path(root).parent/'assets/viewer-static.min.js';manifest=json.loads((root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_bytes());ir.require(sha(viewer.read_bytes())==manifest['viewer_bundle_sha256'],'native_image_probe_official_runtime_hash_changed');pins={str(p):sha(p.read_bytes()) for p in (Path(__file__),JS,Path(ir.__file__),viewer)};events=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1);blocked=[];page.route('**/*',lambda route:(blocked.append(route.request.url),route.abort())[1]);page.set_content('<html><body style="margin:0;background:white"></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer));script=JS.read_text();observed=page.evaluate(script,{'action':'init','xml':xml,'width':width,'height':height,'expected':expected})
   for row,want in zip(observed['images'],expected):
    asset=ir.decode_asset_uri(row.pop('actual_image_uri'),native=True);ir.require(asset['source_asset_sha256']==want['source_asset_sha256'],'native_image_actual_painter_asset_hash_differs_from_source');row['actual_source_asset_sha256']=asset['source_asset_sha256'];row['actual_source_asset_bytes_verified']=True
   before=page.screenshot(type='png');before_size,before_pixels=_pixels(before);baseline_hash=sha(before_pixels)
   for want in expected:
    cid=want['native_cell_id'];moved=page.evaluate(script,{'action':'move','id':cid});after=page.screenshot(type='png');delta=_changed(before,after);ir.require(delta['changed_pixels']>0,'native_image_actual_bitmap_did_not_change:'+cid);restored=page.evaluate(script,{'action':'restore','id':cid});restore_png=page.screenshot(type='png');restore_size,restore_pixels=_pixels(restore_png);ir.require((restore_size,restore_pixels)==(before_size,before_pixels),'native_image_actual_bitmap_not_restored_exactly:'+cid);events.append({'native_cell_id':cid,'source_asset_sha256':want['source_asset_sha256'],'offset':{'x':17,'y':11},'actual_native_paint_changed':True,'actual_native_paint_restored_exactly':True,'before_pixels_sha256':baseline_hash,'after_pixels_sha256':sha(_pixels(after)[1]),'restored_pixels_sha256':sha(restore_pixels),'pixel_difference':delta,'movement':moved,'restoration':restored})
   page.evaluate(script,{'action':'dispose'})
  finally:browser.close()
 ir.require(all(sha(Path(k).read_bytes())==v for k,v in pins.items()),'native_image_probe_implementation_changed_during_audit')
 report={'ok':True,'profile':PROFILE,'candidate_code_sha256':sha(xml.encode() if isinstance(xml,str) else xml),'source_asset_mapping':proof,'native_runtime_version':observed['runtime_version'],'official_viewer_sha256':manifest['viewer_bundle_sha256'],'pins':pins,'source_image_owners':len(expected),'actual_painter_observations':observed['images'],'interventions':events,'all_source_asset_owners_individually_moved':len(events)==len(expected),'model_and_all_live_states_restored':True,'actual_bitmap_restored_exactly':True,'blocked_network_requests':len(blocked),'viewport':[width,height],'interior_editability':'source_asset_unit_only','full_scene_reference_fidelity_assessed':False,'model_calls':0}
 if work is not None:
  work=Path(work).resolve();ir.require(work.is_relative_to(root/'clean'),'native_image_probe_evidence_must_remain_clean');work.mkdir(parents=True,exist_ok=True);out=work/'image_edit_probe.json';blob=(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode();ir.require(not out.exists() or out.read_bytes()==blob,'native_image_probe_immutable_report_changed');out.write_bytes(blob);report['report_file']=str(out)
 return report
if __name__=='__main__':
 import base64
 from PIL import Image
 b=io.BytesIO();Image.new('RGB',(4,2),'#e05040').save(b,format='PNG');png='data:image/png;base64,'+base64.b64encode(b.getvalue()).decode();svg='data:image/svg+xml;base64,'+base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 2"><rect width="4" height="2" fill="#386fd0"/></svg>').decode();objs=[];source='<svg xmlns="http://www.w3.org/2000/svg">';cells='<mxCell id="0"/><mxCell id="1" parent="0"/>'
 for i,uri in enumerate((png,svg)):
  x,y=20+150*i,20;sid='src'+str(i);cid='v'+str(i);a={'x':x,'y':y,'width':100,'height':100};objs.append({'type':'image','id':cid,'sourceId':sid,'href':uri,'matrix':[1,0,0,1,0,0],'style':{'opacity':1},'sceneImage':{'documentIndex':i,'originalInstance':True,'attrs':a,'preserveAspectRatio':'xMidYMid meet','matrix':[1,0,0,1,0,0],'viewportBBox':{'x':x,'y':y,'w':100,'h':100}}});source+='<image id="'+sid+'" href="'+uri+'"/>'
 dom={'objects':objs,'issues':[]};ir.apply_to_dom(dom,(source+'</svg>').encode());ir.require(dom['raster_panel_ir']['ok'],'native_image_probe_control_IR_failed')
 for o in objs:
  r=o['bbox'];uri=ir.decode_asset_uri(o['href'])['canonical_native_uri'];cells+='<mxCell id="'+o['id']+'" vertex="1" parent="1" style="shape=image;imageAspect=0;image='+uri+';"><mxGeometry x="'+ir.num(r['x'])+'" y="'+ir.num(r['y'])+'" width="'+ir.num(r['w'])+'" height="'+ir.num(r['h'])+'" as="geometry"/></mxCell>'
 xml='<mxfile><diagram><mxGraphModel pageWidth="400" pageHeight="180"><root>'+cells+'</root></mxGraphModel></diagram></mxfile>';result=audit(xml,dom,work=R/'clean/native_image_edit_probe_v1_controls'/uuid.uuid4().hex);print(json.dumps({'ok':result['ok'],'source_image_owners':result['source_image_owners'],'official_viewer_sha256':result['official_viewer_sha256'],'report_file':result.get('report_file')}))
