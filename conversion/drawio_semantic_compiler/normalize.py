"""Stage 4: rule-driven minimization of the IR.

Every rule states the equivalence it relies on and checks its preconditions on
the IR before rewriting. Rules run to a fixed point. Anything a rule cannot
prove redundant stays: draw order, layers, selectable groups, ports, user data,
stylenames, extension content and the cell IDs the editor observes.
"""

from decimal import Decimal

import ir
import syntax

EXAMPLES = 8
ZERO = (Decimal(0), Decimal(0))


class Log:
    def __init__(self):
        self.entries = {}

    def add(self, rule, page, detail=None):
        entry = self.entries.setdefault((rule, page), {"rule": rule, "page": page, "count": 0, "examples": []})
        entry["count"] += 1
        if detail is not None and len(entry["examples"]) < EXAMPLES:
            entry["examples"].append(detail)


def unwrap_trivial_user_object(page, number, origin, log):
    """A user object holding only a label edits and paints like a plain value."""
    for cell in page.cells.values():
        if cell.wrapper is not None and not cell.data and not cell.wrapper_extras:
            cell.wrapper = None
            log.add("unwrap_trivial_user_object", number, origin[cell.uid]["original_id"])


def canonical_style(page, number, origin, log):
    """Overwritten keys are dead; keys between two stylenames commute."""
    for cell in page.cells.values():
        if cell.style is None:
            continue
        style, dropped = syntax.canonical_style(cell.style)
        if dropped:
            log.add("drop_overwritten_style_key", number, origin[cell.uid]["original_id"])
        if style != cell.style:
            if not dropped:
                log.add("order_style_keys", number, origin[cell.uid]["original_id"])
            cell.style = style


def drop_zero_offset(page, number, origin, log):
    """The view substitutes (0, 0) for a missing offset."""
    for cell in page.cells.values():
        if cell.geometry is not None and cell.geometry.offset == ZERO:
            cell.geometry.offset = None
            log.add("drop_zero_offset", number, origin[cell.uid]["original_id"])


def frame_blockers(page, cell, terminals):
    """Reasons a non-vertex, non-edge container is more than a coordinate frame."""
    reasons = []
    if page.pinned:
        reasons.append("cell_ids_are_anchors")
    if page.cells[cell.parent].kind == ir.EDGE:
        reasons.append("parent_is_edge")
    if cell.label is not None or cell.wrapper is not None:
        reasons.append("has_value")
    if cell.style is not None:
        reasons.append("has_style")
    if not cell.visible:
        reasons.append("hidden")
    if cell.collapsed:
        reasons.append("collapsed")
    if cell.attrs or cell.extras:
        reasons.append("has_extensions")
    if cell.uid in terminals:
        reasons.append("is_edge_terminal")
    geometry = cell.geometry
    if geometry is not None:
        if geometry.relative:
            reasons.append("relative_geometry")
        if (geometry.offset or geometry.alternate_bounds or geometry.attrs or geometry.extras
                or geometry.source_point or geometry.target_point or geometry.points):
            reasons.append("geometry_extensions")
    children = [page.cells[uid] for uid in cell.children]
    if any(c.kind != ir.EDGE and c.geometry is not None and c.geometry.relative for c in children):
        reasons.append("relative_child")
    if any(c.geometry is not None and c.geometry.extras for c in children):
        reasons.append("child_geometry_extensions")
    return reasons


def shift(cell, dx, dy):
    """Move a cell's local geometry so its page position survives a parent origin change."""
    geometry = cell.geometry
    if cell.kind == ir.EDGE:
        if geometry is not None:
            move = lambda p: None if p is None else (p[0] + dx, p[1] + dy)
            geometry.source_point = move(geometry.source_point)
            geometry.target_point = move(geometry.target_point)
            geometry.points = tuple(move(p) for p in geometry.points)
    elif geometry is not None:
        geometry.x += dx
        geometry.y += dy
    elif cell.kind == ir.FRAME and (dx or dy):
        cell.geometry = ir.Geometry(x=dx, y=dy)


def fold_transparent_frame(page, number, origin, log):
    """Fold a pure coordinate frame into its children.

    A nested cell that is neither vertex nor edge is never painted, hit or
    selected; the editor only adds its origin to its children. With no value,
    style, data or references it carries nothing else, so its children take
    its place in the draw order with the origin added exactly.
    """
    terminals = {ref for cell in page.cells.values() for ref in (cell.source, cell.target) if ref is not None}
    for cell in reversed(list(page.walk())):
        if cell.kind != ir.FRAME or frame_blockers(page, cell, terminals):
            continue
        parent = page.cells[cell.parent]
        dx, dy = (cell.geometry.x, cell.geometry.y) if cell.geometry is not None else ZERO
        for uid in cell.children:
            child = page.cells[uid]
            child.parent = parent.uid
            if dx or dy:
                shift(child, dx, dy)
        index = parent.children.index(cell.uid)
        parent.children[index:index + 1] = cell.children
        del page.cells[cell.uid]
        record = origin[cell.uid]
        record["folded_into"] = parent.uid
        record["frame_offset"] = [syntax.format_number(dx), syntax.format_number(dy)]
        log.add("fold_transparent_frame", number, {"cell": record["original_id"], "children": len(cell.children),
                                                   "offset": record["frame_offset"]})


RULES = (unwrap_trivial_user_object, canonical_style, drop_zero_offset, fold_transparent_frame)

# Reductions that were considered and are not applied, with the reason.
NOT_APPLIED = {
    "drop_default_style_values": "a key equal to the stylesheet default still shadows stylenames and shape "
                                 "defaults; no IR-level proof of redundancy",
    "drop_model_setting_defaults": "grid, guides, page and similar settings default differently per editor "
                                   "mode",
    "remove_vertex_groups": "a vertex group is selectable and moves its children; it is editing semantics",
    "merge_or_drop_layers": "layers are visible in the editor and control locking and visibility",
    "bind_or_free_edge_ends": "a bound end follows its terminal and a free end does not",
    "rename_anchor_ids": "IDs addressed by custom links are names, not storage",
    "rename_observed_ids": "the rough canvas seeds a sketch cell's strokes from a hash of its ID and a %id% "
                           "placeholder prints it; renaming either changes the drawing",
    "round_coordinates": "any rounding moves geometry",
}


def state(page):
    """A cheap fingerprint to detect a fixed point."""
    return (len(page.cells), sum(c.wrapper is not None for c in page.cells.values()),
            tuple(c.style for c in page.cells.values()),
            sum(c.geometry is not None and c.geometry.offset is not None for c in page.cells.values()))


def assign_names(page, origin):
    """Name cells by draw order; keep the IDs the editor observes.

    On a pinned page every ID is an anchor. Elsewhere a cell keeps its ID only
    when it has an ID role, and the others count up in draw order, stepping
    over the kept names. The kept names are semantic content, so the numbering
    is a function of the IR alone and any renaming of unobserved IDs converges.
    """
    if page.pinned:
        used = {origin[uid]["original_id"] for uid in page.cells} - {None}
        counter = 0
        for cell in page.walk():
            cell.name = origin[cell.uid]["original_id"]
            while cell.name is None:
                counter += 1
                if f"c{counter}" not in used:
                    cell.name = f"c{counter}"
                    used.add(cell.name)
    else:
        kept = {cell.uid: origin[cell.uid]["original_id"] for cell in page.cells.values()
                if cell.id_roles and origin[cell.uid]["original_id"] is not None}
        used = set(kept.values())
        counter = 0
        for cell in page.walk():
            cell.name = kept.get(cell.uid)
            while cell.name is None:
                if str(counter) not in used:
                    cell.name = str(counter)
                counter += 1
    for cell in page.cells.values():
        origin[cell.uid]["id"] = cell.name
    folded = {uid: record["folded_into"] for uid, record in origin.items() if "folded_into" in record}
    for uid, target in folded.items():
        while target in folded:
            target = folded[target]
        origin[uid]["folded_into"] = page.cells[target].name


def normalize(document, source_map):
    """Minimize in place. Returns (rule log, audit)."""
    log = Log()
    audit = {"fixed_point_passes": [], "retained": [], "not_applied": NOT_APPLIED}
    for number, (page, origin) in enumerate(zip(document.pages, source_map, strict=True), 1):
        passes = 0
        while True:
            before = state(page)
            for rule in RULES:
                rule(page, number, origin, log)
            passes += 1
            if state(page) == before:
                break
        audit["fixed_point_passes"].append(passes)
        assign_names(page, origin)
        audit["retained"].append(retained(page, number))
    ir.verify(document, named=True)
    return list(log.entries.values()), audit


def retained(page, number):
    """Count what the fixed point keeps because it is semantic."""
    cells = list(page.cells.values())
    terminals = {ref for c in cells for ref in (c.source, c.target) if ref is not None}
    frames = {}
    for cell in cells:
        if cell.kind == ir.FRAME:
            for reason in frame_blockers(page, cell, terminals):
                frames[reason] = frames.get(reason, 0) + 1
    edges = [c for c in cells if c.kind == ir.EDGE]
    return {
        "page": number,
        "cells": len(cells),
        "layers": sum(c.kind == ir.LAYER for c in cells),
        "vertices": sum(c.kind == ir.VERTEX for c in cells),
        "edges": len(edges),
        "vertex_containers": sum(c.kind == ir.VERTEX and bool(c.children) for c in cells),
        "bound_edge_ends": sum((c.source is not None) + (c.target is not None) for c in edges),
        "free_edge_ends": sum((c.source is None) + (c.target is None) for c in edges),
        "frames_kept_by_reason": frames,
        "user_objects_with_data": sum(c.wrapper is not None for c in cells),
        "stylenames": sum(1 for c in cells for key, _ in c.style or () if key is None),
        "cells_with_extensions": sum(bool(c.attrs or c.extras or (c.geometry and (c.geometry.attrs
                                                                                    or c.geometry.extras)))
                                     for c in cells),
        "cell_ids_are_anchors": page.pinned,
        "observed_cell_ids": {role: sum(role in c.id_roles for c in cells) for role in ir.ID_ROLES
                              if any(role in c.id_roles for c in cells)},
    }
