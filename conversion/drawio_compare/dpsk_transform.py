#!/usr/bin/env python3
"""Metamorphic input generator for a draw.io compiler generalization test.

Usage:
    python3 transform.py SOURCE_DIRECTORY OUTPUT_DIRECTORY

Every input is a draw.io file named CASE.drawio.  For each case we emit
several independently useful variants under OUTPUT_DIRECTORY/CASE/ and a
manifest at OUTPUT_DIRECTORY/manifest.json.

The positive transformations are chosen so that the rendered diagram should
be unchanged:

  * format variants move between plain <mxGraphModel> XML and the standard
    draw.io compressed representation (URI-encoded raw DEFLATE + Base64);
  * editable variants move between plain <mxCell> cells and <object> user
    object wrappers;
  * nesting variants insert two real, invisible draw.io group levels and
    rewrite child coordinates / edge waypoints so that absolute positions are
    preserved;
  * combination variants stack nesting, user objects and compression.

Two deliberately altered negative controls are also emitted.  They are the
only variants whose render is supposed to differ from the source.

Only the Python standard library is used.  Source files are only read.
"""

from __future__ import annotations

import argparse
import base64
import copy
import html
import json
import sys
import urllib.parse
import zlib
from decimal import Decimal, InvalidOperation
from pathlib import Path
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Variant catalogue
# ---------------------------------------------------------------------------

VARIANT_SPECS = [
    {
        "name": "format_uncompressed",
        "category": "format",
        "output": "plain",
        "applicability": (
            "Every source whose diagram payload can be decoded, whether it is "
            "already plain <mxGraphModel> XML or standard draw.io compressed XML."
        ),
        "summary": (
            "Re-emit every diagram as uncompressed <mxGraphModel> XML.  No cell, "
            "style or geometry is changed."
        ),
    },
    {
        "name": "format_compressed",
        "category": "format",
        "output": "compressed",
        "applicability": (
            "Every source whose diagram payload can be decoded.  Inputs already "
            "in compressed form are decoded and re-encoded by this generator."
        ),
        "summary": (
            "Re-emit every diagram as a draw.io compressed payload using "
            "URI-encoded raw DEFLATE and standard Base64.  Model content is unchanged."
        ),
    },
    {
        "name": "editable_userobjects",
        "category": "editable",
        "output": "plain",
        "applicability": (
            "Any source containing at least one non-root plain <mxCell>.  Cells that "
            "are already <object>/<UserObject> wrappers are left alone."
        ),
        "summary": (
            "Move id/value from non-root <mxCell> elements into <object label=... id=...> "
            "editable user-object wrappers while style, parent, geometry and edges remain "
            "on the inner mxCell."
        ),
    },
    {
        "name": "editable_plaincells",
        "category": "editable",
        "output": "plain",
        "applicability": (
            "Any source containing <object> or <UserObject> wrappers that contain exactly "
            "one mxCell and do not use placeholders=... (placeholders are kept untouched "
            "because flattening them could change label resolution)."
        ),
        "summary": (
            "Flatten editable user-object wrappers back to plain <mxCell> elements, moving "
            "label->value and wrapper id->cell id."
        ),
    },
    {
        "name": "nesting_all_two_levels",
        "category": "nesting",
        "output": "plain",
        "applicability": (
            "Any source with at least one visible vertex directly parented to root cell '1' "
            "that has positive width and height."
        ),
        "summary": (
            "Add two new real nested group levels under root cell '1' around every directly "
            "root-parented cell.  Child x/y and edge waypoints are shifted by the cumulative "
            "new group offset so absolute coordinates do not change."
        ),
    },
    {
        "name": "nesting_existing_group_two_levels",
        "category": "nesting",
        "output": "plain",
        "applicability": (
            "Any source containing a plain style='group' cell with visible direct vertex "
            "children and usable geometry."
        ),
        "summary": (
            "Add two new nested group levels inside an existing real group and move its "
            "direct children beneath them, preserving absolute positions."
        ),
    },
    {
        "name": "combo_nesting_userobjects_compressed",
        "category": "nesting",
        "output": "compressed",
        "applicability": (
            "Requires the top-level two-level nesting applicability.  User-object wrapping is "
            "applied when plain cells are available; compression is always applied."
        ),
        "summary": (
            "Stack top-level two-level nesting, editable <object> wrappers and compressed XML "
            "in one positive variant to stress combined coordinate and decoder handling."
        ),
    },
    {
        "name": "combo_inner_nesting_userobjects_plain",
        "category": "nesting",
        "output": "plain",
        "applicability": (
            "Requires an existing plain group with visible direct vertex children.  "
            "User-object wrapping is applied when plain cells are available."
        ),
        "summary": (
            "Stack inner two-level group nesting and editable <object> wrappers in plain XML, "
            "adding depth inside an existing group."
        ),
    },
    {
        "name": "negative_geometry_shift",
        "category": "negative",
        "output": "plain",
        "applicability": (
            "Any source with a visible, non-table vertex carrying numeric geometry.  This is a "
            "negative control and is intentionally not render-preserving."
        ),
        "summary": (
            "Intentionally translate one visible cell by (+40,+30) in its parent coordinate "
            "system.  Positive variants are unaffected by this negative category."
        ),
    },
    {
        "name": "negative_content_change",
        "category": "negative",
        "output": "plain",
        "applicability": (
            "Any source with a visible vertex whose value/label is non-empty.  This is a "
            "negative control and is intentionally not render-preserving."
        ),
        "summary": (
            "Intentionally replace one visible label with 'DSH NEGATIVE'.  Positive variants "
            "are unaffected by this negative category."
        ),
    },
]

SPEC_BY_NAME = {spec["name"]: spec for spec in VARIANT_SPECS}

_ZERO = Decimal(0)
_FIVE = Decimal(5)
_FORTY = Decimal(40)
_THIRTY = Decimal(30)


# ---------------------------------------------------------------------------
# Small XML helpers
# ---------------------------------------------------------------------------


def _local(tag):
    """Return an XML local name, tolerating comments and namespaced tags."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _children(elem, name):
    if elem is None:
        return []
    return [child for child in list(elem) if _local(child.tag) == name]


def _first_child(elem, name):
    if elem is None:
        return None
    for child in list(elem):
        if _local(child.tag) == name:
            return child
    return None


def _model_root(model):
    """Find the <root> cell container of an <mxGraphModel> element."""
    if model is None:
        return None
    if _local(model.tag) == "root":
        return model
    if _local(model.tag) not in ("mxGraphModel", "mxfile", "diagram"):
        return None
    return _first_child(model, "root")


# ---------------------------------------------------------------------------
# Numeric helpers (Decimal keeps source coordinates exact)
# ---------------------------------------------------------------------------


def _read_decimal(elem, attr, missing=_ZERO):
    """Read a finite Decimal attribute.  None means the value is unsafe."""
    if elem is None:
        return missing
    raw = elem.get(attr)
    if raw is None:
        return missing
    raw = raw.strip()
    if not raw:
        return _ZERO
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite():
        return None
    return value


def _fmt_decimal(value):
    """Format a Decimal in a draw.io-friendly, compact, non-exponential form."""
    if value == value.to_integral_value():
        return str(int(value))
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


# ---------------------------------------------------------------------------
# draw.io compressed payloads
# ---------------------------------------------------------------------------


def _b64decode_any(text):
    """Decode standard or URL-safe Base64, tolerating percent encoding."""
    compact = "".join(text.split())
    if not compact or compact.startswith("<"):
        return None
    candidates = [compact]
    unquoted = urllib.parse.unquote(compact)
    if unquoted != compact:
        candidates.append(unquoted)
    for candidate in candidates:
        b64 = candidate.replace("-", "+").replace("_", "/")
        b64 += "=" * (-len(b64) % 4)
        try:
            return base64.b64decode(b64, validate=True)
        except Exception:
            continue
    return None


def _inflate_any(raw):
    # raw DEFLATE is the draw.io standard; zlib/gzip are accepted defensively.
    for wbits in (-15, 15, 31, 47):
        try:
            return zlib.decompress(raw, wbits)
        except zlib.error:
            continue
    return None


def _parse_xml_payload(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError("payload XML parse error: %s" % exc) from exc

    tag = _local(root.tag)
    if tag == "mxGraphModel":
        return root
    if tag == "mxfile":
        diagrams = _children(root, "diagram")
        if len(diagrams) != 1:
            raise ValueError("payload <mxfile> must contain exactly one <diagram>")
        diagram = diagrams[0]
        model = _first_child(diagram, "mxGraphModel")
        if model is not None:
            return model
        if (diagram.text or "").strip():
            return _decode_payload_text(diagram.text)
        raise ValueError("payload <diagram> has no model")
    if tag == "diagram":
        model = _first_child(root, "mxGraphModel")
        if model is not None:
            return model
        if (root.text or "").strip():
            return _decode_payload_text(root.text)
        raise ValueError("payload <diagram> has no model")
    raise ValueError("unsupported payload root <%s>" % tag)


def _decode_payload_text(text):
    """Decode a <diagram> text payload into an <mxGraphModel> element."""
    stripped = str(text or "").strip().lstrip("\ufeff")
    if not stripped:
        raise ValueError("diagram payload is empty")

    # A few tools put plain (sometimes HTML-escaped) XML into diagram.text.
    if stripped.startswith("<"):
        return _parse_xml_payload(stripped)
    if stripped.startswith("&lt;"):
        return _parse_xml_payload(html.unescape(stripped))

    # Defensive: percent-encoded XML in a text node.
    unquoted = urllib.parse.unquote(stripped)
    if unquoted.lstrip().startswith("<"):
        return _parse_xml_payload(unquoted.lstrip())
    if unquoted.lstrip().startswith("&lt;"):
        return _parse_xml_payload(html.unescape(unquoted).lstrip())

    raw = _b64decode_any(stripped)
    if raw is None:
        raise ValueError("diagram text is neither XML nor valid Base64")

    inflated = _inflate_any(raw)
    if inflated is None:
        # Some non-standard producers Base64-encode XML without compressing it.
        try:
            maybe = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            maybe = ""
        if maybe.lstrip().startswith("<"):
            return _parse_xml_payload(maybe)
        raise ValueError("Base64 payload could not be inflated as raw DEFLATE or zlib")

    try:
        xml_text = inflated.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("inflated payload is not UTF-8: %s" % exc) from exc

    candidates = []
    for candidate in (
        xml_text,
        urllib.parse.unquote(xml_text),
        html.unescape(xml_text),
        urllib.parse.unquote(html.unescape(xml_text)),
        urllib.parse.unquote_plus(xml_text),
    ):
        candidate = candidate.strip()
        if candidate and candidate.startswith("<") and candidate not in candidates:
            candidates.append(candidate)

    errors = []
    for candidate in candidates:
        try:
            return _parse_xml_payload(candidate)
        except (ET.ParseError, ValueError) as exc:
            errors.append(str(exc))
    detail = errors[0] if errors else "no parseable XML candidate"
    raise ValueError("inflated payload did not contain parseable mxGraphModel XML: %s" % detail)


def _encode_payload(model):
    """Encode an <mxGraphModel> exactly the way draw.io compresses diagrams."""
    clone = copy.deepcopy(model)
    clone.tail = None
    xml_text = ET.tostring(clone, encoding="unicode")
    # encodeURIComponent's unreserved set, which is what draw.io uses.
    encoded = urllib.parse.quote(
        xml_text, safe="-_.!~*'()", encoding="utf-8", errors="strict"
    )
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    compressed = compressor.compress(encoded.encode("utf-8")) + compressor.flush()
    return base64.b64encode(compressed).decode("ascii")


# ---------------------------------------------------------------------------
# File loading / serialization
# ---------------------------------------------------------------------------


def load_case(path):
    """Return (mxfile_element, payloads).

    payloads is a list of dicts with the source diagram element, its decoded
    mxGraphModel element, and whether the source carried a compressed/text
    payload rather than a plain child model.
    """
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise ValueError("XML parse error: %s" % exc) from exc
    except OSError as exc:
        raise ValueError("cannot read source: %s" % exc) from exc

    root = tree.getroot()
    tag = _local(root.tag)
    if tag == "mxfile":
        mxfile = root
    elif tag == "mxGraphModel":
        mxfile = ET.Element("mxfile")
        diagram = ET.SubElement(mxfile, "diagram", {"name": "Page-1", "id": "page-1"})
        diagram.append(root)
    elif tag == "diagram":
        mxfile = ET.Element("mxfile")
        mxfile.append(root)
    else:
        raise ValueError("unsupported root element <%s>" % tag)

    diagrams = _children(mxfile, "diagram")
    if not diagrams:
        raise ValueError("no <diagram> elements found")

    payloads = []
    for index, diagram in enumerate(diagrams):
        model = _first_child(diagram, "mxGraphModel")
        if model is not None:
            source_compressed = False
        else:
            text = diagram.text or ""
            if not text.strip():
                raise ValueError(
                    "diagram %d has neither <mxGraphModel> nor a compressed payload" % (index + 1)
                )
            model = _decode_payload_text(text)
            source_compressed = not (
                text.strip().startswith("<") or text.strip().startswith("&lt;")
            )
        if _local(model.tag) != "mxGraphModel":
            raise ValueError(
                "diagram %d payload root is <%s>, expected <mxGraphModel>"
                % (index + 1, _local(model.tag))
            )
        payloads.append(
            {
                "diagram": diagram,
                "model": model,
                "source_compressed": source_compressed,
            }
        )

    return mxfile, payloads


def _mxfile_with_models(original_mxfile, models, compressed):
    mxfile = copy.deepcopy(original_mxfile)
    diagrams = _children(mxfile, "diagram")
    if len(diagrams) != len(models):
        raise ValueError(
            "cannot serialize %d model(s) into %d diagram(s)"
            % (len(models), len(diagrams))
        )

    for diagram, model in zip(diagrams, models):
        for child in list(diagram):
            if _local(child.tag) == "mxGraphModel":
                diagram.remove(child)
        diagram.text = None
        if compressed:
            diagram.text = _encode_payload(model)
        else:
            model_copy = copy.deepcopy(model)
            model_copy.tail = None
            diagram.append(model_copy)
    return mxfile


def _indent_xml(elem, level=0):
    """Pretty-print a tree without touching textual payload nodes."""
    children = list(elem)
    if not children:
        return
    child_pad = "\n" + "  " * (level + 1)
    closing_pad = "\n" + "  " * level
    if not elem.text or not elem.text.strip():
        elem.text = child_pad
    for child in children:
        _indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = child_pad
    if not children[-1].tail or not children[-1].tail.strip():
        children[-1].tail = closing_pad


def _write_drawio(path, mxfile, pretty):
    if pretty:
        _indent_xml(mxfile)
    data = ET.tostring(mxfile, encoding="utf-8", xml_declaration=True)
    path.write_bytes(data)


def _safe_unlink(path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Cell inspection helpers
# ---------------------------------------------------------------------------


def _iter_cell_records(root):
    """Return draw.io cells that are direct children of <root>.

    A record stores the serialized node (wrapper or mxCell), the inner mxCell,
    the optional wrapper, and the effective id/parent/style.  draw.io models
    are flat: cells live under <root> and relationships use parent attributes.
    """
    records = []
    if root is None:
        return records

    for node in list(root):
        tag = _local(node.tag)
        if tag == "mxCell":
            records.append(
                {
                    "node": node,
                    "inner": node,
                    "wrapper": None,
                    "id": node.get("id"),
                    "parent": node.get("parent"),
                    "style": node.get("style") or "",
                }
            )
        elif tag in ("object", "UserObject"):
            inner = None
            for child in list(node):
                if _local(child.tag) == "mxCell":
                    inner = child
                    break
            if inner is None:
                continue
            parent = inner.get("parent")
            if parent is None:
                parent = node.get("parent")
            style = inner.get("style")
            if style is None:
                style = node.get("style") or ""
            records.append(
                {
                    "node": node,
                    "inner": inner,
                    "wrapper": node,
                    "id": node.get("id") or inner.get("id"),
                    "parent": parent,
                    "style": style or "",
                }
            )
    return records


def _direct_geometry(inner):
    return _first_child(inner, "mxGeometry")


def _cell_visible(record):
    if record["inner"].get("visible") == "0":
        return False
    if record["wrapper"] is not None and record["wrapper"].get("visible") == "0":
        return False
    return True


def _is_effectively_visible(record, by_id):
    """Walk parent links so hidden ancestors do not hide a negative control."""
    seen = set()
    current = record
    while current is not None:
        cid = current.get("id")
        if cid is not None:
            if cid in seen:
                return True
            seen.add(cid)
        if not _cell_visible(current):
            return False
        parent_id = current.get("parent")
        if parent_id in (None, "", "0", "1"):
            return True
        current = by_id.get(parent_id)
    return True


def _cell_value(record):
    if record["wrapper"] is not None and "label" in record["wrapper"].attrib:
        return record["wrapper"].get("label") or ""
    value = record["inner"].get("value")
    return value if value is not None else ""


def _style_map(style):
    result = {}
    for part in str(style or "").split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
        else:
            result[part] = None
    return result


def _is_plain_group(style):
    """True only for draw.io's real invisible group style, not layout containers."""
    tokens = _style_map(style)
    if "group" not in tokens:
        return False
    forbidden = {
        "swimlane",
        "tableLayout",
        "tableRow",
        "childLayout",
        "container",
        "collapsible",
        "startSize",
        "horizontal",
    }
    return not any(key in tokens for key in forbidden)


def _record_bounds(record):
    geometry = _direct_geometry(record["inner"])
    if geometry is None:
        return None
    x = _read_decimal(geometry, "x")
    y = _read_decimal(geometry, "y")
    width = _read_decimal(geometry, "width")
    height = _read_decimal(geometry, "height")
    if None in (x, y, width, height) or width <= 0 or height <= 0:
        return None
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "right": x + width,
        "bottom": y + height,
    }


def _union_bounds(records):
    boxes = [_record_bounds(record) for record in records if _cell_visible(record)]
    boxes = [box for box in boxes if box is not None]
    if not boxes:
        return None
    min_x = min(box["x"] for box in boxes)
    min_y = min(box["y"] for box in boxes)
    max_right = max(box["right"] for box in boxes)
    max_bottom = max(box["bottom"] for box in boxes)
    return {
        "x": min_x,
        "y": min_y,
        "width": max_right - min_x,
        "height": max_bottom - min_y,
    }


def _all_ids(root):
    ids = set()
    if root is None:
        return ids
    for elem in root.iter():
        cid = elem.get("id")
        if cid is not None:
            ids.add(cid)
    return ids


def _fresh_id(ids, prefix):
    index = 1
    while True:
        candidate = "%s_%d" % (prefix, index)
        if candidate not in ids:
            ids.add(candidate)
            return candidate
        index += 1


def _make_group_cell(group_id, parent_id, x, y, width, height):
    cell = ET.Element("mxCell")
    cell.set("id", group_id)
    cell.set("value", "")
    cell.set("style", "group")
    cell.set("connectable", "0")
    cell.set("vertex", "1")
    cell.set("parent", parent_id)
    geometry = ET.SubElement(cell, "mxGeometry")
    geometry.set("x", _fmt_decimal(x))
    geometry.set("y", _fmt_decimal(y))
    geometry.set("width", _fmt_decimal(width))
    geometry.set("height", _fmt_decimal(height))
    geometry.set("as", "geometry")
    return cell


# ---------------------------------------------------------------------------
# Coordinate-preserving group nesting
# ---------------------------------------------------------------------------


def _shift_vertex_geometry(geometry, dx, dy):
    """Shift a vertex geometry by (dx, dy) relative to its current parent."""
    x = _read_decimal(geometry, "x")
    y = _read_decimal(geometry, "y")
    if x is None or y is None:
        return False
    geometry.set("x", _fmt_decimal(x - dx))
    geometry.set("y", _fmt_decimal(y - dy))
    return True


def _shift_edge_geometry(geometry, dx, dy):
    """Shift an edge's absolute waypoints/fallback points by (dx, dy).

    Edge labels (cells with parent=edge) are not touched; their own relative
    geometry keeps them attached to the edge.
    """
    updates = []
    relative = (geometry.get("relative") or "").strip()

    # For ordinary edge geometry relative="1" x/y are not absolute positions.
    if relative != "1":
        for attr, delta in (("x", dx), ("y", dy)):
            if attr in geometry.attrib:
                value = _read_decimal(geometry, attr)
                if value is None:
                    return False
                updates.append((geometry, attr, value - delta))

    def collect_point(point):
        # mxPoint as="offset" on edge-label cells is relative and must not move.
        if (point.get("as") or "").strip() == "offset":
            return True
        x = _read_decimal(point, "x")
        y = _read_decimal(point, "y")
        if x is None or y is None:
            return False
        updates.append((point, "x", x - dx))
        updates.append((point, "y", y - dy))
        return True

    for child in list(geometry):
        tag = _local(child.tag)
        if tag == "Array":
            for point in list(child):
                if _local(point.tag) == "mxPoint" and not collect_point(point):
                    return False
        elif tag == "mxPoint" and not collect_point(child):
            return False

    for elem, attr, value in updates:
        elem.set(attr, _fmt_decimal(value))
    return True


def add_two_group_levels(model, mode, page_number):
    """Insert two real group levels while preserving absolute coordinates.

    mode == "top" wraps every eligible direct child of root cell "1".
    mode == "inner" picks an existing plain group and wraps its direct children.

    Group G1 sits at the union bbox origin of the visible direct vertices.  G2
    is a nested child of G1 at a small positive offset (dx, dy).  Descendants
    are shifted by the cumulative absolute offset (bbox_min + dx/dy), so adding
    G1.x + G2.x restores exactly the original coordinate.  The new group
    geometries stay inside the original content bbox, which avoids changing
    export/extent calculations.
    """
    root = _model_root(model)
    if root is None:
        return {"ok": False, "reason": "model has no <root> cell container"}

    records = _iter_cell_records(root)
    if not records:
        return {"ok": False, "reason": "<root> contains no cells"}

    by_id = {record["id"]: record for record in records if record["id"] is not None}
    if "1" not in by_id:
        return {"ok": False, "reason": "the mandatory root cell id='1' is missing"}

    if mode == "top":
        parent_id = "1"
        parent_record = by_id["1"]
        direct = [record for record in records if record["parent"] == parent_id]
        if not direct:
            return {
                "ok": False,
                "reason": "no cells are parented directly to root cell id='1'",
            }
        visible_vertices = [
            record
            for record in direct
            if record["inner"].get("vertex") == "1"
            and record["id"] not in ("0", "1")
            and _cell_visible(record)
        ]
        bbox = _union_bounds(visible_vertices)
        if bbox is None:
            return {
                "ok": False,
                "reason": "no visible direct vertex with positive geometry at the top level",
            }
        description = "added two nested group levels under root cell '1'"
    elif mode == "inner":
        best = None
        for record in records:
            if record["id"] in (None, "0", "1"):
                continue
            if record["inner"].get("vertex") != "1":
                continue
            if not _is_plain_group(record["style"]):
                continue
            if not _cell_visible(record):
                continue
            if record["inner"].get("collapsed") == "1":
                continue
            parent_id = record["id"]
            direct_candidate = [
                item for item in records if item["parent"] == parent_id
            ]
            visible_children = [
                item
                for item in direct_candidate
                if item["inner"].get("vertex") == "1" and _cell_visible(item)
            ]
            candidate_bbox = _union_bounds(visible_children)
            if candidate_bbox is None:
                continue
            score = (
                len(visible_children),
                candidate_bbox["width"] * candidate_bbox["height"],
            )
            if best is None or score > best[0]:
                best = (score, record, direct_candidate, candidate_bbox)
        if best is None:
            return {
                "ok": False,
                "reason": (
                    "no existing plain style='group' cell with visible direct vertex "
                    "children and usable geometry"
                ),
            }
        _, parent_record, direct, bbox = best
        parent_id = parent_record["id"]
        description = "added two nested group levels inside existing group '%s'" % parent_id
    else:
        return {"ok": False, "reason": "unknown nesting mode %r" % (mode,)}

    bbox_width = bbox["width"]
    bbox_height = bbox["height"]
    dx = min(_FIVE, bbox_width / Decimal(4))
    dy = min(_FIVE, bbox_height / Decimal(4))
    if dx <= 0 or dy <= 0:
        return {
            "ok": False,
            "reason": "content bounding box is too small for a safe non-zero nested offset",
        }

    g1_x = bbox["x"]
    g1_y = bbox["y"]
    g1_width = bbox_width
    g1_height = bbox_height
    g2_x = dx
    g2_y = dy
    g2_width = bbox_width - Decimal(2) * dx
    g2_height = bbox_height - Decimal(2) * dy

    # Absolute offset of G2 in the coordinate system of the target parent.
    shift_x = g1_x + g2_x
    shift_y = g1_y + g2_y

    ids = _all_ids(root)
    prefix = "dshtop" if mode == "top" else "dshinner"
    g1_id = _fresh_id(ids, prefix + "_g1")
    g2_id = _fresh_id(ids, prefix + "_g2")
    g1 = _make_group_cell(g1_id, parent_id, g1_x, g1_y, g1_width, g1_height)
    g2 = _make_group_cell(g2_id, g1_id, g2_x, g2_y, g2_width, g2_height)

    children = list(root)
    try:
        insert_at = children.index(parent_record["node"]) + 1
    except ValueError:
        return {"ok": False, "reason": "could not locate the target parent node"}

    root.insert(insert_at, g1)
    root.insert(insert_at + 1, g2)

    moved_vertices = 0
    moved_edges = 0
    skipped_cells = 0

    for record in direct:
        inner = record["inner"]
        geometry = _direct_geometry(inner)
        if inner.get("edge") == "1":
            if geometry is not None and not _shift_edge_geometry(
                geometry, shift_x, shift_y
            ):
                skipped_cells += 1
                continue
            inner.set("parent", g2_id)
            moved_edges += 1
        elif inner.get("vertex") == "1":
            if geometry is None:
                skipped_cells += 1
                continue
            if (geometry.get("relative") or "").strip() == "1":
                skipped_cells += 1
                continue
            if not _shift_vertex_geometry(geometry, shift_x, shift_y):
                skipped_cells += 1
                continue
            inner.set("parent", g2_id)
            moved_vertices += 1
        else:
            # Unknown non-vertex/non-edge cells are left in place rather than
            # risking a coordinate-system change without enough information.
            skipped_cells += 1

    if moved_vertices + moved_edges == 0:
        root.remove(g1)
        root.remove(g2)
        return {
            "ok": False,
            "reason": (
                "no coordinate-bearing cells could be moved safely; all candidates "
                "had non-numeric or relative geometry"
            ),
        }

    detail = (
        "%s on page %d using new groups '%s' -> '%s' "
        "(G2 offset (%s,%s) relative to G1 at (%s,%s)); moved %d vertex/vertices "
        "and %d edge(s), preserving absolute positions; %d other cell(s) left in place"
        % (
            description,
            page_number,
            g1_id,
            g2_id,
            _fmt_decimal(g2_x),
            _fmt_decimal(g2_y),
            _fmt_decimal(g1_x),
            _fmt_decimal(g1_y),
            moved_vertices,
            moved_edges,
            skipped_cells,
        )
    )
    return {
        "ok": True,
        "detail": detail,
        "moved_vertices": moved_vertices,
        "moved_edges": moved_edges,
        "skipped": skipped_cells,
        "g1": g1_id,
        "g2": g2_id,
    }


# ---------------------------------------------------------------------------
# Editable cell representations
# ---------------------------------------------------------------------------


def _wrap_userobjects(model):
    """Wrap non-root plain mxCells in <object label=... id=...> wrappers."""
    root = _model_root(model)
    if root is None:
        return 0

    wrapped = 0
    for index, child in enumerate(list(root)):
        if _local(child.tag) != "mxCell":
            continue
        cell_id = child.get("id")
        if cell_id is None or not cell_id.strip() or cell_id in ("0", "1"):
            continue

        label = child.get("value")
        if label is None:
            label = ""

        wrapper = ET.Element("object")
        wrapper.set("id", cell_id)
        wrapper.set("label", label)

        # Attributes that belong to the user object rather than the cell.
        for attr in ("link", "tooltip", "placeholders"):
            if attr in child.attrib:
                wrapper.set(attr, child.attrib.pop(attr))

        child.attrib.pop("id", None)
        child.attrib.pop("value", None)

        wrapper.tail = child.tail
        child.tail = None

        root.remove(child)
        wrapper.append(child)
        root.insert(index, wrapper)
        wrapped += 1
    return wrapped


def _flatten_userobjects(model):
    """Flatten simple editable wrappers.  Returns (flattened, kept, unsupported)."""
    root = _model_root(model)
    if root is None:
        return 0, 0, 0

    flattened = 0
    kept = 0
    unsupported = 0

    for index, child in enumerate(list(root)):
        tag = _local(child.tag)
        if tag not in ("object", "UserObject"):
            continue

        inner_children = list(child)
        if len(inner_children) != 1 or _local(inner_children[0].tag) != "mxCell":
            unsupported += 1
            continue
        inner = inner_children[0]

        # Placeholder resolution can change the rendered label; do not flatten.
        if "placeholders" in child.attrib:
            kept += 1
            continue

        wrapper_id = child.get("id")
        if wrapper_id is not None:
            inner.set("id", wrapper_id)

        if "label" in child.attrib:
            inner.set("value", child.get("label") or "")

        # Keep data-bearing attributes where the inner cell does not define one.
        for key, value in child.attrib.items():
            if key in ("id", "label", "placeholders"):
                continue
            if key not in inner.attrib:
                inner.set(key, value)

        inner.tail = child.tail
        child.tail = None

        root.remove(child)
        root.insert(index, inner)
        flattened += 1

    return flattened, kept, unsupported


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------


def _is_layout_positioned(record, by_id):
    style = _style_map(record["style"])
    if style.get("shape") == "tableRow":
        return True
    parent_id = record["parent"]
    parent = by_id.get(parent_id) if parent_id else None
    if parent is not None:
        parent_style = _style_map(parent["style"])
        if parent_style.get("shape") == "tableRow":
            return True
        if parent_style.get("childLayout") == "tableLayout":
            return True
    return False


def _choose_negative_vertex(records, by_id, prefer_text):
    candidates = []
    for record in records:
        if record["id"] in ("0", "1"):
            continue
        if record["inner"].get("vertex") != "1":
            continue
        if not _is_effectively_visible(record, by_id):
            continue
        if _is_layout_positioned(record, by_id):
            continue

        if prefer_text:
            if not _cell_value(record).strip():
                continue
        else:
            geometry = _direct_geometry(record["inner"])
            if geometry is None:
                continue
            if (geometry.get("relative") or "").strip() == "1":
                continue

        bounds = _record_bounds(record)
        area = bounds["width"] * bounds["height"] if bounds is not None else _ZERO
        style = _style_map(record["style"])
        is_group = "group" in style
        is_top_level = 0 if record["parent"] == "1" else 1
        score = (is_top_level, 1 if is_group else 0, -area)
        candidates.append((score, record))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _apply_negative_geometry(model):
    root = _model_root(model)
    if root is None:
        return None
    records = _iter_cell_records(root)
    by_id = {record["id"]: record for record in records if record["id"] is not None}
    record = _choose_negative_vertex(records, by_id, prefer_text=False)
    if record is None:
        return None

    geometry = _direct_geometry(record["inner"])
    if geometry is None:
        return None
    x = _read_decimal(geometry, "x")
    y = _read_decimal(geometry, "y")
    if x is None or y is None:
        return None

    geometry.set("x", _fmt_decimal(x + _FORTY))
    geometry.set("y", _fmt_decimal(y + _THIRTY))
    return {"cell_id": record["id"] or "<no-id>", "dx": "40", "dy": "30"}


def _apply_negative_content(model):
    root = _model_root(model)
    if root is None:
        return None
    records = _iter_cell_records(root)
    by_id = {record["id"]: record for record in records if record["id"] is not None}
    record = _choose_negative_vertex(records, by_id, prefer_text=True)
    if record is None:
        return None

    if record["wrapper"] is not None:
        record["wrapper"].set("label", "DSH NEGATIVE")
    else:
        record["inner"].set("value", "DSH NEGATIVE")
    return {"cell_id": record["id"] or "<no-id>"}


# ---------------------------------------------------------------------------
# Variant construction
# ---------------------------------------------------------------------------


def _generated(mxfile, detail, plain):
    return {
        "status": "generated",
        "mxfile": mxfile,
        "detail": detail,
        "plain": plain,
    }


def _skipped(detail):
    return {"status": "skipped", "detail": detail}


def _source_mix(payloads):
    compressed = sum(1 for payload in payloads if payload["source_compressed"])
    plain = len(payloads) - compressed
    return compressed, plain


def _format_detail(payloads, target):
    compressed, plain = _source_mix(payloads)
    return (
        "%d diagram(s) re-emitted as %s; source payloads: %d compressed, %d "
        "uncompressed; model cells, styles and geometry unchanged"
        % (len(payloads), target, compressed, plain)
    )


def _nesting_summary(results):
    changed = [result for result in results if result["ok"]]
    unchanged = [result for result in results if not result["ok"]]
    parts = [result["detail"] for result in changed]
    if unchanged:
        reasons = []
        for result in unchanged:
            reason = result.get("reason") or "not applicable"
            if reason not in reasons:
                reasons.append(reason)
        parts.append(
            "%d page(s) left unchanged (%s)"
            % (len(unchanged), "; ".join(reasons))
        )
    return "; ".join(parts)


def build_variant(spec, original_mxfile, payloads):
    name = spec["name"]
    models = [copy.deepcopy(payload["model"]) for payload in payloads]

    if name == "format_uncompressed":
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            _format_detail(payloads, "uncompressed mxGraphModel XML"),
            plain=True,
        )

    if name == "format_compressed":
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=True),
            _format_detail(payloads, "compressed XML (URI-encoded raw DEFLATE + Base64)"),
            plain=False,
        )

    if name == "editable_userobjects":
        wrapped = sum(_wrap_userobjects(model) for model in models)
        if wrapped == 0:
            return _skipped(
                "no non-root plain <mxCell> cells were available to wrap; every cell "
                "is already a user object or is a root cell"
            )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            "editable representation: wrapped %d non-root plain <mxCell> cell(s) in "
            "<object label=... id=...> user-object wrappers across %d diagram(s), "
            "moving value->label and id->wrapper; style, parent, source/target and "
            "geometry stayed on the inner mxCell; output is plain XML"
            % (wrapped, len(models)),
            plain=True,
        )

    if name == "editable_plaincells":
        flattened = 0
        kept = 0
        unsupported = 0
        for model in models:
            f, k, u = _flatten_userobjects(model)
            flattened += f
            kept += k
            unsupported += u
        if flattened == 0:
            if kept or unsupported:
                return _skipped(
                    "found editable wrappers but none could be flattened safely "
                    "(%d with placeholders=..., %d with unsupported structure)"
                    % (kept, unsupported)
                )
            return _skipped(
                "no <object> or <UserObject> editable wrappers were present in the source"
            )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            "editable representation: flattened %d <object>/<UserObject> wrapper(s) "
            "back to plain <mxCell> elements (label->value, wrapper id->cell id); "
            "kept %d wrapper(s) with placeholders=... and %d with unsupported "
            "structure untouched; output is plain XML"
            % (flattened, kept, unsupported),
            plain=True,
        )

    if name == "nesting_all_two_levels":
        results = [
            add_two_group_levels(model, "top", index + 1)
            for index, model in enumerate(models)
        ]
        if not any(result["ok"] for result in results):
            reasons = sorted(
                {result.get("reason") or "not applicable" for result in results}
            )
            return _skipped(
                "two-level top nesting was not applicable: %s" % "; ".join(reasons)
            )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            "nesting: " + _nesting_summary(results) + "; output is plain XML",
            plain=True,
        )

    if name == "nesting_existing_group_two_levels":
        results = [
            add_two_group_levels(model, "inner", index + 1)
            for index, model in enumerate(models)
        ]
        if not any(result["ok"] for result in results):
            reasons = sorted(
                {result.get("reason") or "not applicable" for result in results}
            )
            return _skipped(
                "two-level nesting inside an existing group was not applicable: %s"
                % "; ".join(reasons)
            )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            "nesting: " + _nesting_summary(results) + "; output is plain XML",
            plain=True,
        )

    if name == "combo_nesting_userobjects_compressed":
        results = [
            add_two_group_levels(model, "top", index + 1)
            for index, model in enumerate(models)
        ]
        changed = [result for result in results if result["ok"]]
        if not changed:
            reasons = sorted(
                {result.get("reason") or "not applicable" for result in results}
            )
            return _skipped(
                "combination skipped because top-level two-level nesting was not "
                "applicable: %s" % "; ".join(reasons)
            )
        wrapped = sum(_wrap_userobjects(model) for model in models)
        detail = (
            "combination: "
            + _nesting_summary(results)
            + "; then wrapped %d plain cell(s) as editable <object> user objects; "
            "then compressed all %d diagram payload(s)"
            % (wrapped, len(models))
        )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=True),
            detail,
            plain=False,
        )

    if name == "combo_inner_nesting_userobjects_plain":
        results = [
            add_two_group_levels(model, "inner", index + 1)
            for index, model in enumerate(models)
        ]
        changed = [result for result in results if result["ok"]]
        if not changed:
            reasons = sorted(
                {result.get("reason") or "not applicable" for result in results}
            )
            return _skipped(
                "combination skipped because inner-group two-level nesting was not "
                "applicable: %s" % "; ".join(reasons)
            )
        wrapped = sum(_wrap_userobjects(model) for model in models)
        detail = (
            "combination: "
            + _nesting_summary(results)
            + "; then wrapped %d plain cell(s) as editable <object> user objects; "
            "output is plain XML" % wrapped
        )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            detail,
            plain=True,
        )

    if name == "negative_geometry_shift":
        info = _apply_negative_geometry(models[0])
        if info is None:
            return _skipped(
                "negative geometry control not applicable: no visible, non-table "
                "vertex with numeric geometry was found"
            )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            "NEGATIVE CONTROL (geometry): on diagram 1 translated visible cell "
            "id='%s' by (+%s,+%s) in its parent coordinate system; all other cells "
            "and diagrams are unchanged; render is intentionally different"
            % (info["cell_id"], info["dx"], info["dy"]),
            plain=True,
        )

    if name == "negative_content_change":
        info = _apply_negative_content(models[0])
        if info is None:
            return _skipped(
                "negative content control not applicable: no visible vertex with a "
                "non-empty value/label was found"
            )
        return _generated(
            _mxfile_with_models(original_mxfile, models, compressed=False),
            "NEGATIVE CONTROL (content): on diagram 1 replaced the visible label of "
            "cell id='%s' with 'DSH NEGATIVE'; all other cells and diagrams are "
            "unchanged; render is intentionally different" % info["cell_id"],
            plain=True,
        )

    return _skipped("unknown variant type %r" % (name,))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _record(case_name, spec, status, detail, file_name=None):
    return {
        "case": case_name,
        "variant": spec["name"],
        "category": spec["category"],
        "status": status,
        "detail": detail,
        "file": file_name,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Generate metamorphic draw.io variants for every CASE.drawio in a "
            "source directory."
        )
    )
    parser.add_argument("source_directory", help="directory containing CASE.drawio files")
    parser.add_argument("output_directory", help="directory for CASE/VARIANT.drawio outputs")
    args = parser.parse_args(argv)

    source_dir = Path(args.source_directory)
    output_dir = Path(args.output_directory)

    if not source_dir.is_dir():
        print("error: source directory not found: %s" % source_dir, file=sys.stderr)
        return 2
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print("error: cannot create output directory %s: %s" % (output_dir, exc), file=sys.stderr)
        return 2

    try:
        case_paths = sorted(
            (
                path
                for path in source_dir.iterdir()
                if path.is_file() and path.suffix.lower() == ".drawio"
            ),
            key=lambda path: (path.name.lower(), path.name),
        )
    except OSError as exc:
        print("error: cannot list source directory %s: %s" % (source_dir, exc), file=sys.stderr)
        return 2

    records = []
    generated_count = 0
    skipped_count = 0

    for case_path in case_paths:
        case_name = case_path.stem
        case_dir = output_dir / case_name

        try:
            original_mxfile, payloads = load_case(case_path)
            load_error = None
        except Exception as exc:
            original_mxfile = None
            payloads = None
            load_error = (
                "could not decode source safely, so no transform was attempted: "
                "%s: %s" % (type(exc).__name__, exc)
            )

        for spec in VARIANT_SPECS:
            variant_path = case_dir / (spec["name"] + ".drawio")
            relative_name = "%s/%s.drawio" % (case_name, spec["name"])

            if load_error is not None:
                _safe_unlink(variant_path)
                records.append(
                    _record(case_name, spec, "skipped", load_error, None)
                )
                skipped_count += 1
                continue

            try:
                result = build_variant(spec, original_mxfile, payloads)
                if result.get("status") == "generated":
                    case_dir.mkdir(parents=True, exist_ok=True)
                    pretty = result.get("plain", spec["output"] == "plain")
                    _write_drawio(variant_path, result["mxfile"], pretty)
                    records.append(
                        _record(
                            case_name,
                            spec,
                            "generated",
                            result["detail"],
                            relative_name,
                        )
                    )
                    generated_count += 1
                else:
                    _safe_unlink(variant_path)
                    records.append(
                        _record(
                            case_name,
                            spec,
                            "skipped",
                            result.get("detail") or "not applicable",
                            None,
                        )
                    )
                    skipped_count += 1
            except Exception as exc:
                _safe_unlink(variant_path)
                detail = (
                    "transform could not be completed safely and was skipped: "
                    "%s: %s" % (type(exc).__name__, exc)
                )
                records.append(
                    _record(case_name, spec, "skipped", detail, None)
                )
                skipped_count += 1

    variant_types = [
        {
            "name": spec["name"],
            "category": spec["category"],
            "applicability": spec["applicability"],
            "summary": spec["summary"],
        }
        for spec in VARIANT_SPECS
    ]
    manifest = {
        "tool": "transform.py",
        "description": (
            "Metamorphic draw.io variants.  category=format/editable/nesting are "
            "render-preserving positives; category=negative variants intentionally "
            "alter geometry or content."
        ),
        "variant_types": variant_types,
        "records": records,
    }

    manifest_path = output_dir / "manifest.json"
    try:
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        print("error: cannot write manifest %s: %s" % (manifest_path, exc), file=sys.stderr)
        return 2

    print(
        "processed %d case(s): generated %d file(s), skipped %d record(s); manifest: %s"
        % (len(case_paths), generated_count, skipped_count, manifest_path)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
