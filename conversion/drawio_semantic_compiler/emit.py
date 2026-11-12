"""Stage 5: emit native, editable draw.io XML from the IR.

One grammar, one attribute order, one number format, one escaping rule and no
insignificant whitespace, so equal IRs give equal bytes.
"""

from ir import CELL_OPTIONS
from source import xml_attributes
from syntax import format_number, format_style


def nonzero_attributes(keys, values):
    return [(key, format_number(value)) for key, value in zip(keys, values, strict=True) if value]


def point(values, role=None):
    pairs = nonzero_attributes(("x", "y"), values)
    if role is not None:
        pairs.append(("as", role))
    return f"<mxPoint{xml_attributes(pairs)}/>"


def geometry(g):
    pairs = nonzero_attributes(("x", "y", "width", "height"), (g.x, g.y, g.width, g.height))
    if g.relative:
        pairs.append(("relative", "1"))
    pairs.extend(g.attrs)
    pairs.append(("as", "geometry"))
    body = []
    if g.source_point is not None:
        body.append(point(g.source_point, "sourcePoint"))
    if g.target_point is not None:
        body.append(point(g.target_point, "targetPoint"))
    if g.points:
        body.append('<Array as="points">' + "".join(point(p) for p in g.points) + "</Array>")
    if g.offset is not None:
        body.append(point(g.offset, "offset"))
    if g.alternate_bounds is not None:
        bounds = nonzero_attributes(("x", "y", "width", "height"), g.alternate_bounds)
        body.append(f'<mxRectangle{xml_attributes(bounds + [("as", "alternateBounds")])}/>')
    body.extend(g.extras)
    if not body:
        return f"<mxGeometry{xml_attributes(pairs)}/>"
    return f"<mxGeometry{xml_attributes(pairs)}>{''.join(body)}</mxGeometry>"


def cell(page, c):
    pairs = []
    if c.wrapper is None:
        pairs.append(("id", c.name))
        if c.label is not None:
            pairs.append(("value", c.label))
    if c.style is not None:
        pairs.append(("style", format_style(c.style)))
    if c.kind == "vertex":
        pairs.append(("vertex", "1"))
    elif c.kind == "edge":
        pairs.append(("edge", "1"))
    for key in ("parent", "source", "target"):
        ref = getattr(c, key)
        if ref is not None:
            pairs.append((key, page.cells[ref].name))
    pairs.extend((key, "0" if default else "1")
                 for key, default in CELL_OPTIONS if getattr(c, key) != default)
    pairs.extend(c.attrs)
    body = ([geometry(c.geometry)] if c.geometry is not None else []) + list(c.extras)
    inner = f"<mxCell{xml_attributes(pairs)}>{''.join(body)}</mxCell>" if body else f"<mxCell{xml_attributes(pairs)}/>"
    if c.wrapper is None:
        return inner
    outer = ([("label", c.label)] if c.label is not None else []) + list(c.data) + [("id", c.name)]
    return f"<{c.wrapper}{xml_attributes(outer)}>{inner}{''.join(c.wrapper_extras)}</{c.wrapper}>"


def emit(document):
    out = [f"<mxfile{xml_attributes(document.attrs)}>"]
    for page in document.pages:
        pairs = ([("id", page.anchor)] if page.anchor is not None else []) + \
                ([("name", page.name)] if page.name is not None else []) + list(page.attrs)
        out.append(f"<diagram{xml_attributes(pairs)}><mxGraphModel{xml_attributes(page.model_attrs)}><root>")
        out.extend(cell(page, c) for c in page.walk())
        out.append("</root>" + "".join(page.model_extras) + "</mxGraphModel>" + "".join(page.extras)
                   + "</diagram>")
    out.extend(document.extras)
    out.append("</mxfile>\n")
    return "".join(out).encode("utf-8")
