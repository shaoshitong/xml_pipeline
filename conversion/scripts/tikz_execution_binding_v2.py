"""Deterministic native-marker fitting; v1 files and drafts remain immutable.

The marker factory below is pinned to the actual viewer implementation and is
checked against mxMarker in the remote parity test. Final decisions use actual
native PNGs, exact outside-ROI non-regression, IoU/area and physical scale ratios.
No source graph direction, source colors or node/edge identities are fitted.
"""
import copy,hashlib,math,statistics,xml.etree.ElementTree as E
import numpy as np
from scipy.spatial import cKDTree
from scipy.ndimage import binary_erosion,distance_transform_edt
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from svg_convert_v2 import num,path_for
from svg_convert_v3 import unpack,pack
from tikz_execution_marker_quality import _rgb,_mask,_color,check_marker_quality

VIEWER_SHA256='0c12ccf10dcaf0d0ef40ca60a5bc881ba27b57e076797ee39bce46602371f769'
POLICY='native_marker_roi_physical_scale_iou_and_exact_external_pixels_v2'
TYPES=('classic','classicThin','block','blockThin')


def sampled_path(obj,step=.15):
 pen=RecordingPen();parse_path(path_for(obj),TransformPen(pen,tuple(obj['matrix'])));points=[];current=None;start=None
 for operation,values in pen.value:
  if operation=='moveTo':
   if points:raise ValueError('Marker has multiple independent subpaths')
   current=np.array(values[0],float);start=current;points.append(current)
  elif operation=='lineTo':
   end=np.array(values[0],float);count=max(1,math.ceil(np.linalg.norm(end-current)/step))
   points.extend(current+(end-current)*i/count for i in range(1,count+1));current=end
  elif operation=='curveTo':
   a,b,end=map(lambda p:np.array(p,float),values);count=max(8,math.ceil((np.linalg.norm(a-current)+np.linalg.norm(b-a)+np.linalg.norm(end-b))/step));origin=current.copy()
   points.extend((1-t)**3*origin+3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3*end for t in np.linspace(0,1,count+1)[1:]);current=end
  elif operation=='closePath':
   count=max(1,math.ceil(np.linalg.norm(start-current)/step));points.extend(current+(start-current)*i/count for i in range(1,count+1));current=start
  elif operation!='endPath':raise ValueError('Unsupported source marker path operation '+operation)
 return np.array(points)


def _poly_samples(points,step=.2):
 result=[]
 for a,b in zip(points,points[1:]+points[:1]):
  a=np.array(a,float);b=np.array(b,float);count=max(1,math.ceil(np.linalg.norm(b-a)/step));result.extend(a+(b-a)*t/count for t in range(count))
 return np.array(result)


def native_marker_polygon(kind,size,stroke,point=(0.,0.),unit=(1.,0.)):
 """Exact classic/block factory math from the SHA-pinned actual native viewer."""
 if kind not in TYPES:raise ValueError('Only filled native point markers can be fitted')
 u=np.array(unit,float);v=np.array([-u[1],u[0]]);ep=np.array(point,float);tip=ep-u*stroke*1.118;length=size+stroke;width=length/(3 if kind.endswith('Thin') else 2)
 points=[tip,tip-u*length+v*width]
 classic=kind.startswith('classic')
 if classic:points.append(tip-u*.75*length)
 points.append(tip-u*length-v*width)
 shaft_end=ep-u*(.75 if classic else 1)*length-u*stroke*1.118
 return [p.tolist() for p in points],shaft_end.tolist()


def _source_geometry(obj,shaft,side):
 points=sampled_path(obj);shaft_points=sampled_path(shaft)
 delta=shaft_points[0]-shaft_points[1] if side=='start' else shaft_points[-1]-shaft_points[-2];u=delta/np.linalg.norm(delta);v=np.array([-u[1],u[0]])
 tip=points[np.argmax(points@u)];local=np.column_stack(((points-tip)@u,(points-tip)@v));length=float(np.ptp(local[:,0]));width=float(np.ptp(local[:,1]));a,b,c,d,_,_=obj['matrix'];outline=obj['style']['strokeWidth']*math.sqrt(abs(a*d-b*c));a,b,c,d,_,_=shaft['matrix'];stroke=shaft['style']['strokeWidth']*math.sqrt(abs(a*d-b*c))
 if length<.5:raise ValueError('Source marker has insufficient measurable length')
 return {'points':points,'local':local,'tip':tip,'u':u,'v':v,'length':length,'width':width,'stroke':stroke,'outline_stroke':outline}


def marker_metrics(before_png,after_png,xml,dom,binding):
 """Report strict historical 1px results and a fixed physical-scale v2 policy."""
 strict=check_marker_quality(before_png,after_png,xml,dom,binding,max_distance_px=1.);before=_rgb(before_png);after=_rgb(after_png);objects={o['id']:o for o in dom['objects']};proof=binding.get('binding',binding);details=[];roi_union=np.zeros(before.shape[:2],bool)
 for entry,marker in zip(strict['markers'],proof['native_arrowheads']):
  obj=objects[marker['source_object']];geo=_source_geometry(obj,objects[marker['edge']],marker['side']);limit=max(1.,min(.20*geo['length'],max(1.,geo['stroke'])));box=obj['bbox'];padding=math.ceil(geo['outline_stroke']/2+limit+2);x0=max(0,math.floor(box['x'])-padding);y0=max(0,math.floor(box['y'])-padding);x1=min(before.shape[1],math.ceil(box['x']+box['w'])+padding);y1=min(before.shape[0],math.ceil(box['y']+box['h'])+padding);roi_union[y0:y1,x0:x1]=True;expected=_color(obj['style']['fill']);a=_mask(before[y0:y1,x0:x1],expected);b=_mask(after[y0:y1,x0:x1],expected);intersection=int((a&b).sum());union=int((a|b).sum());iou=intersection/max(1,union);area_a=int(a.sum());area_b=int(b.sum());distance=None
  if a.any() and b.any():
   ba=a&~binary_erosion(a,structure=np.ones((3,3)),border_value=0);bb=b&~binary_erosion(b,structure=np.ones((3,3)),border_value=0);distance=float(max(distance_transform_edt(~bb)[ba].max(),distance_transform_edt(~ba)[bb].max()))
  failures=[]
  if distance is None or distance>limit+1e-8:failures.append('scale_calibrated_boundary_distance_exceeded')
  if iou<.70:failures.append('marker_ink_iou_below_0.70')
  ratio=area_b/max(1,area_a)
  if not .85<=ratio<=1.18:failures.append('marker_ink_area_ratio_outside_0.85_1.18')
  style_errors=[x for x in entry['failures'] if x not in ('marker_boundary_distance_exceeds_fixed_limit','marker_ink_area_changed_materially')]
  failures.extend(style_errors)
  details.append({**entry,'strict_one_device_pixel_pass':entry['ok'],'strict_one_pixel_roi':entry['roi'],'roi':[x0,y0,x1,y1],'roi_size_device_px':[x1-x0,y1-y0],'source_stroke_width_device_px':geo['stroke'],'source_marker_outline_width_device_px':geo['outline_stroke'],'source_head_path_length_device_px':geo['length'],'source_head_width_device_px':geo['width'],'source_ink_pixels':area_a,'native_ink_pixels':area_b,'ink_area_difference_pixels':area_b-area_a,'ink_iou':iou,'v2_symmetric_boundary_distance_device_px':distance,'boundary_error_per_head_length':distance/geo['length'] if distance is not None else None,'boundary_error_per_stroke_width':distance/geo['stroke'] if distance is not None and geo['stroke'] else None,'v2_boundary_limit_device_px':limit,'v2_ok':not failures,'v2_failures':failures})
 changed=np.any(before!=after,axis=2);outside=int((changed&~roi_union).sum());external=[]
 if outside:external.append('native_pixels_changed_outside_scale_calibrated_marker_rois')
 ok=bool(details) and not external and all(d['v2_ok'] for d in details)
 return {'policy':POLICY,'ok':ok,'strict_one_device_pixel_pass':strict['ok'],'changed_pixels_outside_marker_rois':outside,'changed_pixels_inside_marker_rois':int((changed&roi_union).sum()),'markers':details,'failures':external+([] if all(d['v2_ok'] for d in details) else ['one_or_more_uniform_marker_gates_failed']),'rules':{'outside_marker_rois_changed_pixels':0,'marker_ink_iou_min':.70,'marker_ink_area_ratio':[.85,1.18],'boundary_limit_formula':'max(1px,min(0.20*source_head_path_length,max(1px,source_stroke_width)))','coarse_type_direction_color_and_native_bound_terminals':'mandatory and never fitted','ink_mask_scope':'Same source-color ink within the marker ROI, including its short shaft overlap.'}}


def fit_native_markers(xml,dom,binding,rank=0):
 """Fixed coarse/fine vector search proposes styles; actual PNG gates decide."""
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};objects={o['id']:o for o in dom['objects']};updated=copy.deepcopy(binding);proof=updated.get('binding',updated);reports=[]
 for marker in proof['native_arrowheads']:
  obj=objects[marker['source_object']];shaft=objects[marker['edge']];geo=_source_geometry(obj,shaft,marker['side']);source=geo['local'];tree=cKDTree(source);stroke=float(unpack(cells[marker['edge']].get('style'))['strokeWidth']);all_candidates={}
  def evaluate(kind,scale,along,normal):
   key=(kind,round(scale,5),round(along,5),round(normal,5))
   if key in all_candidates:return all_candidates[key]
   width_ratio=(2/(3 if kind.endswith('Thin') else 2))*geo['length']*scale/geo['width'];tip_limit=max(.5,min(.15*geo['length'],max(.5,geo['stroke'])))
   if not .8<=scale<=1.2 or not .8<=width_ratio<=1.2 or math.hypot(along,normal)>tip_limit:return None
   size=max(.1,geo['length']*scale-stroke);point=(along+stroke*1.118,normal);polygon,_=native_marker_polygon(kind,size,stroke,point);sample=_poly_samples(polygon);forward=tree.query(sample)[0];reverse=cKDTree(sample).query(source)[0];maximum=float(max(forward.max(),reverse.max()));mean=float((np.mean(forward**2)+np.mean(reverse**2))/2);score=(maximum,mean,abs(along)+abs(normal),abs(scale-1));out={'kind':kind,'size':size,'scale':scale,'along':along,'normal':normal,'vector_max_boundary_distance_px':maximum,'score':score};all_candidates[key]=out;return out
  coarse={kind:[] for kind in TYPES};offset_unit=max(.25,min(.1*geo['length'],max(.25,geo['stroke']/2)))
  for kind in TYPES:
   for scale in (.85,1.,1.15,1.30):
    for along in (-offset_unit,0.,offset_unit):
     candidate=evaluate(kind,scale,along,0.)
     if candidate is not None:coarse[kind].append(candidate)
  for kind in TYPES:
   for seed in sorted(coarse[kind],key=lambda x:x['score'])[:2]:
    for scale_delta in (-.05,-.025,0,.025,.05):
     for along_delta in (-offset_unit/3,-offset_unit/6,0,offset_unit/6,offset_unit/3):
      for normal in (-offset_unit/3,0,offset_unit/3):evaluate(kind,seed['scale']+scale_delta,seed['along']+along_delta,normal)
  ranked=sorted(all_candidates.values(),key=lambda x:x['score']);chosen=ranked[min(rank,len(ranked)-1)];u=geo['u'];v=geo['v'];point=geo['tip']+u*(stroke*1.118+chosen['along'])+v*chosen['normal'];cell=cells[marker['edge']];side=marker['side'];terminal=cell.get('source' if side=='start' else 'target');bbox=objects[terminal]['bbox'];style=unpack(cell.get('style'));prefix='exit' if side=='start' else 'entry';style.update({side+'Arrow':chosen['kind'],side+'Size':num(chosen['size']),prefix+'X':num((point[0]-bbox['x'])/bbox['w']),prefix+'Y':num((point[1]-bbox['y'])/bbox['h']),prefix+'Perimeter':'0'});cell.set('style',pack(style));marker['marker']=chosen['kind'];reports.append({'edge':marker['edge'],'side':side,'source_marker_object':obj['id'],'source_head_length':geo['length'],'source_head_width':geo['width'],'source_stroke_width':geo['stroke'],'chosen':{k:v for k,v in chosen.items() if k!='score'},'searched_candidates':len(all_candidates),'rank':rank})
 return E.tostring(root,encoding='unicode'),updated,{'policy':'pinned_native_classic_block_coarse_fine_vector_fit_v2','viewer_sha256':VIEWER_SHA256,'markers':reports,'does_not_accept_without_actual_native_marker_roi_gate':True}
