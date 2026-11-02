"""Independent source-scene coverage for bound and explicit-coordinate SVG ends.

No source-native flags are accepted. Roles and endpoints are rebuilt from the
fresh authoritative SVG scene, while live interventions use the actual viewer.
"""
import copy,hashlib,json,math,xml.etree.ElementTree as E
from pathlib import Path

POLICY='svg_source_owned_bound_or_explicit_coordinates_coverage_v1'

def require(ok,reason):
 if not ok:raise ValueError(reason)

def edge_points(edge,cells):
 from auto_quality_source_vector_v2 import _style,_world_box
 style=_style(edge);geo=edge.find('mxGeometry');require(geo is not None,'missing_edge_geometry');ends=[]
 for side,prefix in [('source','exit'),('target','entry')]:
  if edge.get(side):
   terminal=cells.get(edge.get(side));require(terminal is not None and terminal.get('vertex')=='1','dangling_named_terminal');x,y,w,h=_world_box(terminal,cells);require(prefix+'X' in style and prefix+'Y' in style and style.get(prefix+'Perimeter')=='0','source_explicit_constraint_missing');point=(x+float(style[prefix+'X'])*w,y+float(style[prefix+'Y'])*h)
   require(not geo.findall("mxPoint[@as='"+side+"Point']"),'ambiguous_bound_and_free_endpoint')
  else:
   matches=geo.findall("mxPoint[@as='"+side+"Point']");require(len(matches)==1,'missing_or_ambiguous_explicit_endpoint');point=tuple(float(matches[0].get(k,'nan')) for k in ('x','y'))
  require(all(math.isfinite(x) for x in point),'nonfinite_native_endpoint');ends.append(point)
 bends=[tuple(float(p.get(k,'nan')) for k in ('x','y')) for p in geo.findall("Array[@as='points']/mxPoint")];require(all(math.isfinite(v) for p in bends for v in p),'nonfinite_native_waypoint')
 return [ends[0],*bends,ends[1]]

def verify(dom,xml,size):
 from compiler_svg_scene_backend_v5 import derive
 from auto_quality_source_vector_v2 import _paint_coverage,_style,_plain
 from svg_convert_v2 import style as source_style
 semantic,proof=derive(dom,size);cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};objects={o['id']:o for o in semantic['objects']};heads={m['head'] for m in proof['markers']};owners={b['owner'] for b in proof['bindings']};errors=[]
 nonedges=copy.deepcopy(semantic);nonedges['objects']=[o for o in semantic['objects'] if o['id'] not in heads|owners]
 paint=_paint_coverage(nonedges,xml);errors+=paint['errors']
 if any(abs(paint['source_layout_translation'][k])>.03 for k in ('dx','dy')):errors.append({'reason':'source_shape_translation_changed'})
 expected=set(objects)-heads|{'0','1'}|{'node_'+n for n in semantic['nodes']}
 if set(cells)!=expected:errors.append({'reason':'source_native_cell_inventory_changed','missing':sorted(expected-set(cells)),'extra':sorted(set(cells)-expected)})
 if {c.get('id') for c in cells.values() if c.get('edge')=='1'}!=owners:errors.append({'reason':'source_native_edge_inventory_changed'})
 for obj in semantic['objects']:
  if obj['id'] in heads:continue
  c=cells.get(obj['id'])
  if c is None:continue
  if obj['type']=='text' and _plain(c.get('value',''))!=obj['text']:errors.append({'reason':'source_text_characters_changed','id':obj['id']})
  if obj.get('node') and c.get('parent')!='node_'+obj['node']:errors.append({'reason':'source_node_membership_changed','id':obj['id']})
 for binding in proof['bindings']:
  key=binding['owner'];obj=objects[key];c=cells.get(key)
  if c is None or c.get('edge')!='1':errors.append({'reason':'source_path_not_native_edge','id':key});continue
  try:
   actual=edge_points(c,cells);expected_points=list(map(tuple,obj['sampledPoints']));st=_style(c)
   for side,field,index in [('source','source_node',0),('target','target_node',-1)]:
    node=binding[field];require(c.get(side)==('node_source_'+node if node else None),'source_endpoint_role_or_owner_changed')
    marker=next((m for m in proof['markers'] if m['owner']==key and m['side']==('start' if side=='source' else 'end')),None)
    if marker:expected_points[index]=tuple(marker['geometry']['native_endpoint'])
   require(len(actual)==len(expected_points) and all(math.dist(a,b)<=.03 for a,b in zip(actual,expected_points)),'source_explicit_path_geometry_changed')
   for prop,value in source_style(obj).items():
    if prop=='html':continue
    got=st.get(prop,{'opacity':'100','fillOpacity':'100','strokeOpacity':'100','strokeWidth':'1'}.get(prop))
    try:same=got is not None and abs(float(got)-float(value))<=.03
    except (ValueError,TypeError):same=got==str(value)
    require(same,'source_edge_paint_style_changed:'+prop)
   require(st.get('edgeStyle')=='none' and st.get('rounded')=='0','source_edge_router_or_rounding_changed')
   for side in ('start','end'):
    marker=next((m for m in proof['markers'] if m['owner']==key and m['side']==side),None)
    if marker:
     geometry=marker['geometry'];required={side+'Arrow':geometry['kind'],side+'Size':geometry['size'],side+'Fill':'1',side+'FillColor':geometry['fill'],side+'StrokeColor':'transparent'}
     for prop,value in required.items():
      got=st.get(prop)
      try:same=got is not None and abs(float(got)-float(value))<=.03
      except (ValueError,TypeError):same=got==str(value)
      require(same,'source_marker_parameter_changed:'+prop)
    else:require(st.get(side+'Arrow','none')=='none','extra_native_marker_not_in_source:'+side)
  except Exception as error:errors.append({'reason':str(error),'id':key})
 return {'ok':not errors,'errors':errors,'paint':paint,'source_binding_proof':proof,'source_layout_translation':{'dx':0,'dy':0},'policy':POLICY,'candidate_independent_original_scene':True}

def structure_checks(xml):
 from harness_context import structure
 result=structure(xml,{})
 errors=[e for e in result['errors'] if e!='unbound_or_invalid_edges'];require(not errors,'svg_other_structure_errors:'+json.dumps(errors));cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
 for cell in cells.values():
  if cell.get('edge')=='1':edge_points(cell,cells)
 return {**{k:v for k,v in result.items() if k not in ('labels','errors')},'ok':True,'policy':POLICY,'source_semantics_still_mandatory':True}

def audit(xml,profile):
 require(profile.get('ok') and profile.get('evidence',{}).get('complete_source_coverage') and profile['evidence']['candidate_code_sha256']==hashlib.sha256(xml.encode()).hexdigest(),'svg_live_editing_requires_complete_current_original_source_proof')
 from native_free_edges_v4 import validate_report
 from native_worker import native
 from playwright.sync_api import sync_playwright
 R=Path('/backup/shaoshitong/img2code_20261029');script=Path(__file__).with_suffix('.js');viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';manifest=json.loads((R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_text());require(hashlib.sha256(viewer.read_bytes()).hexdigest()==manifest['viewer_bundle_sha256'],'native_viewer_identity_changed')
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:
   page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer));result=page.evaluate(script.read_text(),xml)
  finally:browser.close()
 validate_report(result);result.update(policy=POLICY,source_profile=profile['profile'],code_sha256=hashlib.sha256(xml.encode()).hexdigest(),candidate_producer_metadata_used=False)
 return result
