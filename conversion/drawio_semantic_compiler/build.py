"""Stages 2-3: parse cell records and build the verified graph IR.

Reading follows the pinned editor's codec, so the IR states what the editor
would hold after opening the file. Structures the codec would silently repair
or discard in ways that lose the author's intent are reported as errors with
the page and source position of the offending cell.
"""

from collections import Counter
from decimal import Decimal

import ir
from source import CompileError, Diagnostic, Element, RuleLog, attribute_loc, xml_attributes
import syntax

# Written by the editor on save; none of them changes the drawing or how it edits.
FILE_METADATA = frozenset({"host", "modified", "agent", "etag", "version", "type", "compressed", "pages"})
# The scroll position of the last editing session.
VIEW_STATE = frozenset({"dx", "dy"})
CELL_FIELDS = frozenset({"id", "value", "style", "parent", "source", "target", "vertex", "edge",
                         "connectable", "visible", "collapsed"})
GEOMETRY_FIELDS = frozenset({"x", "y", "width", "height", "relative", "as"})
ID_PLACEHOLDER = "%id%"
POINT_ROLES = {"sourcePoint": "source_point", "targetPoint": "target_point", "offset": "offset"}


def escape_text(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")


def fragment(element):
    """Canonical XML of content the compiler carries through without interpreting."""
    attributes = xml_attributes(sorted(element.attrs.items()))
    nested = any(isinstance(child, Element) for child in element.children)
    body = []
    for child in element.children:
        if isinstance(child, Element):
            body.append(fragment(child))
        elif not nested or child.strip():
            body.append(escape_text(child))
    if not body:
        return f"<{element.tag}{attributes}/>"
    return f"<{element.tag}{attributes}>{''.join(body)}</{element.tag}>"


class Builder:
    def __init__(self, source):
        self.source = source
        self.diagnostics = list(source.diagnostics)
        self.errors = []
        self.changes = RuleLog()
        self.source_map = []   # per page: uid -> origin record

    def note(self, severity, code, message, element, cell_id=None, attribute=None, data=None):
        loc = attribute_loc(data, element, attribute) if attribute is not None and data is not None else element.loc
        diagnostics = self.errors if severity == "error" else self.diagnostics
        diagnostics.append(Diagnostic(severity, code, message, loc, cell_id, attribute))

    def read_flag(self, element, key, default, cell_id, data):
        text = element.get(key)
        value, canonical = syntax.flag(text, default)
        if not canonical:
            self.note("warning", "noncanonical_flag", f"{key}={text!r} is read as {'1' if value else '0'}",
                      element, cell_id, key, data)
        return value

    def document(self):
        source = self.source
        text = source.data
        keep_page_ids = b"data:page/id," in text or any(
            b"data:page/id," in page.data for page in source.pages if page.data is not text)
        attrs = ()
        if source.container is not None:
            dropped = sorted(FILE_METADATA & source.container.attrs.keys())
            if dropped:
                self.changes.add("drop_file_metadata", None, dropped)
            attrs = tuple(sorted((k, v) for k, v in source.container.attrs.items() if k not in FILE_METADATA))
        pages = [self.page(page, keep_page_ids) for page in source.pages]
        if self.errors:
            raise CompileError(self.errors + self.diagnostics)
        document = ir.Document(attrs, tuple(fragment(e) for e in source.extras), pages)
        ir.verify(document)
        return document

    def page(self, page, keep_page_ids):
        number, model, data = page.index, page.model, page.data
        diagram = page.diagram
        name = anchor = None
        attrs = ()
        if diagram is not None:
            name = diagram.get("name")
            anchor = diagram.get("id") if keep_page_ids else None
            if diagram.get("id") is not None and not keep_page_ids:
                self.changes.add("drop_unreferenced_page_id", number)
            attrs = tuple(sorted((k, v) for k, v in diagram.attrs.items() if k not in ("id", "name")))
        if page.encoding != "plain":
            self.changes.add("unpack_" + page.encoding + "_page", number)
        view = sorted(VIEW_STATE & model.attrs.keys())
        if view:
            self.changes.add("drop_view_state", number, view)
        model_attrs = tuple(sorted((k, v) for k, v in model.attrs.items() if k not in VIEW_STATE))
        roots = model.elements("root")
        if len(roots) != 1:
            self.note("error", "model_root", f"expected one <root> in the graph model, found {len(roots)}", model)
            roots = roots[:1]
        model_extras = tuple(fragment(e) for e in model.elements() if e.tag != "root")
        pinned = b"data:action/json" in data
        if pinned:
            self.note("info", "cell_ids_are_anchors", "the page has custom action links that address cells "
                      "by ID; cell IDs keep their names", model)

        cells, origin, by_id, raw = {}, {}, {}, {}
        for index, outer in enumerate(roots[0].elements() if roots else (), 1):
            cell = self.cell(len(cells), outer, number, data)
            if cell is None:
                continue
            record, cell_id, inner = cell
            if cell_id is not None:
                if cell_id in by_id:
                    self.note("error", "duplicate_id", f"cell ID {cell_id!r} is already used on this page",
                              outer, cell_id, "id", data)
                    continue
                by_id[cell_id] = record.uid
            cells[record.uid] = record
            raw[record.uid] = inner
            origin[record.uid] = {"original_id": cell_id, "element": outer.tag, "root_child_index": index,
                                  "location": outer.loc.to_json()}
            if record.id_roles:
                origin[record.uid]["id_roles"] = list(record.id_roles)
        self.source_map.append(origin)
        observed = Counter(role for record in cells.values() for role in record.id_roles)
        for role, count in sorted(observed.items()):
            self.note("info", "cell_id_is_observed", f"{count} cell ID(s) on this page are observed by the "
                      f"editor as {role} and keep their names", model)

        parentless = [uid for uid in cells if raw[uid].get("parent") is None]
        if len(parentless) != 1:
            for uid in parentless[1:] or [None]:
                element = raw[uid] if uid is not None else model
                cell_id = origin[uid]["original_id"] if uid is not None else None
                self.note("error", "model_root", "the model needs exactly one cell without a parent; "
                          f"found {len(parentless)}", element, cell_id)
        root = parentless[0] if parentless else None
        for uid, cell in cells.items():
            element, cell_id = raw[uid], origin[uid]["original_id"]
            ref = element.get("parent")
            if ref is not None:
                if ref not in by_id:
                    self.note("error", "unresolved_parent", f"parent {ref!r} is not a cell of this page",
                              element, cell_id, "parent", data)
                elif by_id[ref] == uid:
                    self.note("error", "parent_cycle", "cell is its own parent", element, cell_id, "parent", data)
                else:
                    cell.parent = by_id[ref]
                    cells[cell.parent].children.append(uid)
            for end in ("source", "target"):
                ref = element.get(end)
                if ref is None:
                    continue
                if cell.kind != ir.EDGE:
                    self.note("error", "terminal_on_non_edge", f"only edges can have a {end} terminal",
                              element, cell_id, end, data)
                elif ref not in by_id:
                    self.note("warning", "dangling_terminal", f"{end} terminal {ref!r} is not a cell of this "
                              "page; the editor opens the edge with that end unconnected",
                              element, cell_id, end, data)
                    self.changes.add("drop_dangling_terminal", number, {"cell": cell_id, "end": end, "terminal": ref})
                else:
                    setattr(cell, end, by_id[ref])
        if root is not None:
            cells[root].kind = ir.ROOT
            reached, stack = set(), [root]
            while stack:
                uid = stack.pop()
                reached.add(uid)
                stack.extend(cells[uid].children)
            for uid, cell in cells.items():
                if uid not in reached and cell.parent is not None:
                    element, cell_id = raw[uid], origin[uid]["original_id"]
                    self.note("error", "parent_cycle", "cell is not connected to the model root through its "
                              "parents", element, cell_id, "parent", data)
                elif cell.kind == ir.FRAME and cell.parent == root:
                    cell.kind = ir.LAYER
        return ir.Page(name, anchor, attrs, model_attrs, tuple(fragment(e) for e in page.extras),
                       model_extras, cells, root if root is not None else -1, pinned)

    def cell(self, uid, outer, number, data):
        if outer.tag == "mxCell":
            inner, cell_id, wrapper = outer, outer.get("id"), None
        else:
            found = outer.elements("mxCell")
            if len(found) != 1:
                detail = "holds more than one <mxCell>" if found else "in the model root holds no <mxCell>"
                self.note("error", "user_object_without_cell", f"<{outer.tag}> {detail}", outer, outer.get("id"))
                return None
            inner, cell_id, wrapper = found[0], outer.get("id"), outer.tag
            if inner.get("id") is not None:
                self.note("info" if cell_id is not None else "warning", "inner_id_ignored",
                          "the editor takes a user object's ID from the outer element and ignores the "
                          "ID on its <mxCell>", inner, cell_id, "id", data)
        if cell_id is None:
            self.note("info", "missing_id", "cell has no ID; nothing can refer to it", outer)

        vertex = self.read_flag(inner, "vertex", False, cell_id, data)
        edge = self.read_flag(inner, "edge", False, cell_id, data)
        if vertex and edge:
            self.note("error", "vertex_and_edge", "a cell cannot be both a vertex and an edge",
                      inner, cell_id, "edge", data)
        options = {key: self.read_flag(inner, key, default, cell_id, data)
                   for key, default in ir.CELL_OPTIONS}
        kind = ir.VERTEX if vertex else ir.EDGE if edge else ir.FRAME
        cell = ir.Cell(uid, kind, **options)
        flags = {"vertex": vertex, "edge": edge, **options}
        for key, default in (("vertex", False), ("edge", False), *ir.CELL_OPTIONS):
            if key in inner.attrs and flags[key] == default:
                self.changes.add("omit_default_flag", number)

        if wrapper is not None and inner.get("value") is not None:
            self.note("warning", "user_object_overridden", "value on the inner <mxCell> replaces the user "
                      "object when the editor opens the file; its data is not kept", inner, cell_id, "value", data)
            wrapper = None
            self.changes.add("drop_overridden_user_object", number)
        if wrapper is None:
            cell.label = inner.get("value")
        else:
            cell.wrapper = wrapper
            cell.label = outer.get("label")
            cell.data = tuple(sorted((k, v) for k, v in outer.attrs.items() if k not in ("id", "label")))
            cell.wrapper_extras = tuple(
                fragment(c) if isinstance(c, Element) else escape_text(c)
                for c in outer.children if c is not inner and (isinstance(c, Element) or c.strip()))
        if cell.label == "":
            cell.label = None
            self.changes.add("omit_empty_label", number)

        style = inner.get("style")
        if style is not None:
            cell.style = syntax.parse_style(style) or None
            if cell.style is None:
                self.changes.add("omit_empty_style", number)
            for key, value in cell.style or ():
                if key in syntax.COLOR_KEYS and not syntax.valid_color(value):
                    self.note("warning", "invalid_color", f"{key}={value!r} is not a colour the editor can "
                              "paint", inner, cell_id, "style", data)
        roles = []
        if syntax.id_seeds_sketch(cell.style):
            roles.append(ir.SKETCH_SEED)
        if cell.wrapper is not None and ("placeholders", "1") in cell.data and any(
                ID_PLACEHOLDER in text for text in (cell.label or "", *(value for _, value in cell.data))):
            roles.append(ir.PLACEHOLDER)
        cell.id_roles = tuple(roles)
        if roles and cell_id is None:
            self.note("warning", "implicit_semantic_id", "the editor observes this cell's ID ("
                      + ", ".join(roles) + ") but the file leaves the ID to the editor's counter",
                      outer, None)
        cell.attrs = tuple(sorted((k, v) for k, v in inner.attrs.items() if k not in CELL_FIELDS))
        extras = []
        for child in inner.children:
            if isinstance(child, str):
                if child.strip():
                    self.note("warning", "stray_text", "text inside <mxCell> has no draw.io meaning and is "
                              "dropped", inner, cell_id)
            elif child.tag == "mxGeometry" and child.get("as") == "geometry":
                if cell.geometry is not None:
                    self.note("error", "duplicate_geometry", "cell has more than one geometry", child, cell_id)
                cell.geometry = self.geometry(child, cell_id, data, cell.kind)
            else:
                extras.append(fragment(child))
        cell.extras = tuple(extras)
        return cell, cell_id, inner

    def geometry(self, element, cell_id, data, kind):
        geometry = ir.Geometry()

        def read(node, key):
            text = node.get(key)
            if text is None:
                return Decimal(0)
            value, exact = syntax.number(text)
            if not exact:
                self.note("warning", "invalid_number", f"{key}={text!r} is not a finite number; the editor "
                          f"reads it as {syntax.format_number(value)}", node, cell_id, key, data)
            return value

        for key in ("x", "y", "width", "height"):
            setattr(geometry, key, read(element, key))
        if kind == ir.VERTEX and (geometry.width < 0 or geometry.height < 0):
            self.note("warning", "negative_size", "vertex has a negative width or height", element, cell_id)
        geometry.relative = self.read_flag(element, "relative", False, cell_id, data)
        geometry.attrs = tuple(sorted((k, v) for k, v in element.attrs.items() if k not in GEOMETRY_FIELDS))
        extras, seen = [], set()
        for child in element.elements():
            role = child.get("as")
            points = child.elements()
            plain = not points
            if role in seen:
                self.note("error", "duplicate_geometry", f"geometry has more than one {role}", child, cell_id)
            elif child.tag == "mxPoint" and role in POINT_ROLES and plain and child.attrs.keys() <= {"x", "y", "as"}:
                setattr(geometry, POINT_ROLES[role], (read(child, "x"), read(child, "y")))
            elif (child.tag == "Array" and role == "points" and child.attrs.keys() == {"as"}
                  and all(p.tag == "mxPoint" and p.attrs.keys() <= {"x", "y"} and not p.elements()
                          for p in points)):
                geometry.points = tuple((read(p, "x"), read(p, "y")) for p in points)
            elif (child.tag == "mxRectangle" and role == "alternateBounds" and plain
                  and child.attrs.keys() <= {"x", "y", "width", "height", "as"}):
                geometry.alternate_bounds = tuple(read(child, k) for k in ("x", "y", "width", "height"))
            else:
                extras.append(fragment(child))
                continue
            seen.add(role)
        geometry.extras = tuple(extras)
        return geometry


def build(source):
    """Return (document, source_map, diagnostics, representation_log)."""
    builder = Builder(source)
    document = builder.document()
    return document, builder.source_map, builder.diagnostics, list(builder.changes.entries.values())
