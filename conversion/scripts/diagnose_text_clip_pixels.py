import json,sys
from pathlib import Path
import numpy as np
from PIL import Image
from native_worker import W,now
id=sys.argv[1];parent=W/'native_text_clip_repair_v3'/id;B=next(p for p in parent.iterdir() if (p/'background.png').exists());details=json.loads((B/'clip_details.json').read_text());a=np.array(Image.open(B/'before.png').convert('RGB'));b=np.array(Image.open(B/'candidate.png').convert('RGB'));bg=np.array(Image.open(B/'background.png').convert('RGB'));h,w=a.shape[:2]
def expected(margin):
 mask=np.zeros((h,w),dtype=bool)
 for ch in details['changes']:
  l,t,r,bo=ch['clip_bounds'];x,y,x1,y1=ch['native_range_bbox'];l=max(l,x-margin);t=max(t,y-margin);r=min(r,x1+margin);bo=min(bo,y1+margin);xs=np.arange(w)+.5;ys=np.arange(h)+.5;mask|=(ys[:,None]>=t)&(ys[:,None]<bo)&(xs[None,:]>=l)&(xs[None,:]<r)
 e=bg.copy();e[mask]=a[mask];return e
errors=expected(4)!=b;coords=np.argwhere(errors.any(axis=2));samples=[]
for y,x in coords[:80]:
 relevant=[c for c in details['changes'] if c['native_range_bbox'][0]-30<x<c['native_range_bbox'][2]+30 and c['native_range_bbox'][1]-30<y<c['native_range_bbox'][3]+30]
 samples.append({'xy':[int(x),int(y)],'before':a[y,x].tolist(),'after':b[y,x].tolist(),'background':bg[y,x].tolist(),'near':[{'cell':c['cell'],'box':c['native_range_bbox'],'clip':c['clip_bounds'],'text':c['source_text']} for c in relevant]})
r={'at':now(),'id':id,'mismatch_count':len(coords),'margin_mismatches':{str(m):int(np.any(expected(m)!=b,axis=2).sum()) for m in [4,8,16,32]},'pixels':samples};(B/'pixel_diagnosis.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
