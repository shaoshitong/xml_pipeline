"""Match editable objects using native positions and topology."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html.parser import HTMLParser
from math import hypot
import re
import unicodedata

import networkx as nx
import numpy as np
from scipy.optimize import linear_sum_assignment


def union(boxes):
    boxes = [b for b in boxes if b is not None]
    if not boxes:
        return None
    x, y = min(b[0] for b in boxes), min(b[1] for b in boxes)
    return [x, y, max(b[0] + b[2] for b in boxes) - x, max(b[1] + b[3] for b in boxes) - y]


def center(box):
    return box[0] + box[2] / 2, box[1] + box[3] / 2


def contains(outer, inner, tolerance=2):
    return (outer[0] - tolerance <= inner[0] and outer[1] - tolerance <= inner[1]
            and outer[0] + outer[2] + tolerance >= inner[0] + inner[2]
            and outer[1] + outer[3] + tolerance >= inner[1] + inner[3])


class LabelParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.tables = []
        self.current_table = None
        self.simple_table = False

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "div", "p", "tr", "td", "th", "li"}:
            self.text.append(" ")
        if tag == "table" and self.current_table is None:
            self.current_table = []
            self.simple_table = dict(attrs).get("role") != "presentation"
        if tag == "tr" and self.current_table is not None:
            self.current_table.append(0)
        if tag in {"td", "th"} and self.current_table:
            attrs = dict(attrs)
            self.simple_table &= attrs.get("colspan", "1") == attrs.get("rowspan", "1") == "1"
            self.current_table[-1] += 1

    def handle_endtag(self, tag):
        if tag == "table" and self.current_table:
            if self.simple_table and len(self.current_table) >= 2 and min(self.current_table) >= 2:
                self.tables.append(self.current_table)
            self.current_table = None
        if tag in {"div", "p", "tr", "td", "th", "li"}:
            self.text.append(" ")

    def handle_data(self, data):
        self.text.append(data)


def label_info(cell):
    parser = LabelParser()
    label = cell["label"]
    if cell["style"].get("html") == "1":
        parser.feed(label)
        parser.close()
        label = "".join(parser.text)
    label = re.sub(r"\s+", " ", unicodedata.normalize("NFC", label)).strip()
    return label, parser.tables


@dataclass
class Object:
    kind: str
    cell: dict
    label: str
    members: list = field(default_factory=list)
    table: dict | None = None
    panel: str | None = None
    neighbors: tuple = ()

    @property
    def id(self):
        return self.cell["id"]

    @property
    def ids(self):
        return [self.id] + [member["id"] for member in self.members]

    @property
    def bbox(self):
        return self.cell.get("bbox")

    @property
    def extent(self):
        return union(c.get(key) for c in [self.cell, *self.members]
                     for key in ("bbox", "paint_bbox", "label_bbox"))

    @property
    def style(self):
        return self.cell["style"]

    @property
    def position(self):
        box = self.bbox or self.extent
        return center(box) if box else None


def object_type(cell, children, html_tables):
    style = cell["style"]
    tokens = cell["raw_style"].split(";")
    if cell["kind"] == "edge":
        return "edge"
    if (html_tables or style.get("shape") == "table" or "table" in tokens
            or any(child["style"].get("shape") == "tableRow" for child in children)):
        return "table"
    if (style.get("shape") == "swimlane" or style.get("container") == "1"
            or "group" in tokens or any(child["kind"] == "vertex" for child in children)):
        return "panel"
    raw_style = dict(token.split("=", 1) for token in tokens if "=" in token)
    if ("text" in tokens or style.get("shape") == "text" or
            raw_style.get("fillColor") == raw_style.get("strokeColor") == "none"):
        return "label"
    return "shape"


def table_grid(table, descendants, labels):
    rows = [row for row in descendants.get(table.id, []) if row["kind"] == "vertex"]
    row_cells = [[c for c in descendants.get(row["id"], []) if c["kind"] == "vertex"] for row in rows]
    if row_cells and all(row_cells):
        table.members = [cell for row, cells in zip(rows, row_cells) for cell in [row, *cells]]
        return {"rows": len(rows), "columns_by_row": list(map(len, row_cells)),
                "method": "native_row_cells",
                "labels": [[labels[c["id"]][0] for c in cells] for cells in row_cells]}
    return None


def drawn_grid(panel, descendants, labels, absorbed):
    cells = descendants[panel.id]
    # Transparent groups can wrap a complete grid without changing its rows
    # or columns. Keep those group cells as separate editable objects.
    while len(cells) == 1:
        group, = cells
        if (group["kind"] != "vertex" or group["raw_style"].rstrip(";") != "group"
                or labels[group["id"]][0] or group["collapsed"]):
            break
        cells = descendants[group["id"]]
    if not panel.bbox or len(cells) < 4 or any(
            c["id"] in absorbed or not c.get("bbox") or c["kind"] != "vertex" or descendants.get(c["id"])
            or c["style"].get("shape", "rectangle") not in {"rectangle", "label"}
            or c["style"].get("rotation", "0") != "0"
            or labels[c["id"]][1] for c in cells):
        return None
    rows = defaultdict(list)
    for c in cells:
        rows[round(c["bbox"][1], 1)].append(c)
    ordered = [sorted(row, key=lambda c: c["bbox"][0]) for _, row in sorted(rows.items())]
    cols = len(ordered[0])
    if len(ordered) < 2 or cols < 2 or any(len(row) != cols for row in ordered):
        return None
    origin_x, origin_y, width, height = panel.bbox
    expected_columns = [c["bbox"][::2] for c in ordered[0]]
    y = origin_y
    for row in ordered:
        x = origin_x
        row_height = row[0]["bbox"][3]
        for cell, (col_x, col_w) in zip(row, expected_columns, strict=True):
            cx, cy, cw, ch = cell["bbox"]
            if min(cw, ch) < 3 or max(abs(cx - x), abs(cy - y), abs(cw - col_w),
                                      abs(cx - col_x), abs(ch - row_height)) > .6:
                return None
            x += cw
        if abs(x - origin_x - width) > .6:
            return None
        y += row_height
    if abs(y - origin_y - height) > .6:
        return None
    panel.members = [c for row in ordered for c in row]
    return {"rows": len(ordered), "columns_by_row": [cols] * len(ordered),
            "method": "adjacent_rectangles_fill_group",
            "labels": [[labels[c["id"]][0] for c in row] for row in ordered]}


def table_captions(output, absorbed):
    tables = [o for o in output.values() if o.kind == "table" and o.table and o.bbox and not o.label]
    candidates = defaultdict(list)
    for label in output.values():
        if (label.kind != "label" or not label.bbox or label.id in absorbed
                or not re.search(r"\btable\b", label.label, re.IGNORECASE)):
            continue
        for table in tables:
            if table.cell["parent"] != label.cell["parent"]:
                continue
            gap = label.bbox[1] - (table.bbox[1] + table.bbox[3])
            offset = abs(center(label.bbox)[0] - center(table.bbox)[0])
            if -2 <= gap <= max(26, table.bbox[3] * .6) and offset <= min(label.bbox[2] / 2, 24):
                candidates[label.id].append((abs(gap) + offset, table.id))
    proposed = defaultdict(list)
    for label_id, nearby in candidates.items():
        nearby.sort()
        if len(nearby) == 1 or nearby[1][0] - nearby[0][0] >= 5:
            proposed[nearby[0][1]].append(label_id)
    for table_id, labels in proposed.items():
        if len(labels) == 1:
            table, label = output[table_id], output[labels[0]]
            table.label = label.label
            table.members.append(label.cell)
            absorbed.add(label.id)


def objects(snapshot):
    cells = snapshot.get("cells", [])
    children = defaultdict(list)
    for cell in cells:
        children[cell["parent"]].append(cell)
    labels = {c["id"]: label_info(c) for c in cells}
    output = {}
    absorbed = set()
    for cell in cells:
        if cell["kind"] not in {"vertex", "edge"}:
            continue
        key = cell["id"]
        label, html_tables = labels[key]
        kind = object_type(cell, children[key], html_tables)
        obj = Object(kind, cell, label)
        if kind == "table":
            if len(html_tables) == 1:
                counts = html_tables[0]
                obj.table = {"rows": len(counts), "columns_by_row": counts, "method": "html_table"}
            else:
                obj.table = table_grid(obj, children, labels)
            absorbed.update(obj.ids[1:])
        elif kind == "panel" and obj.bbox and not obj.label:
            obj.table = drawn_grid(obj, children, labels, absorbed)
            if obj.table:
                obj.kind = "table"
                absorbed.update(obj.ids[1:])
        output[key] = obj

    table_captions(output, absorbed)
    # Associate a single centered text cell with an otherwise unlabeled box.
    # Keep both cells in the evidence and check their edit behavior separately.
    boxes = [o for o in output.values() if o.kind == "shape" and o.bbox and not o.label
             and o.style.get("shape", "rectangle") in {"rectangle", "rect", "label"}
             and "image=" not in o.cell["raw_style"] and o.id not in absorbed]
    assignments = defaultdict(list)
    for text in output.values():
        if text.kind != "label" or not text.label or text.id in absorbed:
            continue
        bbox = text.cell.get("label_bbox") or text.bbox
        if bbox is None:
            continue
        hosts = [box for box in boxes if box.cell["parent"] == text.cell["parent"] and
                 contains(box.bbox, bbox) and hypot(*(x - y for x, y in zip(center(box.bbox), center(bbox)))) <=
                 max(5, min(box.bbox[2:]) * .25)]
        if len(hosts) == 1:
            assignments[hosts[0].id].append(text)
    for key, texts in assignments.items():
        if len(texts) == 1:
            output[key].label = texts[0].label
            output[key].members.append(texts[0].cell)
            absorbed.add(texts[0].id)
    output = {k: o for k, o in output.items() if k not in absorbed}
    owners = {cell_id: obj.id for obj in output.values() for cell_id in obj.ids}
    for obj in output.values():
        parent = output.get(owners.get(obj.cell["parent"]))
        while parent is not None and parent.kind not in {"panel", "table"}:
            parent = output.get(owners.get(parent.cell["parent"]))
        obj.panel = parent.id if parent is not None else None

    topology = nx.MultiDiGraph()
    for obj in output.values():
        if obj.kind == "edge":
            a, b = (owners.get(obj.cell[end]) for end in ("source", "target"))
            if a is not None and b is not None:
                topology.add_edge(a, b)
    for key in topology:
        neighbors = set(topology.predecessors(key)) | set(topology.successors(key))
        output[key].neighbors = tuple(sorted(output[n].label.casefold() for n in neighbors if output[n].label))
    return output, owners


def distance(a, b):
    return hypot(a[0] - b[0], a[1] - b[1])


def similarity(a, b, span):
    if a.kind != b.kind:
        return 0
    if a.position is None or b.position is None:
        geometry = .5 if a.position == b.position else 0
    else:
        size = max(15, min(max((a.bbox or a.extent)[2:]), max((b.bbox or b.extent)[2:])))
        geometry = max(0, 1 - distance(a.position, b.position) / max(size * 2, span * .12))
    x, y = a.label.casefold(), b.label.casefold()
    if x and y:
        text = SequenceMatcher(None, x, y, autojunk=False).ratio()
    else:
        text = .67 if not x and not y else .14
    neighborhood = (len(set(a.neighbors) & set(b.neighbors)) /
                    len(set(a.neighbors) | set(b.neighbors))) if a.neighbors and b.neighbors else .5
    shape = .07 if a.style.get("shape", "rectangle") == b.style.get("shape", "rectangle") else 0
    return .48 * text + .36 * geometry + .09 * neighborhood + shape


def assign(left, right, scorer, threshold, margin=.055):
    if not left or not right:
        return []
    matrix = np.array([[scorer(a, b) for b in right] for a in left], dtype=float)
    padded = np.concatenate([matrix, np.full((len(left), len(left)), threshold)], axis=1)
    rows, cols = linear_sum_assignment(padded, maximize=True)
    found = []
    for i, j in zip(rows, cols):
        if j >= len(right) or matrix[i, j] <= threshold:
            continue
        alternatives = np.concatenate([np.delete(matrix[i], j), np.delete(matrix[:, j], i)])
        separated = not len(alternatives) or matrix[i, j] - max(alternatives) >= margin
        found.append((left[i], right[j], "confirmed" if separated else "suspected",
                      round(float(matrix[i, j]), 3)))
    return found


def same_cell_except_parent(a, b, *, allow_label_edit=False):
    coordinates = {"bbox", "paint_bbox", "label_bbox", "points"}
    for key, value in a.items():
        if key == "parent" or value == b[key]:
            continue
        if allow_label_edit and key in {"label", "label_bbox"}:
            continue
        other = b[key]
        if key not in coordinates or value is None or other is None or len(value) != len(other):
            return False
        if key == "points":
            if any(p != q and (p is None or q is None or distance(p, q) > 1e-6)
                   for p, q in zip(value, other, strict=True)):
                return False
        elif any(abs(p - q) > 1e-6 for p, q in zip(value, other, strict=True)):
            return False
    return True


def anchored_matches(left, right, *, compare_labels=False):
    # An ID is useful across revisions only when its observed native fields
    # corroborate the match. Parent changes can come from inserting a group.
    by_id = {o.id: o for o in right}
    matches = []
    for a in left:
        b = by_id.get(a.id)
        if b is None or a.kind != b.kind or a.ids != b.ids:
            continue
        # A complete label replacement can have no lexical overlap. A stable
        # ID and unchanged native bounds and style still identify the cell.
        label_edit = compare_labels and a.bbox is not None and a.bbox == b.bbox
        if (a.label == b.label or label_edit) and all(
                same_cell_except_parent(x, y, allow_label_edit=label_edit)
                for x, y in zip([a.cell, *a.members], [b.cell, *b.members], strict=True)):
            matches.append((a, b, "confirmed", 1.0))
    return matches


def match_vertices(left, right, span):
    # Exact unique labels can survive a large absolute movement. Repeated
    # labels go through geometry, adjacency and matched panel context.
    a = [o for o in left.values() if o.kind != "edge"]
    b = [o for o in right.values() if o.kind != "edge"]
    exact = anchored_matches(a, b, compare_labels=True)
    used_a, used_b = {x.id for x, *_ in exact}, {y.id for _, y, *_ in exact}
    a, b = [o for o in a if o.id not in used_a], [o for o in b if o.id not in used_b]
    a_labels = Counter((o.kind, o.label) for o in a)
    b_labels = Counter((o.kind, o.label) for o in b)
    unique = {(o.kind, o.label): o for o in b if o.label and b_labels[o.kind, o.label] == 1}
    exact.extend((o, unique[o.kind, o.label], "confirmed", 1.0) for o in a if
                 a_labels[o.kind, o.label] == 1 and (o.kind, o.label) in unique)
    used_a, used_b = {x.id for x, *_ in exact}, {y.id for _, y, *_ in exact}
    panels = {x.id: y.id for x, y, *_ in exact if x.kind in {"panel", "table"}}

    def score(x, y):
        base = similarity(x, y, span)
        if x.panel in panels:
            return base + .07 if panels[x.panel] == y.panel else base - .14
        return base

    remaining_a = [o for o in a if o.id not in used_a]
    remaining_b = [o for o in b if o.id not in used_b]
    containers = {"panel", "table"}
    approximate_panels = assign([o for o in remaining_a if o.kind in containers],
                                [o for o in remaining_b if o.kind in containers], score, .52)
    panels.update((x.id, y.id) for x, y, status, _ in approximate_panels if status == "confirmed")
    rest = assign([o for o in remaining_a if o.kind not in containers],
                  [o for o in remaining_b if o.kind not in containers], score, .52)
    return exact + approximate_panels + rest


def terminal_at(edge, end, cells, owners):
    raw = edge.cell[end]
    if raw is not None:
        return owners.get(raw), raw
    points = edge.cell["points"]
    if not points:
        return None, None
    point = points[0 if end == "source" else -1]
    if point is None:
        return None, None
    candidates = []
    for obj in cells.values():
        if obj.kind not in {"shape", "table", "panel"} or obj.bbox is None:
            continue
        x, y, w, h = obj.bbox
        dx, dy = min(abs(point[0] - x), abs(point[0] - x - w)), min(abs(point[1] - y), abs(point[1] - y - h))
        horizontal = dx if y - 5 <= point[1] <= y + h + 5 else 100
        vertical = dy if x - 5 <= point[0] <= x + w + 5 else 100
        gap = min(horizontal, vertical)
        if gap <= 5:
            candidates.append((gap, obj.id))
    candidates.sort()
    if candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] >= 2):
        return candidates[0][1], candidates[0][1]
    return None, None


def edge_score(a, b, terminals_a, terminals_b, mapping, span):
    x = [mapping.get(key) for key, _ in terminals_a[a.id]]
    y = [key for key, _ in terminals_b[b.id]]
    common = max(sum(p is not None and p == q for p, q in zip(x, order))
                 for order in (y, list(reversed(y))))
    p, q = a.cell["points"], b.cell["points"]
    geom = 0
    if p and q and all(v is not None for v in (p[0], p[-1], q[0], q[-1])):
        gap = min(distance(p[0], q[0]) + distance(p[-1], q[-1]),
                  distance(p[0], q[-1]) + distance(p[-1], q[0]))
        geom = max(0, 1 - gap / max(20, span * .18))
    label = 1 if a.label and a.label == b.label else 0
    return max(.46 * common + .16 * geom + .09 * label, .72 * geom + .13 * label)


def arrows(obj):
    return [obj.style.get(k, "none") for k in ("startArrow", "endArrow")]


def ordered_native_correspondence(a, b):
    before, after = a["cells"], b["cells"]
    if a.get("bounds") != b.get("bounds") or len(before) != len(after):
        return None
    # The editor exposes tree traversal order. Accept positional correspondence
    # only when the entire native snapshot agrees under the proposed ID map.
    ids = {x["id"]: y["id"] for x, y in zip(before, after, strict=True)}
    for x, y in zip(before, after, strict=True):
        renamed = {**x, **{key: ids.get(x[key], x[key]) for key in ("id", "parent", "source", "target")}}
        if renamed != y:
            return None
    return ids


def compare_page(snap_a, snap_b, span):
    a, owners_a = objects(snap_a)
    b, owners_b = objects(snap_b)
    native_ids = ordered_native_correspondence(snap_a, snap_b)
    if native_ids is not None and {native_ids[key] for key in a} == b.keys():
        return [(obj, b[native_ids[key]], "confirmed", 1.0) for key, obj in a.items()], []
    vertices = match_vertices(a, b, span)
    mapping = {x.id: y.id for x, y, status, _ in vertices if status == "confirmed"}
    edges_a = [o for o in a.values() if o.kind == "edge"]
    edges_b = [o for o in b.values() if o.kind == "edge"]
    terminal_a = {o.id: [terminal_at(o, end, a, owners_a) for end in ("source", "target")] for o in edges_a}
    terminal_b = {o.id: [terminal_at(o, end, b, owners_b) for end in ("source", "target")] for o in edges_b}
    edges = anchored_matches(edges_a, edges_b)
    anchored_a, anchored_b = {x.id for x, *_ in edges}, {y.id for _, y, *_ in edges}
    edges += assign([o for o in edges_a if o.id not in anchored_a],
                    [o for o in edges_b if o.id not in anchored_b],
                    lambda x, y: edge_score(x, y, terminal_a, terminal_b, mapping, span), .56)
    diagnostics = []
    matches = vertices + edges

    def add(kind, status, x, y, a_value=None, b_value=None, probes=None):
        diagnostics.append({"kind": kind, "status": status, "a_object": x, "b_object": y,
                            "a_value": a_value, "b_value": b_value, "probes": probes})

    for x, y, status, score in matches:
        if status == "suspected":
            add("ambiguous_correspondence", status, x, y, score, score)
        if x.label != y.label:
            add("label_changed", status, x, y, x.label, y.label)
        if x.cell["visible"] != y.cell["visible"]:
            add("visibility_changed", status, x, y, x.cell["visible"], y.cell["visible"])
        if x.cell["collapsed"] != y.cell["collapsed"]:
            add("collapsed_state_changed", status, x, y, x.cell["collapsed"], y.cell["collapsed"])
        if x.kind == "edge":
            appearance = ("strokeColor", "fontColor")
        else:
            appearance = ("shape", "rotation", "fillColor", "strokeColor", "strokeWidth",
                          "dashed", "opacity", "fontSize", "fontColor", "fontFamily")
            if x.members or y.members:
                appearance = appearance[:-3]
        styles = [x.style, y.style]
        if x.kind == "shape" and (x.members or y.members):
            appearance += ("fontColor",)
            styles = [{**obj.style, "fontColor": obj.members[0]["style"].get("fontColor")}
                      if obj.members else obj.style for obj in (x, y)]
        changed = [key for key in appearance if styles[0].get(key) != styles[1].get(key)]
        if x.kind != "edge":
            if x.bbox and y.bbox:
                if distance(x.bbox[:2], y.bbox[:2]) > 2:
                    add(f"{x.kind}_moved", status, x, y, x.bbox[:2], y.bbox[:2])
                if distance(x.bbox[2:], y.bbox[2:]) > 2:
                    add(f"{x.kind}_resized", status, x, y, x.bbox[2:], y.bbox[2:])
            if x.kind == "table":
                if x.table is None or y.table is None:
                    add("table_grid_unresolved", "unknown", x, y, x.table, y.table)
                elif x.table["columns_by_row"] != y.table["columns_by_row"]:
                    add("table_grid_changed", status, x, y, x.table, y.table)
                elif all("labels" in t for t in (x.table, y.table)) and x.table["labels"] != y.table["labels"]:
                    add("table_cell_text_changed", status, x, y, x.table["labels"], y.table["labels"])
            if x.kind == "shape" and bool(x.members) != bool(y.members):
                add("label_edit_binding_changed", status, x, y,
                    "separate_cell" if x.members else "node_value",
                    "separate_cell" if y.members else "node_value",
                    [{"label": obj.members[0]["id"] if obj.members else obj.id, "node": obj.id}
                     for obj in (x, y)])
            if changed:
                add("appearance_style_changed", status, x, y,
                    *({key: style.get(key) for key in changed} for style in styles))
            continue

        if changed:
            add("appearance_style_changed", status, x, y,
                *({key: style.get(key) for key in changed} for style in styles))
        ax, bx = terminal_a[x.id], terminal_b[y.id]
        mapped = [mapping.get(key) for key, _ in ax]
        order = [key for key, _ in bx]
        reversed_order = all(mapped) and mapped == order[::-1] and mapped != order
        old_arrows, new_arrows = arrows(x), arrows(y)
        semantic_arrows = new_arrows[::-1] if reversed_order else new_arrows
        route_a, route_b = x.cell["points"], y.cell["points"]
        if (reversed_order and ((old_arrows[0] == "none") != (old_arrows[1] == "none"))
                and ((semantic_arrows[0] == "none") != (semantic_arrows[1] == "none"))
                and (old_arrows[0] == "none") != (semantic_arrows[0] == "none")):
            add("edge_direction_reversed", status, x, y,
                [key for key, _ in ax] + [old_arrows], order + [new_arrows])
        elif all(mapped) and all(order) and mapped != order and not reversed_order:
            add("edge_terminals_changed", status, x, y, [key for key, _ in ax], order)
        elif old_arrows != semantic_arrows:
            add("edge_arrowheads_changed", status, x, y, old_arrows, semantic_arrows)
        if reversed_order and route_b:
            route_b = route_b[::-1]
        if route_a and route_b and all(p is not None for p in route_a + route_b) and (
                len(route_a) != len(route_b) or any(distance(p, q) > 2 for p, q in zip(route_a, route_b))):
            add("edge_route_changed", status, x, y, route_a, route_b)
        for i, end_a in enumerate(("source", "target")):
            j = 1 - i if reversed_order else i
            end_b = ("source", "target")[j]
            if bool(x.cell[end_a]) == bool(y.cell[end_b]):
                continue
            # Only assert that the two probes test corresponding nodes if the
            # free endpoint is unambiguously on the matched counterpart.
            pair = None
            if ax[i][1] and bx[j][1] and mapped[i] == order[j]:
                pair = [{"edge": x.id, "node": ax[i][1], "end": end_a},
                        {"edge": y.id, "node": bx[j][1], "end": end_b}]
            add("edge_binding_changed", status, x, y,
                {"end": end_a, "terminal": x.cell[end_a]},
                {"end": end_b, "terminal": y.cell[end_b]}, pair)
    used_a, used_b = {x.id for x, *_ in matches}, {y.id for _, y, *_ in matches}
    for x in a.values():
        if x.id not in used_a:
            add("unmatched_" + x.kind, "unmatched", x, None, x.label or x.kind)
    for y in b.values():
        if y.id not in used_b:
            add("unmatched_" + y.kind, "unmatched", None, y, None, y.label or y.kind)
    return matches, diagnostics
