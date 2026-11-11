"""Deterministic draw.io normalization, visual comparison, and evidence export."""

import argparse
from collections import Counter
from dataclasses import dataclass
from itertools import zip_longest
import json
from math import ceil, floor
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image, ImageChops, ImageDraw
from playwright.sync_api import Error as PlaywrightError

from compare import compare_page
from model import decode, load_schema, repair_changes, serialize
from patch_mse_focus_v1 import features, locate
from runtime import Runtime, digest, project_box, shared_frame


SCHEMA = Path(__file__).with_name("mxfile.xsd")
SCHEMA_SHA = "905db85d4e8ebec0e91518cdd62982e0afb3f09ebdcaf9e6b1952957a606639a"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


@dataclass
class Page:
    number: int
    name: str | None
    page_id: str | None
    xml: str
    document: str
    original: str
    compressed: bool
    snapshot: dict
    proof: dict | None = None


def load_pages(runtime, diagram):
    if decode(diagram.xml.encode()).xml != diagram.xml:
        raise ValueError("normalization is not byte-idempotent")
    pages = []
    for metadata, compressed in zip(diagram.pages, diagram.compressed_pages, strict=True):
        normalized = metadata["xml"]
        original_snapshot = runtime.call("snapshot", diagram.source_xml, pageNumber=metadata["number"])
        snapshot = runtime.call("snapshot", diagram.xml, pageNumber=metadata["number"])
        editor_xmls = [serialize(ET.fromstring(s.pop("editor_xml"))) for s in (original_snapshot, snapshot)]
        if editor_xmls[0] != editor_xmls[1]:
            raise ValueError(f"page {metadata['number']}: normalization changed the editor's serialized model")
        expected = [r["normalized_id"] for r in diagram.cell_ids if r["page"] == metadata["number"]]
        actual = [c["id"] for c in snapshot["cells"]]
        if Counter(expected) != Counter(actual):
            raise ValueError(f"page {metadata['number']}: draw.io changed or discarded cell IDs")
        # This includes sibling order, relationships, visibility, style, and
        # native absolute positions in both versions of the page.
        if original_snapshot != snapshot:
            raise ValueError(f"page {metadata['number']}: normalization changed native cell state")
        pages.append(Page(metadata["number"], metadata["name"], metadata["id"], normalized,
                          diagram.xml, diagram.source_xml, compressed, snapshot))
    return pages


def checked_render(runtime, page, frame):
    # Prove normalization independently of the other input's page extent.
    proof_frame = shared_frame(page.snapshot)
    normalized = runtime.render(page.document, proof_frame, page_number=page.number)
    original = runtime.render(page.original, proof_frame, page_number=page.number)
    if original.unresolved or normalized.unresolved:
        raise ValueError(f"page {page.number}: cannot prove render equality with unresolved assets: "
                         f"{sorted(set(original.unresolved + normalized.unresolved))}")
    if original.pixel_sha256 != normalized.pixel_sha256:
        raise ValueError(f"page {page.number}: normalization changed rendered pixels")
    page.proof = {"page": page.number, "name": page.name, "page_id": page.page_id,
                  "original_pixel_sha256": original.pixel_sha256,
                  "normalized_pixel_sha256": normalized.pixel_sha256, "pixel_exact": True,
                  "native_cell_state_exact": True, "native_compressed_decode": bool(page.compressed),
                  "native_codec_exact": True, "byte_idempotent": True, "proof_frame": proof_frame}
    if frame == proof_frame:
        return normalized
    common = runtime.render(page.document, frame, page_number=page.number)
    if common.unresolved:
        raise ValueError(f"page {page.number}: unresolved assets in shared render: {common.unresolved}")
    return common


def coordinates(page, transform):
    cells = []
    for cell in page.snapshot["cells"]:
        record = {**cell, "original_id": cell["id"]}
        for key in ("bbox", "paint_bbox", "label_bbox"):
            record[key + "_png"] = project_box(cell.get(key), transform)
        if cell["points"]:
            record["points_png"] = [project_box([*p, 0, 0], transform)[:2] if p else None
                                    for p in cell["points"]]
        cells.append(record)
    return {"page": page.number, "page_id": page.page_id, "name": page.name,
            "native_graph_bounds_xywh": page.snapshot["bounds"],
            "png_transform": transform, "cells": cells}


def object_ref(obj, transform):
    if obj is None:
        return None
    return {"kind": obj.kind, "label": obj.label, "cell_ids": obj.ids,
            "bbox_page_xywh": obj.extent, "bbox_png_xywh": project_box(obj.extent, transform),
            "table": obj.table, "panel_cell_id": obj.panel}


def clip_box(box, size, padding=12):
    if box is None:
        return None
    x, y, w, h = box
    rect = (max(0, floor(x) - padding), max(0, floor(y) - padding),
            min(size[0], ceil(x + w) + padding), min(size[1], ceil(y + h) + padding))
    return rect if rect[0] < rect[2] and rect[1] < rect[3] else None


def two_up(a, b, headings):
    w, h = a.size
    image = Image.new("RGB", (w * 2 + 8, h + 20), "white")
    image.paste(a, (0, 20))
    image.paste(b, (w + 8, 20))
    draw = ImageDraw.Draw(image)
    for x, label in zip((3, w + 11), headings, strict=True):
        draw.text((x, 3), label, fill="black")
    return image


def write_images(folder, prefix, a, b, diagnostics, mode):
    headings = ("A  Reference", "B  Candidate") if mode == "reference" else ("A  Before", "B  After")
    overview = two_up(a, b, headings)
    draw = ImageDraw.Draw(overview)
    crops = folder / "crops"
    saved = {}
    for item in diagnostics:
        sides = [item[key].get("bbox_png_xywh") if item[key] else None for key in ("a", "b")]
        for offset, box in zip((0, a.width + 8), sides, strict=True):
            rect = clip_box(box, a.size, padding=2)
            if rect is not None:
                x0, y0, x1, y1 = rect
                color = {"confirmed": "#cc3327", "suspected": "#a86c00",
                         "unmatched": "#4e43ab", "unknown": "#52595e"}[item["status"]]
                draw.rectangle((x0 + offset, y0 + 20, x1 + offset, y1 + 20), outline=color, width=2)
                draw.text((x0 + offset + 2, y0 + 21), item["id"].rsplit("-", 1)[-1],
                          fill=color, stroke_fill="white", stroke_width=1)
        regions = tuple(clip_box(box, a.size) for box in sides)
        if not any(regions):
            continue
        if regions not in saved:
            crops.mkdir(exist_ok=True)
            name = f"crops/{item['id']}.png"
            pieces = [image.crop(region or other) for image, region, other in
                      zip((a, b), regions, reversed(regions), strict=True)]
            crop_scale = min(1, 800 / max(max(p.size) for p in pieces))
            scaled = [p.resize(tuple(max(1, round(s * crop_scale)) for s in p.size),
                               Image.Resampling.LANCZOS) if crop_scale < 1 else p for p in pieces]
            tile_size = tuple(max(lengths) for lengths in zip(*(p.size for p in scaled), strict=True))
            tiles = [Image.new("RGB", tile_size, "white") for _ in scaled]
            for tile, piece in zip(tiles, scaled, strict=True):
                tile.paste(piece, (0, 0))
            labels = [heading if region else heading + " (same viewport)"
                      for heading, region in zip(headings, regions, strict=True)]
            two_up(*tiles, labels).save(folder / name)
            saved[regions] = name
        item["crop"] = {"path": saved[regions], "a_bbox_png_xyxy": regions[0], "b_bbox_png_xyxy": regions[1]}
    path = f"{prefix}_overlay.png"
    overview.save(folder / path)
    return path


def render_diff(runtime, folder, left, right, number, mode):
    frame = shared_frame(*(p.snapshot for p in (left, right) if p is not None))
    renders = [checked_render(runtime, p, frame) if p is not None else None for p in (left, right)]
    transform = next(render.transform for render in renders if render is not None)
    images = [r.image if r else Image.new("RGB", frame["dimensions"], "white") for r in renders]
    a, b = images
    prefix = f"page_{number:03d}"
    paths = []
    coords = []
    for letter, page, render in zip(("A", "B"), (left, right), renders, strict=True):
        paths.append(f"{prefix}_{letter}.png" if render else None)
        coords.append(coordinates(page, transform) if page else None)
        if render:
            render.image.save(folder / paths[-1])
    span = max(frame["bounds"][2:])
    empty = {"cells": []}
    matches, differences = compare_page(left.snapshot if left else empty, right.snapshot if right else empty, span)
    diagnostics = []

    def add(kind, status, a_ref, b_ref, a_value, b_value, **extra):
        diagnostic = {"id": f"P{number:03d}-{len(diagnostics) + 1:03d}", "kind": kind,
                      "status": status, "a": a_ref, "b": b_ref, **extra}
        if mode == "reference":
            diagnostic.update(expected=a_value, actual=b_value)
        else:
            diagnostic.update(before=a_value, after=b_value)
        diagnostics.append(diagnostic)
        return diagnostic

    if left is None or right is None:
        page_ref = {"kind": "page", "label": (left or right).name, "cell_ids": [],
                    "bbox_png_xywh": [0, 0, *frame["dimensions"]]}
        add("unmatched_page", "unmatched", page_ref if left else None, page_ref if right else None,
            left.name if left else None, right.name if right else None)
    pending_probes = []
    for diff in differences:
        a_ref = object_ref(diff["a_object"], transform)
        b_ref = object_ref(diff["b_object"], transform)
        diagnostic = add(diff["kind"], diff["status"], a_ref, b_ref, diff["a_value"], diff["b_value"])
        if diff["probes"]:
            pending_probes.append((diagnostic, diff["probes"]))
        elif diff["kind"] == "edge_binding_changed":
            diagnostic["edit_probe"] = {"status": "unknown", "reason": "no unique corresponding visible terminal"}
    if pending_probes:
        result_a, result_b = [
            runtime.call("probe", page.xml, probes=[pair[index] for _, pair in pending_probes])
            for index, page in enumerate((left, right))
        ]
        for (item, pair), result_x, result_y in zip(pending_probes, result_a, result_b, strict=True):
            status_a, status_b = result_x["status"], result_y["status"]
            outcome = "unknown" if "unknown" in (status_a, status_b) else (
                "same_motion_class" if status_a == status_b else "different_motion_class")
            item["edit_probe"] = {"status": outcome, "a": {**pair[0], **result_x}, "b": {**pair[1], **result_y}}
    changed_box = ImageChops.difference(a, b).getbbox()
    visual = {"pixel_exact": changed_box is None, "changed_bbox_png_xyxy": changed_box, "patch_mse": []}
    if changed_box is not None:
        _, error, smooth, fa, fb = features(a, b, {"scale": 1, "dx": 0, "dy": 0})
        visual.update(mean_rgb_mse=float(error.mean()), changed_pixels=int(np.count_nonzero(error)))
        visual["patch_mse"] = locate(*a.size, (error, smooth, fa, fb))
        for patch in visual["patch_mse"]:
            x0, y0, x1, y1 = patch["bbox"]
            patch_ref = {"kind": "image_patch", "cell_ids": [],
                         "bbox_png_xywh": [x0, y0, x1 - x0, y1 - y0]}
            add("visual_patch", "suspected", patch_ref, patch_ref, None, None, patch=patch)
        if not visual["patch_mse"]:
            x0, y0, x1, y1 = changed_box
            patch_ref = {"kind": "image_patch", "cell_ids": [],
                         "bbox_png_xywh": [x0, y0, x1 - x0, y1 - y0]}
            add("visual_difference", "suspected", patch_ref, patch_ref, None, None)
    overlay = write_images(folder, prefix, a, b, diagnostics, mode)
    return {"page": number, "a_page": left.name if left else None, "b_page": right.name if right else None,
            "frame": frame, "a_png": paths[0], "b_png": paths[1], "overlay": overlay,
            "render": visual, "diagnostics": diagnostics,
            "matches": [{"status": status, "score": score, "a": object_ref(x, transform),
                         "b": object_ref(y, transform)} for x, y, status, score in matches]}, coords


def repair_document(runtime, folder, side, diagram, pages):
    output = ET.fromstring(diagram.xml)
    report = []
    for page, element in zip(pages, output.findall("diagram"), strict=True):
        candidate = runtime.call("repair", page.xml)
        changes = repair_changes(candidate["before"], candidate["after"])
        check = {"page": page.number, "native_rule_counts": candidate["rules"], "changes": changes}
        report.append(check)
        if not any(candidate["rules"].values()):
            continue
        snapshot = runtime.call("snapshot", candidate["after"])
        frame = shared_frame(page.snapshot, snapshot)
        before = runtime.render(page.xml, frame)
        after = runtime.render(candidate["after"], frame)
        check["pixel_exact"] = (None if before.unresolved or after.unresolved else
                                before.pixel_sha256 == after.pixel_sha256)
        check["before_pixel_sha256"] = before.pixel_sha256
        check["after_pixel_sha256"] = after.pixel_sha256
        if check["pixel_exact"] is False:
            before.image.save(folder / f"{side}_repair_page_{page.number:03d}_before.png")
            after.image.save(folder / f"{side}_repair_page_{page.number:03d}_after.png")
        element.remove(element.find("mxGraphModel"))
        element.insert(0, ET.fromstring(candidate["after"]))
    if any(any(entry["native_rule_counts"].values()) for entry in report):
        (folder / f"{side}_official_repair.xml").write_text(serialize(output) + "\n", encoding="utf-8")
    write_json(folder / f"{side}_official_repair.json", report)


def write_text_report(path, report):
    lines = [f"drawio-compare | {report['mode']} | {report['summary']}"]
    keys = ("expected", "actual") if report["mode"] == "reference" else ("before", "after")
    for page in report["pages"]:
        state = "pixel exact" if page["render"]["pixel_exact"] else "pixels differ"
        lines.append(f"\nPage {page['page']} | {state} | {page['overlay']}")
        for d in page["diagnostics"]:
            sides = " / ".join(
                f"{key.upper()} {ref.get('label') or ''} {ref['cell_ids']} {ref['bbox_png_xywh']}"
                for key in ("a", "b") if (ref := d[key]) is not None)
            values = " → ".join(str(d[key]) for key in keys) if any(d[key] is not None for key in keys) else ""
            crop = d.get("crop", {}).get("path", "")
            lines.append(f"  {d['id']} [{d['status']}] {d['kind']} {sides} {values} {crop}".rstrip())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(a_path, b_path, folder, mode, repairs=False, runtime=None):
    if runtime is None:
        with Runtime() as shared_runtime:
            return run(a_path, b_path, folder, mode, repairs, shared_runtime)
    if digest(SCHEMA.read_bytes()) != SCHEMA_SHA:
        raise ValueError("official draw.io XSD checksum differs from the pinned schema")
    schema = load_schema(SCHEMA)
    diagrams = [decode(path.read_bytes(), schema) for path in (a_path, b_path)]
    pages_a, pages_b = [load_pages(runtime, diagram) for diagram in diagrams]
    report = {"schema_version": 1, "mode": mode, "runtime": runtime.metadata,
              "page_pairing": "document_order", "normalization": {}, "pages": [],
              "normalized_xml_equal": diagrams[0].xml == diagrams[1].xml}
    coords_a, coords_b = [], []
    for number, (left, right) in enumerate(zip_longest(pages_a, pages_b), 1):
        page, (coord_a, coord_b) = render_diff(runtime, folder, left, right, number, mode)
        report["pages"].append(page)
        if coord_a:
            coords_a.append(coord_a)
        if coord_b:
            coords_b.append(coord_b)
    for letter, path, diagram, pages, coords in zip(
            ("A", "B"), (a_path, b_path), diagrams, (pages_a, pages_b), (coords_a, coords_b), strict=True):
        report["normalization"][letter] = {"input": path.name, "sha256": digest(diagram.xml.encode()),
                                           "pages": [p.proof for p in pages],
                                           "validation": diagram.diagnostics,
                                           "simplifications": diagram.simplifications}
        (folder / f"{letter}_hat.xml").write_text(diagram.xml, encoding="utf-8")
        write_json(folder / f"{letter}_cell_ids.json", diagram.cell_ids)
        write_json(folder / f"{letter}_coordinates.json", coords)
        if repairs:
            repair_document(runtime, folder, letter, diagram, pages)
    report["summary"] = dict(Counter(d["status"] for p in report["pages"] for d in p["diagnostics"]))
    write_json(folder / "diff.json", report)
    write_text_report(folder / "diff.txt", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="new directory for verified outputs")
    parser.add_argument("--mode", choices=("revision", "reference"), default="revision")
    parser.add_argument("--official-repairs", action="store_true", help="export separate official repair proposals")
    args = parser.parse_args(argv)
    try:
        if args.out.exists():
            raise ValueError(f"output directory already exists: {args.out}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".drawio-compare-", dir=args.out.parent) as staging:
            folder = Path(staging) / "result"
            folder.mkdir()
            report = run(args.a, args.b, folder, args.mode, args.official_repairs)
            if args.out.exists():
                raise ValueError(f"output directory already exists: {args.out}")
            folder.rename(args.out)
    except (OSError, ValueError, ET.ParseError, PlaywrightError) as error:
        parser.exit(2, f"drawio-compare: {error}\n")
    print(json.dumps({"report": str(args.out / "diff.json"), "pages": len(report["pages"]),
                      "summary": report["summary"]}, ensure_ascii=False))
    return 0
