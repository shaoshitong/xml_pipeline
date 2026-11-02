"""Exact-original native source with honest bound and explicit coordinate ends."""
import hashlib,json,math,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');JS=Path(__file__).with_suffix('.js')
PROFILE='original_native_per_text_node_physical_font_interventions_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def require_source_proof(record,source_profile,xml):
 require(record.get('source_format')=='drawio'and record['code_sha256']==sha(xml.encode()),'native_run_editing_hash_bound_original_source_required')
 require(source_profile.get('supported')is True and source_profile.get('ok')is True and source_profile.get('profile')=='original_native_per_text_node_physical_fonts_v1','native_run_editing_independent_source_profile_required')
 evidence=source_profile.get('evidence',{})
 for key in ('complete_source_coverage','normalized_original_and_font_only_XML_delta_independently_rederived','fresh_source_RGBA_equals_portable_RGBA','physical_faces_and_glyph_counts_preserved','all_original_markup_and_text_nodes_preserved'):
  require(evidence.get(key)is True,'native_run_editing_missing_source_proof:'+key)
 require(evidence.get('current_code_sha256')==record['code_sha256'],'native_run_editing_source_revision_changed')

def structure_checks(xml,*,record,source_profile):
 from compiler_native_source_repair_editing_v1 import require_source_proof
 from harness_context import structure
 require_source_proof(record,source_profile,xml)
 root=E.fromstring(xml);models=list(root.iter('mxGraphModel'));require(len(models)==1 and (root.tag!='mxfile' or len(root.findall('diagram'))==1),'native_free_exactly_one_uncompressed_page_required')
 model=models[0];parents={c:p for p in model.iter() for c in p};cells={c.get('id') or parents[c].get('id'):c for c in model.iter('mxCell')};vertices={k for k,c in cells.items() if c.get('vertex')=='1'}
 result=structure(xml,{});remaining=[e for e in result['errors'] if e!='unbound_or_invalid_edges'];require(not remaining,'native_free_other_structure_errors:'+json.dumps(remaining))
 free=[]
 for cid,c in cells.items():
  if c.get('parent'):require(c.get('parent') in cells,'native_free_dangling_parent')
  if c.get('edge')!='1':continue
  style={p.split('=',1)[0]:p.split('=',1)[1] for p in c.get('style','').split(';') if '=' in p};g=c.find('mxGeometry')
  for side in ('source','target'):
   if c.get(side):require(c.get(side) in vertices,'native_free_dangling_named_terminal:'+cid+':'+side);continue
   require(not style.get(side+'Port'),'native_free_dangling_named_port')
   points=[] if g is None else g.findall("mxPoint[@as='"+side+"Point']")
   require(len(points)==1,'native_free_missing_or_ambiguous_explicit_endpoint:'+cid+':'+side)
   try:p={k:float(points[0].get(k,'nan')) for k in ('x','y')}
   except ValueError:raise ValueError('native_free_nonfinite_explicit_endpoint')
   require(all(math.isfinite(v) for v in p.values()),'native_free_nonfinite_explicit_endpoint');free.append({'edge':cid,'side':side,'point':p})
 return {**{k:v for k,v in result.items() if k not in ('labels','errors')},'ok':True,'explicit_free_sides':free,'profile':PROFILE}
def validate_report(result):
 require(result.get('ok') is True and result.get('model_and_all_live_states_restored') is True,'native_free_incomplete_live_proof')
 edges=result['edge_count'];moves=result['moves'];require(type(edges) is int and edges>=0 and len(moves)==2*edges,'native_free_incomplete_endpoint_coverage')
 seen=set();sides={}
 def close(a,b):return type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=1e-6
 for move in moves:
  key=(move.get('edge'),move.get('side'));require(key not in seen and key[1] in ('source','target') and move.get('ok') is True,'native_free_duplicate_or_invalid_side');seen.add(key);sides.setdefault(key[0],set()).add(key[1]);mode=move['mode']
  require(mode in ('fixed_constraint','floating_native_perimeter','free_native_coordinate'),'native_free_unknown_source_role')
  if mode=='free_native_coordinate':require(move.get('terminal') is None and move.get('moved_edge')==move['edge'] and all(close(v,v) for v in move['explicit_geometry_point'].values()),'native_free_missing_explicit_geometry_owner')
  else:require(move.get('terminal') and move.get('moved_vertex'),'native_free_missing_bound_vertex_owner')
  interventions=move['interventions'];require(len(interventions)==2,'native_free_two_interventions_required');changed=False
  for index,event in enumerate(interventions):
   offset=({'x':17,'y':11},{'x':-13,'y':19})[index];require(event.get('offset')==offset and event.get('model_and_all_live_states_restored') is True,'native_free_wrong_intervention_or_restore')
   for stage in ('before','after'):
    for source in ('expected','painted'):require(all(close(event[stage]['actual'][axis],event[stage][source][axis]) for axis in ('x','y')),'native_free_actual_routed_or_painted_endpoint_mismatch')
   delta={axis:event['after']['actual'][axis]-event['before']['actual'][axis] for axis in ('x','y')};require(all(close(delta[a],event['delta'][a]) for a in ('x','y')),'native_free_inconsistent_measured_delta');changed|=any(abs(v)>1e-6 for v in delta.values())
   if mode=='free_native_coordinate':require(all(close(delta[a],offset[a]) for a in ('x','y')) and event.get('actual_native_paint_changed') is True and event.get('actual_native_paint_restored') is True,'native_free_coordinate_or_paint_did_not_follow')
   for child in event.get('child_deltas',[]):require(all(close(child[a],offset[a]) for a in ('x','y')),'native_free_bound_child_did_not_follow')
   for group in event.get('label_member_deltas',[]):
    members=group.get('members') or [];require(members and all(close(m[a],members[0][a]) for m in members for a in ('x','y')),'native_free_compound_label_detached')
  require(changed,'native_free_endpoint_unchanged')
 require(len(sides)==edges and all(v=={'source','target'} for v in sides.values()),'native_free_uncovered_edge_side')
 return result

def audit(xml,*,record,source_profile):
 from compiler_native_source_repair_editing_v1 import require_source_proof
 from native_worker import native
 from playwright.sync_api import sync_playwright
 require_source_proof(record,source_profile,xml);structure_checks(xml,record=record,source_profile=source_profile)
 viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';pins={str(p):sha(p.read_bytes()) for p in [Path(__file__),JS,viewer]}
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:
   page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer));result=page.evaluate(JS.read_text(),xml)
  finally:browser.close()
 validate_report(result);require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()),'native_free_implementation_changed');result.update(profile=PROFILE,pins=pins,source_code_sha256=record['source_code_sha256'],current_code_sha256=record['code_sha256']);return result
