"""Generic source/native filled-and-stroked marker fit, including cap and join.

This is a proposal generator. It does not accept a graph or publish records.
Closed native markers can have a different painted tip from an open source
path that returns to its start. Source and native actual browser paint, rather
than just their center paths, therefore define size/tip fitting constraints.
"""
import copy,json,math,xml.etree.ElementTree as E
import numpy as np
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from playwright.sync_api import sync_playwright
from scipy.ndimage import binary_erosion,distance_transform_edt
from tikz_execution_binding_v2 import _source_geometry,native_marker_polygon,TYPES,VIEWER_SHA256
from tikz_execution_marker_quality import _rgb,_color
from svg_convert_v2 import path_for,num
from svg_convert_v3 import unpack,pack


def check_marker_only_delta(before,after):
 """Require every object, payload and edge property except marker ports/styles."""
 old={c.get('id'):c for c in E.fromstring(before).iter('mxCell')};new={c.get('id'):c for c in E.fromstring(after).iter('mxCell')}
 if set(old)!=set(new):raise ValueError('Painted marker fit changed source/native object inventory')
 allowed={side+suffix for side in ('start','end') for suffix in ('Arrow','Size')}|{prefix+suffix for prefix in ('entry','exit') for suffix in ('X','Y','Perimeter')};changes={}
 for id in old:
  a,b=copy.deepcopy(old[id]),copy.deepcopy(new[id]);sa,sb=unpack(a.attrib.pop('style','')),unpack(b.attrib.pop('style',''))
  if E.tostring(a)!=E.tostring(b):raise ValueError('Painted marker fit changed nonstyle object '+id)
  diff={k:[sa.get(k),sb.get(k)] for k in sa.keys()|sb.keys() if sa.get(k)!=sb.get(k)}
  if set(diff)-allowed or diff and old[id].get('edge')!='1':raise ValueError('Painted marker fit changed nonmarker style '+id)
  if diff:changes[id]=diff
 return {'only_native_marker_type_size_and_source_relative_ports_changed':True,'changed_edges':changes}


def local_path(obj,geo):
 pen=RecordingPen();parse_path(path_for(obj),TransformPen(pen,tuple(obj['matrix'])));parts=[]
 for operation,values in pen.value:
  xy=[]
  for p in values:
   q=np.array(p,float)-geo['tip'];xy.extend([float(q@geo['u']),float(q@geo['v'])])
  if operation=='closePath':parts.append('Z')
  elif operation=='endPath':pass
  else:
   letter={'moveTo':'M','lineTo':'L','curveTo':'C','qCurveTo':'Q'}[operation];parts.append(letter+' '.join(map(str,xy)))
 return ' '.join(parts),any(operation=='closePath' for operation,_ in pen.value)


PAINT_FIT=r'''a=>{
const scale=4,pad=4*a.stroke+4,x0=-a.length-pad,y0=-a.width/2-pad,w=Math.ceil((a.length+2*pad)*scale),h=Math.ceil((a.width+2*pad)*scale);
function canvas(){let c=document.createElement('canvas');c.width=w;c.height=h;let x=c.getContext('2d',{willReadFrequently:true});return {c,x}}
let {c,x}=canvas();function prepare(){x.resetTransform();x.clearRect(0,0,w,h);x.setTransform(scale,0,0,scale,-x0*scale,-y0*scale);x.fillStyle='black';x.strokeStyle='black';x.lineWidth=a.outline;x.lineJoin=a.join;x.lineCap=a.cap;x.miterLimit=10}
prepare();let sourcePath=new Path2D(a.path);x.globalAlpha=a.fillAlpha;x.fill(sourcePath);if(a.outline>0){x.globalAlpha=a.strokeAlpha;x.stroke(sourcePath)}x.globalAlpha=1;
function alpha(){let rgba=x.getImageData(0,0,w,h).data;return Uint8Array.from({length:w*h},(_,i)=>rgba[4*i+3])}
const source=alpha(),mass=source.reduce((s,v)=>s+v/255,0);
function bounds(data){let loX=w,loY=h,hiX=-1,hiY=-1;for(let y=0;y<h;y++)for(let z=0;z<w;z++)if(data[y*w+z]>=128){loX=Math.min(loX,z);loY=Math.min(loY,y);hiX=Math.max(hiX,z);hiY=Math.max(hiY,y)}return [loX/scale+x0,loY/scale+y0,(hiX+1)/scale+x0,(hiY+1)/scale+y0]}
const sb=bounds(source);if(sb[0]<=x0||sb[1]<=y0||sb[2]>=x0+w/scale||sb[3]>=y0+h/scale)throw Error('Source marker paint is clipped');
let candidates=[],seen=new Set();
function evaluate(kind,s,along){
 let key=[kind,s.toFixed(5),along.toFixed(5)].join('|');if(seen.has(key))return;seen.add(key);if(s<.8||s>1.2)return;
 let size=Math.max(.1,a.length*s-a.stroke),L=size+a.stroke,d=kind.endsWith('Thin')?3:2,classic=kind.startsWith('classic'),p=[[along,0],[along-L,L/d]];if(classic)p.push([along-.75*L,0]);p.push([along-L,-L/d]);
 prepare();x.lineWidth=a.nativeOutline;x.lineJoin='miter';x.lineCap='butt';let path=new Path2D();path.moveTo(...p[0]);for(let q of p.slice(1))path.lineTo(...q);path.closePath();x.globalAlpha=a.fillAlpha;x.fill(path);if(a.nativeOutline>0){x.globalAlpha=a.strokeAlpha;x.stroke(path)}x.globalAlpha=1;let target=alpha(),tb=bounds(target);
 let lengthRatio=(tb[2]-tb[0])/(sb[2]-sb[0]),widthRatio=(tb[3]-tb[1])/(sb[3]-sb[1]),tipError=Math.abs(tb[2]-sb[2]),normalError=Math.abs(tb[1]+tb[3]-sb[1]-sb[3])/2;
 if(lengthRatio<.85||lengthRatio>1.15||widthRatio<.85||widthRatio>1.15||tipError>.5||normalError>.5)return;
 let error=0,intersection=0,union=0;for(let i=0;i<source.length;i++){error+=Math.abs(source[i]-target[i])/255;intersection+=Math.min(source[i],target[i])/255;union+=Math.max(source[i],target[i])/255}
 candidates.push({kind,size,scale:s,along,normal:0,paintAlphaNormalizedL1:error/mass,paintSoftIoU:intersection/union,paintLengthRatio:lengthRatio,paintWidthRatio:widthRatio,paintTipErrorPx:tipError,paintNormalCenterErrorPx:normalError,sourceCoreBounds:sb,nativeCoreBounds:tb,sourceCoreLength:sb[2]-sb[0],sourceCoreWidth:sb[3]-sb[1]});
}
for(let kind of a.types)for(let s of [.8,.85,.9,.95,1,1.05,1.1,1.15,1.2])for(let along of [-2,-1.5,-1,-.5,0,.5,1,1.5,2].map(k=>k*a.stroke))evaluate(kind,s,along);
const score=(p,q)=>p.paintAlphaNormalizedL1-q.paintAlphaNormalizedL1||q.paintSoftIoU-p.paintSoftIoU||Math.abs(p.along)-Math.abs(q.along);
let seeds=a.types.flatMap(k=>candidates.filter(c=>c.kind==k).sort(score).slice(0,2));for(let seed of seeds)for(let ds of [-.025,-.0125,0,.0125,.025])for(let da of [-.25,-.125,0,.125,.25].map(k=>k*a.stroke))evaluate(seed.kind,seed.scale+ds,seed.along+da);
candidates.sort(score);if(!candidates.length)throw Error('No native marker preserves painted dimensions and tip');return {scale,sourceCoreBounds:sb,sourcePathClosed:a.closed,generatedCandidates:seen.size,validCandidates:candidates.length,ranked:candidates.slice(0,8)};
}'''


def fit_painted_markers(xml,dom,binding,runtime,rank=0):
 import hashlib
 if hashlib.sha256(runtime.read_bytes()).hexdigest()!=VIEWER_SHA256:raise ValueError('Pinned native viewer changed')
 objects={o['id']:o for o in dom['objects']};root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};updated=copy.deepcopy(binding);proof=updated.get('binding',updated);reports=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:
   page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>')
   for marker in proof['native_arrowheads']:
    obj=objects[marker['source_object']];geo=_source_geometry(obj,objects[marker['edge']],marker['side']);d,closed=local_path(obj,geo);style=obj['style'];outline=geo['outline_stroke'] if style['stroke']!='none' else 0.;native_outline=0. if marker['native_marker_stroke']=='transparent' else geo['stroke'];fit=page.evaluate(PAINT_FIT,{'path':d,'closed':closed,'length':geo['length'],'width':geo['width'],'stroke':geo['stroke'],'outline':outline,'nativeOutline':native_outline,'join':style['linejoin'],'cap':'butt' if style['linecap']=='butt' else style['linecap'],'fillAlpha':style['fillOpacity']*style['opacity'],'strokeAlpha':style['strokeOpacity']*style['opacity'],'types':list(TYPES)});chosen=fit['ranked'][min(rank,len(fit['ranked'])-1)];cell=cells[marker['edge']];s=unpack(cell.get('style'));stroke=float(s['strokeWidth']);point=geo['tip']+geo['u']*(stroke*1.118+chosen['along']);prefix='exit' if marker['side']=='start' else 'entry';terminal=cell.get('source' if marker['side']=='start' else 'target');bbox=objects[terminal]['bbox'];s.update({marker['side']+'Arrow':chosen['kind'],marker['side']+'Size':num(chosen['size']),prefix+'X':num((point[0]-bbox['x'])/bbox['w']),prefix+'Y':num((point[1]-bbox['y'])/bbox['h']),prefix+'Perimeter':'0'});cell.set('style',pack(s));marker['marker']=chosen['kind'];reports.append({'edge':marker['edge'],'side':marker['side'],'source_marker_object':obj['id'],'chosen':chosen,'paint_fit':fit})
  finally:browser.close()
 return E.tostring(root,encoding='unicode'),updated,{'policy':'browser_painted_source_cap_join_and_native_marker_fit_v1','source_bytes_and_nonmarker_objects_unchanged':True,'must_pass_actual_full_native_render_gate':True,'paint_constraints':{'core_alpha':.5,'tip_max_difference_device_px':.5,'core_length_ratio':[.85,1.15],'core_width_ratio':[.85,1.15],'normal_center_max_difference_device_px':.5,'direction':'exact source shaft unit; no normal fit offset'},'markers':reports}


def aa_diagnostics(before_png,after_png,dom,binding,quality):
 before=_rgb(before_png);after=_rgb(after_png);objects={o['id']:o for o in dom['objects']};proof=binding.get('binding',binding);details=[]
 for marker,entry in zip(proof['native_arrowheads'],quality['markers']):
  x0,y0,x1,y1=entry['roi'];a=before[y0:y1,x0:x1].astype(float);b=after[y0:y1,x0:x1].astype(float);color=_color(objects[marker['source_object']]['style']['fill']);direction=255-color;denom=float(direction@direction)
  def alpha(data):
   delta=255-data;z=(delta@direction)/denom;residual=np.linalg.norm(delta-z[:,:,None]*direction,axis=2);return np.where(residual<=10,np.clip(z,0,1),0)
  sa,sb=alpha(a),alpha(b);levels=[]
  for threshold in (.15,.35,.5,.75,.9):
   ma=sa>=threshold;mb=sb>=threshold;ba=ma&~binary_erosion(ma,structure=np.ones((3,3)),border_value=0);bb=mb&~binary_erosion(mb,structure=np.ones((3,3)),border_value=0);distances=[]
   if ba.any() and bb.any():distances=np.r_[distance_transform_edt(~bb)[ba],distance_transform_edt(~ba)[bb]]
   levels.append({'source_color_alpha_threshold':threshold,'source_pixels':int(ma.sum()),'native_pixels':int(mb.sum()),'iou':float((ma&mb).sum()/max(1,(ma|mb).sum())),'symmetric_boundary_max_device_px':float(np.max(distances)) if len(distances) else None,'symmetric_boundary_p95_device_px':float(np.quantile(distances,.95)) if len(distances) else None,'symmetric_boundary_mean_device_px':float(np.mean(distances)) if len(distances) else None})
  error=np.abs(sa-sb);color_error=np.abs(a-b);details.append({'edge':marker['edge'],'side':marker['side'],'roi':entry['roi'],'roi_size_device_px':entry['roi_size_device_px'],'alpha_levels':levels,'source_alpha_mass':float(sa.sum()),'native_alpha_mass':float(sb.sum()),'normalized_alpha_l1':float(error.sum()/max(1e-10,sa.sum())),'soft_ink_iou':float(np.minimum(sa,sb).sum()/max(1e-10,np.maximum(sa,sb).sum())),'total_rgb_absolute_error':int(color_error.sum()),'max_rgb_channel_error':int(color_error.max()),'mean_rgb_absolute_error_per_roi_pixel':float(color_error.mean()),'color_error_per_source_full_contrast_ink_pixel':float(color_error.sum()/max(1e-10,sa.sum()*np.abs(direction).sum()))})
 return {'interpretation':'Measurements only; the historical strict and fixed physical-scale gates remain unchanged. Source/native alpha is normalized by the measured source fill color, not by white pixel brightness.','markers':details}
