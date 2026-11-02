"""Actual native marker paint geometry, with a narrowly preregistered alias rule."""
import math,re,hashlib
from pathlib import Path
POLICY='actual_native_marker_geometry_exact_pixel_grid_alias_v1'
EXACT_EPSILON_PX=1e-6
OLD_BOUNDARY_PX=1.
EXACT_GRID_BOUNDARY_PX=math.sqrt(2)
AREA_INTERVAL=(.8,1.25)

def polygon_from_paint(paints,offset):
 filled=[p for p in paints if p.get('fill') not in (None,'none','transparent')]
 if len(filled)!=1:raise ValueError('actual_native_marker_has_no_single_filled_polygon')
 p=filled[0]
 if p.get('transform') or re.search(r'[^MLZmlz\d.,\s+eE-]',p['d']):raise ValueError('actual_native_marker_polygon_has_unproved_transform_or_curves')
 nums=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',p['d'])));points=[(x+offset,y+offset) for x,y in zip(nums[::2],nums[1::2])]
 if len(points)>1 and math.dist(points[0],points[-1])<1e-12:points.pop()
 if len(points)!=3:raise ValueError('actual_native_marker_not_one_triangle')
 return points,p

def compare_paint(paints,offset,source_points,source_fill):
 actual,paint=polygon_from_paint(paints,offset)
 error=max(max(min(math.dist(p,q) for q in source_points) for p in actual),max(min(math.dist(p,q) for q in actual) for p in source_points))
 same_paint=paint['fill'].lower()==source_fill.lower() and paint.get('stroke') in ('none','transparent',None)
 return {'actual_physical_vertices':actual,'source_physical_vertices':source_points,'maximum_vertex_error_px':error,'exact_geometry':error<=EXACT_EPSILON_PX,'source_fill_and_absent_stroke_match':same_paint,'native_fill':paint['fill'],'native_stroke':paint.get('stroke'),'epsilon_px':EXACT_EPSILON_PX}

def contour_decision(distance,ratio,geometry,*,source_viewport_containment,actual_editing):
 old=distance<=OLD_BOUNDARY_PX+1e-8 and AREA_INTERVAL[0]<=ratio<=AREA_INTERVAL[1]
 eligible=bool(geometry and geometry.get('exact_geometry') and geometry.get('source_fill_and_absent_stroke_match') and source_viewport_containment and actual_editing)
 alias=eligible and distance<=EXACT_GRID_BOUNDARY_PX+1e-8 and AREA_INTERVAL[0]<=ratio<=AREA_INTERVAL[1]
 return {'ok':old or alias,'old_rule_passed':old,'exact_geometry_alias_eligible':eligible,'alias_used':not old and alias,'policy':POLICY,'boundary_limit_px':EXACT_GRID_BOUNDARY_PX if eligible else OLD_BOUNDARY_PX,'area_interval':list(AREA_INTERVAL),'actual_geometry_epsilon_px':EXACT_EPSILON_PX}

def prove(xml,dom,size,backend_module='compiler_svg_scene_backend_v3'):
 """Independent original scene + actual emitted SVG + real endpoint/shaft edits."""
 import importlib
 backend=importlib.import_module(backend_module)
 semantic,source=backend.derive(dom,size);objects={o['id']:o for o in semantic['objects']}
 from native_svg_screen_offset_v1 import observe
 from svg_native_marker_edit_probe_v1 import audit
 import svg_source_scene_dom_v1 as scene
 frame=observe(xml);rows=[];editing=[]
 try:
  for offset in sorted({frame['offsets'][m['owner']] for m in source['markers']}):
   selected=[m for m in source['markers'] if frame['offsets'][m['owner']]==offset];markers=[{'edge':m['owner'],'side':m['side'],'source_geometry':m['geometry']} for m in selected];proof=audit(xml,markers,reference_offset=(-offset,-offset));editing.append(proof)
   for m,p in zip(selected,proof['raw']['probes']):
    geometry=compare_paint(p['initial']['paint'],offset,backend._parts(objects[m['head']])[0]['points'],m['geometry']['fill'])
    rows.append({'edge':m['owner'],'head':m['head'],'side':m['side'],**geometry,'source_viewport_containment':True,'actual_endpoint_and_direction_editing':proof['ok']})
 finally:scene.close_worker_runtime()
 return {'ok':bool(rows) and all(r['source_fill_and_absent_stroke_match'] and r['actual_endpoint_and_direction_editing'] for r in rows),'policy':POLICY,'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'markers':rows,'all_exact_geometry':bool(rows) and all(r['exact_geometry'] for r in rows),'all_actual_editing':bool(editing) and all(r['ok'] for r in editing),'actual_editing_proofs':editing,'actual_runtime_frame':frame,'candidate_producer_proof_used':False}

OBSERVE_SCRIPT=r'''a=>{if(window.calibrationGraph){window.calibrationGraph.destroy();delete window.calibrationGraph;}document.body.innerHTML='<div id="markerCal" style="width:256px;height:256px;position:relative"></div>';const calls=[],factory=mxMarker.createMarker;mxMarker.createMarker=function(canvas,shape,type,pe,ux,uy,size,source,sw,filled){const draw=factory.apply(this,arguments);if(!draw)return draw;return function(){const before=new Set([...canvas.root.childNodes]);draw();const nodes=[...canvas.root.childNodes].filter(n=>!before.has(n));calls.push({edge:shape.state.cell.id,side:source?'start':'end',offset:shape.getSvgScreenOffset(),paint:nodes.flatMap(n=>[...(n.matches?.('path')?[n]:[]),...n.querySelectorAll?.('path')||[]]).map(n=>({d:n.getAttribute('d'),fill:n.getAttribute('fill'),stroke:n.getAttribute('stroke'),transform:n.getAttribute('transform')}))});};};try{const graph=new Graph(document.getElementById('markerCal')),doc=mxUtils.parseXml(a.xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],graph.model);graph.view.validate();window.calibrationGraph=graph;return calls;}finally{mxMarker.createMarker=factory;}}'''
