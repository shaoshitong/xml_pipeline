"""Additive, bounded actual native image move/restore development diagnosis.
No QA gate, original probe, source candidate, or canonical record is modified.
"""
import argparse,datetime,hashlib,io,json,math,uuid,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
R=Path('/backup/shaoshitong/img2code_20261029');JS=Path(__file__).with_suffix('.js')
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(z):return (json.dumps(z,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def pixels(b):
 with Image.open(io.BytesIO(b)) as im:return np.asarray(im.convert('RGBA')).copy()
def save(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b
 else:p.write_bytes(b)
 return {'file':str(p),'sha256':sha(b),'bytes':len(b)}
def diff(a,b,work):
 x,y=pixels(a),pixels(b);assert x.shape==y.shape;d=np.abs(x.astype(np.int16)-y.astype(np.int16));mask=np.any(d!=0,axis=2);ys,xs=np.where(mask);result={'same_pixels':not bool(mask.any()),'changed_pixels':int(mask.sum()),'max_channel_difference':int(d.max()),'bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if mask.any() else None,'nonzero_channel_histogram':{str(v):int(n) for v,n in zip(*np.unique(d[d>0],return_counts=True))}};out=np.zeros_like(x);out[:,:,:3]=np.minimum(d[:,:,:3]*16,255).astype(np.uint8);out[:,:,3]=255;buf=io.BytesIO();Image.fromarray(out,'RGBA').save(buf,format='PNG');result['difference_png']=save(work/'difference_amplified_x16.png',buf.getvalue());return result

def summarize(before,after,work):
 changes={};changes['model_exact']=before['model']==after['model'];changes['all_states_including_edge_points_exact']=before['states']==after['states'];changes['svg_outerHTML_exact']=before['svgOuterHTML']==after['svgOuterHTML'];changes['paint_order_exact']=before['paintOrder']==after['paintOrder'];changes['owner_paint_sequence_exact']=[(n['owner'],n['tag']) for n in before['paintOrder']]==[(n['owner'],n['tag']) for n in after['paintOrder']];changes['state_differences']=[{'cell':k,'before':v,'after':after['states'].get(k)} for k,v in before['states'].items() if v!=after['states'].get(k)];a={n['uid']:n for n in before['dom']};b={n['uid']:n for n in after['dom']};changes['new_DOM_node_count']=len(set(b)-set(a));changes['removed_DOM_node_count']=len(set(a)-set(b));changes['same_node_attribute_changes']=[{'uid':k,'owner':a[k]['owner'],'tag':a[k]['tag'],'before':a[k]['attrs'],'after':b[k]['attrs']} for k in set(a)&set(b) if a[k]['attrs']!=b[k]['attrs']];changes['same_node_sibling_changes']=[{'uid':k,'owner':a[k]['owner'],'tag':a[k]['tag'],'before_parent':a[k]['parentUid'],'after_parent':b[k]['parentUid'],'before_next':a[k]['nextUid'],'after_next':b[k]['nextUid']} for k in set(a)&set(b) if (a[k]['parentUid'],a[k]['nextUid'])!=(b[k]['parentUid'],b[k]['nextUid'])];save(work/'before_snapshot.json',raw(before));save(work/'restored_snapshot.json',raw(after));return changes

def run(record_path,dom_path,*,mode='incremental',work):
 from native_worker import native
 from playwright.sync_api import sync_playwright
 import svg_raster_panel_image_ir_v1 as ir
 import native_image_edit_probe_v1 as old
 record=json.loads(Path(record_path).read_bytes());dombytes=Path(dom_path).read_bytes();dom=json.loads(dombytes);xml=(R/record['code_file']).read_text();assert sha(xml.encode())==record['code_sha256'];assert sha((R/record['image_file']).read_bytes())==record['image_sha256'];assert sha(dombytes)==record['compiler_svg_raster_panel_frontend_v1']['sourceproof']['fresh_source_dom_sha256'];mapping=ir.verify_dom_candidate(dom,xml);assert mapping['images'];model=next(ET.fromstring(xml).iter('mxGraphModel'));width=math.ceil(max(float(model.get('pageWidth','0')),max(i['paint_rect']['x']+i['paint_rect']['w'] for i in mapping['images']))+64);height=math.ceil(max(float(model.get('pageHeight','0')),max(i['paint_rect']['y']+i['paint_rect']['h'] for i in mapping['images']))+64);work=Path(work);assert work.resolve().is_relative_to(R/'clean');work.mkdir(parents=True,exist_ok=False);viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';pins={str(p):sha(p.read_bytes()) for p in (Path(__file__),JS,Path(ir.__file__),Path(old.__file__),old.JS,viewer)};report={'schema':'actual_native_image_restore_diagnostic_v1','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':mode,'candidate_code_sha256':record['code_sha256'],'candidate_image_sha256':record['image_sha256'],'source_DOM_metadata_sha256':sha(dombytes),'mapping':mapping,'pins':pins,'accepted':False,'qa_changed':False,'canonical_mutations':0,'normal_conversions':0,'events':[]};script=JS.read_text();full=mode=='fixed_full_refresh'
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
   try:
    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1);page.route('**/*',lambda r:r.abort());page.set_content('<html><body style="margin:0;background:white"></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer));init=page.evaluate(script,{'action':'init','xml':xml,'width':width,'height':height,'expected':mapping['images'],'fullRefresh':full})
    for row,expected in zip(init['images'],mapping['images']):assert ir.decode_asset_uri(row.pop('actual_image_uri'),native=True)['source_asset_sha256']==expected['source_asset_sha256']
    report['initialization']=init;baseline=page.screenshot(type='png');report['baseline_png']=save(work/'baseline.png',baseline);base=page.evaluate(script,{'action':'snapshot'});save(work/'baseline_snapshot.json',raw(base));candidate=(R/record['image_file']).read_bytes();bp=pixels(baseline);cp=pixels(candidate);report['baseline_crop_matches_latest_candidate_bitmap_exact']=bool(np.array_equal(bp[:cp.shape[0],:cp.shape[1]],cp));report['baseline_pixel_sha256']=sha(bp.tobytes())
    for i in mapping['images']:
     cid=i['native_cell_id'];folder=work/cid;folder.mkdir();event={'owner':cid,'source_asset_sha256':i['source_asset_sha256']};moved=page.evaluate(script,{'action':'move','id':cid,'fullRefresh':full});move_png=page.screenshot(type='png');event['moved_png']=save(folder/'moved.png',move_png);event['moved']=moved;save(folder/'moved_snapshot.json',raw(page.evaluate(script,{'action':'snapshot'})));restored=page.evaluate(script,{'action':'restore','id':cid,'fullRefresh':full});restore_png=page.screenshot(type='png');event['restored_png']=save(folder/'restored.png',restore_png);after=page.evaluate(script,{'action':'snapshot'});event['restore']=restored;event['pixels']=diff(baseline,restore_png,folder);event['model_state_DOM']=summarize(base,after,folder);report['events'].append(event);save(folder/'event.json',raw(event))
     if not event['pixels']['same_pixels']:
      report['typed_result']='actual_bitmap_not_restored_exactly';report['first_failed_owner']=cid;break
    else:report['typed_result']='all_owners_model_and_bitmap_restored_exactly'
   finally:browser.close()
 except Exception as error:report['typed_result']='diagnostic_exception';report['exception']={'type':type(error).__name__,'reason':str(error)};raise
 finally:
  report['implementation_unchanged']=all(sha(Path(k).read_bytes())==v for k,v in pins.items());save(work/'report.json',raw(report))
 return report,work
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--record',required=True);p.add_argument('--dom',required=True);p.add_argument('--work',required=True);p.add_argument('--mode',choices=['incremental','fixed_full_refresh'],default='incremental');a=p.parse_args();r,w=run(a.record,a.dom,mode=a.mode,work=a.work);print(json.dumps({'report':str(w/'report.json'),'mode':r['mode'],'result':r['typed_result'],'baseline_crop_matches_latest_candidate_bitmap_exact':r.get('baseline_crop_matches_latest_candidate_bitmap_exact'),'events':[{'owner':e['owner'],'pixels':e['pixels'],'model_exact':e['model_state_DOM']['model_exact'],'states_exact':e['model_state_DOM']['all_states_including_edge_points_exact'],'svg_exact':e['model_state_DOM']['svg_outerHTML_exact'],'owner_order_exact':e['model_state_DOM']['owner_paint_sequence_exact'],'new_nodes':e['model_state_DOM']['new_DOM_node_count'],'removed_nodes':e['model_state_DOM']['removed_DOM_node_count'],'state_diffs':len(e['model_state_DOM']['state_differences']),'attribute_changes':len(e['model_state_DOM']['same_node_attribute_changes']),'sibling_changes':len(e['model_state_DOM']['same_node_sibling_changes'])} for e in r['events']]}))
