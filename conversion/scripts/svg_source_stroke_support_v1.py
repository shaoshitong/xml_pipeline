"""Conservative source paint supports for overlap ordering, never raster fitting.

Unfilled path supports are unions of stroke-expanded Bezier control hull boxes.
Unknown or filled geometry retains a whole-object box. False overlap is allowed;
missing real overlap is not. Every Bezier split is exact de Casteljau subdivision.
"""
import math


def overlap(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def box(points, pad):
    return (min(p[0] for p in points)-pad, min(p[1] for p in points)-pad,
            max(p[0] for p in points)+pad, max(p[1] for p in points)+pad)


def supports(obj):
    st = obj.get('style', {})
    css = obj.get('sceneComputedCss', {})
    m = obj.get('matrix', [1, 0, 0, 1, 0, 0])
    # Frobenius norm upper-bounds the transform's largest singular value.
    norm = math.sqrt(sum(float(v)**2 for v in m[:4]))
    width = float(st.get('strokeWidth', 0)) if st.get('stroke') != 'none' else 0
    miter = max(1., float(css.get('strokeMiterlimit', 4))) if st.get('linejoin') == 'miter' else 1.
    pad = width * norm * max(miter, math.sqrt(2.)) / 2 + .002
    b = obj['bbox']
    broad = (b['x']-pad, b['y']-pad, b['x']+b['w']+pad, b['y']+b['h']+pad)
    if obj.get('type') != 'shape' or st.get('fill') != 'none' or not width:
        return [broad]
    topology = obj.get('sceneGeometry', {}).get('topology', {})
    if not topology.get('subpaths'):
        return [broad]
    regions = []

    def world(p):
        x, y = map(float, p)
        return (m[0]*x + m[2]*y + m[4], m[1]*x + m[3]*y + m[5])

    def subdivide(points, depth=0):
        bound = box(points, pad)
        if depth >= 6 or max(bound[2]-bound[0], bound[3]-bound[1]) <= 8 + 2*pad:
            regions.append(bound)
            return
        levels = [points]
        while len(levels[-1]) > 1:
            levels.append([((a[0]+b[0])/2, (a[1]+b[1])/2)
                           for a, b in zip(levels[-1], levels[-1][1:])])
        subdivide([row[0] for row in levels], depth+1)
        subdivide([row[-1] for row in reversed(levels)], depth+1)

    try:
        for subpath in topology['subpaths']:
            point = first = None
            for op in subpath['operations']:
                kind = op['operation']
                ps = [world(p) for p in op['points']]
                if kind == 'moveTo' and len(ps) == 1:
                    point = first = ps[0]
                elif kind in ('lineTo', 'curveTo', 'qCurveTo') and point is not None:
                    expected = {'lineTo': 1, 'curveTo': 3, 'qCurveTo': 2}[kind]
                    if len(ps) != expected:
                        return [broad]
                    subdivide([point, *ps])
                    point = ps[-1]
                elif kind == 'closePath' and point is not None and first is not None:
                    subdivide([point, first])
                    point = first
                elif kind != 'endPath':
                    return [broad]
        if not regions or not all(math.isfinite(v) for r in regions for v in r):
            return [broad]
        return regions
    except (TypeError, ValueError, KeyError, OverflowError):
        return [broad]


def may_overlap(a, b, cache):
    for obj in (a, b):
        if obj['id'] not in cache:
            cache[obj['id']] = supports(obj)
    ra, rb = cache[a['id']], cache[b['id']]
    ba = (min(r[0] for r in ra), min(r[1] for r in ra), max(r[2] for r in ra), max(r[3] for r in ra))
    bb = (min(r[0] for r in rb), min(r[1] for r in rb), max(r[2] for r in rb), max(r[3] for r in rb))
    return overlap(ba, bb) and any(overlap(x, y) for x in ra for y in rb)
