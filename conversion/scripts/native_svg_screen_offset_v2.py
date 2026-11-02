"""Observed native painter offsets with relative hierarchy displacement algebra.

Every cell receives a desired WORLD displacement. Its local geometry receives
only desired(child)-desired(parent); an edge-child relative vertex uses its
physical mxGeometry.offset, never its fractional/along-path coordinates.
Fresh upstream Graph/mxCodec states, primitives, edits and saved models verify
the transform. No reference pixels or source-specific IDs select parameters.
"""
import hashlib,json,math,xml.etree.ElementTree as E
from pathlib import Path
from svg_convert_v3 import unpack,pack
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
POLICY='actual_native_screen_offset_relative_world_displacements_v2'
sha=lambda b:hashlib.sha256(b).hexdigest()
num=lambda x:format(float(x),'.12f').rstrip('0').rstrip('.') or '0'
def require(ok,reason):
 if not ok:raise ValueError(reason)

SCRIPT=r'''async ({xml,edit})=>{
 const req=(v,s)=>{if(!v)throw Error(s)},near=(a,b,e=1e-6)=>Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<=e;
 document.body.innerHTML='<div id="offsetGraph" style="width:8192px;height:8192px;position:absolute;left:0;top:0"></div>';
 const doc=mxUtils.parseXml(xml),model=doc.getElementsByTagName('mxGraphModel');req(model.length===1,'one_native_model_required');
 for(const item of (model[0].getAttribute('extFonts')||'').split('|').filter(Boolean)){
  const i=item.indexOf('^'),family=item.slice(0,i),url=item.slice(i+1);req(i>0&&url.startsWith('data:font/'),'only_original_inline_native_fonts');
  const face=new FontFace(family,'url("'+url+'")');await face.load();document.fonts.add(face);
 }
 await document.fonts.ready;
 const graph=new Graph(document.getElementById('offsetGraph'));new mxCodec(doc).decode(model[0],graph.model);graph.view.validate();graph.refresh();graph.view.validate();
 req(graph.view.scale===1&&graph.view.translate.x===0&&graph.view.translate.y===0,'unscaled_unpanned_native_probe_required');
 const transparent=c=>!c||c==='none'||c==='transparent'||/^rgba\([^)]*,\s*0(?:\.0+)?\)$/.test(c);
 function primitives(state){
  const node=state.shape?.node;if(!node)return [];
  return [...node.querySelectorAll('path,rect,circle,ellipse,line,polyline,polygon')].flatMap(el=>{
   const s=getComputedStyle(el);let opacity=1;for(let p=el;p&&p!==node.parentNode;p=p.parentElement)opacity*=+getComputedStyle(p).opacity;
   const filled=!['line'].includes(el.localName)&&!transparent(s.fill)&&+s.fillOpacity>0;
   const stroked=!transparent(s.stroke)&&+s.strokeOpacity>0&&parseFloat(s.strokeWidth)>0;
   if(s.display==='none'||s.visibility==='hidden'||!opacity||!filled&&!stroked)return [];
   const b=el.getBoundingClientRect();return [{tag:el.localName,bbox:[b.x,b.y,b.width,b.height],paint:[s.fill,s.stroke,s.fillOpacity,s.strokeOpacity,String(opacity),s.strokeWidth,s.strokeLinecap,s.strokeLinejoin,s.strokeDasharray]}];
  });
 }
 const rect=n=>{const b=n.getBoundingClientRect();return [b.x,b.y,b.width,b.height]};
 function snapshot(g){const out={};for(const c of Object.values(g.model.cells)){const s=g.view.getState(c);if(!s||!c.vertex&&!c.edge)continue;
  out[c.id]={parent:c.parent?.id,vertex:!!c.vertex,edge:!!c.edge,relative:!!c.geometry?.relative,bbox:[s.x,s.y,s.width,s.height],points:s.absolutePoints?.map(p=>[p.x,p.y])||null,primitives:primitives(s),text:s.text?.node?rect(s.text.node):null};}return out;}
 function same(a,b){req(Object.keys(a).sort().join('|')===Object.keys(b).sort().join('|'),'native_state_membership_changed');for(const k of Object.keys(a)){
  for(const f of ['parent','vertex','edge','relative'])req(a[k][f]===b[k][f],'native_state_semantics_changed:'+k);
  for(const f of ['bbox','text']){req(!!a[k][f]===!!b[k][f],'native_box_membership_changed:'+k);if(a[k][f])req(a[k][f].every((v,i)=>near(v,b[k][f][i],1e-4)),'native_box_changed_on_save_or_restore:'+k);}
  req(JSON.stringify(a[k].points)===JSON.stringify(b[k].points),'native_route_changed_on_save_or_restore:'+k);req(a[k].primitives.length===b[k].primitives.length,'native_paint_membership_changed:'+k);
  for(let i=0;i<a[k].primitives.length;i++){const x=a[k].primitives[i],y=b[k].primitives[i];req(x.tag===y.tag&&JSON.stringify(x.paint)===JSON.stringify(y.paint)&&x.bbox.every((v,j)=>near(v,y.bbox[j],1e-4)),'native_paint_changed_on_save_or_restore:'+k);}
 }}
 function encode(g){return mxUtils.getXml(new mxCodec().encode(g.model));}
 async function saveReplay(expected){
  const saved=encode(graph),container=document.createElement('div');container.style.cssText='width:8192px;height:8192px;position:absolute;left:0;top:0';document.body.append(container);const g=new Graph(container);
  try{const d=mxUtils.parseXml(saved);new mxCodec(d).decode(d.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();same(expected,snapshot(g));req(encode(g)===saved,'actual_mxCodec_saved_model_did_not_replay');}
  finally{g.destroy();container.remove();}return true;
 }
 try{
  const cells=snapshot(graph),offsets={},shapes={};for(const c of Object.values(graph.model.cells)){const s=graph.view.getState(c);if(!s?.shape||!cells[c.id]||!cells[c.id].primitives.length)continue;
   const offset=s.shape.getSvgScreenOffset();req([0,.5].includes(offset),'unsupported_actual_svg_screen_offset');offsets[c.id]=offset;shapes[c.id]={offset,painted_primitives:cells[c.id].primitives.length,relative:!!c.geometry?.relative,parent:c.parent?.id};}
  const saved=encode(graph);await saveReplay(cells);const edits=[];
  if(edit)for(const c of Object.values(graph.model.cells).filter(c=>c.vertex&&c.geometry?.relative)){
   const original=c.geometry.clone();for(const delta of [{x:17,y:11},{x:-13,y:19}]){
    const before=snapshot(graph),changed=original.clone();changed.offset=changed.offset?.clone()||new mxPoint();changed.offset.x+=delta.x;changed.offset.y+=delta.y;graph.model.setGeometry(c,changed);graph.view.validate();const after=snapshot(graph);
    req(near(after[c.id].bbox[0]-before[c.id].bbox[0],delta.x)&&near(after[c.id].bbox[1]-before[c.id].bbox[1],delta.y),'relative_native_edit_did_not_follow_physical_offset:'+c.id);
    const descendants=[c],visit=p=>{for(const child of p.children||[]){descendants.push(child);visit(child);}};visit(c);
    for(const member of descendants){if(!before[member.id]||!after[member.id])continue;req(near(after[member.id].bbox[0]-before[member.id].bbox[0],delta.x)&&near(after[member.id].bbox[1]-before[member.id].bbox[1],delta.y),'relative_owned_child_did_not_follow_edit:'+member.id);}
    await saveReplay(after);graph.model.setGeometry(c,original.clone());graph.view.validate();same(before,snapshot(graph));req(encode(graph)===saved,'actual_relative_edit_model_not_restored');edits.push({cell:c.id,delta,actual_relative_vertex_and_owned_children_followed:true,actual_mxCodec_edited_saved_reloaded:true,complete_live_model_and_paint_restored:true});
   }
  }
  return {cells,offsets,actual_shapes:shapes,actual_mxCodec_save_reload_verified:true,relative_edit_interventions:edits,encoded_model:saved};
 }finally{graph.destroy();}
}'''

def observe(xml,edit=True):
 from playwright.sync_api import sync_playwright
 from native_worker import native
 from portable_native_fonts import ready_page
 runtime=native.renderer_path(R).parent/'assets/viewer-static.min.js';manifest=json.loads((R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_bytes());digest=sha(runtime.read_bytes());require(digest==manifest['viewer_bundle_sha256'],'native_offset_runtime_identity_changed')
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
  try:result=ready_page(b).evaluate(SCRIPT,dict(xml=xml,edit=edit))
  finally:b.close()
 require(sha(runtime.read_bytes())==digest,'native_offset_runtime_changed_during_probe');encoded=result.pop('encoded_model')
 return dict(ok=True,policy=POLICY,code_sha256=sha(xml.encode()),runtime_sha256=digest,actual_mxCodec_encoded_model_sha256=sha(encoded.encode()),**result)

def transform(xml,frame,sign=-1):
 require(sign in (-1,1),'invalid_offset_direction');require(frame.get('policy')==POLICY and frame.get('code_sha256')==sha(xml.encode()) and frame.get('actual_mxCodec_save_reload_verified'),'offset_frame_not_bound_to_actual_native_model')
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};offsets=frame['offsets'];states=frame['cells']
 require(all(k in cells and type(v) in (int,float) and v in (0,.5) for k,v in offsets.items()),'invalid_actual_offset_inventory')
 def delta(key):return sign*offsets.get(key,0)
 def add(point,dx,dy):
  point.set('x',num(float(point.get('x',0))+dx));point.set('y',num(float(point.get('y',0))+dy))
 for key,cell in cells.items():
  if cell.get('vertex')!='1' and cell.get('edge')!='1':continue
  require(key in states,'missing_actual_native_cell_state');parent=cell.get('parent');require(parent in cells,'dangling_native_parent');geo=cell.find('mxGeometry');require(geo is not None,'missing_native_geometry');own=delta(key);pd=delta(parent)
  if cell.get('vertex')=='1':
   if geo.get('relative')=='1':
    # This includes UNPAINTED relative label groups: default desired world
    # displacement is zero, so inherited parent-edge movement is undone once.
    offset=geo.find("mxPoint[@as='offset']")
    if own!=pd:
     if offset is None:offset=E.SubElement(geo,'mxPoint',{'as':'offset'})
     add(offset,own-pd,own-pd)
   else:add(geo,own-pd,own-pd)
   continue
  require(geo.get('relative')=='1','nonrelative_native_edge_geometry_pending');style=unpack(cell.get('style',''))
  for side,prefix in [('source','exit'),('target','entry')]:
   terminal=cell.get(side)
   if terminal is None:continue
   require(terminal in states and cells[terminal].get('vertex')=='1','dangling_native_named_terminal');require(prefix+'X' in style and prefix+'Y' in style and style.get(prefix+'Perimeter')=='0','explicit_fixed_native_port_required')
   terminal_style=unpack(cells[terminal].get('style',''));require(float(terminal_style.get('rotation',0))==0 and terminal_style.get('flipH','0')=='0' and terminal_style.get('flipV','0')=='0' and terminal_style.get('direction','east')=='east','nonaxis_native_terminal_requires_independent_constraint_basis')
   width,height=states[terminal]['bbox'][2:];require(min(width,height)>0,'zero_size_native_terminal');style[prefix+'X']=num(float(style[prefix+'X'])+(own-delta(terminal))/width);style[prefix+'Y']=num(float(style[prefix+'Y'])+(own-delta(terminal))/height)
  cell.set('style',pack(style))
  for point in geo.iter('mxPoint'):
   if point.get('as')!='offset':add(point,own-pd,own-pd)
  if cell.get('value','').strip() and own:
   offset=geo.find("mxPoint[@as='offset']")
   if offset is None:offset=E.SubElement(geo,'mxPoint',{'as':'offset'})
   add(offset,-own,-own)
 return E.tostring(root,encoding='unicode')

def verify_translation(before,after,frame,sign=-1):
 require(frame['code_sha256']==sha(before.encode()),'wrong_original_offset_frame');fresh=observe(after,edit=True);a,b=frame['cells'],fresh['cells'];require(a.keys()==b.keys(),'offset_native_cell_membership_changed');require(frame['offsets']==fresh['offsets'],'offset_native_actual_painter_inventory_changed');max_state=0;max_paint=0;point_count=0
 for key,x in a.items():
  y=b[key];d=sign*frame['offsets'].get(key,0)
  for name in ['parent','vertex','edge','relative']:require(x[name]==y[name],'offset_native_topology_or_role_changed')
  for i,(u,v) in enumerate(zip(x['bbox'],y['bbox'])):max_state=max(max_state,abs(v-u-(d if i<2 else 0)))
  require(bool(x['points'])==bool(y['points']),'offset_native_route_membership_changed')
  if x['points']:
   require(len(x['points'])==len(y['points']),'offset_native_route_control_point_removed')
   for p,q in zip(x['points'],y['points']):point_count+=1;max_state=max(max_state,abs(q[0]-p[0]-d),abs(q[1]-p[1]-d))
  require(len(x['primitives'])==len(y['primitives']),'offset_native_paint_primitive_removed')
  for p,q in zip(x['primitives'],y['primitives']):
   require(p['tag']==q['tag'] and p['paint']==q['paint'],'offset_native_paint_style_changed')
   for i,(u,v) in enumerate(zip(p['bbox'],q['bbox'])):max_paint=max(max_paint,abs(v-u-(d if i<2 else 0)))
  require(bool(x['text'])==bool(y['text']),'offset_native_text_paint_removed')
  if x['text']:
   td=0 if x['edge'] else d
   for i,(u,v) in enumerate(zip(x['text'],y['text'])):max_paint=max(max_paint,abs(v-u-(td if i<2 else 0)))
 require(max_state<=.000001,'actual_native_relative_world_translation_changed:'+str(max_state));require(max_paint<=.0001,'actual_native_paint_translation_changed:'+str(max_paint))
 return dict(ok=True,policy=POLICY,before_code_sha256=sha(before.encode()),after_code_sha256=sha(after.encode()),actual_cells_checked=len(a),actual_routed_points_checked=point_count,maximum_actual_world_state_error=max_state,maximum_actual_paint_bbox_error=max_paint,actual_relative_edit_save_reload_interventions=len(fresh['relative_edit_interventions']),actual_mxCodec_complete_save_reload_verified=True,all_source_topology_labels_and_paint_inventory_preserved=True,reference_pixels_used=False)
