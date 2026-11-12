"""Stage 3: the typed graph IR and its verifier.

Cells form one tree per page. Sibling order is draw order. An edge end is
either bound to a cell (``source``/``target``) or free geometry
(``source_point``/``target_point``); the two stay distinct because the editor
moves bound ends with their terminals. Geometry is local to the parent; page
coordinates are derived by :func:`page_origins`.

A cell ID is storage unless the editor observes it. ``id_roles`` names how it
does: ``sketch_seed`` (the rough canvas seeds its strokes from the ID) and
``placeholder`` (a ``%id%`` placeholder prints it). Such a cell keeps its ID.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from syntax import format_number

IR_VERSION = "drawio-semantic-ir/2"

ROOT, LAYER, FRAME, VERTEX, EDGE = "root", "layer", "frame", "vertex", "edge"
KINDS = (ROOT, LAYER, FRAME, VERTEX, EDGE)
SKETCH_SEED, PLACEHOLDER = "sketch_seed", "placeholder"
ID_ROLES = (SKETCH_SEED, PLACEHOLDER)
CELL_OPTIONS = (("connectable", True), ("visible", True), ("collapsed", False))


class IRError(Exception):
    """The IR violates one of its own invariants; a compiler defect, not an input error."""


@dataclass
class Geometry:
    x: Decimal = Decimal(0)
    y: Decimal = Decimal(0)
    width: Decimal = Decimal(0)
    height: Decimal = Decimal(0)
    relative: bool = False
    offset: tuple | None = None          # (x, y) label or relative-child offset
    source_point: tuple | None = None    # free edge ends and fallbacks
    target_point: tuple | None = None
    points: tuple = ()                   # edge waypoints, each (x, y)
    alternate_bounds: tuple | None = None  # (x, y, width, height) of the collapsed form
    attrs: tuple = ()                    # unrecognized attributes, sorted (name, value)
    extras: tuple = ()                   # unrecognized child elements, canonical XML

    def to_json(self):
        result = {}
        for key in ("x", "y", "width", "height"):
            if getattr(self, key) != 0:
                result[key] = format_number(getattr(self, key))
        if self.relative:
            result["relative"] = True
        for key in ("offset", "source_point", "target_point", "alternate_bounds"):
            if getattr(self, key) is not None:
                result[key] = [format_number(v) for v in getattr(self, key)]
        if self.points:
            result["points"] = [[format_number(v) for v in p] for p in self.points]
        if self.attrs:
            result["attributes"] = [list(item) for item in self.attrs]
        if self.extras:
            result["extensions"] = list(self.extras)
        return result


@dataclass
class Cell:
    uid: int
    kind: str
    parent: int | None = None
    children: list = field(default_factory=list)
    label: str | None = None
    wrapper: str | None = None           # user-object element name when the value carries data
    data: tuple = ()                     # user-object attributes besides the label, sorted
    wrapper_extras: tuple = ()           # child content of the user object, canonical XML
    style: tuple | None = None           # ordered style tokens
    geometry: Geometry | None = None
    source: int | None = None
    target: int | None = None
    connectable: bool = True
    visible: bool = True
    collapsed: bool = False
    attrs: tuple = ()                    # unrecognized mxCell attributes, sorted
    extras: tuple = ()                   # unrecognized mxCell children, canonical XML
    id_roles: tuple = ()                 # how the editor observes the ID; non-empty keeps the ID
    name: str | None = None              # the ID in emitted XML


@dataclass
class Page:
    name: str | None
    anchor: str | None                   # page ID, kept only while something refers to it
    attrs: tuple                         # other <diagram> attributes, sorted
    model_attrs: tuple                   # <mxGraphModel> settings, sorted
    extras: tuple                        # other children of <diagram>
    model_extras: tuple                  # children of <mxGraphModel> besides <root>
    cells: dict                          # uid -> Cell
    root: int
    pinned: bool = False                 # cell IDs are named anchors and keep their names

    def walk(self):
        """Cells in draw order: parents first, siblings back to front."""
        stack = [self.root]
        while stack:
            cell = self.cells[stack.pop()]
            yield cell
            stack.extend(reversed(cell.children))


@dataclass
class Document:
    attrs: tuple                         # <mxfile> attributes with editor meaning, sorted
    extras: tuple                        # non-page children of <mxfile>
    pages: list

    def to_json(self):
        pages = []
        for page in self.pages:
            cells = []
            for cell in page.walk():
                record = {"id": cell.name, "kind": cell.kind}
                if cell.parent is not None:
                    record["parent"] = page.cells[cell.parent].name
                if cell.label is not None:
                    record["label"] = cell.label
                if cell.wrapper is not None:
                    record["user_object"] = {"element": cell.wrapper, "data": [list(i) for i in cell.data]}
                    if cell.wrapper_extras:
                        record["user_object"]["extensions"] = list(cell.wrapper_extras)
                if cell.style is not None:
                    record["style"] = [list(token) for token in cell.style]
                if cell.geometry is not None:
                    record["geometry"] = cell.geometry.to_json()
                for end, terminal in (("source", cell.source), ("target", cell.target)):
                    if terminal is not None:
                        record[end] = page.cells[terminal].name
                for key, default in CELL_OPTIONS:
                    value = getattr(cell, key)
                    if value != default:
                        record[key] = value
                if cell.attrs:
                    record["attributes"] = [list(item) for item in cell.attrs]
                if cell.extras:
                    record["extensions"] = list(cell.extras)
                if cell.id_roles:
                    record["id_roles"] = list(cell.id_roles)
                cells.append(record)
            record = {"name": page.name, "id": page.anchor, "settings": [list(i) for i in page.model_attrs],
                      "cell_ids_are_anchors": page.pinned, "cells": cells}
            if page.attrs:
                record["attributes"] = [list(item) for item in page.attrs]
            if page.extras or page.model_extras:
                record["extensions"] = {"page": list(page.extras), "model": list(page.model_extras)}
            pages.append(record)
        result = {"ir": IR_VERSION, "pages": pages}
        if self.attrs:
            result["attributes"] = [list(item) for item in self.attrs]
        if self.extras:
            result["extensions"] = list(self.extras)
        return result


def _finite(value):
    return isinstance(value, Decimal) and value.is_finite()


def verify(document, named=False):
    """Check the IR invariants. ``named`` also requires unique emitted IDs."""
    if not document.pages:
        raise IRError("document has no pages")
    for number, page in enumerate(document.pages, 1):
        cells = page.cells

        def bad(cell, message):
            raise IRError(f"page {number} cell {cell.name or cell.uid}: {message}")

        root = cells.get(page.root)
        if root is None or root.kind != ROOT or root.parent is not None:
            raise IRError(f"page {number}: root cell is missing or has a parent")
        reached = set()
        for cell in page.walk():
            if cell.uid in reached:
                bad(cell, "reached twice; the parent relation is not a tree")
            reached.add(cell.uid)
            if cell.kind not in KINDS:
                bad(cell, f"unknown kind {cell.kind!r}")
            if cells.get(cell.uid) is not cell:
                bad(cell, "is not registered under its own uid")
            for child in cell.children:
                if child not in cells or cells[child].parent != cell.uid:
                    bad(cell, f"child {child} does not name it as parent")
            if cell.kind == ROOT:
                if cell.uid != page.root:
                    bad(cell, "second root")
            else:
                parent = cells[cell.parent]
                if (cell.kind == LAYER) != (parent.kind == ROOT and cell.kind not in (VERTEX, EDGE)):
                    bad(cell, "layer kind disagrees with its position under the root")
            for end in ("source", "target"):
                ref = getattr(cell, end)
                if ref is not None and ref not in cells:
                    bad(cell, f"{end} terminal {ref} is not a cell of this page")
            geometry = cell.geometry
            if geometry is not None:
                numbers = [geometry.x, geometry.y, geometry.width, geometry.height]
                for group in (geometry.offset, geometry.source_point, geometry.target_point,
                              geometry.alternate_bounds, *geometry.points):
                    numbers.extend(group or ())
                if not all(_finite(v) for v in numbers):
                    bad(cell, "geometry is not finite")
            if cell.wrapper is None and (cell.data or cell.wrapper_extras):
                bad(cell, "data without a user object")
            if cell.style is not None and not cell.style:
                bad(cell, "empty style must be absent")
            if cell.label == "":
                bad(cell, "empty label must be absent")
            if set(cell.id_roles) - set(ID_ROLES):
                bad(cell, f"unknown ID role in {cell.id_roles!r}")
        for cell in cells.values():
            if cell.uid not in reached:
                bad(cell, "is not reachable from the root")
            for end in ("source", "target"):
                ref = getattr(cell, end)
                if ref is not None and ref not in reached:
                    bad(cell, f"{end} terminal is outside the model")
        if named:
            names = [cell.name for cell in cells.values()]
            if None in names or "" in names or len(set(names)) != len(names):
                raise IRError(f"page {number}: emitted cell IDs are missing or not unique")


def page_origins(page):
    """Page coordinates of each cell's local origin, as the editor's view sums them.

    Returns uid -> (x, y), or None where the position depends on rendered
    geometry (children of edges and cells with relative geometry).
    """
    origins = {}
    for cell in page.walk():
        parent = page.cells.get(cell.parent) if cell.parent is not None else None
        base = (Decimal(0), Decimal(0)) if parent is None else origins[parent.uid]
        geometry = cell.geometry
        if base is None or (parent is not None and parent.kind == EDGE):
            origins[cell.uid] = None
        elif cell.kind == EDGE or geometry is None:
            origins[cell.uid] = base
        elif geometry.relative:
            if parent is None or parent.geometry is None:
                origins[cell.uid] = None
            else:
                offset = geometry.offset or (Decimal(0), Decimal(0))
                origins[cell.uid] = (base[0] + geometry.x * parent.geometry.width + offset[0],
                                     base[1] + geometry.y * parent.geometry.height + offset[1])
        else:
            origins[cell.uid] = (base[0] + geometry.x, base[1] + geometry.y)
    return origins
