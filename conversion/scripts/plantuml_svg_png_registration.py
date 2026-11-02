import json,numpy as np
from PIL import Image
from skimage.registration import phase_cross_correlation
from skimage.metrics import structural_similarity
from native_worker import R,W
results=[]
for r in json.loads((W/'text_fidelity_selection.json').read_text()):
 if r['format']!='plantuml':continue
 d=W/'plantuml_source_probe'/r['id'];ref=Image.open(R/r['reference']).convert('RGB');svg=Image.open(d/'natural_dejavu_source.png').convert('RGB');a=np.array(ref);b=np.array(svg);shift,error,_=phase_cross_correlation(np.mean(a,axis=2),np.mean(b,axis=2),upsample_factor=10);out={'id':r['id'],'shift_yx':shift.tolist(),'error':float(error)}
 for dx,dy in [(0,0),(round(shift[1]),round(shift[0])),(-1,-1),(-2,-2),(-3,-3),(-4,-4)]:
  bg=Image.new('RGB',svg.size,ref.getpixel((0,0)));bg.paste(svg,(dx,dy));score=float(structural_similarity(np.array(ref.resize((512,512))),np.array(bg.resize((512,512))),channel_axis=2,data_range=255));out.setdefault('translations',[]).append({'dx':int(dx),'dy':int(dy),'score':score})
 results.append(out)
print(json.dumps(results));(W/'plantuml_source_probe/registration.json').write_text(json.dumps(results,indent=2))
