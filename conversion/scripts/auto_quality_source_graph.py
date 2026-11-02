"""Revision-bound automatic source graph checks; no pixel score or visual-review gate.

``check_graph_profile(record, xml)`` checks semantics only.  Its ``ok`` must be
combined with independent resource/font/native-render/movement/fidelity checks.
The function reads original source payloads and never writes data or job state.
Unsupported source grammars fail closed with ``supported=False``.  Browser state
is reused per calling thread for batch use; call ``close_worker_runtime()`` in a
worker's finally block.  Set IMG2CODE_ROOT before importing for another root.
"""
from __future__ import annotations

import collections
import hashlib
import html
import json
import os
import re
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(os.environ.get("IMG2CODE_ROOT", "/backup/shaoshitong/img2code_20261029")).resolve()
CHROMIUM = os.environ.get("IMG2CODE_CHROMIUM", "/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome")
_runtime = threading.local()
_PARSE = """async code=>{const d=await mermaid.mermaidAPI.getDiagramFromText(code);const v=d.db.getVertices?.();return {type:d.type,vertices:v instanceof Map?[...v.entries()]:v,edges:d.db.getEdges?.(),groups:d.db.getSubGraphs?.()};}"""


class UnsupportedProfile(ValueError):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _payload(relative, digest, area="clean"):
    if not isinstance(relative, str) or not relative:
        raise ValueError("Missing source payload path")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT / area):
        raise ValueError("Payload path escapes " + area)
    data = path.read_bytes()
    if not isinstance(digest, str) or _sha(data) != digest:
        raise ValueError("Payload hash mismatch: " + relative)
    return data


def _browser():
    if not hasattr(_runtime, "browser"):
        from playwright.sync_api import sync_playwright
        _runtime.playwright = sync_playwright().start()
        _runtime.browser = _runtime.playwright.chromium.launch(
            executable_path=CHROMIUM, args=["--disable-dev-shm-usage"])
    return _runtime.browser


def close_worker_runtime():
    """Release this thread's reusable browser and Playwright driver."""
    if hasattr(_runtime, "browser"):
        _runtime.browser.close()
        _runtime.playwright.stop()
        _runtime.__dict__.clear()


def _mermaid_source_ast(code):
    if not hasattr(_runtime, "mermaid_page"):
        folder = ROOT / "conversion/runtime/mermaid/node_modules/mermaid"
        bundle = (folder / "dist/mermaid.min.js").read_bytes()
        context = _browser().new_context(service_workers="block")
        context.route("**/*", lambda route: route.abort())
        page = context.new_page()
        page.set_content("<html></html>")
        # Load exactly the bytes whose hash is recorded, rather than re-reading
        # a path after the hash check.
        page.add_script_tag(content=bundle.decode())
        page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:false}})")
        _runtime.mermaid_page = page
        _runtime.mermaid_runtime = {
            "bundle_sha256": _sha(bundle),
            "version": json.loads((folder / "package.json").read_text())["version"],
        }
    return _runtime.mermaid_page.evaluate(_PARSE, code), dict(_runtime.mermaid_runtime)


def _source_dom(svg, width, height):
    if not hasattr(_runtime, "source_page"):
        context = _browser().new_context(java_script_enabled=False, service_workers="block")
        _runtime.source_requests = []
        def reject(route):
            _runtime.source_requests.append(route.request.url)
            route.abort()
        context.route("**/*", reject)
        _runtime.source_page = context.new_page()
    page = _runtime.source_page
    page.set_viewport_size({"width": width, "height": height})
    _runtime.source_requests.clear()
    page.set_content("<style>html,body{margin:0;padding:0;background:white}</style>" + svg)
    page.evaluate("([w,h])=>{const s=document.querySelector('svg');if(!s)throw Error('No source SVG');s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}", [width, height])
    page.evaluate("document.fonts.ready")
    script = (ROOT / "conversion/scripts/svg_dom_pdf.js").read_bytes()
    result = page.evaluate(script.decode())
    if _runtime.source_requests:
        raise ValueError("Source SVG attempted external resource requests")
    return result, {"dom_extractor_sha256": _sha(script)}


def _xml_cells(xml):
    root = ET.fromstring(xml)
    if root.tag == "mxfile" and len(root.findall("diagram")) != 1:
        raise ValueError("Exactly one source graph page is required")
    models = [root] if root.tag == "mxGraphModel" else list(root.iter("mxGraphModel"))
    if len(models) != 1:
        raise ValueError("Exactly one uncompressed mxGraphModel is required")
    parents = {child: parent for parent in root.iter() for child in parent}
    cells, labels, tags = {}, {}, {}
    for cell in models[0].iter("mxCell"):
        wrapper = parents.get(cell)
        cid = cell.get("id") or (wrapper.get("id") if wrapper is not None else None)
        if not cid or cid in cells:
            raise ValueError("Missing or duplicate native cell id")
        cells[cid] = cell
        labels[cid] = _text(cell.get("value") if cell.get("value") is not None else wrapper.get("label", "") if wrapper is not None else "")
        tags[cid] = cell.get("mermaidId") or (wrapper.get("mermaidId") if wrapper is not None else None)
    return cells, labels, tags


def _text(value):
    # Same content normalization as the existing Mermaid semantic checker.
    from html.parser import HTMLParser
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, value):
            self.parts.append(value)
        def handle_starttag(self, tag, attrs):
            if tag == "br":
                self.parts.append(" ")
    parser = Text()
    parser.feed(html.unescape(value or ""))
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def _compact(value):
    return re.sub(r"\s+", "", _text(value))


def _style(cell):
    return dict(token.split("=", 1) for token in cell.get("style", "").split(";") if "=" in token)


def _hidden_semantic_cells(cells, required):
    failures = []
    for cid in required:
        parent = cid
        visited = set()
        while parent in cells:
            if parent in visited:
                raise ValueError("Cyclic native parent chain")
            visited.add(parent)
            cell = cells[parent]
            style = _style(cell)
            hidden = cell.get("visible") == "0" or any(
                float(style.get(key, "100")) <= 0 for key in ("opacity", "textOpacity", "fontOpacity"))
            if hidden:
                failures.append({"reason": "source_semantic_object_explicitly_hidden", "cell": cid, "hidden_by": parent})
                break
            parent = cell.get("parent")
    return failures


def _mermaid_extra_checks(ast, xml):
    """Check arrow sides/types per edge, plus otherwise-unconsumed visible text."""
    cells, labels, tags = _xml_cells(xml)
    vertices = {cid: c for cid, c in cells.items() if c.get("vertex") == "1"}
    edges = {cid: c for cid, c in cells.items() if c.get("edge") == "1"}
    groups = {g["id"]: g for g in ast.get("groups") or []}
    source_vertices = dict(ast["vertices"])
    expected = {sid: _compact(v.get("text") or sid) for sid, v in source_vertices.items()}
    expected.update({sid: _compact(g.get("title") or sid) for sid, g in groups.items()})
    children = collections.defaultdict(list)
    for cid, cell in vertices.items():
        children[cell.get("parent")].append(cid)
    reconstructed = set()
    # Match the v4 checker's editable text-run reconstruction.
    for cid in vertices:
        if tags[cid] and tags[cid].startswith("n:") and not labels[cid]:
            fragments = [labels[k] for k in children[cid] if labels[k] and not tags[k] and "shape=text;" in cells[k].get("style", "")]
            if fragments:
                labels[cid] = " ".join(fragments)
                reconstructed.add(cid)
    mapping = {cid: tag[2:] for cid, tag in tags.items() if cid in vertices and tag and tag.startswith("n:")}
    for sid, label in expected.items():
        choices = [cid for cid in vertices if cid not in mapping and _compact(labels[cid]) == label]
        if sid not in mapping.values() and len(choices) == 1 and sum(v == label for v in expected.values()) == 1:
            mapping[choices[0]] = sid
    arrow_shapes = {"arrow_point": (False, True), "arrow_open": (False, False), "double_arrow_point": (True, True)}
    unknown = sorted({edge.get("type") for edge in ast["edges"] if edge.get("type") not in arrow_shapes}, key=str)
    if unknown:
        raise UnsupportedProfile("Mermaid arrow types need another profile: " + repr(unknown))
    wanted = collections.Counter((e["start"], e["end"], _compact(e.get("text", "")), *arrow_shapes[e["type"]]) for e in ast["edges"])
    actual = collections.Counter()
    failures = []
    for cid, cell in edges.items():
        label = labels[cid] or " ".join(labels[k] for k in children[cid] if labels[k])
        style = _style(cell)
        sides = tuple(style.get(side + "Arrow", "none") not in ("", "none") for side in ("start", "end"))
        actual[(mapping.get(cell.get("source")), mapping.get(cell.get("target")), _compact(label), *sides)] += 1
        for side, has in zip(("start", "end"), sides):
            if has and style[side + "Arrow"] not in ("block", "blockThin", "classic", "classicThin", "open", "openThin"):
                failures.append({"reason": "non_point_native_arrow_type", "edge": cid, "side": side})
    if wanted != actual:
        failures.append({"reason": "source_edge_arrow_side_or_label_mismatch", "missing": list((wanted - actual).elements()), "extra": list((actual - wanted).elements())})
    required_text = set()
    for cid in mapping:
        if cid in reconstructed:
            required_text.update(k for k in children[cid] if labels[k] and not tags[k] and "shape=text;" in cells[k].get("style", ""))
        elif labels[cid]:
            required_text.add(cid)
    for cid in edges:
        if labels[cid]:
            required_text.add(cid)
        else:
            required_text.update(k for k in children[cid] if labels[k])
    failures.extend(_hidden_semantic_cells(cells, set(mapping) | set(edges) | required_text))
    for cid, cell in vertices.items():
        if not labels[cid] or cid in mapping:
            continue
        parent = cell.get("parent")
        seen = {cid}
        while parent in cells and parent not in mapping and parent not in edges:
            if parent in seen:
                raise ValueError("Cyclic native parent chain")
            seen.add(parent)
            parent = cells[parent].get("parent")
        if parent not in mapping and parent not in edges:
            failures.append({"reason": "visible_text_outside_source_graph", "cell": cid, "text": labels[cid]})
        elif parent in mapping and (parent not in reconstructed or cell.get("parent") != parent):
            # A node with its own complete label cannot silently gain additional
            # child text.  Reconstructed text runs are allowed only when the v4
            # checker actually consumed those direct fragments as that label.
            failures.append({"reason": "unconsumed_visible_child_text", "cell": cid, "parent": parent, "text": labels[cid]})
        elif parent in edges and (labels[parent] or cell.get("parent") != parent):
            failures.append({"reason": "unconsumed_visible_edge_text", "cell": cid, "parent": parent, "text": labels[cid]})
    return failures, {"expected_directed_arrow_edges": sum(wanted.values()), "mapped_semantic_vertices": len(mapping), "required_source_text_cells": sorted(required_text)}


def _check_mermaid(code, xml):
    from mermaid_semantic_v4 import check
    ast, parser = _mermaid_source_ast(code)
    if not ast.get("vertices") or ast.get("edges") is None:
        raise UnsupportedProfile("Unsupported Mermaid diagram type: " + str(ast.get("type")))
    result = check(ast, xml)
    extra, evidence = _mermaid_extra_checks(ast, xml)
    failures = [] if result["status"] == "node_edge_text_match" else [{"reason": "source_content_mismatch", "details": result}]
    failures.extend(extra)
    return failures, {"parser_runtime": parser, "source_semantic_check": result, **evidence}


def _check_tikz(record, code, xml):
    from tikz_literal_graph import parse_literal
    from tikz_literal_connectivity import bind
    try:
        graph = parse_literal(code)
    except ValueError as exc:
        raise UnsupportedProfile(str(exc)) from exc
    archive_name = record.get("previous_candidate_archive")
    if not archive_name:
        raise UnsupportedProfile("Literal TikZ profile requires its preserved pre-binding baseline")
    archive = (ROOT / archive_name).resolve()
    if not archive.is_relative_to(ROOT / "conversion/harness_sessions"):
        raise ValueError("Baseline archive escapes owned Harness sessions")
    baseline_record = json.loads((archive / "conversion.json").read_bytes())
    for field in ("id", "source_code_sha256", "source_image_sha256"):
        if not record.get(field) or baseline_record.get(field) != record[field]:
            raise ValueError("Baseline source identity mismatch: " + field)
    baseline = _payload(str((archive / "diagram.drawio").relative_to(ROOT)), baseline_record.get("code_sha256"), "conversion/harness_sessions").decode()
    svg = _payload(record.get("source_render_svg"), record.get("source_render_svg_sha256"))
    if baseline_record.get("source_render_svg_sha256") != _sha(svg):
        raise ValueError("Baseline and current source render differ")
    image = _payload(record.get("original_reference"), record.get("source_image_sha256"))
    from PIL import Image
    import io
    width, height = Image.open(io.BytesIO(image)).size
    dom, extractor = _source_dom(svg.decode(), width, height)
    # bind() checks identities of extracted objects, but does not interpret the
    # extractor's issue list. A dropped textPath/foreignObject or failed marker
    # expansion can otherwise be missing from BOTH baseline and reconstruction.
    # This literal adapter has no proven native mapping for these paint features.
    # Keep them in the automatic exception queue rather than claiming full source
    # coverage from an incomplete DOM (or relying on a high global pixel score).
    if dom.get("issues"):
        raise UnsupportedProfile("Fresh source DOM contains unmapped visible features: " + json.dumps(dom["issues"][:20]))
    regenerated, proof = bind(baseline, dom, code)
    if not proof.get("complete"):
        raise UnsupportedProfile("Fresh deterministic binding unsupported: " + json.dumps(proof.get("issues", [])))
    failures = []
    # This is structural source-reconstruction equality, NOT image pixel equality.
    # It covers current node IDs, every glyph, groups, terminals, labels/backgrounds,
    # marker sides and all preserved source objects; old report booleans are ignored.
    if ET.canonicalize(regenerated) != ET.canonicalize(xml):
        failures.append({"reason": "current_xml_differs_from_fresh_source_graph_reconstruction"})
    cells, _, _ = _xml_cells(xml)
    required_text = sorted(o["id"] for o in dom["objects"] if o["type"] == "text" and o.get("text", "").strip())
    failures.extend(_hidden_semantic_cells(cells, set(proof["nodes"].values()) | set(proof["bound_edges"]) | set(required_text)))
    return failures, {
        "source_parser": graph["parser"],
        "complete_statement_coverage": graph["complete_statement_coverage"],
        "source_nodes": len(graph["nodes"]), "source_edges": len(graph["edges"]),
        "source_dom_sha256": _sha(json.dumps(dom, sort_keys=True, separators=(",", ":")).encode()),
        "source_svg_sha256": _sha(svg), "baseline_code_sha256": _sha(baseline.encode()),
        "fresh_reconstructed_code_sha256": _sha(regenerated.encode()),
        "edge_label_groups": len(proof.get("edge_child_labels", [])),
        "native_marker_count": len(proof.get("native_arrowheads", [])),
        "required_source_text_cells": required_text,
        "arrow_contour_fidelity_requires_separate_gate": bool(proof.get("native_arrowheads")),
        "limitations": ["Native arrow contour differences require the independent automated local-raster fidelity gate.", "No source-image/native pixel equality is required by this semantic adapter."],
        **extractor,
    }


def check_graph_profile(record, xml: str) -> dict:
    """Return current revision's source semantics result, without publishing it."""
    source_format = record.get("source_format") or record.get("source_record", {}).get("format")
    profile = {"mermaid": "mermaid_official_ast_source_graph_v1", "tikz": "tikz_literal_fresh_source_binding_v1"}.get(source_format, "unsupported_source_graph")
    result = {"supported": source_format in ("mermaid", "tikz"), "ok": False, "profile": profile, "failures": [], "evidence": {}}
    if not result["supported"]:
        result["failures"].append({"reason": "unsupported_source_format", "format": source_format})
        return result
    try:
        current_hash = _sha(xml.encode())
        if current_hash != record.get("code_sha256"):
            raise ValueError("Current XML hash differs from record revision")
        source_hash = record.get("source_code_sha256")
        source = _payload(record.get("original_source_code"), source_hash)
        identity = record.get("source_record", {})
        if identity.get("code_sha256") and identity["code_sha256"] != source_hash:
            raise ValueError("Source identity hash conflicts with current source payload")
        result["evidence"] = {"code_sha256": current_hash, "source_code_sha256": _sha(source), "record_id": record.get("id")}
        failures, evidence = _check_mermaid(source.decode(), xml) if source_format == "mermaid" else _check_tikz(record, source.decode(), xml)
        result["failures"].extend(failures)
        result["evidence"].update(evidence)
        result["ok"] = not failures
    except UnsupportedProfile as exc:
        result["supported"] = False
        result["failures"].append({"reason": "unsupported_source_graph_profile", "error": str(exc)[:3000]})
    except Exception as exc:
        result["failures"].append({"reason": "source_graph_validation_error", "type": type(exc).__name__, "error": str(exc)[:3000]})
    return result
