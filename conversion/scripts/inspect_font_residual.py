import json,sqlite3,hashlib
from PIL import Image,ImageChops
import numpy as np
from native_worker import R,W,native
D=sqlite3.connect(W/'jobs.sqlite');id='00133b4c9ac2bed76362684a28455e5e7d16ebd5949f2362f1d730403700e7b9';r=D.execute('select input_code_sha256,record from native_font_embeddings_v3 where id=?',(id,)).fetchone();path=W/'native_font_embedding_v3'/id/r[0];old=json.loads((path/'before_record.json').read_text());png=(R/old['image_file']).read_bytes();assert hashlib.sha256(png).hexdigest()==old['image_sha256'];xml=(path/'stack_zero.drawio').read_text();w,h=Image.open(R/old['image_file']).size;fresh=native.native_job(xml,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'];(path/'stack_zero.png').write_bytes(fresh['png']);a=Image.open(R/old['image_file']).convert('RGB');b=Image.open(path/'stack_zero.png').convert('RGB');aa=np.array(a);bb=np.array(b);assert aa.shape==bb.shape;mask=np.any(aa!=bb,axis=2);obs=json.loads((path/'observed_fonts.json').read_text());details=json.loads((path/'font_details.json').read_text());changes={c['cell']:c for c in details['changes']};regions=[]
for row in obs:
 box=row['bbox'];x=max(0,int(box['x'])-4);y=max(0,int(box['y'])-4);x1=min(w,int(box['x']+box['width'])+5);y1=min(h,int(box['y']+box['height'])+5);n=int(mask[y:y1,x:x1].sum())
 if n:
  regions.append({**row,'changed_pixels':n,'change':changes.get(row['cell'])});crop=(x,y,x1,y1);left=a.crop(crop);right=b.crop(crop);out=Image.new('RGB',(left.width*2,left.height),'white');out.paste(left,(0,0));out.paste(right,(left.width,0));out.resize((out.width*3,out.height*3)).save(path/('region_'+row['cell']+'.png'))
result={'id':id,'path':str(path),'format':old['source_format'],'different_pixels':int(mask.sum()),'regions':regions};(path/'residual_regions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
