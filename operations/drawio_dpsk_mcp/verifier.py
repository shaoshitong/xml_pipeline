"""Compile, render and compare checkpoints on the host side of the sandbox."""

from collections import Counter
from hashlib import sha256
import json
from math import ceil, floor
import os
import re
import socketserver
import stat
from threading import Thread
from tempfile import TemporaryDirectory
from uuid import uuid4

from compare import compare_page
from compiler import compile_bytes
from patch_mse_focus_v1 import features, locate, on_white, registration, score
from runtime import Runtime, project_box, shared_frame
from source import CompileError

CHECKS = 4
MAX_BYTES = 1024 * 1024
CHECKPOINT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\.drawio")
EMBED = re.compile(r"(?:&lt;|<)(?:img|svg)\b|data\s*:\s*image/|(?:[;\"]image=)", re.I)
PRIORITY = {
    "label_changed": 0, "edge_direction_reversed": 0, "edge_terminals_changed": 0,
    "edge_arrowheads_changed": 0, "unmatched_panel": 0, "unmatched_table": 0,
    "unmatched_shape": 1, "unmatched_label": 1, "unmatched_edge": 1,
    "table_grid_changed": 1, "table_cell_text_changed": 1, "edge_binding_changed": 2,
    "appearance_style_changed": 3, "ambiguous_correspondence": 5,
}


def read_candidate(case, name):
    if not isinstance(name, str) or not CHECKPOINT.fullmatch(name):
        raise ValueError("Use a case-local .drawio filename")
    fd = os.open(case / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("Checkpoint must be a regular file")
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Checkpoint exceeds 1 MiB")
    return data


def native(runtime, compiled, target):
    xml = compiled.xml.decode()
    snapshot = runtime.call("snapshot", xml, pageNumber=1)
    rendered = runtime.render(xml, shared_frame(snapshot))
    if rendered.unresolved:
        raise ValueError("Candidate has unresolved rendering assets")
    fit = registration(target, rendered.image)
    return snapshot, rendered, fit


def aligned_snapshot(snapshot, transform, fit):
    scale = transform["scale"] * fit["scale"]
    offset = [v * fit["scale"] + fit[axis] for v, axis in zip(transform["offset"], ("dx", "dy"))]
    projection = {"scale": scale, "offset": offset}
    cells = []
    for cell in snapshot["cells"]:
        shifted = {**cell, **{key: project_box(cell.get(key), projection)
                              for key in ("bbox", "paint_bbox", "label_bbox")}}
        if cell["points"]:
            shifted["points"] = [project_box([*point, 0, 0], projection)[:2] if point else None
                                 for point in cell["points"]]
        cells.append(shifted)
    return {"cells": cells}


def target_region(obj, size):
    if obj is None or obj.extent is None:
        return None
    x, y, w, h = obj.extent
    # Return an approximate search region, never reference coordinates or geometry.
    region = [max(0, floor((x - 8) / 16) * 16), max(0, floor((y - 8) / 16) * 16),
              min(size[0], ceil((x + w + 8) / 16) * 16), min(size[1], ceil((y + h + 8) / 16) * 16)]
    return region if region[0] < region[2] and region[1] < region[3] else None


def diagnostics(differences, source_map, size):
    origins = {cell["id"]: cell for cell in source_map["pages"][0]["cells"]}
    ordered = sorted(differences, key=lambda diff: (diff["status"] in ("suspected", "unknown"),
                                                   PRIORITY.get(diff["kind"], 2)))
    issues = []
    emitted = Counter()
    for diff in ordered:
        kind = diff["kind"]
        if emitted[kind] >= 3:
            continue
        gold, candidate = diff["a_object"], diff["b_object"]
        refs = [origins[key] for key in candidate.ids if key in origins] if candidate else []
        location = target_region(gold or candidate, size)
        cells = [{"id": ref["original_id"], "line": ref["location"]["line"]} for ref in refs[:5]]
        side = "both" if gold and candidate else ("target_only" if gold else "candidate_only")
        issue = {"kind": kind, "confidence": diff["status"], "side": side,
                 "candidate_cells": cells, "target_region_xyxy": location}
        if kind == "appearance_style_changed":
            issue["style_fields"] = sorted(diff["b_value"])
        issues.append(issue)
        emitted[kind] += 1
        if len(issues) == 18:
            break
    return issues


class Verifier:
    def __init__(self, case, gold, *, reveal_structure):
        self.case = case
        self.target = on_white(case / "target.png")
        self.gold = gold
        self.gold_snapshot = None
        self.reveal_structure = reveal_structure
        self.checked = {}
        self.scores = {}
        self.calls = []

    def evaluate(self, data):
        candidate = compile_bytes(data)
        if len(candidate.document.pages) != 1:
            raise ValueError("Submit a single-page candidate for this image")
        if EMBED.search(candidate.xml.decode()):
            raise ValueError("Use editable objects and remove embedded or external images")
        with Runtime() as runtime:
            snapshot, render, fit = native(runtime, candidate, self.target)
            if self.gold_snapshot is None:
                gold, gold_render, gold_fit = native(runtime, self.gold, self.target)
                self.gold_snapshot = aligned_snapshot(gold, gold_render.transform, gold_fit)
        if not any(c["kind"] == "vertex" and c["visible"] for c in snapshot["cells"]):
            raise ValueError("Candidate has no visible editable vertices")
        aligned = aligned_snapshot(snapshot, render.transform, fit)
        matches, differences = compare_page(self.gold_snapshot, aligned, max(self.target.size))
        frame, *metrics = features(self.target, render.image, fit)
        visual = score((0, 0, *self.target.size), *metrics)
        patches = locate(*self.target.size, metrics)
        filename = f"preview-{uuid4().hex[:12]}.png"
        with (self.case / filename).open("xb") as preview:
            frame.save(preview, format="PNG")
        counts = dict(Counter(d["kind"] for d in differences))
        private = {
            "mse": visual["mse"], "foreground_iou": visual["foreground_iou"],
            "canonical_exact": candidate.xml == self.gold.xml, "issues": counts,
            "confirmed_matches": sum(status == "confirmed" for _, _, status, _ in matches),
            "target_only": sum(d["b_object"] is None for d in differences),
            "candidate_only": sum(d["a_object"] is None for d in differences),
            "structural_issues": len(differences), "render_path": filename,
            "fit": fit, "pixels_exact_after_alignment": visual["mse"] == 0,
        }
        result = {"ok": True, "candidate_png": filename, "mse": round(visual["mse"], 6),
                  "foreground_iou": round(visual["foreground_iou"], 4),
                  "image_regions_xyxy": [patch["bbox"] for patch in patches[:5]]}
        if self.reveal_structure:
            result.update(structural_counts=counts,
                          issues=diagnostics(differences, candidate.source_map, self.target.size))
        return result, private

    def check(self, request):
        if not isinstance(request, dict) or set(request) != {"candidate"}:
            return {"ok": False, "error": "Expected only a candidate filename"}
        try:
            data = read_candidate(self.case, request["candidate"])
        except OSError:
            return {"ok": False, "error": "Checkpoint could not be opened"}
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        digest = sha256(data).hexdigest()
        if digest not in self.checked:
            if len(self.checked) == CHECKS:
                return {"ok": False, "error": "Checkpoint budget exhausted", "checks_remaining": 0}
            try:
                result, self.scores[digest] = self.evaluate(data)
            except CompileError as error:
                result = {"ok": False, "compiler_errors": [d.to_json() for d in error.diagnostics[:8]]}
            except Exception as error:
                # Native backend errors may contain private document material.
                result = {"ok": False, "error": "Candidate could not be rendered or compared"}
                self.scores[digest] = {"backend_error": type(error).__name__}
            self.checked[digest] = result
        return {**self.checked[digest], "candidate": request["candidate"],
                "checks_remaining": CHECKS - len(self.checked)}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            request = json.loads(self.rfile.readline(4096))
        except ValueError:
            request = None
        verifier = self.server.verifier
        response = verifier.check(request)
        verifier.calls.append(response)
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode() + b"\n")


class Service:
    def __init__(self, verifier):
        self.verifier = verifier

    def __enter__(self):
        self.directory = TemporaryDirectory(prefix="drawio-mcp-", dir="/tmp")
        self.server = socketserver.UnixStreamServer(self.directory.name + "/check.sock", Handler)
        self.server.verifier = self.verifier
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.directory.name

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()
