import json
from PIL import Image
from native_worker import R,W,native,now
id='001015f272ec17f67d59c06833b78bd58f9abfd3b23877c48fddf3ed25c4213a';B=next((W/'native_text_clip_repair_v3'/id).iterdir());xml=(B/'candidate.drawio').read_text();w,h=Image.open(B/'candidate.png').size;r=native.native_job(xml,w,h,120,W/'rendering_clipbox_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert r['ok'] and r['png']==(B/'candidate.png').read_bytes();(B/'clipbox_render.json').write_text(json.dumps(r['native_render'],indent=2));print(json.dumps([x for x in r['native_render']['actual_clip_boxes'] if x['cell'] in ['125','126']]))
