"""Decode and write uncompressed draw.io files without reordering graph cells."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

from lxml import etree

from arxiv_author_native_assets_v1 import models


# mxCell defaults in the pinned draw.io editor. Only native mxCell fields
# participate; user objects can define identically named custom attributes.
CELL_DEFAULTS = {"vertex": "0", "edge": "0", "connectable": "1", "visible": "1", "collapsed": "0"}


def serialize(element):
    # Attribute order has no XML semantics. Child order has draw.io semantics.
    for node in element.iter():
        if len(node.attrib) > 1:
            attributes = sorted(node.attrib.items())
            node.attrib.clear()
            node.attrib.update(attributes)
        if node.tag in {"mxfile", "diagram", "mxGraphModel", "root"}:
            if node.text is not None and not node.text.strip():
                node.text = None
            for child in node:
                if child.tail is not None and not child.tail.strip():
                    child.tail = None
    return ET.tostring(element, encoding="unicode")


def cell_index(model):
    root = model.find("root")
    if root is None or len(model.findall("root")) != 1:
        raise ValueError("expected one draw.io model root")
    cells = {}
    for index, outer in enumerate(root):
        cell = outer if outer.tag == "mxCell" else outer.find("mxCell")
        if cell is None:
            continue
        cell_id = outer.get("id") or cell.get("id")
        if cell_id is None or cell_id in cells:
            raise ValueError(f"missing or duplicate cell ID at root child {index + 1}")
        cells[cell_id] = (outer, cell, index + 1)
    parents = {key: cell.get("parent") for key, (_, cell, _) in cells.items()}
    for cell_id in parents:
        path = set()
        ancestor = cell_id
        while ancestor is not None:
            if ancestor in path or ancestor not in parents:
                raise ValueError(f"cyclic or unresolved parent of cell {cell_id}")
            path.add(ancestor)
            ancestor = parents[ancestor]
    return cells


@dataclass
class Diagram:
    xml: str
    source_xml: str
    compressed_pages: list
    pages: list
    cell_ids: list
    diagnostics: list
    simplifications: list


def decode(blob, schema=None):
    # Reuse the pipeline's bounded deflate/URI decoder. Decode UTF-8 first so
    # alternate encodings cannot bypass its DTD guard.
    source = blob.decode("utf-8-sig")
    source_root, input_models = models(source)
    compressed_pages = [False] * len(input_models)
    for index, page in enumerate(source_root.findall("diagram")):
        body = (page.text or "").strip()
        if page.find("mxGraphModel") is None and body and not body.startswith("<"):
            compressed_pages[index] = True
    if source_root.tag == "mxfile":
        output = deepcopy(source_root)
    else:
        output = ET.Element("mxfile")
        ET.SubElement(output, "diagram", {"name": "Page-1"})
    output.set("compressed", "false")
    simplifications = []
    for number, (page, model) in enumerate(zip(output.findall("diagram"), input_models, strict=True), 1):
        page.text = None
        embedded = page.find("mxGraphModel")
        index = list(page).index(embedded) if embedded is not None else 0
        if embedded is not None:
            page.remove(embedded)
        model = deepcopy(model)
        page.insert(index, model)
        for cell_id, (_, cell, _) in cell_index(model).items():
            dropped = [key for key, value in CELL_DEFAULTS.items() if cell.get(key) == value]
            if dropped:
                for key in dropped:
                    del cell.attrib[key]
                simplifications.append({"page": number, "cell_id": cell_id,
                                        "rule": "omit_native_defaults", "attributes": dropped})
    xml = serialize(output) + "\n"
    pages, ids, diagnostics = [], [], []
    for number, page in enumerate(output.findall("diagram"), 1):
        model = page.find("mxGraphModel")
        cells = cell_index(model)
        pages.append({"number": number, "id": page.get("id"), "name": page.get("name"),
                      "xml": ET.tostring(model, encoding="unicode")})
        for cell_id, (outer, cell, index) in cells.items():
            ids.append({"page": number, "page_id": page.get("id"),
                        "original_id": cell_id, "normalized_id": cell_id,
                        "root_child_index": index, "element": outer.tag})
            for endpoint in ("source", "target"):
                ref = cell.get(endpoint)
                if ref is not None and ref not in cells:
                    diagnostics.append({"page": number, "cell_id": cell_id,
                                        "kind": "dangling_terminal", "end": endpoint,
                                        "terminal_id": ref})
    if schema is not None:
        root = etree.fromstring(xml.encode(), parser=etree.XMLParser(resolve_entities=False, no_network=True))
        if not schema.validate(root):
            diagnostics.extend({"kind": "xsd_advisory", "path": error.path, "message": error.message}
                               for error in schema.error_log)
    return Diagram(xml, source, compressed_pages, pages, ids, diagnostics, simplifications)


def repair_changes(before, after):
    old = cell_index(ET.fromstring(before))
    new = cell_index(ET.fromstring(after))
    changes = []
    for key in old.keys() & new.keys():
        a, b = old[key][1], new[key][1]
        a_geo, b_geo = a.find("mxGeometry"), b.find("mxGeometry")
        if a.get("parent") != b.get("parent"):
            changes.append({"rule": "edge_parent", "cell_id": key,
                            "before": a.get("parent"), "after": b.get("parent")})
        if a_geo is None and b_geo is not None and b.get("edge") == "1":
            changes.append({"rule": "missing_edge_geometry", "cell_id": key})
        if a_geo is not None and b_geo is not None and b.get("vertex") == "1":
            previous = [a_geo.get(k, "0") for k in ("width", "height")]
            current = [b_geo.get(k, "0") for k in ("width", "height")]
            if [float(v) for v in previous] != [float(v) for v in current]:
                changes.append({"rule": "grow_container", "cell_id": key,
                                "before": previous, "after": current})
    return sorted(changes, key=lambda item: (item["cell_id"], item["rule"]))


def load_schema(path):
    if path is None:
        return None
    return etree.XMLSchema(etree.parse(str(Path(path)), parser=etree.XMLParser(no_network=True)))
