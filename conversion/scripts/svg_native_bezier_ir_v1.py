"""Compile source L/Q/C segments to the pinned drawio native cubic connector.

Degree elevation and de Casteljau subdivision preserve the source curve. The
native getWaypoints method discards consecutive screen points less than one
pixel apart. Subdivision therefore stops before any cubic control is discarded;
the resulting source-derived terminal-span bound is recorded without a waiver.
"""
import math,re,hashlib
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path
from fontTools.misc.bezierTools import splitCubicAtT


def compile_path(path,matrix=(1,0,0,1,0,0),maximum_span=2.,maximum_points=12000):
    if not math.isfinite(maximum_span)or maximum_span<=0:
        raise ValueError('source_bezier_invalid_span')
    if re.search('[Aa]',path):
        return dict(mode='source_sampled_polyline',reason='elliptical_arc_requires_bounded_arc_compiler')
    pen=RecordingPen();parse_path(path,pen)
    a,b,c,d,e,f=matrix
    if not all(math.isfinite(v)for v in matrix)or a*d-b*c==0:
        raise ValueError('source_bezier_invalid_matrix')
    transform=lambda p:(a*p[0]+c*p[1]+e,b*p[0]+d*p[1]+f)
    current=None;segments=[];moves=0;has_curves=False
    for operation,values in pen.value:
        if operation=='moveTo':
            moves+=1
            if moves>1:raise ValueError('source_bezier_multiple_subpaths')
            current=transform(values[0])
        elif operation in ('lineTo','qCurveTo','curveTo'):
            points=[current]+[transform(p)for p in values]
            if operation=='lineTo':
                start,end=points
                points=[start,tuple((2*s+t)/3 for s,t in zip(start,end)),
                        tuple((s+2*t)/3 for s,t in zip(start,end)),end]
            elif operation=='qCurveTo':
                has_curves=True
                if len(points)!=3:raise ValueError('source_bezier_unexpanded_quadratic')
                start,control,end=points
                points=[start,tuple((s+2*t)/3 for s,t in zip(start,control)),
                        tuple((2*s+t)/3 for s,t in zip(control,end)),end]
            else:
                has_curves=True
                if len(points)!=4:raise ValueError('source_bezier_unexpanded_cubic')
            segments.append(points);current=points[-1]
        elif operation=='closePath':raise ValueError('source_bezier_closed_owner')
        elif operation!='endPath':raise ValueError('source_bezier_unknown_operation:'+operation)
    if not has_curves:return dict(mode='source_sampled_polyline',reason='source_has_no_bezier_segments')
    points=[];subdivisions=[]
    visited=0
    def retained(piece):
        return all(max(abs(p[0]-q[0]),abs(p[1]-q[1]))>=1.0001 for p,q in zip(piece,piece[1:]))
    def subdivide(piece,start=0.,end=1.,depth=0):
        nonlocal visited
        visited+=1
        if visited>maximum_points*2:raise ValueError('source_bezier_control_point_resource_bound')
        if not all(math.isfinite(v)for p in piece for v in p):
            raise ValueError('source_bezier_nonfinite_control')
        bound=3*max(math.dist(p,q)for p,q in zip(piece,piece[1:]))
        if bound>maximum_span and depth<20:
            left,right=splitCubicAtT(*piece,.5)
            if retained(left)and retained(right):
                mid=(start+end)/2
                return subdivide(left,start,mid,depth+1)+subdivide(right,mid,end,depth+1)
        if not retained(piece):
            # A repeated endpoint control is intrinsic to some valid cubics,
            # but the pinned target drops it. Do not silently change its degree.
            raise ValueError('native_bezier_control_filter_would_change_source_curve')
        return [(piece,start,end,bound)]
    for segment in segments:
        pieces=subdivide(segment)
        if len(points)+3*len(pieces)+1>maximum_points:
            raise ValueError('source_bezier_control_point_resource_bound')
        if not points:points.append(pieces[0][0][0])
        for piece,_,_,_ in pieces:points.extend(piece[1:])
        subdivisions.append(dict(segments=len(pieces),source_parameter_intervals=[[a,b]for _,a,b,_ in pieces],
                                 maximum_segment_arc_length_upper_bound_px=max(p[3]for p in pieces),
                                 terminal_segment_arc_length_upper_bound_px=pieces[-1][3]))
    if not all(math.isfinite(v)for point in points for v in point):
        raise ValueError('source_bezier_nonfinite_control')
    return dict(mode='native_cubic_bezier',points=[list(p)for p in points],
                source_path_sha256=hashlib.sha256(path.encode()).hexdigest(),
                matrix=list(matrix),subdivisions=subdivisions,requested_maximum_span_px=maximum_span,
                native_waypoint_filter_invariant=True,minimum_consecutive_control_Linf_px=1.0001,
                exact_degree_elevation_and_subdivision=True,style=dict(bezier='1',curved='0'))
