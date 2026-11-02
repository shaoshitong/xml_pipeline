import hashlib,io,json,sqlite3,math
import numpy as np
from PIL import Image
from skimage.registration import phase_cross_correlation
from native_worker import R,W,native,now
from native_translation import translate
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite');ids=['4b9f5161955963bf7502185ac81bfd2d83d13a3c4dfd2e0183a8c7e4f40e6759','e647ce1486f91f14571889932f1ac166004219b8bba528ac469587f6107d0e6e'];ids +=[x[0] for x in D.execute("select id from jobs where state='needs_quality_repair' and json_extract(output_record,'$.conversion_method')='plantuml_pinned_2025_7_source_svg_native_geometry_v1' order by id limit 4")];results=[]
for id in ids:
 o=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);xml=(R/o['code_file']).read_text();png=(R/o['image_file']).read_bytes();ref=(R/o['original_reference']).read_bytes();a=np.array(Image.open(io.BytesIO(ref)).convert('RGB'));b=np.array(Image.open(io.BytesIO(png)).convert('RGB'));d=W/'plantuml_translation_probe'/id;d.mkdir(parents=True,exist_ok=True);row={'id':id,'before_ssim':metric(ref,png),'variants':[]}
 try:
  assert a.shape==b.shape,'same-canvas translation only';shift,err,_=phase_cross_correlation(a.mean(axis=2),b.mean(axis=2),upsample_factor=10);row['phase_shift_yx']=shift.tolist();candidates=list(dict.fromkeys([(round(float(shift[1])*2)/2,round(float(shift[0])*2)/2),(round(float(shift[1])),round(float(shift[0])))]));w,h=a.shape[1],a.shape[0]
  for n,(dx,dy) in enumerate(candidates):
   if max(abs(dx),abs(dy))>8 or (dx==0 and dy==0):continue
   moved,proof=translate(xml,dx,dy);render=native.native_job(moved,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];audit=render['native_render'];assert not audit['content_outside_declared_canvas'],'translation creates clipped content';score=metric(ref,render['png']);(d/(str(n)+'.drawio')).write_text(moved);(d/(str(n)+'.png')).write_bytes(render['png']);row['variants'].append({'name':str(n),'dx':dx,'dy':dy,'ssim':score,'proof':proof,'render':audit})
 except Exception as e:row['error']=repr(e)
 results.append(row);print(json.dumps({k:([{q:z for q,z in x.items() if q not in ['proof','render']} for x in v] if k=='variants' else v) for k,v in row.items()}),flush=True)
(W/'plantuml_translation_probe/report.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
