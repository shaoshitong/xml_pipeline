"""Exact two-stop, full-bbox axis linear-gradient source/native paint contract.

Original source elements remain native stencils. No new raster asset is made.
Other gradient/effect/transform families remain explicit pending.
"""
from pathlib import Path
import hashlib,math,re,xml.etree.ElementTree as E
from svg_raster_panel_image_ir_v2 import _styles,_world_box
POLICY='original_object_bbox_full_axis_two_stop_gradient_native_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(x,r):
 if not x:raise ValueError(r)
def unit(v):
 v=str(v);x=float(v[:-1])/100 if v.endswith('%')else float(v)
 require(math.isfinite(x),'gradient_nonfinite_coordinate');return x
def coords(g):return [unit(g.get(k,d))for k,d in[('x1','0%'),('y1','0%'),('x2','100%'),('y2','0%')]]
def direction(c):
 x1,y1,x2,y2=c
 if y1==y2 and(x1,x2)in[(0.,1.),(1.,0.)]:return'east'if x2>x1 else'west'
 if x1==x2 and(y1,y2)in[(0.,1.),(1.,0.)]:return'south'if y2>y1 else'north'
 raise ValueError('gradient_non_full_bbox_axis_requires_separate_mapping')
def extract_static(code):
 root=E.fromstring(code);out=[]
 for e in root.iter():
  if e.tag.rsplit('}',1)[-1]!='linearGradient':continue
  require(e.get('id'),'gradient_definition_ID_missing');require(e.get('gradientUnits','objectBoundingBox')=='objectBoundingBox','gradient_user_space_requires_separate_mapping')
  require(not e.get('gradientTransform'),'gradient_transform_requires_separate_mapping');require(e.get('spreadMethod','pad')=='pad','gradient_nonpad_spread_requires_separate_mapping')
  require(not any(k.rsplit('}',1)[-1]=='href'for k in e.attrib),'gradient_inheritance_requires_separate_mapping')
  stops=[c for c in e if c.tag.rsplit('}',1)[-1]=='stop'];require(len(stops)==2 and[unit(s.get('offset','0'))for s in stops]==[0.,1.],'gradient_requires_two_endpoint_stops')
  out.append(dict(definition_id=e.get('id'),coordinates=coords(e.attrib),direction=direction(coords(e.attrib)),units='objectBoundingBox',spread='pad',source_stop_attributes=[dict(s.attrib)for s in stops]))
 require(out,'gradient_profile_requires_original_linearGradient_definitions');return dict(policy=POLICY,source_code_sha256=sha(code),definitions=out)
def rgb(s):
 m=re.fullmatch(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',s)
 require(m is not None,'gradient_stop_color_requires_opaque_computed_sRGB');v=list(map(int,m.groups()));require(all(0<=x<=255 for x in v),'gradient_stop_color_bound');return'#'+''.join(f'{x:02x}'for x in v)
def apply_to_dom(dom,code):
 static=extract_static(code);defs={r['definition_id']:r for r in static['definitions']};proofs=[];proved=set()
 for o in dom.get('objects',[]):
  fill=(o.get('style')or{}).get('fill','')
  if not fill.startswith('url('):continue
  require(o.get('type')=='shape','gradient_only_original_shape_fill_supported');g=o.get('gradient')or{};key=g.get('definitionId');require(key in defs and g.get('tag')=='linearGradient','gradient_original_definition_not_freshly_bound')
  require(g.get('units')=='objectBoundingBox'and not g.get('transform')and g.get('spreadMethod')=='pad','gradient_fresh_coordinate_system_changed')
  require(coords(g)==defs[key]['coordinates'],'gradient_fresh_original_coordinates_changed')
  require(g.get('colorInterpolation','sRGB').lower()=='srgb','gradient_non_sRGB_requires_separate_mapping')
  stops=g.get('stops',[]);require(len(stops)==2 and[s['offset']for s in stops]==[0,1],'gradient_fresh_stop_inventory_changed')
  colors=[rgb(s['color'])for s in stops];alpha=[float(s['opacity'])for s in stops];require(all(math.isfinite(a)and 0<=a<=1 for a in alpha),'gradient_stop_alpha_invalid')
  m=list(map(float,o['matrix']));a,b,c,d,_,_=m;require(all(math.isfinite(x)for x in m)and abs(b)<=1e-8 and abs(c)<=1e-8 and a>0 and d>0,'gradient_nonpositive_axis_CTM_requires_separate_mapping')
  style=o['style'];require(abs(float(style.get('fillOpacity',1))-1)<=1e-8,'gradient_fill_alpha_compositing_requires_separate_mapping')
  if style.get('stroke')!='none'and float(style.get('strokeWidth',0))>0:require(abs(a-d)<=max(1,a,d)*1e-7,'gradient_nonconformal_stroke_requires_separate_mapping')
  from svg_convert_v2 import style as emit_style
  st=emit_style(o);want=dict(fillColor=colors[0],gradientColor=colors[1],gradientDirection=defs[key]['direction'],gradientFillAlpha=alpha[0]*100,gradientAlpha=alpha[1]*100)
  for k,v in want.items():require(str(st[k]).lower()==str(v).lower()or k.endswith('Alpha')and abs(float(st[k])-v)<1e-8,'gradient_emitter_not_exact_source_mapping:'+k)
  row=dict(native_cell_id=o['id'],source_element_id=o.get('sourceId'),source_code_sha256=sha(code),definition_id=key,coordinates=defs[key]['coordinates'],direction=want['gradientDirection'],colors=colors,stop_opacities=alpha,ctm=m,source_paint_rect=o['bbox'],native_style=want,source_definition=defs[key],all_source_gradient_objects_remain_native_stencils=True)
  o['linear_gradient_ir']=row;proofs.append(row);proved.add(o['id'])
 # An unused author definition produces no paint. Its absence must be proved
 # again from the fresh source scene and exact native gradient inventory.
 for field in('issues','sceneIssues'):
  kept=[]
  for issue in dom.get(field,[]):
   matching=[o for o in dom['objects']if o.get('sourceId')==issue.get('id')and(not issue.get('tag')or o.get('tag')==issue['tag'])and o.get('style',{}).get('fill')==issue.get('value')]
   if issue.get('reason')=='fill_paint_server'and matching and all(o['id']in proved for o in matching):continue
   kept.append(issue)
  dom[field]=kept
 dom['linear_gradient_ir']=dict(policy=POLICY,source_code_sha256=sha(code),gradients=proofs,original_source_gradient_paint_instances=len(proofs),unused_original_gradient_definitions_only=not proofs,new_raster_assets=0)
 return dom
def verify_dom_candidate(dom,xml):
 proof=dom.get('linear_gradient_ir')or{};require(proof.get('policy')==POLICY,'gradient_complete_original_IR_missing');rows=proof['gradients'];cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};ids={r['native_cell_id']for r in rows};actual={k for k,c in cells.items()if _styles(c.get('style','')).get('gradientColor')not in(None,'','none')};require(ids==actual,'gradient_native_inventory_missing_extra_or_reused')
 verified=[]
 for row in rows:
  c=cells[row['native_cell_id']];require(c.get('vertex')=='1'and _styles(c.get('style','')).get('shape','').startswith('stencil('),'gradient_original_shape_not_editable_native_stencil');st=_styles(c.get('style',''))
  for k,v in row['native_style'].items():
   if k.endswith('Alpha'):require(abs(float(st.get(k,'nan'))-v)<=1e-8,'gradient_native_stop_alpha_changed')
   else:require(st.get(k,'').lower()==str(v).lower(),'gradient_native_original_style_changed:'+k)
  box=_world_box(c,cells);require(all(abs(box[k]-row['source_paint_rect'][k])<=.03 for k in('x','y','w','h')),'gradient_native_original_paint_rect_changed');verified.append(row)
 return dict(ok=True,policy=POLICY,gradients=verified,new_raster_assets=0,source_code_sha256=proof['source_code_sha256'])
