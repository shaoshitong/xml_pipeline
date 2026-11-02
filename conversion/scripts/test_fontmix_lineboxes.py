from native_worker import R,W,native
from pathlib import Path
from PIL import Image
import json,xml.etree.ElementTree as E
B=W/'font_portability_probe_v2';results=[]
for id in ['fixture','0024a3897c4df8abd0a40ab93ae9401b0d434defebfb6f27d39106affd450010']:
 p=B/id;xml=(p/'candidate.drawio').read_text();png=(p/'before.png').read_bytes();w,h=Image.open(p/'before.png').size
 for mode,css in [('zero','line-height:0;'),('inherit','line-height:inherit;')]:
  root=E.fromstring(xml)
  for c in root.iter('mxCell'):
   if c.get('value','').startswith('<span style="font-family:NativeFace_'):c.set('value',c.get('value').replace('<span style="','<span style="'+css))
  new=E.tostring(root,encoding='unicode');out=native.native_job(new,w,h,120,W/'rendering_fontproof/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');result={'id':id,'mode':mode,'ok':out['ok'],'exact':out.get('png')==png};results.append(result);print(json.dumps(result),flush=True)
  if out['ok']:(p/(mode+'.png')).write_bytes(out['png']);(p/(mode+'.drawio')).write_text(new)
(B/'linebox_tests.json').write_text(json.dumps(results,indent=2))
