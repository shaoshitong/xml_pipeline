import json,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from portable_native_fonts_v2 import ready_page,capture,embed
from fontmix_validation import verify_graph,verify_fonts,zero_lineboxes
B=W/'font_portability_probe_v2';T=W/'font_portability_validated_v2';T.mkdir(exist_ok=True);results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser)
 for old in sorted(B.iterdir()):
  if not old.is_dir() or not (old/'before.png').exists():continue
  target=T/old.name;target.mkdir(exist_ok=True);xml=(old/'before.drawio').read_text();png=(old/'before.png').read_bytes();w,h=Image.open(old/'before.png').size;result={'id':old.name,'attempts':[],'ok':False}
  try:
   obs=capture(page,xml);new,fonts,details=embed(xml,obs,target/'fonts',page);(target/'observations.json').write_text(json.dumps(obs,indent=2));(target/'details.json').write_text(json.dumps(details,indent=2));assert not details['issues'],str(details['issues']);result['mixed_cells']=details['mixed_text_cells']
   for variant,candidate in [('inherited',new),('zero',zero_lineboxes(new,details))]:
    v={'variant':variant}
    try:
     verify_graph(xml,candidate,details);render=native.native_job(candidate,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];(target/(variant+'.png')).write_bytes(render['png']);(target/(variant+'.drawio')).write_text(candidate);(target/(variant+'_render.json')).write_text(json.dumps(render['native_render'],indent=2));verify_fonts(obs,render['native_render'],details);v['fonts_ok']=True;v['pixels_identical']=render['png']==png;assert v['pixels_identical'],'Native pixels changed';v['ok']=True;result['ok']=True;result['selected']=variant
    except Exception as e:v.update(ok=False,error=repr(e))
    result['attempts'].append(v)
    if result['ok']:break
   if result['ok']:
    # Independent semantic and geometry negatives must fail, even if a caller restores labels in a canonical comparison.
    c=E.fromstring(candidate);cell=next(c for c in c.iter('mxCell') if '<span' in c.get('value',''));cell.set('value',cell.get('value').replace('</span>','X</span>',1))
    try:verify_graph(xml,E.tostring(c,encoding='unicode'),details);raise RuntimeError('Text corruption passed')
    except AssertionError:result['negative_text_rejected']=True
    c=E.fromstring(candidate);geometry=next(c.iter('mxGeometry'));geometry.set('x',str(float(geometry.get('x','0'))+1))
    try:verify_graph(xml,E.tostring(c,encoding='unicode'),details);raise RuntimeError('Geometry corruption passed')
    except AssertionError:result['negative_geometry_rejected']=True
    fake=json.loads(json.dumps(render['native_render']));next(f for r in fake['actual_platform_font_usage'] for f in r['fonts'] if f['glyphCount'])['isCustomFont']=False
    try:verify_fonts(obs,fake,details);raise RuntimeError('System fallback passed')
    except AssertionError:result['negative_system_fallback_rejected']=True
  except Exception as e:result.update(ok=False,error=repr(e))
  results.append(result);(target/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 browser.close()
(T/'test_report.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
