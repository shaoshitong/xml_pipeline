"""Compensate the pinned native SVG painter's actual half-pixel screen offset.

This is a renderer coordinate transform, never an image registration. The
actual upstream shape object supplies its offset, then XML geometry/ports are
translated inversely while topology, style and source vectors stay unchanged.
"""
import hashlib,math,xml.etree.ElementTree as ET
from pathlib import Path
from svg_convert_v3 import unpack,pack
from svg_convert_v2 import num
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
POLICY='fresh_actual_native_svg_screen_offset_inverse_geometry_v1'
SCRIPT=r'''xml=>{document.body.innerHTML='<div id="offsetGraph" style="width:8192px;height:8192px;position:relative"></div>';const graph=new Graph(document.getElementById('offsetGraph')),doc=mxUtils.parseXml(xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],graph.model);graph.view.validate();const rows={};for(const cell of Object.values(graph.model.cells)){const state=graph.view.getState(cell);if(!state?.shape||cell.id==='0'||cell.id==='1')continue;const style=graph.getCellStyle(cell);if(style.group==='1'||style.shape==='text')continue;if(!cell.edge&&style.fillColor==='none'&&style.strokeColor==='none')continue;const offset=state.shape.getSvgScreenOffset();if(!Number.isFinite(offset)||![0,.5].includes(offset))throw Error('unsupported_actual_native_screen_offset');rows[cell.id]={offset,actual_node_transform:state.shape.node?.getAttribute('transform'),actual_stroke_width:state.shape.strokewidth,edge:!!cell.edge};}graph.destroy();return rows;}'''

def observe(xml):
 from playwright.sync_api import sync_playwright
 from native_worker import native
 from portable_native_fonts import ready_page
 runtime=native.renderer_path(R).parent/'assets/viewer-static.min.js';manifest=__import__('json').loads((R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_text());digest=hashlib.sha256(runtime.read_bytes()).hexdigest()
 if digest!=manifest['viewer_bundle_sha256']:raise ValueError('native_screen_offset_runtime_identity_changed')
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   page=ready_page(browser);rows=page.evaluate(SCRIPT,xml)
  finally:browser.close()
 if hashlib.sha256(runtime.read_bytes()).hexdigest()!=digest:raise ValueError('native_screen_offset_runtime_changed_during_probe')
 return {'ok':True,'policy':POLICY,'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'runtime_sha256':digest,'actual_shapes':rows,'offsets':{k:v['offset'] for k,v in rows.items()}}

def transform(xml,offsets,sign=-1):
 """Move each painted geometry/connector frame while preserving endpoint binds."""
 from auto_quality_source_vector_v2 import _world_box
 if sign not in (-1,1):raise ValueError('invalid_native_screen_offset_transform_direction')
 tree=ET.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')}
 for key,value in offsets.items():
  if key not in cells or not isinstance(value,(int,float)) or not math.isfinite(value) or value not in (0,.5):raise ValueError('invalid_actual_native_screen_offset_inventory')
 before={key:_world_box(cell,cells) for key,cell in cells.items() if cell.get('vertex')=='1' and cell.find('mxGeometry') is not None and cell.find('mxGeometry').get('relative')!='1'}
 def depth(key):
  count=0;parent=cells[key].get('parent');seen={key}
  while parent in cells and parent not in seen:seen.add(parent);count+=1;parent=cells[parent].get('parent')
  return count
 for key in sorted(before,key=depth):
  cell=cells[key];geo=cell.find('mxGeometry');parent=cell.get('parent');parent_delta=[0.,0.]
  if parent in before:
   current=_world_box(cells[parent],cells);parent_delta=[current[i]-before[parent][i] for i in (0,1)]
  desired=sign*offsets.get(key,0)
  geo.set('x',num(float(geo.get('x',0))+desired-parent_delta[0]));geo.set('y',num(float(geo.get('y',0))+desired-parent_delta[1]))
 for key,offset in offsets.items():
  cell=cells[key];geo=cell.find('mxGeometry')
  if offset and cell.get('vertex')=='1' and geo is not None and geo.get('relative')=='1':raise ValueError('native_relative_vector_needs_separate_screen_offset_mapping')
 after={key:_world_box(cells[key],cells) for key in before}
 for key,offset in offsets.items():
  cell=cells[key]
  if cell.get('edge')!='1':continue
  delta=sign*offset;style=unpack(cell.get('style',''));parent=cell.get('parent');parent_delta=[after[parent][i]-before[parent][i] for i in (0,1)] if parent in before else [0,0]
  for attr,prefix in [('source','exit'),('target','entry')]:
   terminal=cell.get(attr)
   if terminal is None:continue
   if terminal not in before or prefix+'X' not in style or prefix+'Y' not in style:raise ValueError('native_screen_offset_requires_explicit_terminal_port_geometry')
   old,new=before[terminal],after[terminal]
   if min(new[2:])<=0:raise ValueError('native_screen_offset_terminal_has_zero_size')
   style[prefix+'X']=num((old[0]+float(style[prefix+'X'])*old[2]+delta-new[0])/new[2]);style[prefix+'Y']=num((old[1]+float(style[prefix+'Y'])*old[3]+delta-new[1])/new[3])
  cell.set('style',pack(style));geo=cell.find('mxGeometry')
  for point in geo.iter('mxPoint'):
   if point.get('as')=='offset':continue
   point.set('x',num(float(point.get('x',0))+delta-parent_delta[0]));point.set('y',num(float(point.get('y',0))+delta-parent_delta[1]))
 return ET.tostring(tree,encoding='unicode')
