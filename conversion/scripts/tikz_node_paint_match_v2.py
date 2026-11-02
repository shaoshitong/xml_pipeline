"""Match an executed node's own driver rectangle to the source PDF vector.

Ownership comes from PGF execution, never text-box containment, area ratios,
nearby nodes, or target pixels. Other path types remain explicit pending work.
"""
import hashlib
import math
import re

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from svg_convert_v2 import path_for

SOURCE_VECTOR_TOLERANCE_PX = .05  # Existing PGF/PDF vector agreement contract.
TOKEN = re.compile(r'\\pgfsyssoftpath@([A-Za-z]+)token\s*\{([^{}]+)\}\{([^{}]+)\}')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def dimension(value):
    require(re.fullmatch(r'[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)pt', value) is not None,
            'source_node_paint_dimension_not_literal')
    number = float(value[:-2])
    require(math.isfinite(number), 'source_node_paint_dimension_not_finite')
    return number


def _rectangle(points):
    points = [list(point) for point in points]
    if len(points) > 1 and math.dist(points[0], points[-1]) < 1e-7:
        points.pop()
    require(len(points) == 4 and all(all(math.isfinite(n) for n in p) for p in points),
            'source_node_paint_not_four_corner_rectangle')
    vectors = [[points[(i + 1) % 4][j] - points[i][j] for j in (0, 1)] for i in range(4)]
    lengths = [math.hypot(*v) for v in vectors]
    require(min(lengths) > 1e-7, 'source_node_paint_degenerate_rectangle')
    # TeX fixed-point rounding is checked only to identify the primitive type;
    # actual source-to-PDF agreement is still checked at every vector corner.
    require(all(abs(sum(vectors[i][j] * vectors[(i + 1) % 4][j] for j in (0, 1))) /
                (lengths[i] * lengths[(i + 1) % 4]) <= .0001 for i in range(4)),
            'source_node_paint_nonrectangular_contour_pending')
    return points


def source_rectangle(softpath, mapping):
    tokens = list(TOKEN.finditer(softpath))
    require(tokens and not TOKEN.sub('', softpath).strip(), 'source_node_paint_softpath_unsupported')
    operations = [(m[1], dimension(m[2]), dimension(m[3])) for m in tokens]
    kinds = [op[0] for op in operations]
    if kinds == ['rectcorner', 'rectsize']:
        _, x, y = operations[0]
        _, width, height = operations[1]
        points = [[x, y], [x + width, y], [x + width, y + height], [x, y + height]]
    else:
        require(kinds[0] == 'moveto' and kinds[-1] == 'closepath'
                and all(kind == 'lineto' for kind in kinds[1:-1]),
                'source_node_paint_curved_or_open_contour_pending')
        points = [[x, y] for _, x, y in operations[:-1]]
    a, b, c, d, tx, ty = mapping['matrix']
    require(all(math.isfinite(v) for v in (a, b, c, d, tx, ty)) and a > 0 and d < 0
            and abs(b) < 1e-10 and abs(c) < 1e-10,
            'source_node_paint_requires_proved_PGF_PDF_mapping')
    return _rectangle([[a * x + tx, d * y + ty] for x, y in points])


def actual_rectangle(obj):
    pen = RecordingPen()
    parse_path(path_for(obj), TransformPen(pen, tuple(obj['matrix'])))
    points = []
    closed = False
    for kind, values in pen.value:
        if kind == 'moveTo':
            require(not points, 'source_PDF_node_paint_multiple_subpaths_pending')
            points.append(values[0])
        elif kind == 'lineTo':
            points.append(values[0])
        elif kind == 'closePath':
            closed = True
        else:
            raise ValueError('source_PDF_node_paint_curved_or_open_contour_pending')
    require(closed, 'source_PDF_node_paint_open_contour_pending')
    return _rectangle(points)


def corner_error(expected, actual):
    require(len(expected) == len(actual) == 4, 'source_node_corner_inventory_changed')
    return min(max(math.dist(expected[i], ordered[(i + offset) % 4]) for i in range(4))
               for ordered in (actual, list(reversed(actual))) for offset in range(4))


def match_backgrounds(dom, paint_events, mapping, excluded=()):
    """Return exact source-owned rectangles and auditable vector agreements."""
    excluded = set(excluded)
    grouped = {}
    for paint in paint_events:
        require(paint['mode'] in ('fill', 'stroke', 'fillstroke'), 'source_node_driver_mode_unknown')
        current, processed = paint['current_softpath'], paint['processed_softpath']
        require(current and current == processed, 'source_node_actual_and_processed_softpath_differ')
        key = hashlib.sha256(current.encode()).hexdigest()
        item = grouped.setdefault(key, dict(path=current, modes=set(), sequences=[]))
        item['modes'].add(paint['mode'])
        item['sequences'].append(paint['sequence'])
    result = []
    proofs = []
    for digest, item in grouped.items():
        expected = source_rectangle(item['path'], mapping)
        fill = bool(item['modes'] & {'fill', 'fillstroke'})
        stroke = bool(item['modes'] & {'stroke', 'fillstroke'})
        candidates = []
        for obj in dom['objects']:
            if obj['type'] != 'shape' or obj['id'] in excluded:
                continue
            if (obj['style']['fill'] != 'none', obj['style']['stroke'] != 'none') != (fill, stroke):
                continue
            try:
                actual = actual_rectangle(obj)
            except (ValueError, KeyError):
                continue
            error = corner_error(expected, actual)
            if error <= SOURCE_VECTOR_TOLERANCE_PX:
                candidates.append((obj, error))
        require(len(candidates) == 1, 'executed_node_driver_rectangle_not_uniquely_matched_to_PDF')
        obj, error = candidates[0]
        require(obj['id'] not in {x['id'] for x in result}, 'executed_node_driver_shape_reused')
        result.append(obj)
        proofs.append(dict(source_object=obj['id'], source_driver_softpath_sha256=digest,
                           source_driver_sequences=item['sequences'], source_driver_modes=sorted(item['modes']),
                           maximum_corner_error_px=error, tolerance_px=SOURCE_VECTOR_TOLERANCE_PX,
                           source_execution_ownership=True, target_pixels_used=False))
    return result, proofs
