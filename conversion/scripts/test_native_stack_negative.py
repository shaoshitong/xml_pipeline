import json,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now
from fontmix_validation import verify_graph,verify_fonts
P=next(p for p in (W/'font_native_stack_tests').iterdir() if p.name.startswith('004832'));xml=(P/'candidate.drawio').read_text();details=json.loads((P/'details.json').read_text());obs=json.loads((P/'observations.json').read_text());root=E.fromstring(xml);target=next(ch for ch in details['changes'] if len(ch['native_font_stack'])>2);family=target['native_font_stack'][-1];count=0
for cell in root.iter('mxCell'):
 style=dict(x.split('=',1) for x in cell.get('style','').split(';') if '=' in x)
 if 'fontFamily' in style and family in style['fontFamily'].split(',') and style['fontFamily']!=family:
  style['fontFamily']=','.join(f for f in style['fontFamily'].split(',') if f!=family);cell.set('style',';'.join(k+'='+v for k,v in style.items())+';');count+=1
assert count;w,h=Image.open(P/'candidate.png').size;render=native.native_job(E.tostring(root,encoding='unicode'),w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];rejected=False
try:verify_fonts(obs,render['native_render'],details)
except AssertionError as e:rejected=True;reason=str(e)
assert rejected
root=E.fromstring(xml);cell=next(c for c in root.iter('mxCell') if c.get('value'));cell.set('value',cell.get('value')+'X');text_rejected=False
try:verify_graph((P/'before.drawio').read_text(),E.tostring(root,encoding='unicode'),details)
except AssertionError:text_rejected=True
assert text_rejected;result={'at':now(),'ok':True,'missing_fallback_family_rejected_by_actual_fonts':True,'missing_fallback_native_pixels_changed':render['png']!=(P/'candidate.png').read_bytes(),'editable_text_corruption_rejected':True,'reason':reason};(W/'native_font_v4_negative_test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
