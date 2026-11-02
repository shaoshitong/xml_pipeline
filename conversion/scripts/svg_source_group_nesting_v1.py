"""Nest inferred source-outline groups while preserving exact model coordinates.

The old emitter puts every node group on the same layer. A late annotation of
an outer node then paints before an intervening inner node. This pass expresses
strict, unambiguous source-outline containment as native nested groups. It does
not reorder source cells, infer from reference pixels, change edges, or waive
the independent source-paint-order check.
"""
from __future__ import annotations

from decimal import Decimal
import xml.etree.ElementTree as ET


def _style(cell):
    return dict(part.split("=", 1) for part in cell.get("style", "").split(";") if "=" in part)


def _number(geometry, name):
    value = Decimal(geometry.get(name, "0"))
    if not value.is_finite():
        raise ValueError("source_group_nonfinite_geometry")
    return value


def _world_rectangles(cells):
    origins = {}

    def origin(identifier, seen=frozenset()):
        if identifier in origins:
            return origins[identifier]
        if identifier in seen:
            raise ValueError("source_group_parent_cycle")
        if identifier not in cells:
            raise ValueError("source_group_missing_parent:" + identifier)
        cell = cells[identifier]
        parent = cell.get("parent")
        x, y = origin(parent, seen | {identifier}) if parent else (Decimal(0), Decimal(0))
        geometry = cell.find("mxGeometry")
        if cell.get("vertex") == "1" and geometry is not None:
            if geometry.get("relative", "0") != "0":
                raise ValueError("source_group_relative_vertex_requires_separate_mapping")
            x += _number(geometry, "x")
            y += _number(geometry, "y")
        origins[identifier] = x, y
        return x, y

    rectangles = {}
    for identifier, cell in cells.items():
        geometry = cell.find("mxGeometry")
        if cell.get("vertex") == "1" and geometry is not None:
            rectangles[identifier] = (*origin(identifier), _number(geometry, "width"), _number(geometry, "height"))
    return rectangles


def _contains(outer, inner):
    x, y, w, h = outer
    a, b, c, d = inner
    return w > 0 and h > 0 and c > 0 and d > 0 and w * h > c * d and x <= a and y <= b and a + c <= x + w and b + d <= y + h


def nest_source_groups(xml):
    tree = ET.fromstring(xml)
    root = tree.find(".//mxGraphModel/root")
    if root is None:
        raise ValueError("source_group_missing_model_root")
    ordered = list(root.findall("mxCell"))
    cells = {cell.get("id"): cell for cell in ordered}
    if len(cells) != len(ordered) or None in cells or "1" not in cells:
        raise ValueError("source_group_invalid_cell_identity")
    before = _world_rectangles(cells)
    groups = {}
    for identifier, cell in cells.items():
        if not identifier.startswith("node_source_") or _style(cell).get("group") != "1":
            continue
        style = _style(cell)
        if any(style.get(key, "0") != "0" for key in ("rotation", "flipH", "flipV")):
            raise ValueError("source_group_transformed_parent_requires_separate_mapping")
        if cell.get("parent") != "1" and not cell.get("parent", "").startswith("node_source_"):
            raise ValueError("source_group_non_source_parent_requires_separate_mapping")
        groups[identifier] = before[identifier]
    edges = {identifier: ET.tostring(cell) for identifier, cell in cells.items() if cell.get("edge") == "1"}
    changes, ambiguous = [], []
    for identifier, box in groups.items():
        candidates = sorted((outer[2] * outer[3], parent) for parent, outer in groups.items() if _contains(outer, box))
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            ambiguous.append(identifier)
            parent = "1"
        else:
            parent = candidates[0][1] if candidates else "1"
        cell = cells[identifier]
        old_parent = cell.get("parent")
        if old_parent == parent:
            continue
        geometry = cell.find("mxGeometry")
        px, py = before[parent][:2] if parent in before else (Decimal(0), Decimal(0))
        cell.set("parent", parent)
        geometry.set("x", str(box[0] - px))
        geometry.set("y", str(box[1] - py))
        changes.append({"group": identifier, "old_parent": old_parent, "new_parent": parent})
    if _world_rectangles(cells) != before:
        raise ValueError("source_group_world_geometry_changed")
    if any(ET.tostring(cells[identifier]) != serialized for identifier, serialized in edges.items()):
        raise ValueError("source_group_edge_geometry_or_binding_changed")
    return ET.tostring(tree, encoding="unicode"), {
        "policy": "strict_unambiguous_source_outline_nested_groups_v1",
        "source_groups": len(groups),
        "nested_groups": sum(cells[identifier].get("parent") != "1" for identifier in groups),
        "changes": changes,
        "ambiguous_containment_left_on_layer": ambiguous,
        "all_vertex_world_rectangles_exactly_preserved": True,
        "all_edge_geometry_and_binding_attributes_unchanged": True,
        "source_cell_serialization_order_unchanged": True,
        "reference_pixels_used": False,
        "independent_native_paint_order_check_still_required": True,
    }
