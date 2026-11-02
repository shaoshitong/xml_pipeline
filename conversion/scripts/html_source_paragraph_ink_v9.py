"""Exact full signed-RGB ink, streamed without multi-GB int64 temporaries."""
import io
import numpy as np
from PIL import Image
CHUNK_ROWS=128
def ink_metrics(source_png,source_hidden,native_png,native_hidden,offset):
 arrays=[]
 for blob in(source_png,source_hidden,native_png,native_hidden):
  with Image.open(io.BytesIO(blob))as image:
   rgb=image.convert('RGB');arrays.append(np.frombuffer(rgb.tobytes(),dtype=np.uint8).reshape(rgb.height,rgb.width,3))
 src,bg,nat,nbg=arrays;assert src.shape==bg.shape and nat.shape==nbg.shape;assert len(offset)==2 and all(x>=0 and abs(x-round(x))<1e-8 for x in offset);dx,dy=map(lambda x:int(round(x)),offset);assert dx+src.shape[1]<=nat.shape[1]and dy+src.shape[0]<=nat.shape[0]
 source_count=native_count=both_count=mask_diff=color_diff=maximum=0;box=None
 for top in range(0,nat.shape[0],CHUNK_ROWS):
  bottom=min(nat.shape[0],top+CHUNK_ROWS);b=np.subtract(nat[top:bottom],nbg[top:bottom],dtype=np.int16);a=np.zeros_like(b);lo=max(top,dy);hi=min(bottom,dy+src.shape[0])
  if hi>lo:a[lo-top:hi-top,dx:dx+src.shape[1]]=np.subtract(src[lo-dy:hi-dy],bg[lo-dy:hi-dy],dtype=np.int16)
  am=np.any(a!=0,axis=2);bm=np.any(b!=0,axis=2);delta=np.abs(a-b);union=am|bm;source_count+=int(am.sum());native_count+=int(bm.sum());both_count+=int((am&bm).sum());mask_diff+=int((am^bm).sum());color_diff+=int(np.any(delta!=0,axis=2).sum());maximum=max(maximum,int(delta.max(initial=0)));ys,xs=np.where(union)
  if len(xs):
   current=[int(xs.min()),int(ys.min())+top,int(xs.max())+1,int(ys.max())+top+1];box=current if box is None else[min(box[0],current[0]),min(box[1],current[1]),max(box[2],current[2]),max(box[3],current[3])]
 return{'source_ink_pixels':source_count,'native_ink_pixels':native_count,'mask_disagreement_pixels':mask_diff,'actual_color_contribution_disagreement_pixels':color_diff,'maximum_channel_difference':maximum,'source_ink_recall':both_count/max(source_count,1),'native_ink_precision':both_count/max(native_count,1),'ink_bbox':box,'exact_same_domain_source_native_ink':color_diff==0}
