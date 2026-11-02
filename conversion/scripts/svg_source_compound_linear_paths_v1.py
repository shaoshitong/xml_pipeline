"""Represent every straight open SVG subpath as its own editable native edge.

This transforms only the semantic observation consumed by the native emitter.
The original SVG, source browser capture and reference bytes remain untouched.
Curves, markers, transparency, effects and use instances are not approximated.
"""
import copy, hashlib, math
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path

POLICY='source_exact_opaque_straight_open_subpaths_to_independent_native_edges_v1'

def _need(value, reason):
    if not value:raise ValueError(reason)

def expand(dom):
    result=copy.deepcopy(dom);objects=[];ids={o['id']for o in result['objects']}
    proofs=list(result.get('sourceCompoundLinearPaths',[]))
    ancestors=result.get('sceneMetadata',{}).get('ancestors',{})
    for original in result['objects']:
        if original.get('type')!='shape' or original.get('tag')!='path' or original.get('style',{}).get('fill')!='none':
            objects.append(original);continue
        path=original.get('d')or'';pen=RecordingPen();parse_path(path,pen)
        if sum(operation=='moveTo'for operation,_ in pen.value)<2:
            objects.append(original);continue
        # Leave genuinely unsupported representations to the original rejector.
        if any(operation not in ('moveTo','lineTo','endPath')for operation,_ in pen.value):
            objects.append(original);continue
        style=original['style'];css=original.get('sceneComputedCss',{})
        _need(style.get('stroke')not in ('none',None)and float(style.get('strokeWidth',0))>0,'compound_path_requires_visible_stroke')
        _need(style.get('linecap')=='butt'and style.get('linejoin')=='miter','compound_path_cap_or_join_requires_another_native_mapping')
        _need(all(float(style.get(k,1))==1 for k in ('opacity','strokeOpacity'))and css.get('strokeColorAlpha')==1,'compound_path_nonopaque_stroke_requires_union_compositing')
        _need(not original.get('markerOwner')and not original.get('sceneMarkerContexts')and not original.get('sceneUseContexts'),'compound_path_marker_or_use_requires_separate_ownership')
        _need(all(original.get(k,'none')in ('none',None)for k in ('markerStart','markerEnd')),'compound_path_markers_require_per_subpath_mapping')
        _need(all(float(ancestors[ref]['opacity'])==1 for ref in original.get('sceneAncestry',[])),'compound_path_ancestor_alpha_requires_union_compositing')
        _need(css.get('mixBlendMode','normal')=='normal'and css.get('isolation','auto')=='auto'and all(css.get(k,'none')=='none'for k in ('filter','clipPath','maskImage')),'compound_path_effect_requires_union_compositing')
        _need(float(str(css.get('strokeDashoffset','0')).replace('px',''))==0,'compound_path_dash_phase_requires_separate_mapping')
        matrix=original['matrix'];_need(len(matrix)==6 and all(math.isfinite(v)for v in matrix),'compound_path_nonfinite_source_matrix')
        a,b,c,d,e,f=matrix
        _need(a*d-b*c!=0,'compound_path_singular_source_matrix')
        parts=[];current=None
        for operation,values in pen.value:
            if operation=='moveTo':
                if current is not None:parts.append(current)
                current=[tuple(values[0])]
            elif operation=='lineTo':
                _need(current is not None,'compound_path_draw_before_move');current.append(tuple(values[0]))
            elif operation=='endPath':
                if current is not None:parts.append(current);current=None
        if current is not None:parts.append(current)
        _need(2<=len(parts)<=256,'compound_path_subpath_resource_bound')
        _need(all(len(part)>=2 and all(math.isfinite(v)for p in part for v in p)for part in parts),'compound_path_empty_or_nonfinite_subpath')
        world=lambda p:(a*p[0]+c*p[1]+e,b*p[0]+d*p[1]+f)
        all_points=[world(p)for part in parts for p in part];xs=[p[0]for p in all_points];ys=[p[1]for p in all_points]
        union=dict(x=min(xs),y=min(ys),w=max(xs)-min(xs),h=max(ys)-min(ys))
        _need(all(abs(union[k]-original['bbox'][k])<=.03 for k in union),'compound_path_original_browser_bounds_differ_from_exact_source_vertices')
        children=[]
        for index,part in enumerate(parts):
            identifier=original['id']+'__compound_segment_'+str(index+1)
            _need(identifier not in ids,'compound_path_generated_ID_collision');ids.add(identifier)
            points=[world(p)for p in part];xs=[p[0]for p in points];ys=[p[1]for p in points]
            child=copy.deepcopy(original);child.update(id=identifier,d='M'+repr(part[0][0])+','+repr(part[0][1])+' '+ ' '.join('L'+repr(x)+','+repr(y)for x,y in part[1:]),
                bbox=dict(x=min(xs),y=min(ys),w=max(xs)-min(xs),h=max(ys)-min(ys)),sampledPoints=[list(p)for p in points],endpoints=[list(points[0]),list(points[-1])],sceneCompoundOriginalId=original['id'],sceneCompoundPartIndex=index)
            child['sceneGeometry']=dict(matrix=copy.deepcopy(original.get('sceneGeometry',{}).get('matrix',{})),closure=False,
                sampledPoints=[list(p)for p in points],samplingBasis='Exact original straight subpath vertices under original affine CTM; no curve sampling',
                topology=dict(subpaths=[dict(closed=False,operations=[dict(operation='moveTo'if i==0 else'lineTo',points=[list(p)])for i,p in enumerate(part)]+[dict(operation='endPath',points=[])])]))
            children.append(dict(id=identifier,index=index,local_vertices=[list(p)for p in part],world_vertices=[list(p)for p in points],path_sha256=hashlib.sha256(child['d'].encode()).hexdigest()))
            objects.append(child)
        proofs.append(dict(original_object=original['id'],original_path_sha256=hashlib.sha256(path.encode()).hexdigest(),matrix=list(matrix),original_browser_bbox=original['bbox'],exact_vertex_union_bbox=union,children=children,
            all_original_subpaths_accounted=True,source_vertex_order_preserved=True,source_style_and_scene_ancestry_inherited=True,reference_pixels_used=False,policy=POLICY))
    _need(len(objects)<=20000,'compound_path_expanded_object_resource_bound')
    result['objects']=objects;result['sourceCompoundLinearPaths']=proofs
    return result

def controls():
    def source(path):
        return dict(objects=[dict(id='path',type='shape',tag='path',d=path,matrix=[1,0,0,1,0,0],bbox=dict(x=0,y=0,w=40,h=30),style=dict(fill='none',stroke='black',strokeWidth=1,linecap='butt',linejoin='miter',opacity=1,strokeOpacity=1),sceneComputedCss=dict(strokeColorAlpha=1),sceneAncestry=[])],sceneMetadata=dict(ancestors={}))
    dom=source('M0,0 L20,10 M20,10 L40,30');before=copy.deepcopy(dom);out=expand(dom)
    checks=dict(two_edges_preserve_all_source_vertices=[o['sampledPoints']for o in out['objects']]==[[[0,0],[20,10]],[[20,10],[40,30]]],original_observation_unchanged=dom==before,idempotent=expand(out)==out)
    for name,change in [('alpha',lambda o:o['style'].update(strokeOpacity=.5)),('marker',lambda o:o.update(markerEnd='url(#arrow)')),('rounded_cap',lambda o:o['style'].update(linecap='round'))]:
        bad=copy.deepcopy(dom);change(bad['objects'][0])
        try:expand(bad);checks['reject_'+name]=False
        except ValueError:checks['reject_'+name]=True
    curve=source('M0,0 Q10,0 20,10 M20,10 L40,30');checks['curves_not_linearized']=expand(curve)['objects']==curve['objects']
    closed=source('M0,0 L20,10 Z M20,10 L40,30');checks['closed_subpaths_not_discarded']=expand(closed)['objects']==closed['objects']
    _need(all(checks.values()),'compound_path_control_failure:'+str(checks));return checks
