import json
from PIL import Image
from native_worker import R,W,native,now
from fontmix_stack import stacked_variant
from fontmix_validation import verify_graph,verify_fonts
B=W/'font_portability_probe_v2';T=W/'font_portability_primary_v2';out=[]
for prefix in ['0024a3897']:
 p=next(p for p in T.iterdir() if p.name.startswith(prefix));before=(B/p.name/'before.drawio').read_text();xml,details=stacked_variant(before,(p/'zero.drawio').read_text(),json.loads((p/'details.json').read_text()));verify_graph(before,xml,details);w,h=Image.open(B/p.name/'before.png').size;render=native.native_job(xml,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];verify_fonts(json.loads((p/'observations.json').read_text()),render['native_render'],details);(p/'stack.drawio').write_text(xml);(p/'stack.png').write_bytes(render['png']);(p/'stack_details.json').write_text(json.dumps(details,indent=2));result={'id':p.name,'at':now(),'stacked_cells':details['stacked_text_cells'],'font_counts_preserved':True,'native_pixels_identical':render['png']==(B/p.name/'before.png').read_bytes()};out.append(result);print(json.dumps(result),flush=True)
(W/'native_font_stack_tests.json').write_text(json.dumps(out,indent=2))
