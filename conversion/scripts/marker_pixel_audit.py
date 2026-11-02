"""Account for local marker changes and tiny AA changes on exact unchanged paths."""
import io,math
import numpy as np
from PIL import Image

def audit(before_png,after_png,dom,markers,tails):
 a=np.asarray(Image.open(io.BytesIO(before_png)).convert('RGB'));b=np.asarray(Image.open(io.BytesIO(after_png)).convert('RGB'));assert a.shape==b.shape
 h,w=a.shape[:2];mask=np.zeros((h,w),bool);objects={o['id']:o for o in dom['objects']}
 def box(xs,ys,pad):mask[max(0,math.floor(min(ys))-pad):min(h,math.ceil(max(ys))+pad),max(0,math.floor(min(xs))-pad):min(w,math.ceil(max(xs))+pad)]=True
 for marker in markers:
  o=objects[marker['source_arrow_object']];bb=o['bbox'];pad=math.ceil(o['style']['strokeWidth']*math.sqrt(abs(o['matrix'][0]*o['matrix'][3]-o['matrix'][1]*o['matrix'][2]))*3+4);box([bb['x'],bb['x']+bb['w']],[bb['y'],bb['y']+bb['h']],pad)
 changed=np.any(a!=b,axis=2);outside_arrow=int((changed&~mask).sum())
 for tail in tails:
  pts=tail['old_tail']+tail['new_tail'];box([p[0] for p in pts],[p[1] for p in pts],math.ceil(tail['stroke_width']*3+4))
 yy,xx=np.where(changed&~mask);explained=[];unexplained=[]
 for y,x in zip(yy,xx):
  delta=int(np.max(np.abs(a[y,x].astype(int)-b[y,x].astype(int))));entry={'x':int(x),'y':int(y),'max_channel_delta':delta};edge=None
  if delta<=4:
   for t in tails:
    pts=t['unchanged_prefix'];color=t['stroke_color'];assert color.startswith('#') and len(color)==7
    rgb=np.array([int(color[i:i+2],16) for i in (1,3,5)]);vec=rgb-255;den=float(vec@vec)
    if den==0:continue
    def is_stroke_color(pixel):
     alpha=float((pixel.astype(float)-255)@vec)/den
     return 0<=alpha<=1 and np.max(np.abs(255+alpha*vec-pixel))<=2
    if not is_stroke_color(a[y,x]) or not is_stroke_color(b[y,x]):continue
    for u,v in zip(pts,pts[1:]):
     dx,dy=v[0]-u[0],v[1]-u[1];den=dx*dx+dy*dy
     if den==0:continue
     k=max(0,min(1,((x+.5-u[0])*dx+(y+.5-u[1])*dy)/den));distance=math.hypot(x+.5-u[0]-k*dx,y+.5-u[1]-k*dy)
     if distance<=t['stroke_width']/2+1:edge=t['edge'];break
    if edge:break
  if edge:explained.append({**entry,'unchanged_native_edge':edge})
  else:unexplained.append(entry)
 return {'ok':not unexplained,'changed_pixels':int(changed.sum()),'outside_source_arrow_bbox':outside_arrow,'outside_arrow_and_tail_regions':len(xx),'unchanged_path_antialias_pixels':explained,'unexplained_pixels':unexplained[:100],'unexplained_pixel_count':len(unexplained),'antialias_rule':'At most 4/255 per channel; only within unchanged native path stroke, matching that stroke over white. XML graph/fonts/text preservation checked independently.'}
