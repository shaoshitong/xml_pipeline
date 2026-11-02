"""Finite SOURCE-only DOM/SVG paint-context calibration, never acceptance.

No reference image chooses coordinates. All overlays use untouched SOURCE
Unicode/computed CSS and independently observed alphabetic baseline/lineboxes.
"""
from pathlib import Path
import hashlib,io,json,mimetypes,sqlite3,sys,urllib.parse,uuid
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import html_source_whitespace_capture_v8 as cap
from html_css_baseline_probe_v1 import observe
from html_source_clip_v8 import ink_metrics
ID='0bc37fc196e3f7ea12094ff9fe36f687bf2ff2c17308c27c7435ba5677ed4d20'
B=W/'html_source_frontend_v8_development'/ID/'5c373c4cb5104374be4d4adcfa481ad1/compiler'
VARIANTS=('line_html','line_foreignObject','line_svg','paragraph_html','paragraph_foreignObject')
MUTATIONS=('removed_character','wrong_font','wrong_color','wrong_spacing','true_displacement')
sha=lambda b:hashlib.sha256(b).hexdigest()
def asset(p):return{'file':str(p),'sha256':sha(p.read_bytes())}
def physical(cdp,node_expression):
 result=cdp.send('Runtime.evaluate',{'expression':node_expression,'returnByValue':False})['result'];oid=result['objectId']
 try:
  node=cdp.send('DOM.requestNode',{'objectId':oid})['nodeId']
  if not node:raise ValueError('actual_text_nodeId_zero')
  return{'basis':'actual_text_node','node':cdp.send('DOM.describeNode',{'nodeId':node})['node'],'fonts':cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']}
 finally:cdp.send('Runtime.releaseObject',{'objectId':oid})
def main():
 out=W/'html_source_paint_context_calibration_v1'/uuid.uuid4().hex;out.mkdir(parents=True)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as d:raw=d.execute('select input_record,input_manifest from jobs where id=?',(ID,)).fetchone()
 source,manifest=map(json.loads,raw);code=(R/manifest['source_code']).read_bytes();assert sha(code)==source['code_sha256'];assets=(R/manifest['asset_root']).resolve();size=Image.open(B/'source/source.native.png').size;blocked=[];rows=[]
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path=cap.CHROME,args=['--disable-dev-shm-usage']);context=browser.new_context(viewport=dict(zip(('width','height'),size)),java_script_enabled=False,service_workers='block')
  def route(req):
   u=urllib.parse.urlparse(req.request.url);name=urllib.parse.unquote(u.path.lstrip('/'))
   if u.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
   if name=='index.html':req.fulfill(body=code,content_type='text/html');return
   target=(assets/name).resolve();assert target.is_relative_to(assets)and target.is_file();req.fulfill(body=target.read_bytes(),content_type=mimetypes.guess_type(str(target))[0]or'application/octet-stream')
  context.route('**/*',route);page=context.new_page();page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready');normal=cap.screenshot(page);assert normal==(B/'source/source.native.png').read_bytes()
  dom=page.evaluate(cap.source_js());dom=page.evaluate(cap.SOURCE_GLYPHS,dom)['dom'];assert cap.screenshot(page)==normal
  obj=next(o for o in dom['objects']if str(o['id']+1)=='98');dom['_baseline_probe_cells']=['98'];baseline=observe(page,lambda:cap.screenshot(page),dom);assert baseline['ok'];original=next(row for row in baseline['rows']if row['measurable']);last=next(g for g in reversed(original['before']['chars'])if g['width']and g['height']);source_baseline=original['baseline']['y']+obj['actualSourceGlyphs'][0]['y']-last['y']
  js=(W/'scripts/html_source_paint_context_calibration_v1.js').read_text();metadata=page.evaluate(js,{'operation':'initialize','object':obj,'baseline':source_baseline});assert cap.screenshot(page)==normal
  cdp=context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');cdp.send('DOM.getDocument',{'depth':-1});metadata['physicalOriginalNode']=physical(cdp,'window.__sourcePaintContextCalibrationV1.node')
  (out/'source.png').write_bytes(normal);(out/'source_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2));(out/'source_baseline_proof.json').write_text(json.dumps(baseline,ensure_ascii=False,indent=2))
  # This finite plan is fixed before any score. No offsets, renderer settings,
  # fonts or acceptance threshold are chosen from resulting PNGs.
  plans=[(v,None)for v in VARIANTS if v.startswith('paragraph_')]+[('paragraph_html',m)for m in MUTATIONS]
  if sys.argv[1:]==['color_only']:plans=[('paragraph_html','wrong_color')]
  for index,(variant,mutation)in enumerate(plans):
   assert cap.screenshot(page)==normal,'source_not_restored_before_variant'
   hide=page.evaluate(js,{'operation':'hide','variant':variant});assert hide['allOriginalRangesUnchanged']and hide['allOriginalCssUnchanged'];hidden=cap.screenshot(page)
   obs=page.evaluate(js,{'operation':'overlay','variant':variant,'mutation':mutation});assert obs['originalSourceRangesUnchanged']and obs['originalSourceCssUnchanged'];cdp.send('DOM.getDocument',{'depth':-1});obs['physicalOverlayNode']=physical(cdp,'window.__sourcePaintContextCalibrationV1.overlayTextNode');image=cap.screenshot(page)
   path=out/(str(index).zfill(2)+'_'+variant+('_'+mutation if mutation else''));path.mkdir();(path/'overlay.png').write_bytes(image);(path/'hidden.png').write_bytes(hidden);(path/'observation.json').write_text(json.dumps(obs,ensure_ascii=False,indent=2));metric=ink_metrics(normal,hidden,image,hidden,(0,0));row={'variant':variant,'mutation':mutation,'ink':metric,'maximumRangeDifference':obs['maximumAbsoluteRangeDifference'],'overlay':asset(path/'overlay.png'),'hidden':asset(path/'hidden.png'),'observation':asset(path/'observation.json')};rows.append(row)
   page.evaluate(js,{'operation':'clear'});assert cap.screenshot(page)==normal,'restored_source_png_changed'
   print(json.dumps({'variant':variant,'mutation':mutation,'ink':metric,'range':obs['maximumAbsoluteRangeDifference']}),flush=True)
  cdp.detach();context.close();browser.close()
 assert not blocked
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as d:assert raw==d.execute('select input_record,input_manifest from jobs where id=?',(ID,)).fetchone()
 result={'id':ID,'cell':'98','source_code_sha256':source['code_sha256'],'source_image_sha256':source['image_sha256'],'source_png':asset(out/'source.png'),'source_metadata':asset(out/'source_metadata.json'),'source_baseline':asset(out/'source_baseline_proof.json'),'frozen_plan':{'variants':VARIANTS,'semantic_negatives':MUTATIONS,'no_coordinate_or_font_search':True},'all_source_pixels_restored_after_every_variant':True,'canonical_source_unchanged':True,'rows':rows,'new_heldout':0,'models':0,'qualification_or_gate_changed':False}
 (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({'report':asset(out/'report.json'),'rows':len(rows)}),flush=True)
if __name__=='__main__':main()
