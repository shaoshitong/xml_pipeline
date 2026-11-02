"""Analytic endpoint directions of one open SVG path, in source and screen space.

SVG2 paths.html#PathDirectionality and painting.html#OrientAttribute define the
directions. No sampled chords, reference pixels, or emitted native objects enter
this calculation. Degenerate controls use the first noncoincident control.
"""
import math
from fontTools.pens.recordingPen import RecordingPen
from fontTools.svgLib.path import parse_path
from fontTools.svgLib.path.arc import EllipticalArc


class _SVGArc(EllipticalArc):
    def draw(self, pen):
        if self.current_point==self.target_point:return
        if self.rx==0 or self.ry==0:
            pen.lineTo((self.target_point.real,self.target_point.imag))
        else:super().draw(pen)


def _unit(vector):
    length=math.hypot(*vector)
    if not math.isfinite(length) or length==0:
        raise ValueError('source_endpoint_direction_degenerate')
    return [vector[0]/length,vector[1]/length]


def directions(path, matrix=(1,0,0,1,0,0)):
    if len(matrix)!=6 or not all(math.isfinite(x)for x in matrix):
        raise ValueError('source_endpoint_direction_nonfinite_matrix')
    a,b,c,d,e,f=matrix
    if a*d-b*c==0:raise ValueError('source_endpoint_direction_singular_transform')
    pen=RecordingPen();parse_path(path,pen,arc_class=_SVGArc)
    segments=[];current=None;moves=0;closed=False
    for operation,points in pen.value:
        if any(not math.isfinite(value)for point in points if point is not None for value in point):
            raise ValueError('source_endpoint_direction_nonfinite_path')
        if operation=='moveTo':
            moves+=1
            if moves!=1:raise ValueError('source_endpoint_direction_multiple_subpaths')
            current=tuple(points[0])
        elif operation in ('lineTo','curveTo','qCurveTo'):
            if current is None or closed:raise ValueError('source_endpoint_direction_discontinuous_path')
            expected={'lineTo':1,'curveTo':3,'qCurveTo':2}[operation]
            if len(points)!=expected or any(p is None for p in points):
                raise ValueError('source_endpoint_direction_unexpanded_bezier')
            controls=[current]+[tuple(p)for p in points]
            segments.append((operation,controls));current=controls[-1]
        elif operation=='closePath':closed=True
        elif operation!='endPath':raise ValueError('source_endpoint_direction_unknown_operation:'+operation)
    if closed:raise ValueError('source_endpoint_direction_closed_owner')
    if not segments:raise ValueError('source_endpoint_direction_empty_owner')
    result={}
    for side in ('start','end'):
        endpoint=segments[0 if side=='start'else -1][1][0 if side=='start'else -1]
        order=range(len(segments))if side=='start'else reversed(range(len(segments)))
        witness=None
        for index in order:
            operation,controls=segments[index]
            base=controls[0 if side=='start'else -1]
            indices=range(1,len(controls))if side=='start'else reversed(range(len(controls)-1))
            for control_index in indices:
                control=controls[control_index]
                vector=(control[0]-base[0],control[1]-base[1])if side=='start'else(base[0]-control[0],base[1]-control[1])
                if vector!=(0,0):
                    witness=dict(segment=index,operation=operation,control=control_index)
                    break
            if witness is not None:break
        # SVG defines the positive x direction for an entirely zero-length path.
        if witness is None:vector=(1,0);witness=dict(entire_path_zero_length=True)
        local=_unit(vector);screen=_unit((a*local[0]+c*local[1],b*local[0]+d*local[1]))
        point=[a*endpoint[0]+c*endpoint[1]+e,b*endpoint[0]+d*endpoint[1]+f]
        outward=[-v for v in screen]if side=='start'else screen
        result[side]=dict(point_local=list(endpoint),point_screen=point,forward_local=local,
                          forward_screen=screen,outward_screen=outward,witness=witness)
    result['method']='SVG2_analytic_open_path_endpoint_direction_v1'
    result['source_path']=path;result['source_matrix']=list(matrix)
    return result


def marker_angle(endpoint,side,orient):
    """Marker rotation in the owner's local coordinate system, before its CTM."""
    if side not in ('start','end'):raise ValueError('source_marker_side_invalid')
    if orient in ('auto','auto-start-reverse'):
        vector=endpoint[side]['forward_local'];angle=math.degrees(math.atan2(vector[1],vector[0]))
        if orient=='auto-start-reverse'and side=='start':angle+=180
        return angle
    raise ValueError('source_endpoint_direction_marker_requires_automatic_orientation')
