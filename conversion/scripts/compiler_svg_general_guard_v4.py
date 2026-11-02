"""Whole-source compositing and actual overlapping paint-order guard for v5.

Adds conservative missing feature checks without changing the frozen frontend,
its source/reference/raster rules, or the calibrated exact-marker exception.
"""
import copy,hashlib,json,math,sys,xml.etree.ElementTree as ET
from pathlib import Path
import compiler_svg_scene_frontend_v8 as frontend
R,W=frontend.R,frontend.W
VERSION=frontend.VERSION
UNIT='general_svg_v8_analytic_endpoint_cubic_bezier_nested_groups_source_compositing_order_guard_v4'
UNITS={'svg':UNIT}
sha=frontend.sha;raw=frontend.raw;require=frontend.require

def configuration(data_root=R):
 config=copy.deepcopy(frontend.configuration(data_root));config['pins'][str(Path(__file__).resolve())]=sha(Path(__file__).read_bytes());config['policy']=UNIT+':'+sha(raw(config['pins']))[:20];config.update(unit=UNIT,unseen_ready=False,automatic_rollout=False)
 return config

def static_support(job):
 result=frontend.static_support(job);result['unit']=UNIT;return result

def source_admission(source,code,size):
 result=frontend.source_admission(source,code,size);result['unit']=UNIT;return result

convert=frontend.convert
prepare_source=frontend.prepare_source
source_reproduction=frontend.source_reproduction
quality_visual=frontend.quality_visual
audit_editing=frontend.audit_editing
structure_checks=frontend.structure_checks


def source_features(dom,size):
 from compiler_svg_scene_backend_v7 import derive
 semantic,binding=derive(dom,size);owners={b['owner'] for b in binding['bindings']};failures=[]
 for key,context in dom.get('sceneMetadata',{}).get('markerContexts',{}).items():
  css=context.get('definitionComputedCss',{})
  if any(abs(float(css.get(prop,1))-1)>1e-8 for prop in ('opacity','fillOpacity','strokeOpacity')):
   failures.append({'reason':'source_marker_definition_alpha_requires_compositing_frontend','context':key})
  if any(css.get(prop,'none')not in ('none','',None)for prop in ('filter','clipPath','maskImage')) or css.get('mixBlendMode','normal')!='normal':
   failures.append({'reason':'source_marker_definition_effect_requires_compositing_frontend','context':key})
 for obj in dom['objects']:
  key=obj['id'];style=obj.get('style',{});css=obj.get('sceneComputedCss',{})
  if abs(float(style.get('opacity',1))-1)>1e-8:failures.append({'reason':'source_element_or_ancestor_opacity_requires_compositing_frontend','id':key})
  if css.get('mixBlendMode','normal')!='normal' or css.get('isolation','auto') not in ('auto',None):failures.append({'reason':'source_blend_or_isolation_requires_compositing_frontend','id':key})
  if css.get('vectorEffect','none') not in ('none','',None):failures.append({'reason':'source_vector_effect_requires_another_native_stroke_mapping','id':key})
  if style.get('fill')!='none' and style.get('stroke')!='none' and css.get('paintOrder','normal') not in ('normal','fill stroke markers'):failures.append({'reason':'source_internal_paint_order_not_in_native_stencil_mapping','id':key})
  if key in owners:
   m=obj.get('matrix',[1,0,0,1,0,0]);sx=math.hypot(m[0],m[1]);sy=math.hypot(m[2],m[3]);dot=m[0]*m[2]+m[1]*m[3]
   if style.get('stroke')!='none'and float(style.get('strokeWidth',0))>0 and (abs(sx-sy)>max(1,sx,sy)*1e-7 or abs(dot)>max(1,sx*sy)*1e-7):
    failures.append({'reason':'source_stroked_nonconformal_connector_requires_outline_compiler','id':key})
   try:dashoffset=float(str(css.get('strokeDashoffset','0')).replace('px',''))
   except ValueError:dashoffset=float('inf')
   if dashoffset!=0:failures.append({'reason':'source_connector_dash_offset_not_mapped','id':key})
   if style.get('linecap')!='butt' or style.get('linejoin')!='miter':failures.append({'reason':'source_connector_cap_or_join_requires_explicit_native_mapping','id':key})
  for ref in obj.get('sceneAncestry',[]):
   ancestor=dom.get('sceneMetadata',{}).get('ancestors',{}).get(ref,{})
   if ancestor.get('mixBlendMode','normal')!='normal' or ancestor.get('isolation','auto') not in ('auto',None):failures.append({'reason':'source_ancestor_blend_or_isolation_not_mapped','id':key,'ancestor':ref})
 return {'ok':not failures,'failures':failures,'semantic':semantic,'binding':binding}

PAINT_ORDER_SCRIPT=r'''a=>{document.body.innerHTML='<div id="orderProbe" style="width:8192px;height:8192px;position:relative"></div>';const graph=new Graph(document.getElementById('orderProbe')),doc=mxUtils.parseXml(a.xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],graph.model);graph.view.validate();const rows=[];for(const [id,type] of a.items){const state=graph.view.getState(graph.model.cells[id]),node=type==='text'?state?.text?.node:state?.shape?.node;if(!node)throw Error('actual_native_source_paint_node_missing:'+id);rows.push({id,node});}rows.sort((a,b)=>a.node===b.node?0:a.node.compareDocumentPosition(b.node)&Node.DOCUMENT_POSITION_FOLLOWING?-1:1);const ranks={};let rank=0,last=null;for(const row of rows){if(row.node!==last){rank++;last=row.node;}ranks[row.id]=rank;}graph.destroy();return ranks;}'''

def paint_order(dom,xml,size):
 from compiler_svg_scene_backend_v7 import derive
 from playwright.sync_api import sync_playwright
 from portable_native_fonts import ready_page
 from native_worker import native
 semantic,binding=derive(dom,size);heads={m['head']:m['owner'] for m in binding['markers']};cells={c.get('id') for c in ET.fromstring(xml).iter('mxCell')};items={}
 for obj in semantic['objects']:
  key=heads.get(obj['id'],obj['id']);require(key in cells,'source_paint_object_missing_from_native_order_probe');items[key]='shape' if obj['id'] in heads else obj['type']
 runtime=native.renderer_path(R).parent/'assets/viewer-static.min.js';expected=json.loads((R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_text())['viewer_bundle_sha256'];require(sha(runtime.read_bytes())==expected,'actual_native_paint_order_runtime_changed')
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=frontend.CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
  try:page=ready_page(browser);ranks=page.evaluate(PAINT_ORDER_SCRIPT,{'xml':xml,'items':list(items.items())})
  finally:browser.close()
 require(sha(runtime.read_bytes())==expected,'actual_native_paint_order_runtime_changed_during_probe')
 def box(o):
  b=o['bbox'];s=o.get('style',{});m=o.get('matrix',[1,0,0,1,0,0]);scale=math.sqrt(abs(m[0]*m[3]-m[1]*m[2]));pad=float(s.get('strokeWidth',0))*scale/2 if s.get('stroke')!='none' else 0
  return b['x']-pad,b['y']-pad,b['x']+b['w']+pad,b['y']+b['h']+pad
 failures=[];checked=0;objects=semantic['objects']
 for index,left in enumerate(objects):
  la=box(left);a=heads.get(left['id'],left['id'])
  for right in objects[index+1:]:
   b=heads.get(right['id'],right['id'])
   if a==b:continue
   rb=box(right)
   if min(la[2],rb[2])<=max(la[0],rb[0]) or min(la[3],rb[3])<=max(la[1],rb[1]):continue
   checked+=1
   if ranks[a]>ranks[b]:failures.append({'reason':'actual_overlapping_native_source_paint_order_changed','source_before':left['id'],'source_after':right['id']})
 return {'ok':not failures,'failures':failures,'overlapping_pairs_checked':checked,'actual_native_paint_nodes':len(ranks),'runtime_sha256':expected,'method':'actual upstream source-object native DOM paint order with source stroke-expanded overlap envelopes'}


def check_source(record,xml,source,data_root,native_info=None):
 result=frontend.check_source(record,xml,source,data_root,native_info=native_info)
 if not result.get('ok'):return result
 try:
  prepared=frontend.prepare_source(record);guard=source_features(prepared['capture']['dom'],prepared['size']);order=paint_order(prepared['capture']['dom'],xml,prepared['size']) if guard['ok'] else {'ok':False,'failures':[]}
  result['evidence']['checks']['complete_source_compositing_guard']={k:v for k,v in guard.items() if k not in ('semantic','binding')};result['evidence']['checks']['actual_source_overlap_paint_order']=order
  result['failures']+=guard['failures']+order['failures'];result['ok']=not result['failures'];result['evidence']['complete_source_coverage']=result['ok'];result['profile']=UNIT
 except Exception as error:result['failures'].append({'reason':'complete_source_order_or_compositing_guard_failed','detail':str(error)[:1600]});result['ok']=False;result['evidence']['complete_source_coverage']=False
 return result
