import json
from PIL import Image
from native_worker import R,W,native
P=W/'native_font_embedding_v3/00133b4c9ac2bed76362684a28455e5e7d16ebd5949f2362f1d730403700e7b9/5c5740b6a69085b3637435ce528d806544ba1822730170572b4075a04c4d640a';old=json.loads((P/'before_record.json').read_text());w,h=Image.open(R/old['image_file']).size;rows={}
for name in ['before','stack_zero']:
 xml=(P/(name+'.drawio')).read_text();out=native.native_job(xml,w,h,120,W/'rendering_fontpositions/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert out['ok'];row=next(x for x in out['native_render']['actual_text_positions'] if x['cell']=='129');rows[name]=row
(P/'position_comparison.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
