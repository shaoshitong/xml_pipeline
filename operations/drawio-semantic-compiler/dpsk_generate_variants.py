#!/usr/bin/env python3
"""Generate deterministic, editable draw.io metamorphic variants.

The program is deliberately self contained and uses only the Python standard
library.  It never invokes draw.io, a renderer, a compiler, or an external
process.  Each source document is decoded, structurally mutated, and written
back as one independent candidate.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import math
import os
import random
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path


EXPECTED_INPUTS = 50
CELL_TAGS = frozenset(("mxCell", "object", "UserObject", "userobject"))
NATIVE_REFERENCE_ATTRIBUTES = ("parent", "source", "target")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PRETTY_XML_RE = re.compile(r"\n[ \t]*<")
SKETCH_STYLE_RE = re.compile(
    r"(?:^|;)\s*(?:sketch|freehand|comic|rough)\s*=\s*(?:1|true)\s*(?:;|$)",
    re.IGNORECASE,
)
BASE64_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Small XML helpers
# ---------------------------------------------------------------------------


def _local(element):
    tag = getattr(element, "tag", None)
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _tag_in_namespace(sample, local_name):
    tag = getattr(sample, "tag", "")
    if isinstance(tag, str) and tag.startswith("{"):
        return tag[: tag.index("}") + 1] + local_name
    return local_name


def _is_cell_element(element):
    return _local(element) in CELL_TAGS


def _is_mxcell(element):
    return _local(element) == "mxCell"


def _record_id(element):
    value = element.get("id")
    if value:
        return value
    for child in element.iter():
        if child is element:
            continue
        if _is_mxcell(child) and child.get("id"):
            return child.get("id")
    return None


def _record_parent(element):
    if _is_mxcell(element):
        return element.get("parent")
    for child in element.iter():
        if child is element:
            continue
        if _is_mxcell(child) and child.get("parent") is not None:
            return child.get("parent")
    return element.get("parent")


def _set_record_parent(element, parent_id):
    if _is_mxcell(element):
        element.set("parent", parent_id)
        return
    for child in element.iter():
        if child is not element and _is_mxcell(child):
            child.set("parent", parent_id)
    if element.get("parent") is not None:
        element.set("parent", parent_id)


def _record_style(element):
    value = element.get("style")
    if value:
        return value
    for child in element.iter():
        if child is element:
            continue
        if _is_mxcell(child) and child.get("style"):
            return child.get("style")
    return ""


def _record_link(element):
    value = element.get("link")
    if value:
        return value
    for child in element.iter():
        if child is element:
            continue
        if _is_mxcell(child) and child.get("link"):
            return child.get("link")
    return ""


def _record_geometry(element):
    for child in element.iter():
        if _local(child) == "mxGeometry":
            return child
    return None


def _record_is_edge(element):
    for child in element.iter():
        if _is_cell_element(child) and child.get("edge") == "1":
            return True
    return False


def _all_cell_elements(model_element):
    return [element for element in model_element.iter() if _is_cell_element(element)]


def _direct_cell_records(graph_root):
    records = []
    for child in list(graph_root):
        if not _is_cell_element(child):
            continue
        if _record_id(child) is None:
            continue
        records.append(child)
    return records


def _find_graph_root(model_element):
    if _local(model_element) == "mxGraphModel":
        for child in model_element.iter():
            if _local(child) == "root":
                return child
        return None
    for child in model_element.iter():
        if _local(child) == "root":
            return child
    return None


def _parse_xml(source):
    parser = ET.XMLParser(
        target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
    )
    parser.feed(source)
    return parser.close()


def _register_namespaces(data):
    try:
        for _event, item in ET.iterparse(
            io.BytesIO(data), events=("start-ns",)
        ):
            prefix, uri = item
            if prefix == "xml":
                continue
            try:
                ET.register_namespace(prefix, uri)
            except (KeyError, ValueError):
                pass
    except Exception:
        # Namespace registration is only cosmetic.  Parsing reports real XML
        # errors later with a much more useful context.
        pass


# ---------------------------------------------------------------------------
# Diagram payload encoding / decoding
# ---------------------------------------------------------------------------


def _looks_pretty(xml_text):
    return bool(PRETTY_XML_RE.search(xml_text or ""))


def _external_variants(value):
    values = [value]
    try:
        once = urllib.parse.unquote(value)
        if once not in values:
            values.append(once)
        twice = urllib.parse.unquote(once)
        if twice not in values:
            values.append(twice)
    except Exception:
        pass
    return values


def _decode_diagram_text(text):
    """Return ("compressed"|"plain", xml_text) or None.

    draw.io normally uses URL-encoded raw DEFLATE + Base64 for compressed
    diagrams.  A few exports use zlib/gzip wrappers, so all three are
    accepted.  Uncompressed diagram payloads are returned verbatim after one
    URL decode when necessary.
    """

    if not text or not text.strip():
        return None
    stripped = text.strip()
    if stripped.lstrip("\ufeff \t\r\n").startswith("<"):
        return ("plain", stripped.lstrip("\ufeff \t\r\n"))

    candidates = []
    for value in (
        urllib.parse.unquote(stripped),
        urllib.parse.unquote_plus(stripped),
        stripped,
    ):
        if value not in candidates:
            candidates.append(value)

    for value in candidates:
        clean = value.lstrip("\ufeff \t\r\n")
        if clean.startswith("<"):
            return ("plain", clean)

    for value in candidates:
        compact = BASE64_WS_RE.sub("", value)
        if not compact:
            continue
        compact = compact.replace("-", "+").replace("_", "/")
        remainder = len(compact) % 4
        if remainder:
            compact += "=" * (4 - remainder)
        try:
            compressed = base64.b64decode(compact, validate=False)
        except (binascii.Error, ValueError):
            continue
        if not compressed:
            continue

        for wbits in (-15, 15, 31):
            try:
                raw = zlib.decompress(compressed, wbits)
            except (zlib.error, ValueError):
                continue
            try:
                decoded = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            decoded = decoded.lstrip("\ufeff \t\r\n")
            if decoded.startswith("<"):
                # Some exporters deflate raw XML rather than URI-encoded XML.
                return ("compressed", decoded)
            for xml_text in (
                urllib.parse.unquote(decoded),
                urllib.parse.unquote_plus(decoded),
                decoded,
            ):
                xml_text = xml_text.lstrip("\ufeff \t\r\n")
                if xml_text.startswith("<"):
                    return ("compressed", xml_text)
    return None


def _parse_model_payload(payload):
    try:
        parsed = _parse_xml(payload.lstrip("\ufeff \t\r\n"))
    except (ET.ParseError, ValueError):
        return None
    if _local(parsed) == "mxGraphModel":
        return parsed
    for element in parsed.iter():
        if _local(element) == "mxGraphModel":
            return element
    return None


def _encode_compressed_payload(model_xml, level):
    uri_encoded = urllib.parse.quote(model_xml, safe="")
    compressor = zlib.compressobj(level, zlib.DEFLATED, -15)
    raw = compressor.compress(uri_encoded.encode("utf-8")) + compressor.flush()
    return base64.b64encode(raw).decode("ascii")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _strip_whitespace_only_text(element):
    if element.text is not None and not element.text.strip():
        element.text = None
    if element.tail is not None and not element.tail.strip():
        element.tail = None
    for child in list(element):
        _strip_whitespace_only_text(child)


def _indent_element(element, level):
    children = list(element)
    if not children:
        return
    if element.text is not None and element.text.strip():
        # Do not rewrite mixed content.  draw.io graph models are structural,
        # but this keeps the function safe for unusual custom payloads.
        return
    child_prefix = "\n" + "  " * (level + 1)
    element.text = child_prefix
    for index, child in enumerate(children):
        _indent_element(child, level + 1)
        if index + 1 == len(children):
            child.tail = "\n" + "  " * level
        else:
            child.tail = child_prefix


def _prepare_model_xml(model_element, pretty):
    _strip_whitespace_only_text(model_element)
    if pretty:
        _indent_element(model_element, 0)
    model_element.tail = None


# ---------------------------------------------------------------------------
# Graph maps, geometry, and depth
# ---------------------------------------------------------------------------


def _build_record_maps(graph_root):
    order = []
    element_by_id = {}
    parent_by_id = {}
    geometry_by_id = {}
    for element in _direct_cell_records(graph_root):
        record_id = _record_id(element)
        if not record_id or record_id in element_by_id:
            continue
        order.append(record_id)
        element_by_id[record_id] = element
        parent_by_id[record_id] = _record_parent(element)
        geometry = _record_geometry(element)
        if geometry is not None:
            geometry_by_id[record_id] = geometry

    children = {}
    for record_id in order:
        parent_id = parent_by_id.get(record_id)
        if parent_id is not None:
            children.setdefault(parent_id, []).append(record_id)
    return order, element_by_id, parent_by_id, geometry_by_id, children


def _style_value(style, key):
    if not style:
        return None
    for part in style.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name.strip() == key:
            return value.strip()
    return None


def _safe_float(value, default=None):
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _geometry_xy(geometry, require_attributes=False):
    if geometry is None:
        return None
    if require_attributes and (
        geometry.get("x") is None or geometry.get("y") is None
    ):
        return None
    x = _safe_float(geometry.get("x", "0"), 0.0)
    y = _safe_float(geometry.get("y", "0"), 0.0)
    if x is None or y is None:
        return None
    return (x, y)


def _geometry_size(geometry):
    if geometry is None:
        return (0.0, 0.0)
    width = _safe_float(geometry.get("width", "0"), 0.0)
    height = _safe_float(geometry.get("height", "0"), 0.0)
    if width is None or width < 0:
        width = 0.0
    if height is None or height < 0:
        height = 0.0
    return (width, height)


def _format_number(value):
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    text = ("%.6f" % value).rstrip("0").rstrip(".")
    return text or "0"


def _absolute_xy(record_id, parent_by_id, geometry_by_id):
    x = 0.0
    y = 0.0
    current = record_id
    seen = set()
    while current is not None and current not in seen:
        seen.add(current)
        geometry = geometry_by_id.get(current)
        if geometry is not None:
            xy = _geometry_xy(geometry, require_attributes=False)
            if xy is None:
                return None
            x += xy[0]
            y += xy[1]
        current = parent_by_id.get(current)
    return (x, y)


def _subtree_ids(record_id, children_by_id):
    result = []
    stack = [record_id]
    seen = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        result.append(current)
        for child in reversed(children_by_id.get(current, ())):
            if child not in seen:
                stack.append(child)
    return result


def _style_has_unsafe_transform(record_id, element_by_id, parent_by_id):
    current = record_id
    seen = set()
    while current is not None and current not in seen:
        seen.add(current)
        element = element_by_id.get(current)
        if element is None:
            break
        style = _record_style(element)
        rotation = _style_value(style, "rotation")
        if rotation is not None:
            parsed = _safe_float(rotation)
            if parsed is None or abs(parsed) > 1e-9:
                return True
        for flag in ("flipH", "flipV"):
            value = _style_value(style, flag)
            if value is not None and value.lower() in ("1", "true"):
                return True
        scale = _style_value(style, "scale")
        if scale is not None:
            parsed = _safe_float(scale)
            if parsed is None or abs(parsed - 1.0) > 1e-9:
                return True
        current = parent_by_id.get(current)
    return False


def _depth_one(record_id, parent_by_id, memo=None):
    if memo is None:
        memo = {}
    if record_id in memo:
        return memo[record_id]
    visiting = set()

    def visit(current):
        if current in memo:
            return memo[current]
        if current in visiting:
            return 0
        visiting.add(current)
        parent = parent_by_id.get(current)
        if parent is None:
            value = 0
        elif parent not in parent_by_id:
            value = 1
        else:
            value = 1 + visit(parent)
        visiting.discard(current)
        memo[current] = value
        return value

    return visit(record_id)


def _max_depth(order, parent_by_id):
    memo = {}
    maximum = 0
    for record_id in order:
        maximum = max(maximum, _depth_one(record_id, parent_by_id, memo))
    return maximum


def _max_depth_from_root(graph_root):
    order, _elements, parent_by_id, _geometry, _children = _build_record_maps(
        graph_root
    )
    return _max_depth(order, parent_by_id)


def _choose_layer(order, parent_by_id):
    for record_id in order:
        if record_id != "0" and parent_by_id.get(record_id) == "0":
            return record_id
    if "1" in parent_by_id:
        return "1"
    if "0" in parent_by_id:
        return "0"
    return None


def _is_ancestor(ancestor_id, record_id, parent_by_id):
    current = parent_by_id.get(record_id)
    seen = set()
    while current is not None and current not in seen:
        if current == ancestor_id:
            return True
        seen.add(current)
        current = parent_by_id.get(current)
    return False


# ---------------------------------------------------------------------------
# Deterministic identifiers
# ---------------------------------------------------------------------------


def _make_cell_id(seed_material, page_index, old_id, used_ids):
    for attempt in range(10000):
        digest = hashlib.sha256(
            seed_material
            + b"\x00cell\x00"
            + str(page_index).encode("utf-8")
            + b"\x00"
            + str(attempt).encode("ascii")
            + b"\x00"
            + old_id.encode("utf-8")
        ).hexdigest()
        candidate = "mxv" + digest[:18]
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
    raise RuntimeError("could not allocate a unique cell identifier")


def _make_frame_id(seed_material, used_ids, counter):
    for attempt in range(10000):
        digest = hashlib.sha256(
            seed_material
            + b"\x00frame\x00"
            + str(counter[0]).encode("ascii")
            + b"\x00"
            + str(attempt).encode("ascii")
        ).hexdigest()
        candidate = "mxf" + digest[:18]
        if candidate not in used_ids:
            used_ids.add(candidate)
            counter[0] += 1
            return candidate
    raise RuntimeError("could not allocate a unique coordinate-frame identifier")


def _make_page_id(seed_material, used_ids):
    for attempt in range(10000):
        digest = hashlib.sha256(
            seed_material + b"\x00page\x00" + str(attempt).encode("ascii")
        ).hexdigest()
        candidate = "mxp" + digest[:18]
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
    raise RuntimeError("could not allocate a unique page identifier")


def _contains_token(text, token):
    if not token:
        return False
    pattern = (
        r"(?<![A-Za-z0-9_.\-])"
        + re.escape(token)
        + r"(?![A-Za-z0-9_.\-])"
    )
    return re.search(pattern, text) is not None


def _referenced_ids(text, ids):
    """Find standalone ID references with the same boundaries in one scan."""
    run = re.compile(r"[A-Za-z0-9_.-]+")
    ordinary = {identifier for identifier in ids if run.fullmatch(identifier)}
    found = {match[0] for match in run.finditer(text) if match[0] in ordinary}
    found.update(identifier for identifier in ids - ordinary if _contains_token(text, identifier))
    return found


# ---------------------------------------------------------------------------
# ID rewriting
# ---------------------------------------------------------------------------


def _model_external_text(model_element):
    chunks = []
    for element in model_element.iter():
        for key, value in element.attrib.items():
            if key == "id" or key in NATIVE_REFERENCE_ATTRIBUTES:
                continue
            chunks.extend(_external_variants(value))
        if element.text and element.text.strip():
            chunks.extend(_external_variants(element.text))
        if element.tail and element.tail.strip():
            chunks.extend(_external_variants(element.tail))
    return "\n".join(chunks)


def _outer_external_text(outer_root):
    candidates = [outer_root]
    if _local(outer_root) == "mxfile":
        candidates.extend(
            child for child in list(outer_root) if _local(child) == "diagram"
        )
    chunks = []
    for element in candidates:
        for key, value in element.attrib.items():
            if key == "id" or key in NATIVE_REFERENCE_ATTRIBUTES:
                continue
            chunks.extend(_external_variants(value))
    return "\n".join(chunks)


def _collect_protected_ids(models):
    model_cells = []
    all_ids = set()
    for model in models:
        cells = _all_cell_elements(model)
        model_cells.append(cells)
        for element in cells:
            record_id = element.get("id")
            if record_id:
                all_ids.add(record_id)

    external_chunks = []
    for cells in model_cells:
        for element in cells:
            for key, value in element.attrib.items():
                if key == "id" or key in NATIVE_REFERENCE_ATTRIBUTES:
                    continue
                external_chunks.extend(_external_variants(value))
            if element.text and element.text.strip():
                external_chunks.extend(_external_variants(element.text))
            if element.tail and element.tail.strip():
                external_chunks.extend(_external_variants(element.tail))
    # The caller adds document-level attributes and all model attribute values
    # (including geometry/custom fields) to this blob before matching.
    blob = "\n".join(external_chunks)
    protected = _referenced_ids(blob, all_ids)

    for cells in model_cells:
        for element in cells:
            record_id = element.get("id")
            if not record_id:
                continue
            if _record_link(element) or SKETCH_STYLE_RE.search(
                _record_style(element) or ""
            ):
                protected.add(record_id)
    return all_ids, protected


def _rewrite_model_ids(
    model_element,
    page_index,
    protected_global,
    used_ids,
    seed_material,
):
    cells = _all_cell_elements(model_element)
    unique_ids = []
    seen = set()
    for element in cells:
        record_id = element.get("id")
        if record_id and record_id not in seen:
            seen.add(record_id)
            unique_ids.append(record_id)

    mapping = {}
    for record_id in unique_ids:
        if record_id in ("0", "1") or record_id in protected_global:
            mapping[record_id] = record_id
        else:
            mapping[record_id] = _make_cell_id(
                seed_material, page_index, record_id, used_ids
            )

    renamed = 0
    changed_id_attributes = 0
    for record_id, replacement in mapping.items():
        if replacement != record_id:
            renamed += 1
    for element in cells:
        old_id = element.get("id")
        if old_id in mapping and mapping[old_id] != old_id:
            element.set("id", mapping[old_id])
            changed_id_attributes += 1

    references_rewritten = 0
    for element in model_element.iter():
        if not _is_cell_element(element):
            continue
        for attribute in NATIVE_REFERENCE_ATTRIBUTES:
            value = element.get(attribute)
            if value in mapping and mapping[value] != value:
                element.set(attribute, mapping[value])
                references_rewritten += 1

    return {
        "renamed": renamed,
        "preserved": len(mapping) - renamed,
        "changed_id_attributes": changed_id_attributes,
        "native_references_rewritten": references_rewritten,
        "cell_id_count": len(unique_ids),
    }


# ---------------------------------------------------------------------------
# Coordinate frames
# ---------------------------------------------------------------------------


def _make_frame_cell(
    namespace_sample,
    frame_id,
    parent_id,
    x,
    y,
    width,
    height,
):
    cell = ET.Element(
        _tag_in_namespace(namespace_sample, "mxCell"),
        {
            "id": frame_id,
            "parent": parent_id,
        },
    )
    ET.SubElement(
        cell,
        _tag_in_namespace(namespace_sample, "mxGeometry"),
        {
            "x": _format_number(x),
            "y": _format_number(y),
            "width": _format_number(width),
            "height": _format_number(height),
            "as": "geometry",
        },
    )
    return cell


def _subtree_bbox(
    record_id,
    element_by_id,
    parent_by_id,
    geometry_by_id,
    children_by_id,
):
    minimum_x = None
    minimum_y = None
    maximum_x = None
    maximum_y = None
    for current in _subtree_ids(record_id, children_by_id):
        element = element_by_id.get(current)
        if element is None or _record_is_edge(element):
            continue
        geometry = geometry_by_id.get(current)
        if geometry is None:
            continue
        absolute = _absolute_xy(current, parent_by_id, geometry_by_id)
        size = _geometry_size(geometry)
        if absolute is None:
            continue
        left = absolute[0]
        top = absolute[1]
        right = left + size[0]
        bottom = top + size[1]
        if minimum_x is None:
            minimum_x = left
            minimum_y = top
            maximum_x = right
            maximum_y = bottom
        else:
            minimum_x = min(minimum_x, left)
            minimum_y = min(minimum_y, top)
            maximum_x = max(maximum_x, right)
            maximum_y = max(maximum_y, bottom)
    if minimum_x is None:
        return None
    return (minimum_x, minimum_y, maximum_x, maximum_y)


def _wrap_branch(
    graph_root,
    record_id,
    frame_count,
    element_by_id,
    parent_by_id,
    geometry_by_id,
    children_by_id,
    seed_material,
    used_ids,
    frame_counter,
):
    element = element_by_id.get(record_id)
    if element is None:
        return None
    parent_id = parent_by_id.get(record_id)
    geometry = geometry_by_id.get(record_id)
    if parent_id is None or parent_id == "0" or geometry is None:
        return None
    if geometry.get("relative") == "1":
        return None
    origin = _geometry_xy(geometry, require_attributes=True)
    if origin is None:
        return None
    absolute_parent = _absolute_xy(parent_id, parent_by_id, geometry_by_id)
    if absolute_parent is None:
        return None

    bbox = _subtree_bbox(
        record_id,
        element_by_id,
        parent_by_id,
        geometry_by_id,
        children_by_id,
    )

    frames = []
    current_parent = parent_id
    current_absolute = absolute_parent
    for index in range(frame_count):
        local_x, local_y = origin if index == 0 else (0, 0)
        current_absolute = (
            current_absolute[0] + local_x,
            current_absolute[1] + local_y,
        )
        if bbox is not None:
            width = max(24.0, bbox[2] - current_absolute[0] + 12.0)
            height = max(24.0, bbox[3] - current_absolute[1] + 12.0)
        else:
            width = 24.0
            height = 24.0
        frame_id = _make_frame_id(seed_material, used_ids, frame_counter)
        frame = _make_frame_cell(
            graph_root,
            frame_id,
            current_parent,
            local_x,
            local_y,
            width,
            height,
        )
        if index == 0:
            # Move the original tokens verbatim. Adding and subtracting float
            # offsets can round coordinates and move a painted pixel.
            _record_geometry(frame).set("x", geometry.get("x"))
            _record_geometry(frame).set("y", geometry.get("y"))
        frames.append(frame)
        current_parent = frame_id

    geometry.set("x", "0")
    geometry.set("y", "0")
    _set_record_parent(element, current_parent)

    insertion_index = list(graph_root).index(element)
    for frame in frames:
        graph_root.insert(insertion_index, frame)
        insertion_index += 1

    return {
        "frames": frame_count,
        "compensated": 1,
        "branch_id": record_id,
    }


def _add_empty_frame_chain(
    graph_root,
    parent_id,
    frame_count,
    seed_material,
    used_ids,
    frame_counter,
):
    if parent_id is None:
        return 0
    current_parent = parent_id
    for index in range(frame_count):
        frame_id = _make_frame_id(seed_material, used_ids, frame_counter)
        frame = _make_frame_cell(
            graph_root,
            frame_id,
            current_parent,
            4.0 + 3.0 * index,
            -4.0 - 2.0 * index,
            40.0,
            40.0,
        )
        graph_root.append(frame)
        current_parent = frame_id
    return frame_count


def _record_chain(stats, length, empty):
    if length <= 0:
        return
    stats["frames_inserted"] += length
    stats["frame_chains"] += 1
    stats["frame_nesting_depth"] = max(
        stats["frame_nesting_depth"], length
    )
    stats["chain_lengths"].append(length)
    if empty:
        stats["empty_chains"] += 1


def _select_wrap_candidates(
    order,
    element_by_id,
    parent_by_id,
    geometry_by_id,
    children_by_id,
    seed_material,
):
    ranked = []
    for record_id in order:
        parent_id = parent_by_id.get(record_id)
        if not parent_id or parent_id == "0" or parent_id not in element_by_id:
            continue
        element = element_by_id[record_id]
        if _record_is_edge(element):
            continue
        geometry = geometry_by_id.get(record_id)
        if geometry is None or _geometry_xy(
            geometry, require_attributes=True
        ) is None:
            continue
        if _style_has_unsafe_transform(
            record_id, element_by_id, parent_by_id
        ):
            continue
        if _absolute_xy(record_id, parent_by_id, geometry_by_id) is None:
            continue
        rank_hash = hashlib.sha256(
            seed_material
            + b"\x00branch\x00"
            + record_id.encode("utf-8")
        ).digest()
        has_children = 0 if children_by_id.get(record_id) else 1
        is_group = 0 if "group" in _record_style(element).lower() else 1
        ranked.append((has_children, is_group, rank_hash, record_id))
    ranked.sort()

    selected = []
    for _has_children, _is_group, _rank, record_id in ranked:
        if any(
            _is_ancestor(record_id, other, parent_by_id)
            or _is_ancestor(other, record_id, parent_by_id)
            for other in selected
        ):
            continue
        selected.append(record_id)
        if len(selected) >= 2:
            break
    return selected


def _insert_coordinate_frames(
    graph_root,
    source_depth,
    seed_material,
    used_ids,
    frame_counter,
):
    stats = {
        "frames_inserted": 0,
        "frame_chains": 0,
        "frame_nesting_depth": 0,
        "chain_lengths": [],
        "empty_chains": 0,
        "wrapped_branches": 0,
        "geometry_compensated": 0,
        "depth_after_frames": source_depth,
    }
    order, element_by_id, parent_by_id, geometry_by_id, children_by_id = (
        _build_record_maps(graph_root)
    )
    if not order:
        return stats

    random_source = random.Random(
        int.from_bytes(
            hashlib.sha256(seed_material + b"\x00frames\x00").digest()[:16],
            "big",
        )
    )
    selected = _select_wrap_candidates(
        order,
        element_by_id,
        parent_by_id,
        geometry_by_id,
        children_by_id,
        seed_material,
    )

    for record_id in selected:
        frame_count = 2 + random_source.randrange(2)
        result = _wrap_branch(
            graph_root,
            record_id,
            frame_count,
            element_by_id,
            parent_by_id,
            geometry_by_id,
            children_by_id,
            seed_material,
            used_ids,
            frame_counter,
        )
        if result is None:
            continue
        stats["wrapped_branches"] += 1
        stats["geometry_compensated"] += result["compensated"]
        _record_chain(stats, result["frames"], empty=False)

    layer_id = _choose_layer(order, parent_by_id)
    if stats["wrapped_branches"] < 2 and layer_id is not None:
        for _ in range(2 - stats["wrapped_branches"]):
            added = _add_empty_frame_chain(
                graph_root,
                layer_id,
                2,
                seed_material,
                used_ids,
                frame_counter,
            )
            if added:
                _record_chain(stats, added, empty=True)

    current_depth = _max_depth_from_root(graph_root)
    if current_depth <= source_depth and layer_id is not None:
        base_depth = _depth_one(layer_id, parent_by_id)
        needed_length = max(2, source_depth - base_depth + 1)
        # A very deep source should still get a meaningful frame chain without
        # allowing adversarial inputs to create an unbounded pile of wrappers.
        needed_length = min(needed_length, 48)
        added = _add_empty_frame_chain(
            graph_root,
            layer_id,
            needed_length,
            seed_material,
            used_ids,
            frame_counter,
        )
        if added:
            _record_chain(stats, added, empty=True)

    stats["depth_after_frames"] = _max_depth_from_root(graph_root)
    return stats


# ---------------------------------------------------------------------------
# Record permutation
# ---------------------------------------------------------------------------


def _find_permutation_candidate(graph_root, seed_material):
    order, element_by_id, parent_by_id, _geometry_by_id, children_by_id = (
        _build_record_maps(graph_root)
    )
    if len(order) < 3:
        return None
    index_by_id = {record_id: index for index, record_id in enumerate(order)}

    candidates = []
    for parent_id, direct_children in children_by_id.items():
        if parent_id == "0" or parent_id not in element_by_id:
            continue
        direct = [
            child
            for child in direct_children
            if child in element_by_id and child in index_by_id
        ]
        if len(direct) < 2:
            continue

        branch_blocks = {}
        selected_ids = set()
        invalid = False
        for child_id in direct:
            subtree = _subtree_ids(child_id, children_by_id)
            if any(record_id not in index_by_id for record_id in subtree):
                invalid = True
                break
            selected_ids.update(subtree)
            block = [record_id for record_id in subtree if record_id != child_id]
            block.sort(key=lambda value: index_by_id[value])
            branch_blocks[child_id] = block
        if invalid or parent_id in selected_ids:
            continue
        nonempty = [child_id for child_id in direct if branch_blocks[child_id]]
        if len(nonempty) < 2:
            continue

        indices = sorted(index_by_id[record_id] for record_id in selected_ids)
        if not indices:
            continue
        if indices[-1] - indices[0] + 1 != len(indices):
            continue
        span_ids = order[indices[0] : indices[-1] + 1]
        if any(record_id not in selected_ids for record_id in span_ids):
            continue
        if index_by_id.get(parent_id) is None:
            continue
        if index_by_id[parent_id] >= indices[0]:
            continue

        candidates.append(
            {
                "parent": parent_id,
                "direct": direct,
                "blocks": branch_blocks,
                "selected_ids": selected_ids,
                "indices": indices,
                "span_ids": span_ids,
                "nonempty_count": len(nonempty),
                "root_order": list(direct),
            }
        )

    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            -item["nonempty_count"],
            len(item["selected_ids"]),
            item["parent"],
        )
    )
    return candidates[0], order, element_by_id, index_by_id


def _permute_records(graph_root, seed_material):
    found = _find_permutation_candidate(graph_root, seed_material)
    if found is None:
        return None
    candidate, order, element_by_id, index_by_id = found
    parent_id = candidate["parent"]
    direct = candidate["root_order"]
    blocks = candidate["blocks"]
    selected_ids = candidate["selected_ids"]
    span_ids = candidate["span_ids"]

    random_source = random.Random(
        int.from_bytes(
            hashlib.sha256(
                seed_material + b"\x00permute\x00" + parent_id.encode("utf-8")
            ).digest()[:16],
            "big",
        )
    )
    block_indices = [index for index, child in enumerate(direct) if blocks[child]]
    block_order = list(block_indices)
    new_sequence = None
    old_sequence = list(span_ids)
    for attempt in range(12):
        random_source.shuffle(block_order)
        if attempt and block_order == block_indices:
            continue
        sequence = list(direct)
        for block_index in block_order:
            sequence.extend(blocks[direct[block_index]])
        if sequence != old_sequence:
            new_sequence = sequence
            break
    if new_sequence is None:
        while block_order == block_indices:
            block_order = block_order[1:] + block_order[:1]
        sequence = list(direct)
        for block_index in block_order:
            sequence.extend(blocks[direct[block_index]])
        if sequence != old_sequence:
            new_sequence = sequence
    if new_sequence is None:
        return None

    # The selected records are flat direct children of <root>.  Verify that
    # the XML span contains exactly those records and no comments/PIs, so the
    # permutation does not silently drop document nodes.
    root_children = list(graph_root)
    position_by_object = {
        id(child): position for position, child in enumerate(root_children)
    }
    selected_elements = [element_by_id[record_id] for record_id in selected_ids]
    positions = sorted(position_by_object[id(element)] for element in selected_elements)
    start = positions[0]
    end = positions[-1]
    if end - start + 1 != len(selected_elements):
        return None
    span_elements = root_children[start : end + 1]
    if any(not _is_cell_element(element) for element in span_elements):
        return None
    if {id(element) for element in span_elements} != {
        id(element) for element in selected_elements
    }:
        return None

    for element in span_elements:
        graph_root.remove(element)
    for offset, record_id in enumerate(new_sequence):
        graph_root.insert(start + offset, element_by_id[record_id])

    return {
        "parent": parent_id,
        "independent_branches": candidate["nonempty_count"],
        "branch_roots_preserved": len(direct),
        "records_permuted": len(new_sequence),
        "sibling_order_preserved": True,
    }


# ---------------------------------------------------------------------------
# Per-model mutation
# ---------------------------------------------------------------------------


def _process_model(
    model_element,
    page_index,
    protected_global,
    used_ids,
    seed_material,
    frame_counter,
):
    graph_root = _find_graph_root(model_element)
    stats = {
        "graph_root_found": graph_root is not None,
        "renamed": 0,
        "preserved": 0,
        "changed_id_attributes": 0,
        "native_references_rewritten": 0,
        "cell_id_count": 0,
        "frames": {
            "frames_inserted": 0,
            "frame_chains": 0,
            "frame_nesting_depth": 0,
            "chain_lengths": [],
            "empty_chains": 0,
            "wrapped_branches": 0,
            "geometry_compensated": 0,
            "depth_after_frames": 0,
        },
        "permutation": None,
        "source_depth": 0,
        "final_depth": 0,
        "skipped": [],
    }
    if graph_root is None:
        stats["skipped"].append("graph_root")
        return stats

    source_depth = _max_depth_from_root(graph_root)
    stats["source_depth"] = source_depth
    id_stats = _rewrite_model_ids(
        model_element,
        page_index,
        protected_global,
        used_ids,
        seed_material,
    )
    stats.update(id_stats)

    frame_stats = _insert_coordinate_frames(
        graph_root,
        source_depth,
        seed_material,
        used_ids,
        frame_counter,
    )
    stats["frames"] = frame_stats

    permutation = _permute_records(
        graph_root, seed_material + b"\x00page\x00" + str(page_index).encode("ascii")
    )
    if permutation is None:
        order, _elements, parent_by_id, _geometry, _children = _build_record_maps(
            graph_root
        )
        layer_id = _choose_layer(order, parent_by_id)
        if layer_id is not None:
            for _ in range(2):
                added = _add_empty_frame_chain(
                    graph_root,
                    layer_id,
                    2,
                    seed_material,
                    used_ids,
                    frame_counter,
                )
                if added:
                    _record_chain(stats["frames"], added, empty=True)
            permutation = _permute_records(
                graph_root,
                seed_material
                + b"\x00page\x00"
                + str(page_index).encode("ascii")
                + b"\x00retry",
            )

    stats["permutation"] = permutation
    if frame_stats["wrapped_branches"] == 0:
        stats["skipped"].append("coordinate_frame_wrapping")
    if frame_stats["geometry_compensated"] == 0:
        stats["skipped"].append("geometry_compensation")
    if frame_stats["frames_inserted"] == 0:
        stats["skipped"].append("coordinate_frames")
    if permutation is None:
        stats["skipped"].append("record_permutation")

    stats["final_depth"] = _max_depth_from_root(graph_root)
    if stats["final_depth"] <= source_depth:
        stats["skipped"].append("nesting_depth_increase")
    if stats["renamed"] == 0:
        stats["skipped"].append("id_rewrite")
    return stats


# ---------------------------------------------------------------------------
# Diagram entry preparation
# ---------------------------------------------------------------------------


def _new_entry(diagram, model, source_mode, source_pretty, index):
    return {
        "index": index,
        "diagram": diagram,
        "model": model,
        "source_mode": source_mode,
        "source_pretty": source_pretty,
        "target_mode": None,
        "target_pretty": None,
        "compression_level": 1,
    }


def _entry_from_diagram(diagram, index):
    text = (diagram.text or "").strip()
    direct_model = None
    for child in list(diagram):
        if _local(child) == "mxGraphModel":
            direct_model = child
            break

    if text:
        decoded = _decode_diagram_text(text)
        if decoded is not None:
            kind, payload = decoded
            model = _parse_model_payload(payload)
            if model is not None:
                return _new_entry(
                    diagram,
                    model,
                    "compressed" if kind == "compressed" else "plain",
                    _looks_pretty(payload),
                    index,
                )

    if direct_model is not None:
        serialized = ET.tostring(direct_model, encoding="unicode")
        return _new_entry(
            diagram,
            direct_model,
            "plain",
            _looks_pretty(serialized),
            index,
        )

    if text:
        return _new_entry(diagram, None, "unknown", None, index)
    return _new_entry(diagram, None, "empty", None, index)


def _decide_compression_and_formatting(entries, seed_material):
    for entry in entries:
        source_mode = entry["source_mode"]
        if source_mode == "compressed":
            target_mode = "plain"
        elif source_mode in ("plain", "bare"):
            target_mode = "compressed"
        else:
            target_mode = None
        entry["target_mode"] = target_mode

        source_pretty = entry["source_pretty"]
        if entry["model"] is not None and source_pretty is not None:
            entry["target_pretty"] = not source_pretty
        else:
            entry["target_pretty"] = None

        digest = hashlib.sha256(
            seed_material
            + b"\x00compression\x00"
            + str(entry["index"]).encode("ascii")
        ).hexdigest()
        entry["compression_level"] = 1 + (int(digest[:8], 16) % 9)


# ---------------------------------------------------------------------------
# Document generation
# ---------------------------------------------------------------------------


def _make_mxfile_for_bare_graph(graph_root_element, seed_material, used_ids):
    mxfile = ET.Element(_tag_in_namespace(graph_root_element, "mxfile"))
    page_id = _make_page_id(seed_material, used_ids)
    diagram = ET.SubElement(
        mxfile,
        _tag_in_namespace(graph_root_element, "diagram"),
        {"id": page_id, "name": "Page-1"},
    )
    return mxfile, diagram


def _generate_candidate(source_bytes, row, row_index, seed_text):
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    seed_material = (
        seed_text.encode("utf-8")
        + b"\x00row\x00"
        + str(row_index).encode("ascii")
        + b"\x00"
        + str(row["id"]).encode("utf-8")
        + b"\x00"
        + source_sha.encode("ascii")
    )
    _register_namespaces(source_bytes)
    outer = _parse_xml(source_bytes)
    outer_kind = _local(outer)

    entries = []
    wrapper_created = False
    used_ids = set()
    for element in outer.iter():
        if _is_cell_element(element) and element.get("id"):
            used_ids.add(element.get("id"))
    for child in outer.iter():
        if _local(child) == "diagram" and child.get("id"):
            used_ids.add(child.get("id"))

    if outer_kind == "mxfile":
        mxfile = outer
        diagram_elements = [
            child for child in list(outer) if _local(child) == "diagram"
        ]
        for index, diagram in enumerate(diagram_elements):
            entry = _entry_from_diagram(diagram, index)
            entries.append(entry)
    elif outer_kind == "diagram":
        mxfile = ET.Element(_tag_in_namespace(outer, "mxfile"))
        outer.tail = None
        mxfile.append(outer)
        wrapper_created = True
        entries.append(_entry_from_diagram(outer, 0))
    elif outer_kind == "mxGraphModel":
        mxfile, diagram = _make_mxfile_for_bare_graph(
            outer, seed_material, used_ids
        )
        wrapper_created = True
        pretty_source = _looks_pretty(ET.tostring(outer, encoding="unicode"))
        # A bare model is uncompressed source material, so the candidate uses
        # the compressed diagram representation.
        entries.append(_new_entry(diagram, outer, "bare", pretty_source, 0))
    else:
        raise ValueError(
            "unsupported draw.io root element <%s>" % (outer_kind or "?")
        )

    models = [entry["model"] for entry in entries if entry["model"] is not None]
    source_depths = []
    for model in models:
        graph_root = _find_graph_root(model)
        source_depths.append(
            0 if graph_root is None else _max_depth_from_root(graph_root)
        )
    before_depth = max(source_depths) if source_depths else 0

    external_chunks = [_outer_external_text(outer)]
    for model in models:
        external_chunks.append(_model_external_text(model))
    external_blob = "\n".join(external_chunks)

    all_ids = set()
    cells_by_model = []
    for model in models:
        cells = _all_cell_elements(model)
        cells_by_model.append(cells)
        for element in cells:
            record_id = element.get("id")
            if record_id:
                all_ids.add(record_id)
    used_ids.update(all_ids)

    protected = _referenced_ids(external_blob, all_ids)
    for cells in cells_by_model:
        for element in cells:
            record_id = element.get("id")
            if not record_id:
                continue
            if _record_link(element) or SKETCH_STYLE_RE.search(
                _record_style(element) or ""
            ):
                protected.add(record_id)

    _decide_compression_and_formatting(entries, seed_material)

    frame_counter = [0]
    per_model_stats = []
    for index, entry in enumerate(entries):
        model = entry["model"]
        if model is None:
            per_model_stats.append(None)
            continue
        stats = _process_model(
            model,
            index,
            protected,
            used_ids,
            seed_material,
            frame_counter,
        )
        per_model_stats.append(stats)

    compression_sources = []
    compression_candidates = []
    formatting_sources = []
    formatting_candidates = []
    compression_changed = False
    formatting_changed = False

    for entry in entries:
        source_mode = entry["source_mode"]
        target_mode = entry["target_mode"]
        compression_sources.append(source_mode)
        compression_candidates.append(target_mode or "unchanged")
        if (
            source_mode in ("compressed", "plain", "bare")
            and target_mode is not None
            and source_mode != target_mode
        ):
            compression_changed = True

        source_pretty = entry["source_pretty"]
        target_pretty = entry["target_pretty"]
        if source_pretty is None or target_pretty is None:
            formatting_sources.append("unknown")
            formatting_candidates.append("unchanged")
        else:
            formatting_sources.append("pretty" if source_pretty else "compact")
            formatting_candidates.append(
                "pretty" if target_pretty else "compact"
            )
            if source_pretty != target_pretty:
                formatting_changed = True

    # Serialize each mutated model and change the diagram representation.
    for entry in entries:
        model = entry["model"]
        if model is None:
            continue
        target_mode = entry["target_mode"]
        target_pretty = entry["target_pretty"]
        if target_mode is None or target_pretty is None:
            continue
        _prepare_model_xml(model, target_pretty)
        diagram = entry["diagram"]

        if target_mode == "compressed":
            model_xml = ET.tostring(model, encoding="unicode")
            encoded = _encode_compressed_payload(
                model_xml, entry["compression_level"]
            )
            for child in list(diagram):
                diagram.remove(child)
            diagram.text = encoded
        else:
            for child in list(diagram):
                diagram.remove(child)
            diagram.text = None
            model.tail = None
            diagram.append(model)

    candidate_text = ET.tostring(mxfile, encoding="unicode")
    candidate_bytes = (
        '<?xml version="1.0" encoding="UTF-8"?>\n' + candidate_text
    ).encode("utf-8")

    if not models:
        # No graph model means the document-level formatting is all we can
        # change.  Keep the declaration newline deterministic.
        candidate_bytes = (
            '<?xml version="1.0" encoding="UTF-8"?>\n' + candidate_text
        ).encode("utf-8")

    aggregate = {
        "renamed": 0,
        "preserved": 0,
        "changed_id_attributes": 0,
        "native_references_rewritten": 0,
        "frames_inserted": 0,
        "frame_chains": 0,
        "frame_nesting_depth": 0,
        "empty_chains": 0,
        "wrapped_branches": 0,
        "geometry_compensated": 0,
        "permuted_pages": 0,
        "records_permuted": 0,
        "skipped": [],
    }
    target_depths = []
    for index, stats in enumerate(per_model_stats):
        entry = entries[index]
        if stats is None:
            if entry["source_mode"] == "unknown":
                if "diagram_decode" not in aggregate["skipped"]:
                    aggregate["skipped"].append("diagram_decode")
            continue
        for key in (
            "renamed",
            "preserved",
            "changed_id_attributes",
            "native_references_rewritten",
        ):
            aggregate[key] += stats.get(key, 0)
        frames = stats["frames"]
        aggregate["frames_inserted"] += frames["frames_inserted"]
        aggregate["frame_chains"] += frames["frame_chains"]
        aggregate["frame_nesting_depth"] = max(
            aggregate["frame_nesting_depth"],
            frames["frame_nesting_depth"],
        )
        aggregate["empty_chains"] += frames["empty_chains"]
        aggregate["wrapped_branches"] += frames["wrapped_branches"]
        aggregate["geometry_compensated"] += frames[
            "geometry_compensated"
        ]
        target_depths.append(stats["final_depth"])
        if stats["permutation"] is not None:
            aggregate["permuted_pages"] += 1
            aggregate["records_permuted"] += stats["permutation"][
                "records_permuted"
            ]
        for skipped in stats["skipped"]:
            if skipped not in aggregate["skipped"]:
                aggregate["skipped"].append(skipped)

    after_depth = max(target_depths) if target_depths else 0
    if not compression_changed:
        aggregate["skipped"].append("compression_change")
    if not formatting_changed:
        aggregate["skipped"].append("formatting_change")
    if aggregate["frames_inserted"] == 0:
        aggregate["skipped"].append("coordinate_frames")
    if aggregate["renamed"] == 0:
        aggregate["skipped"].append("id_rewrite")
    if aggregate["permuted_pages"] == 0:
        aggregate["skipped"].append("record_permutation")
    if after_depth <= before_depth:
        aggregate["skipped"].append("nesting_depth_increase")
    if not models:
        aggregate["skipped"].append("graph_model")

    skipped_operations = []
    for skipped in aggregate["skipped"]:
        if skipped not in skipped_operations:
            skipped_operations.append(skipped)

    change_types = []
    if aggregate["renamed"] > 0:
        change_types.append("id_rewrite")
    if aggregate["native_references_rewritten"] > 0:
        change_types.append("native_reference_rewrite")
    if wrapper_created:
        change_types.append("mxfile_wrapper")
    if aggregate["frames_inserted"] > 0:
        change_types.append("coordinate_frames")
    if aggregate["geometry_compensated"] > 0:
        change_types.append("geometry_compensation")
    if aggregate["permuted_pages"] > 0:
        change_types.append("record_permutation")
    if compression_changed:
        change_types.append("compression_change")
    if formatting_changed:
        change_types.append("formatting_change")

    operations = {
        "ids": {
            "renamed": aggregate["renamed"],
            "preserved": aggregate["preserved"],
            "cell_id_count": len(all_ids),
            "changed_id_attributes": aggregate["changed_id_attributes"],
            "native_references_rewritten": aggregate[
                "native_references_rewritten"
            ],
        },
        "frames": {
            "inserted": aggregate["frames_inserted"],
            "chains": aggregate["frame_chains"],
            "maximum_chain_length": aggregate["frame_nesting_depth"],
            "empty_chains": aggregate["empty_chains"],
            "wrapped_branches": aggregate["wrapped_branches"],
            "geometry_compensated_cells": aggregate[
                "geometry_compensated"
            ],
        },
        "record_permutation": {
            "pages_permuted": aggregate["permuted_pages"],
            "records_permuted": aggregate["records_permuted"],
        },
        "compression": {
            "source_modes": compression_sources,
            "candidate_modes": compression_candidates,
            "changed": compression_changed,
        },
        "formatting": {
            "source_modes": formatting_sources,
            "candidate_modes": formatting_candidates,
            "changed": formatting_changed,
        },
    }

    meta = {
        "schema_version": 1,
        "source_xml": str(row["xml"]),
        "source_sha256": source_sha,
        "input_sha256": source_sha,
        "source_bytes": len(source_bytes),
        "diagram_count": len(entries),
        "change_types": change_types,
        "renamed": aggregate["renamed"],
        "renamed_count": aggregate["renamed"],
        "preserved_id_count": aggregate["preserved"],
        "nesting_depth": after_depth,
        "nesting_depth_before": before_depth,
        "nesting_depth_definition": "maximum parent-edge chain length",
        "frame_nesting_depth": aggregate["frame_nesting_depth"],
        "frames_inserted": aggregate["frames_inserted"],
        "record_permutation_pages": aggregate["permuted_pages"],
        "compression_changed": compression_changed,
        "formatting_changed": formatting_changed,
        "skipped_operations": skipped_operations,
        "operations": operations,
    }
    return candidate_bytes, meta


# ---------------------------------------------------------------------------
# Manifest and filesystem
# ---------------------------------------------------------------------------


def _load_manifest(manifest_path):
    try:
        raw = manifest_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError("cannot read manifest: %s" % exc) from exc

    rows = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "manifest line %d is not valid JSON: %s" % (line_number, exc)
            ) from exc
        if not isinstance(item, dict):
            raise ValueError("manifest line %d must be a JSON object" % line_number)
        row_id = item.get("id")
        xml_path = item.get("xml")
        if not isinstance(row_id, str) or not SAFE_ID_RE.match(row_id):
            raise ValueError(
                "manifest line %d has an unsafe or missing id" % line_number
            )
        if not isinstance(xml_path, str) or not xml_path:
            raise ValueError(
                "manifest line %d has a missing xml path" % line_number
            )
        path = Path(xml_path)
        if not path.is_absolute():
            raise ValueError(
                "manifest line %d xml path must be absolute" % line_number
            )
        if not path.is_file():
            raise ValueError(
                "manifest line %d xml file does not exist: %s"
                % (line_number, path)
            )
        rows.append({"id": row_id, "xml": str(path)})

    if len(rows) != EXPECTED_INPUTS:
        raise ValueError(
            "manifest must contain exactly %d records; found %d"
            % (EXPECTED_INPUTS, len(rows))
        )
    seen_ids = set()
    for row in rows:
        if row["id"] in seen_ids:
            raise ValueError("duplicate manifest id: %s" % row["id"])
        seen_ids.add(row["id"])
    return rows


def _atomic_write(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp.%d" % os.getpid())
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass


def _build_variants_record(row, candidate_name, candidate_bytes, meta):
    output_sha = hashlib.sha256(candidate_bytes).hexdigest()
    record = dict(meta)
    record.update(
        {
            "id": row["id"],
            "candidate": candidate_name,
            "output": candidate_name,
            "candidate_path": os.path.abspath(
                os.path.join(OUTPUT_DIRECTORY, candidate_name)
            )
            if OUTPUT_DIRECTORY
            else candidate_name,
            "candidate_sha256": output_sha,
            "output_sha256": output_sha,
            "candidate_bytes": len(candidate_bytes),
            "hashes": {
                "source_sha256": record.get("source_sha256"),
                "input_sha256": record.get("input_sha256"),
                "candidate_sha256": output_sha,
                "output_sha256": output_sha,
            },
        }
    )
    return record


OUTPUT_DIRECTORY = ""


def main(argv=None):
    global OUTPUT_DIRECTORY
    parser = argparse.ArgumentParser(
        description=(
            "Generate 50 deterministic, editable draw.io metamorphic "
            "candidates from a JSONL manifest."
        )
    )
    parser.add_argument("--manifest", required=True, help="input JSONL manifest")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--seed", required=True, help="deterministic seed")
    args = parser.parse_args(argv)

    try:
        rows = _load_manifest(Path(args.manifest))
        out_directory = Path(args.out)
        if out_directory.exists() and not out_directory.is_dir():
            raise ValueError("--out is not a directory: %s" % out_directory)
        out_directory.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIRECTORY = str(out_directory)

        generated = []
        for index, row in enumerate(rows):
            source_path = Path(row["xml"])
            source_bytes = source_path.read_bytes()
            candidate_bytes, meta = _generate_candidate(
                source_bytes, row, index, str(args.seed)
            )
            candidate_name = row["id"] + ".drawio"
            variant_record = _build_variants_record(
                row, candidate_name, candidate_bytes, meta
            )
            generated.append(
                (
                    candidate_name,
                    candidate_bytes,
                    variant_record,
                )
            )

        for candidate_name, candidate_bytes, _record in generated:
            _atomic_write(out_directory / candidate_name, candidate_bytes)

        variants_data = "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for _name, _data, record in generated
        ).encode("utf-8")
        _atomic_write(out_directory / "variants.jsonl", variants_data)
    except (OSError, ValueError, ET.ParseError) as exc:
        print("generate_variants.py: %s" % exc, file=sys.stderr)
        return 1

    print(
        "generated %d draw.io variants in %s"
        % (len(generated), out_directory)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
