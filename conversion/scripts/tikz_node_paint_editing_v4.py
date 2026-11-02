"""Complete PGF/PDF source-proven native bound and coordinate endpoints."""
import base64,hashlib,json,math,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');JS=Path(__file__).with_name('tikz_export_frame_editing_node_paint_v2.js');PRECISION=Path(__file__).with_name('tikz_editing_paint_precision_v1.js')
PROFILE='complete_actual_PGF_node_owned_label_bound_and_free_interventions_v4'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def require_source_proof(record,source_profile,xml):
 require(record.get('source_format')=='tikz','tikz_free_requires_original_TikZ_source')
 require(source_profile.get('supported') is True and source_profile.get('ok') is True and not source_profile.get('failures'),'tikz_free_full_PGF_PDF_source_not_verified')
 evidence=source_profile.get('evidence',{})
 require(evidence.get('source_label_driver_ownership_complete')is True,'tikz_node_driver_ownership_not_verified')
 require(evidence.get('complete_source_coverage') is True and evidence.get('candidate_code_sha256')==record['code_sha256']==sha(xml.encode()),'tikz_free_source_proof_not_bound_to_current_XML')
 require(source_profile.get('profile')=='compiler_tikz_node_paint_viewport_v2','tikz_free_wrong_source_frontend')
 require(evidence.get('actual_original_PDF_paint_inventory',{}).get('complete_actual_PDF_paint_inventory') is True,'tikz_free_missing_actual_original_PDF_display_list_proof')
 for key in ('source_code_sha256','source_image_sha256'):
  require(evidence.get(key)==record[key],'tikz_free_original_identity_changed')
 return True

def structure_checks(xml,*,record,source_profile):
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
 vertices=result.get('vertex_count');vertex_moves=result.get('vertex_moves')
 require(type(vertices) is int and isinstance(vertex_moves,list) and len(vertex_moves)==vertices and len({x['cell'] for x in vertex_moves})==vertices,'tikz_vertex_intervention_coverage_incomplete')
 for row in vertex_moves:
  require(row.get('ok') is True and len(row['interventions'])==2,'tikz_vertex_actual_edit_incomplete')
  for index,item in enumerate(row['interventions']):
   offset=({'x':17,'y':11},{'x':-13,'y':19})[index]
   require(item.get('offset')==offset and item.get('actual_native_paint_followed') is True and item.get('model_and_all_live_states_restored') is True,'tikz_vertex_paint_or_restore_incomplete')
   require(all(close(item['actual_native_vertex_delta'][a],offset[a]) for a in ('x','y')),'tikz_vertex_actual_delta_differs')
   proofs=item.get('painted_member_precision_proofs');require(isinstance(proofs,list)and len(proofs)==item['painted_members'],'tikz_vertex_complete_paint_precision_proof_missing')
   for observed in proofs:
    b,a=observed['before'],observed['after'];points=lambda row:dict(left=row['x'],right=row['x']+row['width'],top=row['y'],bottom=row['y']+row['height']);before,after=points(b),points(a)
    require(observed['proof'].get('ok')is True and observed['proof'].get('policy')=='SVG_DOMRect_binary32_corner_intervals_v1','tikz_vertex_paint_precision_policy_changed')
    for corner in ('left','right','top','bottom'):
     x,y=before[corner],after[corner];delta=offset['x'if corner in('left','right')else'y'];require(all(math.isfinite(v)for v in(x,y,delta))and max(abs(x),abs(y))<=2*8192,'tikz_vertex_paint_precision_outside_supported_canvas')
     half=lambda v:2**-150 if v==0 else 2**(max(-149,math.floor(math.log2(abs(v)))-23)-1)
     bound=max(1e-4,half(x)+half(y)+8*2**-52*max(1,abs(x),abs(y),abs(delta)))
     require(abs(y-x-delta)<=bound,'tikz_vertex_actual_painted_corner_did_not_follow')

 return result

def audit(xml,*,record,source_profile):
 from native_worker import native
 from playwright.sync_api import sync_playwright
 require_source_proof(record,source_profile,xml);structure_checks(xml,record=record,source_profile=source_profile)
 viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';pins={str(p):sha(p.read_bytes()) for p in [Path(__file__),JS,PRECISION,viewer]}
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:
   page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer));page.add_script_tag(path=str(PRECISION))
   faces=[]
   for font in record.get('native_embedded_fonts',[]):
    path=(R/font['file']).resolve(strict=True);require(path.is_relative_to(R/'clean'),'editing_font_outside_clean');data=path.read_bytes();require(sha(data)==font['sha256'],'editing_embedded_font_changed');faces.append({'family':font['family'],'uri':'data:font/otf;base64,'+base64.b64encode(data).decode()})
   loaded=page.evaluate('''async faces=>{for(const item of faces){const face=new FontFace(item.family,'url("'+item.uri+'")');await face.load();document.fonts.add(face);}await document.fonts.ready;return [...document.fonts].map(f=>({family:f.family,status:f.status}));}''',faces)
   require(all(any(f['family'].strip('"\'')==want['family'] and f['status']=='loaded' for f in loaded) for want in faces),'actual_source_editing_fonts_not_loaded')
   result=page.evaluate(JS.read_text(),xml);result['actual_source_editing_fonts_loaded']=loaded
  finally:browser.close()
 validate_report(result);require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()),'native_free_implementation_changed');result.update(profile=PROFILE,pins=pins,source_code_sha256=record['source_code_sha256'],current_code_sha256=record['code_sha256']);return result
