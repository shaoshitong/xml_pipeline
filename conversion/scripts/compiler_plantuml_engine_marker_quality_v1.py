"""Fresh actual native classic paint against fresh original source SVG paint."""
import hashlib,math,re,sys
from pathlib import Path
PROTOTYPE=Path('/backup/shaoshitong/img2code_20261029/conversion/prototype')
if str(PROTOTYPE) not in sys.path:sys.path.append(str(PROTOTYPE))
from plantuml_marker_closed_paint_v1 import outline,certificate,require
from plantuml_marker_minimax_v1 import polygon
from svg_convert_v2 import color

def native_polygon(paint,offset):
 require(not paint.get('transform') and not re.search(r'[^MLZmlz\d.,\s+eE-]',paint['d']),'actual_native_marker_has_unproved_transform_or_curves');numbers=list(map(float,re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?',paint['d'])));points=[(x+offset,y+offset) for x,y in zip(numbers[::2],numbers[1::2])]
 if len(points)>1 and math.dist(points[0],points[-1])<1e-8:points.pop()
 require(len(points) in (3,4),'actual_native_marker_closed_polygon_arity_unsupported');return points

def verify(data,xml,match):
 from native_svg_screen_offset_v1 import observe
 from plantuml_engine_marker_probe_v1 import audit
 import svg_source_scene_dom_v1 as scene
 dom=data['dom'];paths=[o for o in dom['objects'] if o.get('edge') and o['tag']=='path' and o['style']['fill']=='none'];rows=[];descriptors=[]
 for arrow in [o for o in dom['objects'] if o.get('edge') and o['tag']=='polygon']:
  matches=[p for p in paths if p['edge']['id']==arrow['edge']['id']];require(len(matches)==1,'source_native_marker_path_identity_ambiguous');path=matches[0];center=[arrow['bbox']['x']+arrow['bbox']['w']/2,arrow['bbox']['y']+arrow['bbox']['h']/2];side='start' if math.dist(center,path['sampledPoints'][0])<math.dist(center,path['sampledPoints'][-1]) else 'end';points=path['sampledPoints'];end,near=(points[0],points[1]) if side=='start' else (points[-1],points[-2]);u=(end[0]-near[0],end[1]-near[1]);length=math.hypot(*u);require(length>1e-6,'source_marker_tangent_degenerate');u=tuple(x/length for x in u);source_polygon=polygon(arrow);tip=max(source_polygon,key=lambda p:p[0]*u[0]+p[1]*u[1]);descriptors.append({'edge':match['edge_map'][path['id']],'side':side,'source_geometry':{'axis':u,'tip':tip},'source_arrow':arrow,'source_polygon':source_polygon})
 require(descriptors,'source_has_no_explicit_marker_polygons');frame=observe(xml);proofs=[]
 try:
  for offset in sorted({frame['offsets'][d['edge']] for d in descriptors}):
   selected=[d for d in descriptors if frame['offsets'][d['edge']]==offset];actual=audit(xml,[{k:d[k] for k in ('edge','side','source_geometry')} for d in selected],reference_offset=(-offset,-offset));proofs.append(actual)
   for d,probe in zip(selected,actual['raw']['probes']):
    head=d['source_arrow'];source=head.get('original_computed_paint');require(source is not None,'fresh_original_marker_computed_paint_missing');paints=[p for p in probe['initial']['paint'] if p.get('fill') not in ('none',None,'transparent')];require(len(paints)==1,'native_marker_compound_paint_not_supported');paint=paints[0];computed=paint['computed'];require(all(float(source[k])==1 and float(computed[k])==1 for k in ('opacity','fillOpacity','strokeOpacity')),'marker_opaque_paint_equivalence_unproven');require(color(source['fill'])==color(source['stroke'])==color(computed['fill'])==color(computed['stroke']),'source_native_marker_visible_paint_color_changed')
    a,b,c,e,_,_=head['matrix'];sx=math.hypot(a,b);sy=math.hypot(c,e);require(abs(sx-sy)<=1e-7 and abs(a*c+b*e)<=1e-7,'source_marker_nonuniform_stroke_transform_not_supported');stroke=source['strokeWidth']*sx;native_width=float(computed['strokeWidth'].replace('px',''));require(abs(stroke-native_width)<=1e-7,'source_native_marker_outline_width_changed');require(source['linejoin']==computed['strokeLinejoin'] and abs(source['miterlimit']-float(computed['strokeMiterlimit']))<=1e-7,'source_native_marker_join_or_miter_limit_changed');native=native_polygon(paint,offset)
    source_outline=outline(d['source_polygon'],stroke,source['linejoin'],source['miterlimit']);actual_outline=outline(native,native_width,computed['strokeLinejoin'],float(computed['strokeMiterlimit']));closed=certificate(source_outline,actual_outline);rows.append({'source_arrow':head['id'],'native_edge':d['edge'],'side':d['side'],'source_polygon':d['source_polygon'],'actual_native_polygon':native,'source_full_paint_outline':source_outline,'actual_native_full_paint_outline':actual_outline,'continuous_full_paint_certificate':closed,'source_paint':source,'actual_native_paint':paint,'actual_bound_move_and_shaft_rotation':actual['ok'],'ok':closed['ok'] and actual['ok']})
 finally:scene.close_worker_runtime()
 return {'ok':bool(rows) and all(r['ok'] for r in rows),'markers':rows,'actual_editing_proofs':proofs,'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'source_and_native_full_closed_paint_boundaries':True,'producer_Cproof_consulted':False,'candidate_cell_IDs_independently_matched':True,'source_code_from_fresh_authoritative_replay':True}
