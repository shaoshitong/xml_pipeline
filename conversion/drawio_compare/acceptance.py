"""Controlled acceptance cases and optional five real pairs, on HKUST3."""

import argparse
from base64 import b64encode
from pathlib import Path
from time import monotonic
from urllib.parse import quote
import xml.etree.ElementTree as ET
import zlib

from cli import run, write_json
from runtime import Runtime


BOX = "rounded=0;whiteSpace=wrap;html=0;align=center;verticalAlign=middle;fillColor=#e0f0ff;"
ARROW = ("noEdgeStyle=1;rounded=0;startArrow=none;endArrow=block;"
         "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;")


def model():
    doc = ET.Element("mxGraphModel")
    root = ET.SubElement(doc, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    return doc, root


def node(root, key, value, box, parent="1", style=BOX, **extra):
    cell = ET.SubElement(root, "mxCell", id=key, value=value, style=style, parent=parent, vertex="1", **extra)
    ET.SubElement(cell, "mxGeometry", dict(zip(("x", "y", "width", "height"), map(str, box), strict=True)),
                  **{"as": "geometry"})


def edge(root, key, source=None, target=None, free=None, missing_geometry=False):
    cell = ET.SubElement(root, "mxCell", id=key, style=ARROW, edge="1", parent="1")
    if source:
        cell.set("source", source)
    if target:
        cell.set("target", target)
    if not missing_geometry:
        geometry = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        for name, (x, y) in zip(("sourcePoint", "targetPoint"), free or []):
            ET.SubElement(geometry, "mxPoint", x=str(x), y=str(y), **{"as": name})


def flow(*, flip=False, free=False, branch=True, prefix="", missing_geometry=False):
    doc, root = model()
    for key, value, bbox in (("start", "Start", (20, 20, 80, 40)),
                             ("goal", "Goal", (200, 20, 80, 40)),
                             ("review", "Review", (200, 110, 80, 40))):
        if branch or key != "review":
            node(root, prefix + key, value, bbox)
    if free:
        edge(root, prefix + "link", free=[(100, 40), (200, 40)])
    else:
        src, dst = ("goal", "start") if flip else ("start", "goal")
        edge(root, prefix + "link", prefix + src, prefix + dst, missing_geometry=missing_geometry)
    if branch:
        edge(root, prefix + "branch", prefix + "start", prefix + "review")
    return ET.tostring(doc)


def labels(split):
    doc, root = model()
    node(root, "box", "" if split else "Input", (10, 10, 100, 40))
    if split:
        node(root, "text", "Input", (10, 10, 100, 40),
             style="text;html=0;align=center;verticalAlign=middle;fillColor=none;strokeColor=none;")
    return ET.tostring(doc)


def tables(rows, cols):
    doc, root = model()
    node(root, "table", "Related Table A", (15, 15, 160, 120), style="shape=table;container=1;childLayout=tableLayout;")
    for i in range(rows):
        row = f"row{i}"
        node(root, row, "", (0, 120 / rows * i, 160, 120 / rows), parent="table",
             style="shape=tableRow;container=1;")
        for j in range(cols):
            node(root, f"cell{i}-{j}", f"{i},{j}", (160 / cols * j, 0, 160 / cols, 120 / rows),
                 parent=row, style="shape=partialRectangle;")
    return ET.tostring(doc)


def panels(x, width=240, collapsed=False):
    doc, root = model()
    node(root, "panel", "Outer panel", (x, -29, width, 110),
         style="swimlane;container=1;startSize=25;fillColor=#e0f0ff;", collapsed=str(int(collapsed)))
    node(root, "inside", "Nested", (140, 38, 80, 28), parent="panel")
    node(root, "marker", "", (-32, 114, 20, 20), style="fillColor=#ff0000;strokeColor=none;")
    return ET.tostring(doc)


def nested_edge():
    doc, root = model()
    node(root, "panel", "Panel", (-40, 20, 320, 115), style="swimlane;startSize=20;")
    node(root, "from", "Source", (20, 35, 80, 40), parent="panel")
    node(root, "to", "Destination", (180, 35, 90, 40), parent="panel")
    edge(root, "e", "from", "to")
    return ET.tostring(doc)


def wrapped(raw, compress=False, extra=False):
    root = ET.Element("mxfile", compressed=str(compress).lower())
    for number in range(1, 3 if extra else 2):
        page = ET.SubElement(root, "diagram", name=f"Page-{number}")
        if compress:
            encoder = zlib.compressobj(wbits=-15)
            data = encoder.compress(quote(raw.decode(), safe="~!*'()").encode()) + encoder.flush()
            page.text = b64encode(data).decode()
        else:
            page.append(ET.fromstring(raw))
    return ET.tostring(root)


def explicit_defaults(raw):
    doc = ET.fromstring(raw)
    for cell in doc.findall("./root/mxCell"):
        cell.set("visible", "1")
        cell.set("connectable", "1")
        cell.set("collapsed", "0")
        if cell.get("edge") is None:
            cell.set("edge", "0")
    return ET.tostring(doc)


def differences(report, kind):
    return [d for page in report["pages"] for d in page["diagnostics"] if d["kind"] == kind]


def verify(report, folder):
    assert all(p["pixel_exact"] and p["native_cell_state_exact"] and p["native_codec_exact"] and p["byte_idempotent"]
               for side in report["normalization"].values() for p in side["pages"])
    for page in report["pages"]:
        assert (folder / page["overlay"]).stat().st_size > 0
        for diagnostic in page["diagnostics"]:
            for side in (diagnostic["a"], diagnostic["b"]):
                if side and side["bbox_png_xywh"]:
                    assert (folder / diagnostic["crop"]["path"]).stat().st_size > 0


def accept(folder, fixtures):
    from PIL import Image
    import json

    folder.mkdir(parents=True, exist_ok=False)
    cases = {
        "id_only": (flow(), flow(prefix="random_")),
        "wrapping": (flow(), wrapped(flow(), compress=True)),
        "redundant_defaults": (flow(), explicit_defaults(flow())),
        "split_merge": (labels(False), labels(True)),
        "reverse": (flow(), flow(flip=True)),
        "branch_removed": (flow(), flow(branch=False)),
        "table_grid": (tables(4, 2), tables(3, 4)),
        "panel_shift": (panels(10), panels(90)),
        "free_edge": (flow(branch=False), flow(branch=False, free=True)),
        "official_repair": (flow(missing_geometry=True), panels(10, width=150)),
        "edge_parent_repair": (nested_edge(), nested_edge()),
        "multi_page_hidden": (wrapped(panels(0, collapsed=True), extra=True), panels(0, collapsed=True)),
        "fractional_scale": (panels(2310), panels(2420)),
    }
    with Runtime() as runtime:
        summary = {}
        for key, (a, b) in cases.items():
            started = monotonic()
            case = folder / key
            case.mkdir()
            aa, bb = case / "input-A.drawio", case / "input-B.drawio"
            aa.write_bytes(a)
            bb.write_bytes(b)
            report = run(aa, bb, case, "reference", repairs=key in {"official_repair", "edge_parent_repair"},
                         runtime=runtime)
            verify(report, case)
            page = report["pages"][0]
            if key in {"id_only", "wrapping", "redundant_defaults"}:
                assert page["render"]["pixel_exact"] and not page["diagnostics"], key
            if key == "wrapping":
                assert report["normalized_xml_equal"] and report["normalization"]["B"]["pages"][0]["native_compressed_decode"]
            if key == "redundant_defaults":
                assert report["normalized_xml_equal"] and report["normalization"]["B"]["simplifications"]
            if key == "split_merge":
                assert all(d["kind"] in {"label_edit_binding_changed", "visual_patch"} for d in page["diagnostics"])
                diagnostic, = differences(report, "label_edit_binding_changed")
                assert diagnostic["edit_probe"]["status"] == "different_motion_class", diagnostic
            if key == "reverse":
                assert any(d["status"] == "confirmed" for d in differences(report, "edge_direction_reversed"))
            if key == "branch_removed":
                assert differences(report, "unmatched_edge") and differences(report, "unmatched_shape")
            if key == "table_grid":
                diagnostic, = differences(report, "table_grid_changed")
                assert diagnostic["expected"]["columns_by_row"] == [2] * 4
                assert diagnostic["actual"]["columns_by_row"] == [4] * 3
            if key == "panel_shift":
                diagnostic, = differences(report, "panel_moved")
                assert diagnostic["actual"][0] - diagnostic["expected"][0] == 80
            if key == "free_edge":
                assert page["render"]["pixel_exact"], page["render"]
                diagnostics = differences(report, "edge_binding_changed")
                assert len(diagnostics) == 2, diagnostics
                assert all(d["edit_probe"]["status"] == "different_motion_class" and
                           d["edit_probe"]["a"]["status"] == "moved" and
                           d["edit_probe"]["b"]["status"] == "stationary" and
                           all(d["edit_probe"][side]["restored_exact"] for side in ("a", "b"))
                           for d in diagnostics), diagnostics
            if key == "official_repair":
                for letter, rule in (("A", "missing_edge_geometry"), ("B", "grow_container")):
                    evidence = json.loads((case / f"{letter}_official_repair.json").read_text())[0]
                    assert evidence["pixel_exact"] is False and any(c["rule"] == rule for c in evidence["changes"]), evidence
            if key == "edge_parent_repair":
                evidence = json.loads((case / "A_official_repair.json").read_text())[0]
                assert {"rule": "edge_parent", "cell_id": "e", "before": "1", "after": "panel"} in evidence["changes"]
                assert ET.parse(case / "A_hat.xml").find('.//mxCell[@id="e"]').get("parent") == "1"
            if key == "multi_page_hidden":
                assert len(report["pages"]) == 2 and differences(report, "unmatched_page")
                hidden = next(c for c in json.loads((case / "A_coordinates.json").read_text())[0]["cells"]
                              if c["id"] == "inside")
                assert not hidden["visible"] and hidden["bbox_png"] is None
            if key == "fractional_scale":
                coord = json.loads((case / "A_coordinates.json").read_text())[0]
                marker = next(c for c in coord["cells"] if c["id"] == "marker")
                x, y, w, h = marker["bbox_png"]
                assert coord["png_transform"]["scale"] < 1
                with Image.open(case / "page_001_A.png") as image:
                    assert image.getpixel((round(x + w / 2), round(y + h / 2))) == (255, 0, 0)
            summary[key] = {"pixels_exact": page["render"]["pixel_exact"], "summary": report["summary"],
                            "elapsed_seconds": round(monotonic() - started, 2)}
            print(key, "PASS", summary[key], flush=True)
        if fixtures:
            for key in ("002", "012", "013", "017", "022"):
                started = monotonic()
                a = fixtures / "outputs/random100_new540_final_seed20261103100_v1/pairs" / key / "author.drawio"
                b = fixtures / "outputs/dpsk_img2code_max_pilot_20261111" / key / "round1.drawio"
                case = folder / f"pilot_{key}"
                case.mkdir()
                report = run(a, b, case, "reference", runtime=runtime)
                verify(report, case)
                assert report["pages"][0]["diagnostics"]
                summary[f"pilot_{key}"] = {"summary": report["summary"],
                                           "pages": len(report["pages"]),
                                           "render": report["pages"][0]["render"],
                                           "elapsed_seconds": round(monotonic() - started, 2)}
                print("pilot", key, "PASS", report["summary"], summary[f"pilot_{key}"]["elapsed_seconds"], flush=True)
        write_json(folder / "acceptance.json", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path)
    args = parser.parse_args()
    accept(args.out, args.fixtures)
