"""Native acceptance: open source and compiled XML in the pinned draw.io editor
and require the same model, the same pixels and the same edit behaviour.

Runs on the lab host. The pinned runtime comes from ``drawio_compare`` in the
directory named by DRAWIO_COMPARE_SOURCE (default: next to this package).
"""

import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASELINE = Path(os.environ.get("DRAWIO_COMPARE_SOURCE", HERE.parent))
for folder in (BASELINE / "scripts", BASELINE / "drawio_compare"):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

VERIFY = (HERE / "verify.js").read_text()
TOLERANCE = 1e-6      # only used where folded frames re-associate float sums
MOVE_PROBES = 12
LABEL_PROBES = 3
FOLD_PROBES = 2
STATE_FIELDS = ("kind", "parent", "source", "target", "connectable", "visible", "collapsed", "label",
                "painted_label", "data", "style", "id_seeds_sketch", "shown", "bbox", "paint_bbox", "label_bbox",
                "points")


def open_runtime():
    from runtime import Runtime
    return Runtime()


def call(runtime, operation, xml, **options):
    page = runtime.renderer.page
    page.bring_to_front()
    return page.evaluate(VERIFY, {"operation": operation, "xml": xml, **options})


def close(a, b, tolerance):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return a == b or abs(a - b) <= tolerance
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, tolerance) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[key], b[key], tolerance) for key in a)
    return a == b


def align(original, compiled, folded):
    """Pair the editor's cells of both documents by draw-order position.

    ``folded`` holds the draw-order positions of the source cells the compiler
    folded away; both the editor and the IR walk parents first in child order.
    """
    cells = original["cells"]
    kept = [i for i in range(len(cells)) if i not in folded]
    position = {old: new for new, old in enumerate(kept)}

    def translate(ref):
        while ref in folded:
            ref = cells[ref]["parent"]
        return position.get(ref, ref)

    return kept, translate, bool(folded)


def compare_states(original, compiled, folded):
    """Differences between two editor snapshots; empty when equivalent."""
    kept, translate, has_folds = align(original, compiled, folded)
    tolerance = TOLERANCE if has_folds else 0
    differences = []
    if len(kept) != len(compiled["cells"]):
        return [{"field": "cell_count", "original": len(kept), "compiled": len(compiled["cells"])}], kept
    for new, old in enumerate(kept):
        a, b = original["cells"][old], compiled["cells"][new]
        if a["id_seeds_sketch"] and a["id"] != b["id"]:
            # The editor paints this cell from its ID; the compiled file must keep the name.
            differences.append({"field": "observed_id", "original_id": a["id"], "compiled_id": b["id"],
                                "original": a["id"], "compiled": b["id"]})
        for field in STATE_FIELDS:
            x, y = a[field], b[field]
            if field in ("parent", "source", "target"):
                x = translate(x)
            elif field == "style":
                x, y = original["styles"][x], compiled["styles"][y]
            if not close(x, y, tolerance):
                differences.append({"field": field, "original_id": a["id"], "compiled_id": b["id"],
                                    "original": x if field != "style" else style_delta(x, y)[0],
                                    "compiled": y if field != "style" else style_delta(x, y)[1]})
                if len(differences) >= 20:
                    return differences, kept
    return differences, kept


def style_delta(a, b):
    a, b = json.loads(a), json.loads(b)
    keys = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
    return {k: a.get(k) for k in keys}, {k: b.get(k) for k in keys}


def spread(items, count):
    """A deterministic, evenly spaced sample."""
    if len(items) <= count:
        return list(items)
    return [items[(i * len(items)) // count] for i in range(count)]


def plan_probes(snapshot):
    """Edit probes over the compiled page, as positions in its draw order.

    Moves cover terminals of bound edge ends, vertices lying under free edge
    ends, containers and tables with their children, and edge labels.
    """
    cells = snapshot["cells"]
    children = {}
    for i, cell in enumerate(cells):
        children.setdefault(cell["parent"], []).append(i)
    shown = lambda i: cells[i]["shown"] and cells[i]["geometry"] is not None
    bound, free, containers, labels = [], [], [], []
    vertices = [i for i, c in enumerate(cells) if c["kind"] == "vertex" and shown(i) and c["bbox"]]
    for i, cell in enumerate(cells):
        if cell["kind"] == "edge" and cell["shown"] and cell["points"]:
            for end, point in (("source", cell["points"][0]), ("target", cell["points"][-1])):
                terminal = cell[end]
                if terminal is not None and terminal >= 0 and shown(terminal):
                    bound.append({"operation": "move", "cell": terminal, "watch": [[i, end]], "class": "bound_end"})
                elif terminal is None and point and len(free) < 64:
                    under = next((v for v in reversed(vertices)
                                  if cells[v]["bbox"][0] - 1 <= point[0] <= cells[v]["bbox"][0] + cells[v]["bbox"][2] + 1
                                  and cells[v]["bbox"][1] - 1 <= point[1] <= cells[v]["bbox"][1] + cells[v]["bbox"][3] + 1),
                                 None)
                    if under is not None:
                        free.append({"operation": "move", "cell": under, "watch": [[i, end]], "class": "free_end"})
        elif cell["kind"] == "vertex" and shown(i):
            kids = [k for k in children.get(i, []) if cells[k]["shown"]]
            if cells[cell["parent"]]["kind"] == "edge" if cell["parent"] is not None else False:
                labels.append({"operation": "move", "cell": i, "watch": [[i, "bbox"]], "class": "edge_label"})
            elif kids:
                containers.append({"operation": "move", "cell": i, "class": "container",
                                   "watch": [[i, "bbox"]] + [[k, "bbox"] for k in spread(kids, 3)]})
    plain = [{"operation": "move", "cell": i, "watch": [[i, "bbox"]], "class": "vertex"} for i in vertices]
    share = MOVE_PROBES // 4
    probes = spread(bound, share) + spread(free, share) + spread(containers, share) + spread(labels, 1)
    probes += spread(plain, max(2, MOVE_PROBES - len(probes)))
    labelled = [i for i in vertices if cells[i]["label"]] or vertices
    probes += [{"operation": "relabel", "cell": i, "watch": [], "class": "relabel"}
               for i in spread(labelled, LABEL_PROBES)]
    foldable = [p["cell"] for p in containers
                if json_value(snapshot, p["cell"], "collapsible") != "0"]
    probes += [{"operation": "fold", "cell": i, "watch": [[k, "bbox"] for k in spread(children[i], 3)],
                "class": "fold"} for i in spread(foldable, FOLD_PROBES)]
    return probes


def json_value(snapshot, position, key):
    return json.loads(snapshot["styles"][snapshot["cells"][position]["style"]]).get(key)


def verify_page(runtime, source_xml, compiled_xml, number, folded, folder=None):
    from runtime import shared_frame
    original = call(runtime, "snapshot", source_xml, pageNumber=number)
    compiled = call(runtime, "snapshot", compiled_xml, pageNumber=number)
    differences, kept = compare_states(original, compiled, folded)
    result = {"page": number, "cells": len(compiled["cells"]), "model_equal": not differences,
              "model_differences": differences,
              "sketch_seeded_cells": sum(cell["id_seeds_sketch"] for cell in original["cells"])}

    frame = shared_frame(original, compiled)
    renders = [runtime.render(xml, frame, page_number=number) for xml in (source_xml, compiled_xml)]
    result.update(frame=frame, original_pixel_sha256=renders[0].pixel_sha256,
                  compiled_pixel_sha256=renders[1].pixel_sha256,
                  pixel_equal=renders[0].pixel_sha256 == renders[1].pixel_sha256,
                  unresolved_assets={"original": renders[0].unresolved, "compiled": renders[1].unresolved})
    if not result["pixel_equal"] and folder is not None:
        from PIL import ImageChops
        for name, render in zip(("original", "compiled"), renders):
            render.image.save(Path(folder) / f"page_{number:03d}_{name}.png")
        result["changed_bbox_png_xyxy"] = ImageChops.difference(renders[0].image, renders[1].image).getbbox()

    edit = {"equal": None, "probes": 0, "inert": 0, "classes": {}}
    if not differences:
        probes = plan_probes(compiled)
        back = {new: old for new, old in enumerate(kept)}
        mirrored = [{**p, "cell": back[p["cell"]], "watch": [[back[i], what] for i, what in p["watch"]]}
                    for p in probes]
        none = {"probes": [], "model_restored": True}
        after = call(runtime, "probe", compiled_xml, pageNumber=number, probes=probes) if probes else none
        before = call(runtime, "probe", source_xml, pageNumber=number, probes=mirrored) if probes else none
        mismatches = []
        if not (before["model_restored"] and after["model_restored"]):
            mismatches.append({"probe": None, "original": {"model_restored": before["model_restored"]},
                               "compiled": {"model_restored": after["model_restored"]}})
        for item, x, y in zip(probes, before["probes"], after["probes"]):
            edit["classes"][item["class"]] = edit["classes"].get(item["class"], 0) + 1
            # The editor may undo an edit itself (a table lays its rows out again);
            # such a probe is inert, and must be inert in both documents.
            edit["inert"] += not y.get("changed_model")
            sound = y.get("status") == "done" and y.get("restored")
            if not sound or not close(x, y, TOLERANCE):
                mismatches.append({"probe": item, "compiled_id": compiled["cells"][item["cell"]]["id"],
                                   "original": x, "compiled": y})
        edit.update(equal=not mismatches, probes=len(probes), mismatches=mismatches[:10])
    result["edit"] = edit
    result["equal"] = bool(result["model_equal"] and result["pixel_equal"] and edit["equal"]
                           and renders[0].unresolved == renders[1].unresolved)
    return result


def verify_documents(runtime, source_bytes, compilation, folder=None, target=None):
    """Compare the source with its compilation, or with ``target`` bytes that
    the compilation is meant to equal (the canonical base of a variant)."""
    source_xml = source_bytes.decode("utf-8-sig")
    compiled_xml = (compilation.xml if target is None else target).decode("utf-8")
    pages = []
    for page in compilation.source_map["pages"]:
        folded = {c["draw_index"] for c in page["cells"] if "folded_into" in c}
        pages.append(verify_page(runtime, source_xml, compiled_xml, page["page"], folded, folder))
    return {"schema": "drawio-semantic-native-acceptance/1", "runtime": runtime.metadata,
            "equal": all(page["equal"] for page in pages),
            "assets_resolved": not any(p["unresolved_assets"]["original"] or p["unresolved_assets"]["compiled"]
                                       for p in pages),
            "pages": pages}


def verify_files(source_bytes, compilation, folder=None):
    with open_runtime() as runtime:
        return verify_documents(runtime, source_bytes, compilation, folder)
