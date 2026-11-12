"""Structural census of the frozen corpus. Read-only; informs compiler rules."""

import argparse
import base64
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?\Z")
CELL_ATTRS = {"id", "value", "style", "parent", "source", "target", "vertex", "edge",
              "connectable", "visible", "collapsed"}


def page_models(blob, facts):
    root = ET.fromstring(blob)
    facts["root_tag:" + root.tag] += 1
    if root.tag == "mxGraphModel":
        return root, [(None, root)]
    result = []
    for key in root.attrib:
        facts["mxfile_attr:" + key] += 1
    for child in root:
        facts["mxfile_child:" + str(child.tag)] += 1
    for page in root.findall("diagram"):
        for key in page.attrib:
            facts["diagram_attr:" + key] += 1
        model = page.find("mxGraphModel")
        if model is None:
            text = (page.text or "").strip()
            if text.startswith("<"):
                facts["page:escaped_xml"] += 1
                model = ET.fromstring(text)
            else:
                facts["page:compressed"] += 1
                raw = zlib.decompress(base64.b64decode("".join(text.split())), -15)
                model = ET.fromstring(urllib.parse.unquote(raw.decode()))
        else:
            facts["page:plain"] += 1
            if len(page) != 1 or (page.text or "").strip():
                facts["page:extra_content"] += 1
        result.append((page, model))
    return root, result


def census(args):
    root_dir, row = args
    facts = Counter()
    try:
        blob = (Path(root_dir) / row["code_file"]).read_bytes()
        if blob.startswith(b"\xef\xbb\xbf"):
            facts["file:bom"] += 1
        if blob.lstrip().startswith(b"<?xml"):
            facts["file:xml_declaration"] += 1
        if b"<!--" in blob:
            facts["file:comment"] += 1
        _, pages = page_models(blob, facts)
        facts["pages:%s" % min(len(pages), 5)] += 1
        for _, model in pages:
            for key in model.attrib:
                facts["model_attr:" + key] += 1
            for child in model:
                facts["model_child:" + child.tag] += 1
            root = model.find("root")
            if root is None:
                facts["model:no_root"] += 1
                continue
            cells = {}
            order = []
            for outer in root:
                cell = outer if outer.tag == "mxCell" else outer.find("mxCell")
                facts["root_child:" + outer.tag] += 1
                if cell is None:
                    facts["wrapper:no_cell"] += 1
                    continue
                if outer is not cell:
                    if len(outer) != 1:
                        facts["wrapper:extra_children"] += 1
                    if cell.get("id") is not None:
                        facts["wrapper:inner_id"] += 1
                    keys = set(outer.attrib) - {"id", "label"}
                    facts["wrapper:trivial" if not keys else "wrapper:data"] += 1
                    for key in keys:
                        facts["wrapper_attr:" + key] += 1
                    if "placeholders" in outer.attrib:
                        facts["wrapper:placeholders"] += 1
                    link = outer.get("link") or ""
                    facts["link:" + link.split(",")[0][:24].split("://")[0]] += 1 if link else 0
                    if (outer.text or "").strip() or (cell.tail or "").strip():
                        facts["wrapper:text"] += 1
                for key in cell.attrib:
                    if key not in CELL_ATTRS:
                        facts["cell_extra_attr:" + key] += 1
                if (cell.text or "").strip():
                    facts["cell:text"] += 1
                cid = outer.get("id") if outer is not cell else cell.get("id")
                if cid is None:
                    facts["cell:no_id"] += 1
                    continue
                if cid in cells:
                    facts["cell:duplicate_id"] += 1
                cells[cid] = cell
                order.append(cid)
                for child in cell:
                    facts["cell_child:%s/%s" % (child.tag, child.get("as"))] += 1
                    if child.tag == "mxGeometry":
                        for key, value in child.attrib.items():
                            if key not in {"x", "y", "width", "height", "relative", "as"}:
                                facts["geometry_attr:" + key] += 1
                            elif key in {"x", "y", "width", "height"} and not NUMBER.match(value):
                                facts["geometry:noncanonical_number"] += 1
                                facts["number_sample:" + value[:24]] += 1
                        for sub in child:
                            facts["geometry_child:%s/%s" % (sub.tag, sub.get("as"))] += 1
                            for key in sub.attrib:
                                if key not in {"x", "y", "as", "width", "height"}:
                                    facts["geometry_child_attr:%s/%s" % (sub.tag, key)] += 1
                            for point in sub:
                                facts["array_child:" + point.tag] += 1
                                for key in point.attrib:
                                    if key not in {"x", "y"}:
                                        facts["array_point_attr:" + key] += 1
                if len(cell.findall("mxGeometry")) > 1:
                    facts["cell:multiple_geometry"] += 1
            facts["cells"] += len(order)
            roots = [cid for cid in order if cells[cid].get("parent") is None]
            if len(roots) != 1:
                facts["model:roots_%d" % len(roots)] += 1
            elif roots[0] != order[0]:
                facts["model:root_not_first"] += 1
            position = {cid: index for index, cid in enumerate(order)}
            for cid in order:
                cell = cells[cid]
                parent = cell.get("parent")
                vertex, edge = cell.get("vertex") == "1", cell.get("edge") == "1"
                if vertex and edge:
                    facts["cell:vertex_and_edge"] += 1
                for key in ("vertex", "edge", "connectable", "visible", "collapsed"):
                    value = cell.get(key)
                    if value is not None and value not in ("0", "1"):
                        facts["cell:flag_value:%s=%s" % (key, value[:12])] += 1
                if parent is not None:
                    if parent not in cells:
                        facts["cell:unresolved_parent"] += 1
                        continue
                    if position[parent] > position[cid]:
                        facts["cell:parent_after_child"] += 1
                    seen, node = set(), cid
                    while node is not None and node in cells and node not in seen:
                        seen.add(node)
                        node = cells[node].get("parent")
                    if node is not None:
                        facts["cell:parent_cycle_or_orphan"] += 1
                    grand = cells[parent].get("parent")
                    pcell = cells[parent]
                    if grand is None:
                        facts["layer" if not (vertex or edge) else "cell:vertex_or_edge_layer"] += 1
                        if cell.get("value") or cell.get("style"):
                            facts["layer:named_or_styled"] += 1
                        if cell.find("mxGeometry") is not None:
                            facts["layer:geometry"] += 1
                    elif not (vertex or edge):
                        facts["frame:nested_plain_cell"] += 1
                        if cell.find("mxGeometry") is not None:
                            facts["frame:with_geometry"] += 1
                    if pcell.get("edge") == "1":
                        facts["child_of_edge:" + ("vertex" if vertex else "edge" if edge else "plain")] += 1
                    elif pcell.get("vertex") == "1" and grand is not None:
                        facts["child_of_vertex"] += 1
                for end in ("source", "target"):
                    ref = cell.get(end)
                    if ref is not None:
                        if ref not in cells:
                            facts["edge:dangling_" + end] += 1
                        elif cells[ref].get("edge") == "1":
                            facts["edge:terminal_is_edge"] += 1
                        if not edge:
                            facts["cell:terminal_on_non_edge"] += 1
                style = cell.get("style") or ""
                if style:
                    tokens = style.split(";")
                    keys = [t.split("=", 1)[0] for t in tokens if "=" in t]
                    if len(keys) != len(set(keys)):
                        facts["style:duplicate_key"] += 1
                    for index, token in enumerate(tokens):
                        if token and "=" not in token:
                            facts["style_bare:" + token[:30]] += 1
                            if index:
                                facts["style:bare_not_first"] += 1
                        elif token.startswith("="):
                            facts["style:empty_key"] += 1
                    if not style.endswith(";"):
                        facts["style:no_trailing_semicolon"] += 1
                    if ";;" in style:
                        facts["style:empty_token"] += 1
                    if style != style.strip() or re.search(r";\s|\s;|\s=|=\s", style):
                        facts["style:whitespace"] += 1
                value = cell.get("value") or ""
                if "data:action/json" in value or "data:page/id" in value:
                    facts["value:internal_link"] += 1
    except Exception as error:  # the census reports rather than judges
        facts["error:%s:%s" % (type(error).__name__, str(error)[:60])] += 1
    return row["id"], dict(facts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.manifest.read_text().splitlines() if line.strip()]
    occurrences, files, examples = Counter(), Counter(), {}
    with ProcessPoolExecutor(args.workers) as pool:
        for case_id, facts in pool.map(census, [(str(args.root), row) for row in rows], chunksize=8):
            for key, count in facts.items():
                occurrences[key] += count
                files[key] += 1
                examples.setdefault(key, []).append(case_id) if len(examples.get(key, [])) < 3 else None
    report = {key: {"occurrences": occurrences[key], "files": files[key], "examples": examples[key]}
              for key in sorted(occurrences)}
    args.output.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"rows": len(rows), "facts": len(report)}))


if __name__ == "__main__":
    main()
