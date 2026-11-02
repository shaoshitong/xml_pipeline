import json,sqlite3,io
import numpy as np
from scipy.ndimage import label,find_objects
from PIL import Image
from native_worker import R,W,now
id='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641';D=sqlite3.connect(W/'jobs.sqlite');r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);B=W/'mermaid_variant_source_probe'/id;ref=np.asarray(Image.open(R/r['original_reference']).convert('RGB'));source=np.asarray(Image.open(B/'10.9.1_html.png').convert('RGB'));pairs=[]
for color in ['f9d5e5','eeac99','e06377','c83349']:
 rgb=np.array([int(color[k:k+2],16) for k in (0,2,4)]);sets=[]
 for im in [source,ref]:
  labs,n=label(np.all(im==rgb,axis=2));boxes=[]
  for k,s in enumerate(find_objects(labs),1):
   area=int((labs[s]==k).sum())
   if area<400:continue
   y,x=s;boxes.append({'x0':x.start,'y0':y.start,'x1':x.stop,'y1':y.stop,'area':area})
  sets.append(sorted(boxes,key=lambda b:(b['y0'],b['x0'])))
 assert len(sets[0])==len(sets[1]) and sets[0],(color,sets)
 for a,b in zip(*sets):pairs.append({'color':color,'source':a,'reference':b})
fits={}
for axis in ['x','y']:
 x=np.array([p['source'][axis+str(k)] for p in pairs for k in [0,1]],float);y=np.array([p['reference'][axis+str(k)] for p in pairs for k in [0,1]],float);coef=np.linalg.lstsq(np.column_stack([x,np.ones_like(x)]),y,rcond=None)[0];res=y-(coef[0]*x+coef[1]);fits[axis]={'scale':float(coef[0]),'offset':float(coef[1]),'max_abs_residual':float(np.max(np.abs(res))),'residuals':res.tolist()}
result={'at':now(),'id':id,'pairs':pairs,'fits':fits};(B/'reference_scale_fit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
