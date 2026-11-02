"""Exact source-point equivalence under the real pinned native SVG formatter.

No epsilon is added. Raw actual factory path coordinate strings must equal
calling that runtime's canvas.format on the corresponding source vertex in
the same identity canvas CTM and recorded native screen-offset frame.
"""
from pathlib import Path
import hashlib,json,math,re
R=Path('/backup/shaoshitong/img2code_20261029')
POLICY='exact_original_source_vertices_under_pinned_native_SVG_serialization_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(x,r):
 if not x:raise ValueError(r)
NUMBER=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'
FORMAT_JS=r'''rows=>{const root=document.createElementNS('http://www.w3.org/2000/svg','g'),canvas=new mxSvgCanvas2D(root);const format=x=>String(canvas.format(x));return {formatter:String(canvas.format),formatter_owner:'new pinned mxSvgCanvas2D instance',default_canvas_CTM:{dx:canvas.state.dx,dy:canvas.state.dy,scale:canvas.state.scale},rows:rows.map(r=>({key:r.key,expected:r.source.map(([x,y])=>[format(x-r.offset),format(y-r.offset)]),counterfactual:r.source.map(([x,y],i)=>[format(x-r.offset+(i===0?1:0)),format(y-r.offset)])}))};}'''
def prove(xml,geometry,source_code_sha256):
 require(geometry['code_sha256']==sha(xml.encode())and geometry.get('candidate_producer_proof_used')is False,'serialization_proof_not_independent_actual_factory')
 from native_worker import native
 from playwright.sync_api import sync_playwright
 from portable_native_fonts import ready_page
 viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';manifest=json.loads((R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_bytes());require(sha(viewer.read_bytes())==manifest['viewer_bundle_sha256'],'serialization_real_runtime_pin_changed')
 probes={}
 for group in geometry['actual_editing_proofs']:
  require(group.get('ok')is True,'serialization_original_actual_editing_not_proved')
  for p in group['raw']['probes']:probes[(p['edge'],p['side'])]=p['initial']
 rows=[];inputs=[]
 for g in geometry['markers']:
  key=(g['edge'],g['side']);p=probes[key];painted=[r for r in p['paint']if r.get('fill')not in(None,'none','transparent')];require(len(painted)==1,'serialization_actual_marker_not_one_filled_path');paint=painted[0]
  require(not paint.get('transform')and not re.search(r'[^MLZmlz\d.,\s+eE-]',paint['d']),'serialization_marker_actual_path_transform_or_topology_unproved')
  values=re.findall(NUMBER,paint['d']);require(len(values)%2==0,'serialization_actual_path_coordinates_invalid');actual=list(map(list,zip(values[::2],values[1::2])))
  if len(actual)>1 and actual[0]==actual[-1]:actual.pop()
  source=g['source_physical_vertices'];require(len(actual)==len(source)==3,'serialization_requires_actual_and_source_triangle_topology')
  require(all(math.isfinite(float(v))for point in source for v in point),'serialization_nonfinite_source_vertex')
  offset=geometry['actual_runtime_frame']['offsets'][g['edge']];ctm=p['canvas'];require(ctm==dict(dx=0,dy=0,scale=1),'serialization_canvas_CTM_requires_separate_source_mapping')
  k=g['edge']+':'+g['side'];inputs.append(dict(key=k,source=source,offset=offset));rows.append(dict(key=k,edge=g['edge'],head=g['head'],side=g['side'],actual_raw_SVG_path=paint['d'],actual_coordinate_strings=actual,source_physical_vertices=source,native_screen_offset=offset,actual_native_canvas_CTM=ctm,old_numeric_geometry_exact=g['exact_geometry'],old_maximum_vertex_error_px=g['maximum_vertex_error_px'],source_fill_and_absent_stroke_match=g['source_fill_and_absent_stroke_match'],source_viewport_containment=g['source_viewport_containment'],actual_endpoint_and_direction_editing=g['actual_endpoint_and_direction_editing']))
 require(rows,'serialization_no_actual_original_markers')
 with sync_playwright()as pw:
  browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:page=ready_page(browser);formatted=page.evaluate(FORMAT_JS,inputs)
  finally:browser.close()
 require(formatted['default_canvas_CTM']==dict(dx=0,dy=0,scale=1),'serialization_real_formatter_default_CTM_changed');bykey={r['key']:r for r in formatted['rows']}
 for r in rows:
  expected=bykey[r['key']]['expected'];counter=bykey[r['key']]['counterfactual'];actual=r['actual_coordinate_strings'];sets=lambda points:sorted(tuple(p)for p in points)
  r.update(expected_real_official_formatter_coordinate_strings=expected,exact_under_official_serialization=sets(actual)==sets(expected),comparison='exact coordinate strings, triangle vertices matched as one closed filled triangle',no_epsilon_used=True)
  require(sets(actual)!=sets(counter),'serialization_source_vertex_plus_one_negative_not_rejected');r['one_source_vertex_plus_one_counterfactual_rejected']=True
 require(sha(viewer.read_bytes())==manifest['viewer_bundle_sha256'],'serialization_real_runtime_changed_during_proof')
 return dict(ok=True,policy=POLICY,candidate_code_sha256=sha(xml.encode()),source_code_sha256=source_code_sha256,actual_runtime_sha256=manifest['viewer_bundle_sha256'],actual_formatter_function_sha256=sha(formatted['formatter'].encode()),actual_formatter_function=formatted['formatter'],actual_formatter_instance=formatted['formatter_owner'],source_to_native_canvas_mapping='source physical screen point minus the independently observed native SVG screen offset; actual canvas dx=dy=0, scale=1',markers=rows,all_markers_exact_under_official_serialization=all(r['exact_under_official_serialization']for r in rows),equivalent_markers=sum(r['exact_under_official_serialization']for r in rows),parameter_search=False,reference_pixels_read=False,source_or_actual_native_SVG_replaced=False,models=0)

def contour_decision(distance,ratio,geometry,serialization):
 from native_marker_geometry_exact_v1 import contour_decision as frozen,EXACT_GRID_BOUNDARY_PX,AREA_INTERVAL
 old=frozen(distance,ratio,geometry,source_viewport_containment=geometry['source_viewport_containment'],actual_editing=geometry['actual_endpoint_and_direction_editing'])
 if old['ok']:return {**old,'serialization_equivalence_used':False}
 eligible=bool(serialization and serialization.get('exact_under_official_serialization')is True and serialization.get('no_epsilon_used')is True and geometry['source_fill_and_absent_stroke_match']and geometry['source_viewport_containment']and geometry['actual_endpoint_and_direction_editing'])
 accepted=eligible and distance<=EXACT_GRID_BOUNDARY_PX+1e-8 and AREA_INTERVAL[0]<=ratio<=AREA_INTERVAL[1]
 return {**old,'ok':accepted,'policy':POLICY,'serialization_equivalence_used':accepted,'exact_under_official_serialization':eligible,'old_numeric_exact_geometry':geometry['exact_geometry'],'original_1px_rule_unchanged':True,'original_boundary_limit_px':old['boundary_limit_px'],'boundary_limit_px':EXACT_GRID_BOUNDARY_PX if accepted else old['boundary_limit_px'],'existing_exact_equivalence_grid_alias_bound_unchanged':EXACT_GRID_BOUNDARY_PX,'source_equivalence_basis':'exact strings from real pinned native canvas.format; no epsilon expansion'}
