"""Fixed local marker contour gate, with exact outside-ROI non-regression.

Inputs must be actual pinned-renderer before/after PNGs for the supplied XML.
This pure image/style gate never generates geometry or accepts a corpus item.
"""
import io,math,re,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from scipy.ndimage import binary_erosion,distance_transform_edt
from svg_convert_v2 import color
from svg_convert_v3 import unpack


def _rgb(data):
 image=Image.open(io.BytesIO(data)).convert('RGBA');white=Image.new('RGBA',image.size,'white');white.alpha_composite(image)
 return np.asarray(white.convert('RGB'))


def _color(value):
 value=color(value)
 if re.fullmatch(r'#[0-9a-fA-F]{6}',value):return np.array([int(value[i:i+2],16) for i in (1,3,5)],dtype=float)
 basic={'black':[0,0,0],'blue':[0,0,255],'red':[255,0,0],'green':[0,128,0],'white':[255,255,255]}
 if value in basic:return np.array(basic[value],dtype=float)
 raise ValueError('Unsupported exact marker color '+str(value))


def _mask(pixels,expected):
 direction=255-expected;denominator=float(direction@direction)
 if denominator<1:raise ValueError('White-on-white marker has no measurable visible contour')
 delta=255-pixels.astype(float);alpha=np.sum(delta*direction,axis=2)/denominator
 residual=np.linalg.norm(delta-alpha[:,:,None]*direction,axis=2)
 return (alpha>=.15)&(alpha<=1.04)&(residual<=10)


def check_marker_quality(before_png,after_png,xml,dom,binding,max_distance_px=1.):
 result={'ok':False,'failures':[],'markers':[],'max_allowed_boundary_distance_device_px':max_distance_px,'policy':'exact_outside_marker_rois_and_symmetric_marker_boundaries_v1'}
 try:
  before=_rgb(before_png);after=_rgb(after_png)
  if before.shape!=after.shape:raise ValueError('Marker comparison canvases differ')
  cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};objects={o['id']:o for o in dom['objects']};proof=binding.get('binding',binding);markers=proof['native_arrowheads'];union=np.zeros(before.shape[:2],dtype=bool)
  for marker in markers:
   obj=objects[marker['source_object']];box=obj['bbox'];aa,ab,ac,ad,_,_=obj['matrix'];sw=obj['style']['strokeWidth']*math.sqrt(abs(aa*ad-ab*ac));padding=math.ceil(sw/2+max_distance_px+2)
   x0=max(0,math.floor(box['x'])-padding);y0=max(0,math.floor(box['y'])-padding);x1=min(before.shape[1],math.ceil(box['x']+box['w'])+padding);y1=min(before.shape[0],math.ceil(box['y']+box['h'])+padding)
   union[y0:y1,x0:x1]=True;cell=cells.get(marker['edge']);style=unpack(cell.get('style','')) if cell is not None else {};side=marker['side'];failures=[]
   if cell is None or cell.get('edge')!='1' or not cell.get('source') or not cell.get('target'):failures.append('marker_not_on_bound_native_edge')
   if style.get(side+'Arrow')!=marker['marker'] or style.get(side+'Fill')!='1':failures.append('native_marker_type_or_fill_changed')
   if style.get(side+'FillColor')!=color(obj['style']['fill']) or style.get(side+'StrokeColor')!=marker['native_marker_stroke']:failures.append('native_marker_color_or_outline_changed')
   expected=_color(obj['style']['fill']);a=_mask(before[y0:y1,x0:x1],expected);b=_mask(after[y0:y1,x0:x1],expected)
   if not a.any() or not b.any():failures.append('missing_visible_source_or_native_marker');maximum=None;ratio=0
   else:
    ba=a&~binary_erosion(a,structure=np.ones((3,3)),border_value=0);bb=b&~binary_erosion(b,structure=np.ones((3,3)),border_value=0)
    maximum=float(max(distance_transform_edt(~bb)[ba].max(),distance_transform_edt(~ba)[bb].max()));ratio=float(b.sum()/a.sum())
    if maximum>max_distance_px+1e-8:failures.append('marker_boundary_distance_exceeds_fixed_limit')
    if not .8<=ratio<=1.25:failures.append('marker_ink_area_changed_materially')
   entry={'edge':marker['edge'],'side':side,'source_marker_object':obj['id'],'roi':[x0,y0,x1,y1],'symmetric_boundary_distance_device_px':maximum,'native_source_color_ink_area_ratio':ratio,'ok':not failures,'failures':failures};result['markers'].append(entry)
  changed=np.any(before!=after,axis=2);outside=int((changed&~union).sum());result['changed_pixels_outside_marker_rois']=outside;result['changed_pixels_inside_marker_rois']=int((changed&union).sum());result['marker_count']=len(markers)
  if outside:result['failures'].append('native_pixels_changed_outside_source_marker_rois')
  if not markers:result['failures'].append('no_source_markers_for_this_gate')
  if any(not m['ok'] for m in result['markers']):result['failures'].append('one_or_more_local_marker_contours_failed')
  result['ok']=not result['failures']
 except Exception as exc:result['failures'].append(type(exc).__name__+': '+str(exc))
 return result
