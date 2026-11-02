"""Finite exact filled-triangle SVG-marker to real native-marker proposals.

This module never publishes or accepts. It preserves every nonmarker cell and
shaft waypoint. It only replaces one source marker triangle by an exact native
block/blockThin on its already-bound source owner. Fresh native edit probes,
strict render and marker-ROI/original-image gates remain mandatory.
"""
import copy,hashlib,json,math
from pathlib import Path
import xml.etree.ElementTree as E
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from svg_convert_v2 import path_for,num,color
from svg_convert_v3 import unpack,pack
from tikz_execution_binding_v2 import native_marker_polygon,VIEWER_SHA256

POLICY='exact_source_owned_filled_triangle_native_marker_candidate_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()

class Unsupported(ValueError):
    def __init__(self,reason,**evidence):self.reason=reason;self.evidence=evidence;super().__init__(reason)

def _require(condition,reason,**evidence):
    if not condition:raise Unsupported(reason,**evidence)

def _points(obj):
    pen=RecordingPen();parse_path(path_for(obj),TransformPen(pen,tuple(obj['matrix'])));parts=[];points=[];closed=False
    for op,p in pen.value:
        _require(op in ('moveTo','lineTo','closePath','endPath'),'curved_marker_or_owner_requires_separate_painted_profile',id=obj['id'],operation=op)
        if op=='moveTo':
            if points:parts.append((points,closed))
            points=[tuple(p[0])];closed=False
        elif op=='lineTo':points.append(tuple(p[0]))
        elif op=='closePath':closed=True
    if points:parts.append((points,closed))
    for points,closed in parts:
        if len(points)>1 and math.dist(points[0],points[-1])<1e-8:points.pop()
    return parts

def _segment_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];n=dx*dx+dy*dy;t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/n)) if n else 0
    return math.dist(p,(a[0]+t*dx,a[1]+t*dy))

def _outline(obj,tolerance=.01):
    """Convex closed source outline with a proven Hausdorff error budget.

    A Bezier lies in its control hull. If every control point is within epsilon
    of its endpoint segment, the whole curve is within epsilon; continuity of
    projection gives the reverse segment-to-curve bound. Otherwise de Casteljau
    subdivision continues. Known ellipse/rounded-rect arc approximation adds
    its independent analytic cubic error bound; generic SVG arcs are deferred.
    """
    approximation=0.;a,b,c,d,_,_=obj['matrix'];scale=math.sqrt(a*a+b*b+c*c+d*d);tag=obj['tag'];attrs=obj['attrs']
    if tag=='path':_require(not __import__('re').search('[Aa]',obj.get('d') or ''),'source_node_generic_arc_needs_actual_contour_binding_profile',id=obj['id'])
    if tag in ('circle','ellipse','rect'):
        radius=max(attrs.get(k,0) for k in (('r','rx','ry') if tag!='rect' else ('rx','ry')));approximation=.000273*radius*scale
        _require(approximation<=.01,'source_node_arc_to_cubic_error_exceeds_binding_budget',id=obj['id'],arc_approximation_error_bound_px=approximation)
    pen=RecordingPen();parse_path(path_for(obj),TransformPen(pen,tuple(obj['matrix'])));points=[];start=None;current=None;closed=False;contours=0
    def flatten(control,depth=0):
        _require(depth<=24,'source_node_curve_flattening_depth_limit',id=obj['id']);bound=max(_segment_distance(p,control[0],control[-1]) for p in control)
        if bound<=tolerance:points.append(control[-1]);return
        levels=[control]
        while len(levels[-1])>1:levels.append([((p[0]+q[0])/2,(p[1]+q[1])/2) for p,q in zip(levels[-1],levels[-1][1:])])
        flatten([level[0] for level in levels],depth+1);flatten([level[-1] for level in levels[::-1]],depth+1)
    for operation,values in pen.value:
        if operation=='moveTo':contours+=1;current=tuple(values[0]);start=current;points.append(current)
        elif operation=='lineTo':current=tuple(values[0]);points.append(current)
        elif operation in ('curveTo','qCurveTo'):
            _require(len(values)==(3 if operation=='curveTo' else 2),'source_node_curve_has_unsupported_control_arity',id=obj['id']);flatten([current]+[tuple(p) for p in values]);current=tuple(values[-1])
        elif operation=='closePath':closed=True;current=start
        elif operation=='endPath':pass
        else:raise Unsupported('source_node_outline_operation_not_in_binding_rule',id=obj['id'],operation=operation)
        _require(len(points)<=20000,'source_node_outline_point_limit',id=obj['id'])
    _require(contours==1 and closed and len(points)>=3,'source_node_requires_one_closed_outline',id=obj['id'])
    if math.dist(points[0],points[-1])<1e-8:points.pop()
    def area(p):return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p,p[1:]+p[:1])))/2
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    unique=sorted(set(points));lower=[];upper=[]
    for p in unique:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in unique[::-1]:
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    hull=lower[:-1]+upper[:-1];hull_area=area(hull);signed_area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]));sign=1 if signed_area>0 else -1
    for previous,current,following in zip(points[-1:]+points[:-1],points,points[1:]+points[:1]):
        turn=cross(previous,current,following);forward=(current[0]-previous[0],current[1]-previous[1]);back=(following[0]-current[0],following[1]-current[1]);_require(sign*turn>=-1e-8 and (abs(turn)>1e-8 or forward[0]*back[0]+forward[1]*back[1]>=-1e-8),'source_node_outline_not_proven_simple_convex',id=obj['id'])
    _require(hull_area>1e-6 and abs(area(points)-hull_area)<=max(1e-6,hull_area*1e-8),'source_node_outline_not_proven_simple_convex',id=obj['id']);return points,tolerance+approximation

def _inside_convex(point,polygon,tolerance=1e-6):
    signs=[]
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        cross=(b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]);length=math.dist(a,b)
        if abs(cross)>tolerance*max(length,1):signs.append(cross>0)
    return not signs or all(sign==signs[0] for sign in signs)

def _opaque_plain_paint(obj,owner=False):
    style=obj['style'];css=obj.get('sceneComputedCss',{})
    _require(all(abs(float(style.get(k,1))-1)<1e-8 for k in ('opacity','fillOpacity','strokeOpacity')),'marker_or_owner_alpha_requires_separate_compositing_profile',id=obj['id'])
    _require(not obj.get('gradient') and not obj.get('filterDefinition'),'marker_or_owner_paint_server_or_filter_not_in_exact_triangle_rule',id=obj['id'])
    _require(not any(str(style.get(k,'')).startswith('url(') for k in ('fill','stroke')),'marker_or_owner_paint_server_not_in_exact_triangle_rule',id=obj['id'])
    for name in ('filter','clipPath','maskImage'):_require(css.get(name,'none')=='none','marker_or_owner_css_clip_filter_or_mask_not_in_exact_triangle_rule',id=obj['id'],property=name)
    _require(css.get('mixBlendMode','normal')=='normal' and css.get('isolation','auto')=='auto','marker_or_owner_blending_not_in_exact_triangle_rule',id=obj['id'])
    if owner:_require(style['fill']=='none' and style['stroke']!='none' and style['strokeWidth']>0 and style['dash']=='none','native_marker_requires_visible_solid_unfilled_source_owner',id=obj['id'])
    else:_require(style['fill']!='none' and style['stroke']=='none','source_marker_outline_or_unfilled_head_requires_painted_fit',id=obj['id'])
    for channel in ('fill','stroke'):
        if style[channel]=='none':continue
        from auto_quality_svg_closed_scene_v1 import _color_alpha
        _require(_color_alpha(style[channel])==1,'marker_or_owner_rgba_alpha_not_in_exact_triangle_rule',id=obj['id'])

def _triangle_geometry(head,owner,side):
    parts=_points(head);_require(len(parts)==1 and parts[0][1] and len(parts[0][0])==3,'source_marker_is_not_one_closed_triangle',id=head['id']);points=parts[0][0]
    shaft=_points(owner);_require(len(shaft)==1 and not shaft[0][1] and len(shaft[0][0])>=2,'source_owner_not_one_open_line_only_path',id=owner['id'])
    sp=shaft[0][0];end,near=(sp[0],sp[1]) if side=='start' else (sp[-1],sp[-2]);length=math.dist(end,near);_require(length>1e-6,'zero_source_endpoint_tangent',id=owner['id']);u=((end[0]-near[0])/length,(end[1]-near[1])/length);v=(-u[1],u[0]);project=lambda p:(p[0]*u[0]+p[1]*u[1],p[0]*v[0]+p[1]*v[1]);ordered=sorted(points,key=lambda p:project(p)[0]);tip=ordered[-1];base=ordered[:2];tip_l,tip_n=project(tip);bl=[project(p)[0] for p in base];bn=[project(p)[1] for p in base];head_length=tip_l-sum(bl)/2;width=abs(bn[1]-bn[0]);_require(head_length>.5 and width>.5,'source_marker_has_insufficient_physical_extent',id=head['id']);_require(abs(bl[0]-bl[1])<=.02 and abs(sum(bn)/2-tip_n)<=.02,'source_marker_triangle_not_symmetric_about_owner_outward_tangent',id=head['id']);ratio=width/head_length;kind=min(('block','blockThin'),key=lambda k:abs(ratio-(1 if k=='block' else 2/3)));a,b,c,d,_,_=owner['matrix'];sx=math.hypot(a,b);sy=math.hypot(c,d);_require(abs(sx-sy)<max(1,sx,sy)*1e-7 and abs(a*c+b*d)<max(1,sx*sy)*1e-7,'source_owner_nonuniform_or_shear_stroke_unproven',id=owner['id']);stroke=owner['style']['strokeWidth']*sx;size=head_length-stroke;_require(size>.1,'source_head_too_short_for_native_factory_stroke',id=head['id']);endpoint=(tip[0]+u[0]*stroke*1.118,tip[1]+u[1]*stroke*1.118);native,_=native_marker_polygon(kind,size,stroke,endpoint,u);maximum=max(max(min(math.dist(p,q) for q in native) for p in points),max(min(math.dist(p,q) for q in points) for p in native));_require(maximum<=.03,'triangle_aspect_or_direction_not_exactly_expressible_by_verified_block_factories',id=head['id'],source_width_length_ratio=ratio,nearest_native_kind=kind,maximum_vertex_error_px=maximum)
    return {'kind':kind,'size':size,'stroke':stroke,'tip':tip,'axis':u,'length':head_length,'width':width,'source_points':points,'source_owner_points':sp,'native_endpoint':endpoint,'maximum_vertex_error_px':maximum}

def _terminal_binding(terminal_id,tip,objects,cells,offset,page_size):
    from auto_quality_source_vector_v2 import _world_box
    obj=objects.get(terminal_id);_require(obj is not None and obj.get('type')=='shape' and obj.get('style',{}).get('fill')!='none','native_terminal_has_no_direct_filled_source_object',terminal=terminal_id)
    own_outline,own_uncertainty=_outline(obj)
    actual=_world_box(cells[terminal_id],cells);box=obj['bbox'];_require(all(abs(a-b)<.03 for a,b in zip(actual,(box['x']+offset[0],box['y']+offset[1],box['w'],box['h']))),'native_terminal_not_at_current_source_geometry',terminal=terminal_id)
    distances=[]
    for candidate in objects.values():
        if candidate.get('markerOwner') or candidate.get('type')!='shape' or candidate['style']['fill']=='none':continue
        bbox=candidate['bbox']
        if bbox['w']*bbox['h']>=page_size[0]*page_size[1]*.65:continue
        try:points,uncertainty=_outline(candidate)
        except Unsupported:continue
        distance=min(_segment_distance(tip,a,b) for a,b in zip(points,points[1:]+points[:1]));distances.append((distance,uncertainty,candidate['id']))
    own=next((distance for distance,uncertainty,id in distances if id==terminal_id),None);_require(own is not None and own+own_uncertainty<=.75,'source_head_tip_not_on_selected_actual_node_outline',terminal=terminal_id,distance_px=own,contour_uncertainty_px=own_uncertainty);ambiguous=[{'id':id,'distance_lower_bound_px':max(0,distance-uncertainty)} for distance,uncertainty,id in distances if id!=terminal_id and distance-uncertainty<=own+own_uncertainty+.25];_require(not ambiguous,'source_head_tip_has_ambiguous_source_node_outline_binding',terminal=terminal_id,candidates=ambiguous[:10]);return {'terminal':terminal_id,'source_tip_to_outline_distance_px':own,'contour_Hausdorff_error_bound_px':own_uncertainty,'source_tip_to_true_outline_distance_upper_bound_px':own+own_uncertainty,'competing_outline_count_within_quarter_pixel':0,'source_filled_outline_and_current_native_geometry_verified':True}

def propose_from_scene(dom,xml,offset=(0,0),page_size=None):
    """Pure deterministic proposal, with explicit unsupported records per context."""
    import auto_quality_source_vector_v2 as prior
    result={'policy':POLICY,'ok':False,'failures':[],'markers':[],'changed_edges':[],'candidate_xml':None,'requires_fresh_native_roi_editing_and_full_original_quality':True};objects={o['id']:o for o in dom['objects']};tree=E.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')};input_cells=copy.deepcopy(cells);cr=tree.find('.//mxGraphModel/root');contexts=dom.get('sceneMetadata',{}).get('markerContexts',{});page_size=page_size or dom.get('sceneCapture',{}).get('referenceSize');_require(page_size and len(page_size)==2,'missing_source_reference_page_size')
    try:
        _require(contexts,'no_explicit_source_marker_owner_contexts');_require(not any(issue.get('reason')=='marker_mid' for issue in dom.get('issues',[])),'source_marker_mid_has_no_verified_native_endpoint_representation');baseline=prior._paint_coverage(dom,xml);_require(baseline['ok'],'baseline_full_source_paint_geometry_not_proven',errors=baseline['errors'][:10]);translation=baseline['source_layout_translation'];_require(max(abs(translation[k]-offset[i]) for i,k in enumerate(('dx','dy')))<=.03,'baseline_canvas_translation_lacks_verified_source_registration');result['baseline_source_paint']=baseline;changed=set();consumed=set()
        for key,ctx in contexts.items():
            try:
                owner=objects.get(ctx['owner']);heads=[o for o in dom['objects'] if key in o.get('sceneMarkerContexts',[])];_require(owner is not None and len(heads)==1,'source_marker_is_not_single_paint_object',context=key);head=heads[0];side=ctx['side'];_require(side in ('start','end'),'source_marker_mid_has_no_verified_native_endpoint_representation',context=key);_require(ctx.get('ownerBBoxIsOriginalDocumentInstance') and not owner.get('sceneUseContexts'),'source_marker_owner_is_not_original_document_instance',context=key);_require(not ctx.get('selectorRisks') and not set(ctx.get('risks',[]))-{'synthetic_clone_does_not_apply_marker_viewport_clip'},'source_marker_clone_context_or_css_not_proven',context=key,risks=ctx.get('risks'));_require(ctx.get('refCoordinateInterpretationProven') and not ctx['viewBox']['w'] and not ctx['viewBox']['h'],'source_marker_viewbox_or_reference_coordinates_outside_first_exact_rule',context=key);_opaque_plain_paint(owner,True);_opaque_plain_paint(head);definition_css=ctx.get('definitionComputedCss',{});_require(all(abs(float(definition_css.get(name,1))-1)<1e-8 for name in ('opacity','fillOpacity','strokeOpacity')) and all(definition_css.get(name,'none')=='none' for name in ('filter','clipPath','maskImage')) and definition_css.get('mixBlendMode','normal')=='normal','source_marker_definition_compositing_not_proven',context=key)
                relevant_refs=set(owner.get('sceneAncestry',[])+head.get('sceneAncestry',[])+ctx.get('definitionAncestry',[]));ancestor_ids={dom['sceneMetadata']['ancestors'][ref].get('id','') for ref in relevant_refs};effects=[issue for issue in dom.get('issues',[]) if issue.get('reason') in ('filter','clipPath','maskImage','mix_blend_mode') and issue.get('id','') in ancestor_ids];_require(not effects,'source_marker_or_owner_ancestor_compositing_not_proven',context=key,issues=effects)
                geo=_triangle_geometry(head,owner,side);viewport=[tuple(p) for p in ctx.get('viewportScreenPolygon',[])];_require(len(viewport)==4 and all(_inside_convex(p,viewport) for p in geo['source_points']),'source_marker_paint_exceeds_actual_marker_viewport',context=key);edge=cells.get(owner['id']);_require(edge is not None and edge.get('edge')=='1' and edge.get('source') and edge.get('target'),'source_marker_owner_not_bound_to_both_native_terminals',context=key);_require(edge.get('source')!=edge.get('target'),'self_loop_requires_separate_native_marker_profile',context=key);_require(not any(c.get('parent')==edge.get('id') for c in cells.values()),'native_edge_children_need_position_preserving_marker_adapter',context=key);native_points=prior._edge_points(input_cells[owner['id']],input_cells);source_points=geo['source_owner_points'];_require(math.dist(native_points[0],(source_points[0][0]+offset[0],source_points[0][1]+offset[1]))<=.05 and math.dist(native_points[-1],(source_points[-1][0]+offset[0],source_points[-1][1]+offset[1]))<=.05,'native_owner_endpoint_not_at_original_source_endpoint',context=key);terminal=edge.get('source' if side=='start' else 'target');binding=_terminal_binding(terminal,geo['tip'],objects,cells,offset,page_size)
                other_side='end' if side=='start' else 'start';other_tip=source_points[-1] if other_side=='end' else source_points[0]
                for other_key,other_ctx in contexts.items():
                    if other_ctx['owner']==owner['id'] and other_ctx['side']==other_side:
                        other_heads=[o for o in dom['objects'] if other_key in o.get('sceneMarkerContexts',[])];_require(len(other_heads)==1,'other_source_marker_has_no_unique_head',context=other_key);other_tip=_triangle_geometry(other_heads[0],owner,other_side)['tip']
                other_binding=_terminal_binding(edge.get('target' if side=='start' else 'source'),other_tip,objects,cells,offset,page_size)
                head_cell=cells.get(head['id']);_require(head_cell is not None and head_cell.get('vertex')=='1' and head_cell.get('parent')=='1' and head['id'] not in consumed,'source_head_is_not_standalone_original_native_paint',context=key);style=unpack(edge.get('style'));_require(style.get(side+'Arrow','none')=='none','source_owner_already_has_native_marker',context=key);box=prior._world_box(cells[terminal],cells);endpoint=(geo['native_endpoint'][0]+offset[0],geo['native_endpoint'][1]+offset[1]);prefix='exit' if side=='start' else 'entry';style.update({side+'Arrow':geo['kind'],side+'Size':num(geo['size']),side+'Fill':'1',side+'FillColor':color(head['style']['fill']),side+'StrokeColor':'transparent',prefix+'X':num((endpoint[0]-box[0])/box[2]),prefix+'Y':num((endpoint[1]-box[1])/box[3]),prefix+'Perimeter':'0'});edge.set('style',pack(style));cr.remove(head_cell);consumed.add(head['id']);changed.add(owner['id']);result['markers'].append({'context':key,'edge':owner['id'],'side':side,'source_head_object':head['id'],'source_marker_definition':ctx['markerDefinitionId'],'native_marker':geo['kind'],'source_geometry':geo,'viewport_full_filled_triangle_containment_proven':True,'source_outline_binding':binding,'other_source_outline_binding':other_binding})
            except Unsupported as error:result['failures'].append({'reason':error.reason,'context':key,**error.evidence})
        _require(result['markers'],'no_marker_context_satisfies_exact_triangle_rule');candidate=E.tostring(tree,encoding='unicode');result.update(ok=True,changed_edges=sorted(changed),candidate_xml=candidate,input_code_sha256=sha(xml.encode()),candidate_code_sha256=sha(candidate.encode()),consumed_source_head_ids=sorted(consumed),reference_offset=list(offset),native_viewer_sha256=VIEWER_SHA256,implementation_sha256=sha(Path(__file__).read_bytes()),all_other_source_objects_and_assets_preserved=True,complete_source_marker_coverage=not result['failures'])
    except Unsupported as error:result['failures'].append({'reason':error.reason,**error.evidence})
    return result

def verify_candidate_from_scene(dom,before,after,proof,offset=(0,0)):
    """Replay from actual source facts; no proof flag or claimed fit is trusted."""
    replay=propose_from_scene(dom,before,offset)
    _require(replay['ok'],'source_native_triangle_candidate_not_replayable',failures=replay['failures'])
    _require(replay['candidate_xml']==after and replay['candidate_code_sha256']==proof.get('candidate_code_sha256'),'native_triangle_candidate_differs_from_source_replay')
    _require(replay['input_code_sha256']==proof.get('input_code_sha256') and replay['consumed_source_head_ids']==proof.get('consumed_source_head_ids'),'native_triangle_proof_input_or_consumed_source_heads_changed')
    return {'ok':True,'policy':POLICY,'source_rule_replayed':True,'all_other_native_cells_assets_text_and_geometry_unchanged':True,'marker_count':len(replay['markers']),'native_viewer_sha256':VIEWER_SHA256,'accepted':False}

def propose(record,xml):
    import auto_quality_source_vector_v2 as prior
    from auto_quality_svg_closed_scene_v1 import capture_closed_scene
    try:from auto_quality_common_v4 import registration_record
    except ImportError:from auto_quality_common_v3 import registration_record
    prior._identity(record,xml);reference=prior._read_clean(record['original_reference'],record['source_image_sha256']);_,contract=registration_record(record,reference,xml);offset=contract['original_page_offset'] if contract else [0,0];dom=capture_closed_scene(record);result=propose_from_scene(dom,xml,offset,dom['sceneCapture']['referenceSize']);prior._identity(record,xml);result.update(record_id=record['id'],input_code_sha256=record['code_sha256'],input_image_sha256=record['image_sha256'],source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],source_dom_sha256=sha(json.dumps(dom,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()));return result,dom
