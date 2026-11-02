import json,sqlite3,xml.etree.ElementTree as E,io
import numpy as np
from PIL import Image
from native_worker import R,W,native,now
from native_text_clip import verify_graph
id='00415df3102c6167b8656ddfc48958e7c9e33b501c68fe381fa80147c050f411';B=W/'poster_header_layout'/id;D=sqlite3.connect(W/'jobs.sqlite');out=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);before=(R/out['code_file']).read_text();after=(B/'clip_candidate.drawio').read_text();details=json.loads((B/'clip_details.json').read_text());verify_graph(before,after,details);oldpos=json.loads((B/'before_native_positions.json').read_text());newrender=json.loads((B/'clip_candidate_render.json').read_text());newpos={x['cell']:x for x in newrender['actual_text_positions']};position_errors=[]
for row in oldpos:
 a=[c for r in row['runs'] for c in r['chars']];b=[c for r in newpos[row['cell']]['runs'] for c in r['chars']]
 if a!=b:position_errors.append(row['cell'])
root=E.fromstring(before);changed={x['cell'] for x in details['changes']}
for c in root.iter('mxCell'):
 if c.get('id') in changed:c.set('value','')
w,h=Image.open(R/out['image_file']).size;background={'png':(B/'clip_background.png').read_bytes()};a=np.array(Image.open(R/out['image_file']).convert('RGB'));b=np.array(Image.open(B/'clip_candidate.png').convert('RGB'));bg=np.array(Image.open(io.BytesIO(background['png'])).convert('RGB'));assert a.shape==b.shape==bg.shape;mask=np.zeros((h,w),dtype=bool)
for ch in details['changes']:
 left,top,right,bottom=ch['clip_bounds'];x,y,x1,y1=ch['native_range_bbox'];left=max(left,x-4);top=max(top,y-4);right=min(right,x1+4);bottom=min(bottom,y1+4);assert all(float(v).is_integer() for v in ch['clip_bounds']),'Fractional CSS clip needs coverage-weight proof';xs=np.arange(w)+.5;ys=np.arange(h)+.5;mask|=(ys[:,None]>=top)&(ys[:,None]<bottom)&(xs[None,:]>=left)&(xs[None,:]<right)
expected=bg.copy();expected[mask]=a[mask];pixel_errors=int(np.any(expected!=b,axis=2).sum());unchanged_outside_clip_text=int(np.any(a!=b,axis=2).sum());coords=np.argwhere(np.any(expected!=b,axis=2));examples=[{'xy':[int(x),int(y)],'before':a[y,x].tolist(),'expected':expected[y,x].tolist(),'actual':b[y,x].tolist(),'background':bg[y,x].tolist()} for y,x in coords[:30]];report={'mismatch_pixels':examples,'at':now(),'id':id,'full_text_geometry_and_graph_preserved':True,'all_native_character_bounds_unchanged':not position_errors,'position_errors':position_errors,'expected_source_clip_pixel_mismatches':pixel_errors,'actual_changed_pixels':unchanged_outside_clip_text,'changed_text_cells':len(changed),'visible_text_preserved_and_only_hidden_source_pixels_removed':pixel_errors==0,'ok':not position_errors and pixel_errors==0};(B/'clip_background.png').write_bytes(background['png']);(B/'clip_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
