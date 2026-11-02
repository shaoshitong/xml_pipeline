"""Exact PGF driver ownership for closed PDF line/cubic node contours.

No text bounding-box/area rule, raster fitting, flattening, or vertex guessing.
Every original line endpoint and cubic control point must match the PDF scene.
"""
import hashlib
import math

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from svg_convert_v2 import path_for
from tikz_node_paint_match_v2 import TOKEN, dimension, require, SOURCE_VECTOR_TOLERANCE_PX


def _without_terminal_moveto_state(operations):
    operations = list(operations)
    # PGF's rounded path lowering emits Z followed by a point-reset moveto.
    # A moveto with no drawing command is not stroked (SVG2, painting 13.5.1).
    # Keep the original full path hash/provenance; normalize only this terminal
    # nonpainting state for ownership comparison. A second drawn subpath fails.
    while operations:
        if operations[-1][0] == 'moveTo':
            operations.pop()
        elif len(operations) >= 2 and operations[-1][0] == 'endPath' and operations[-2][0] == 'moveTo':
            operations = operations[:-2]
        else:
            break
    return operations


def _segments(operations):
    operations = _without_terminal_moveto_state(operations)
    require(operations and operations[0][0] == 'moveTo' and operations[-1][0] == 'closePath',
            'source_node_paint_requires_one_complete_closed_contour')
    start = operations[0][1][0]
    current = start
    segments = []
    for kind, points in operations[1:-1]:
        require(kind in ('lineTo', 'curveTo') and len(points) == (1 if kind == 'lineTo' else 3),
                'source_node_paint_multiple_subpaths_or_unknown_operator_pending')
        require(all(len(point) == 2 and all(math.isfinite(value) for value in point) for point in points),
                'source_node_paint_control_point_not_finite')
        segments.append((kind, tuple(tuple(point) for point in [current, *points])))
        current = points[-1]
    if math.dist(current, start) > 1e-7:
        segments.append(('lineTo', (tuple(current), tuple(start))))
    require(segments, 'source_node_paint_empty_contour')
    return segments


def source_contour(softpath, mapping):
    tokens = list(TOKEN.finditer(softpath))
    require(tokens and not TOKEN.sub('', softpath).strip(), 'source_node_paint_softpath_unsupported')
    parsed = [(token[1], (dimension(token[2]), dimension(token[3]))) for token in tokens]
    if [kind for kind, point in parsed] == ['rectcorner', 'rectsize']:
        x, y = parsed[0][1]
        width, height = parsed[1][1]
        operations = [('moveTo', [(x, y)]), ('lineTo', [(x + width, y)]),
                      ('lineTo', [(x + width, y + height)]), ('lineTo', [(x, y + height)]),
                      ('closePath', [])]
    else:
        operations = []
        index = 0
        while index < len(parsed):
            kind, point = parsed[index]
            if kind in ('moveto', 'lineto', 'closepath'):
                operations.append(({'moveto': 'moveTo', 'lineto': 'lineTo', 'closepath': 'closePath'}[kind],
                                   [] if kind == 'closepath' else [point]))
                index += 1
            elif kind == 'curvetosupporta':
                require([item[0] for item in parsed[index:index + 3]] ==
                        ['curvetosupporta', 'curvetosupportb', 'curveto'],
                        'source_node_paint_cubic_control_coverage_incomplete')
                operations.append(('curveTo', [item[1] for item in parsed[index:index + 3]]))
                index += 3
            else:
                raise ValueError('source_node_paint_softpath_operator_pending:' + kind)
    a, b, c, d, tx, ty = mapping['matrix']
    require(all(math.isfinite(value) for value in (a, b, c, d, tx, ty)) and a > 0 and d < 0
            and abs(b) < 1e-10 and abs(c) < 1e-10,
            'source_node_paint_requires_proved_PGF_PDF_mapping')
    return _segments([(kind, [(a * x + tx, d * y + ty) for x, y in points])
                      for kind, points in operations])


def actual_contour(obj, with_evidence=False):
    pen = RecordingPen()
    parse_path(path_for(obj), TransformPen(pen, tuple(obj['matrix'])))
    operations = _without_terminal_moveto_state(pen.value)
    evidence = {'implicit_smooth_closed_cycle_equivalent': False}
    if operations and operations[-1][0] == 'endPath':
        # MuPDF can expose PGF's already closed rounded contour as an open
        # smooth cycle. Prove zero closing length and equal end tangents with
        # butt caps/no dashes before ownership-only canonicalization. Keep the
        # original native SVG path unchanged. SVG2 13.5.7 gives an empty join
        # when incoming/outgoing tangents coincide.
        require(operations[0][0] == 'moveTo' and len(operations) >= 4,
                'source_PDF_node_paint_open_contour_pending')
        first, last = operations[1], operations[-2]
        require(first[0] in ('lineTo', 'curveTo') and last[0] in ('lineTo', 'curveTo'),
                'source_PDF_node_paint_open_contour_pending')
        start = operations[0][1][0]
        end = last[1][-1]
        initial_control = first[1][0]
        last_start = operations[-3][1][-1]
        final_control = last[1][-2] if last[0] == 'curveTo' else last_start
        forward = [initial_control[i] - start[i] for i in (0, 1)]
        incoming = [end[i] - final_control[i] for i in (0, 1)]
        norms = math.hypot(*forward) * math.hypot(*incoming)
        require(math.dist(start, end) < 1e-7 and norms > 1e-12
                and abs(forward[0] * incoming[1] - forward[1] * incoming[0]) / norms < 1e-10
                and sum(a * b for a, b in zip(forward, incoming)) / norms > 1 - 1e-10
                and obj['style'].get('linecap') == 'butt' and obj['style'].get('dash') == 'none'
                and obj.get('markerStart', 'none') == obj.get('markerEnd', 'none') == 'none',
                'source_PDF_open_contour_has_no_exact_smooth_closed_cycle_proof')
        operations[-1] = ('closePath', [])
        evidence['implicit_smooth_closed_cycle_equivalent'] = True
    segments = _segments(operations)
    return (segments, evidence) if with_evidence else segments


def contour_error(expected, actual):
    if len(expected) != len(actual):
        return float('inf')
    reverse = [(kind, tuple(reversed(points))) for kind, points in reversed(actual)]
    errors = []
    for order in (actual, reverse):
        for shift in range(len(order)):
            rotated = order[shift:] + order[:shift]
            if any(a[0] != b[0] or len(a[1]) != len(b[1]) for a, b in zip(expected, rotated)):
                continue
            errors.append(max(math.dist(left, right) for a, b in zip(expected, rotated)
                              for left, right in zip(a[1], b[1])))
    return min(errors, default=float('inf'))


def match_backgrounds(dom, paint_events, mapping, excluded=()):
    excluded = set(excluded)
    grouped = {}
    for paint in paint_events:
        require(paint['mode'] in ('fill', 'stroke', 'fillstroke'), 'source_node_driver_mode_unknown')
        current, processed = paint['current_softpath'], paint['processed_softpath']
        require(current and current == processed, 'source_node_actual_and_processed_softpath_differ')
        digest = hashlib.sha256(current.encode()).hexdigest()
        item = grouped.setdefault(digest, dict(path=current, modes=set(), sequences=[]))
        item['modes'].add(paint['mode'])
        item['sequences'].append(paint['sequence'])
    results, proofs = [], []
    for digest, item in grouped.items():
        expected = source_contour(item['path'], mapping)
        modes = (bool(item['modes'] & {'fill', 'fillstroke'}), bool(item['modes'] & {'stroke', 'fillstroke'}))
        matches = []
        for obj in dom['objects']:
            if obj['type'] != 'shape' or obj['id'] in excluded:
                continue
            if (obj['style']['fill'] != 'none', obj['style']['stroke'] != 'none') != modes:
                continue
            try:
                actual, evidence = actual_contour(obj, with_evidence=True)
            except (ValueError, KeyError):
                continue
            error = contour_error(expected, actual)
            if error <= SOURCE_VECTOR_TOLERANCE_PX:
                matches.append((obj, error, evidence))
        require(len(matches) == 1, 'executed_node_driver_contour_not_uniquely_matched_to_PDF')
        obj, error, evidence = matches[0]
        require(obj['id'] not in {value['id'] for value in results}, 'executed_node_driver_shape_reused')
        results.append(obj)
        proofs.append(dict(source_object=obj['id'], source_driver_softpath_sha256=digest,
                           source_driver_sequences=item['sequences'], source_driver_modes=sorted(item['modes']),
                           maximum_control_point_error_px=error, tolerance_px=SOURCE_VECTOR_TOLERANCE_PX,
                           source_line_segments=sum(kind == 'lineTo' for kind, points in expected),
                           source_cubic_segments=sum(kind == 'curveTo' for kind, points in expected),
                           original_complete_driver_path_hash_retained=True,
                           terminal_moveto_only_state_has_no_painted_segment=True,
                           actual_PDF_contour_canonicalization=evidence,
                           source_execution_ownership=True, target_pixels_used=False))
    return results, proofs
