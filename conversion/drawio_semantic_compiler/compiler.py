"""The compilation pipeline: unpack, parse, build IR, normalize, emit, re-read."""

from dataclasses import dataclass
from hashlib import sha256
import json
from operator import itemgetter

from build import build
from emit import emit
import ir
from normalize import normalize
from source import CompileError, Diagnostic, unpack

COMPILER_VERSION = "drawio-semantic-compiler/1.1.1"


@dataclass
class Compilation:
    xml: bytes
    document: ir.Document
    ir_json: dict
    source_map: dict
    report: dict


def front(data):
    """Stages 1-4. Returns the normalized IR and everything recorded on the way."""
    source = unpack(data)
    document, origins, diagnostics, representation = build(source)
    before = [len(page.cells) for page in document.pages]
    for page, origin in zip(document.pages, origins, strict=True):
        for index, cell in enumerate(page.walk()):
            origin[cell.uid]["draw_index"] = index
    rules, audit = normalize(document, origins)
    encodings = [page.encoding for page in source.pages]
    return document, origins, diagnostics, representation, rules, audit, encodings, before


def compile_bytes(data, self_check=True):
    """Compile draw.io XML bytes to canonical XML, IR, source map and report."""
    document, origins, diagnostics, representation, rules, audit, encodings, before = front(data)
    xml = emit(document)
    ir_json = document.to_json()
    checks = {"ir_verified": True}
    if self_check:
        # The emitted file must read back as the same IR and compile to itself.
        rebuilt, _, _, repeated_representation, repeated_rules, *_ = front(xml)
        checks["emitted_xml_rebuilds_ir"] = rebuilt.to_json() == ir_json
        checks["recompilation_byte_stable"] = emit(rebuilt) == xml
        checks["emitted_xml_is_fixed_point"] = not (repeated_representation or repeated_rules)
        if not all(checks.values()):
            failed = sorted(key for key, value in checks.items() if not value)
            raise CompileError(Diagnostic("error", "self_check", "compiler self-check failed: "
                                          + ", ".join(failed)))
    pages = []
    for number, (page, origin, encoding, cells_before) in enumerate(
            zip(document.pages, origins, encodings, before, strict=True), 1):
        origin_points = ir.page_origins(page)
        for cell in page.cells.values():
            position = origin_points[cell.uid]
            if position is not None and cell.kind in (ir.VERTEX, ir.FRAME):
                origin[cell.uid]["page_xy"] = [float(position[0]), float(position[1])]
        cells = sorted(origin.values(), key=itemgetter("root_child_index"))
        pages.append({"page": number, "name": page.name, "source_encoding": encoding,
                      "source_cells": cells_before, "cells": cells})
    source_map = {"schema": "drawio-semantic-source-map/1", "pages": pages}
    report = {
        "schema": "drawio-semantic-compile-report/1",
        "compiler": COMPILER_VERSION,
        "ir": ir.IR_VERSION,
        "input": {"sha256": sha256(data).hexdigest(), "bytes": len(data)},
        "output": {"sha256": sha256(xml).hexdigest(), "bytes": len(xml)},
        "ir_sha256": sha256(dump(ir_json)).hexdigest(),
        "pages": len(document.pages),
        "stages": ["unpack", "lex_and_parse", "build_and_verify_ir", "normalize_ir", "emit_xml",
                   "reread_and_recompile"],
        "checks": checks,
        "representation_changes": representation,
        "rules_applied": rules,
        "reducibility_audit": audit,
        "diagnostics": [d.to_json() for d in diagnostics],
    }
    return Compilation(xml, document, ir_json, source_map, report)


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=1, allow_nan=False) + "\n").encode("utf-8")
