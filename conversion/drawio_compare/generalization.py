"""Sample held-out draw.io files and evaluate externally generated transformations."""

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
import random
import re
import shutil
import xml.etree.ElementTree as ET

from playwright.sync_api import Error as PlaywrightError

from cli import run, write_json
from model import cell_index, decode
from runtime import Runtime, digest


HOLDOUT_EXCLUSIONS = {"002", "012", "013", "017", "022"}
TOKEN = re.compile(r"[a-zA-Z0-9_-]{1,80}\Z")
CATEGORIES = {"format", "nesting", "editable", "negative"}


def profile(blob):
    doc = decode(blob)
    index = {(page["number"], key): (outer, cell) for page in doc.pages
             for key, (outer, cell, _) in cell_index(ET.fromstring(page["xml"])).items()}
    vertices = {key for key, (_, cell) in index.items() if cell.get("vertex") == "1"}
    labels = [(outer.get("label") or cell.get("value") or "") for outer, cell in index.values()]
    return {
        "pages": len(doc.pages),
        "cells": len(doc.cell_ids),
        "edges": sum(c.get("edge") == "1" for _, c in index.values()),
        "nested": sum((page, c.get("parent")) in vertices for (page, _), (_, c) in index.items()),
        "table": any("table" in c.get("style", "").lower() for _, c in index.values())
        or any("<table" in label.lower() for label in labels),
        "math": any("$$" in label or "\\(" in label for label in labels),
        "html": any("html=1" in c.get("style", "") and label for (_, c), label in zip(index.values(), labels)),
        "sha256": digest(blob),
    }


def select(dataset, out, seed):
    profiles = {}
    for path in sorted(dataset.glob("pairs/*/author.drawio")):
        case = path.parent.name
        if not TOKEN.fullmatch(case) or case in HOLDOUT_EXCLUSIONS:
            continue
        try:
            stats = profile(path.read_bytes())
        except (ValueError, ET.ParseError):
            continue
        profiles[case] = {"path": str(path), **stats}
    if len(profiles) < 12:
        raise ValueError("at least twelve held-out source files are required")
    rng = random.Random(seed)
    order = sorted(profiles)
    rng.shuffle(order)
    chosen = {}
    for stratum, applicable in (
        ("table", lambda p: p["table"]),
        ("math", lambda p: p["math"]),
        ("nested", lambda p: p["nested"] >= 5),
        ("flow", lambda p: p["edges"] >= 5),
    ):
        for case in [c for c in order if c not in chosen and applicable(profiles[c])][:3]:
            chosen[case] = stratum
    for case in order:
        if len(chosen) == 12:
            break
        chosen.setdefault(case, "other")
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for case, stratum in sorted(chosen.items()):
        record = profiles[case]
        shutil.copyfile(record["path"], out / f"{case}.drawio")
        records.append({"case": case, "stratum": stratum, **record})
    write_json(out / "sources.json", {"seed": seed, "population": len(profiles), "records": records})
    print(json.dumps({"population": len(profiles), "held_out": list(sorted(chosen))}), flush=True)


def work_items(sources, variants):
    records = json.loads((variants / "manifest.json").read_text())["records"]
    by_case = defaultdict(list)
    seen = set()
    available = {p.stem for p in sources.glob("*.drawio")}
    for record in records:
        case, variant, category, status = (record.get(k) for k in ("case", "variant", "category", "status"))
        if (case not in available or not isinstance(variant, str) or not TOKEN.fullmatch(variant)
                or category not in CATEGORIES or status not in {"generated", "skipped"}
                or (case, variant) in seen):
            raise ValueError(f"invalid or repeated variant record: {record}")
        seen.add((case, variant))
        by_case[case].append(record)
    if set(by_case) != available or len({variant for _, variant in seen}) < 6:
        raise ValueError("the transformation manifest did not cover all held-out cases and six variant types")
    expected = {(case, record["variant"]) for case, items in by_case.items() for record in items
                if record["status"] == "generated"}
    actual = {(p.parent.name, p.stem) for p in variants.glob("*/*.drawio") if p.is_file() and not p.is_symlink()}
    if actual != expected:
        raise ValueError("variant files do not match the transformation manifest")
    return sorted(by_case.items())


def raw_render_agrees(runtime, source, variant, report, cache):
    matches = []
    for page in report["pages"]:
        if page["a_png"] is None or page["b_png"] is None:
            matches.append(False)
            continue
        number, frame = page["page"], page["frame"]
        key = number, json.dumps(frame, sort_keys=True)
        if key not in cache:
            cache[key] = runtime.render(source, frame, page_number=number)
        before = cache[key]
        after = runtime.render(variant, frame, page_number=number)
        if before.unresolved or after.unresolved:
            raise ValueError("unresolved raw-render assets")
        matches.append(before.pixel_sha256 == after.pixel_sha256)
    return matches


def check_shard(cases, sources, variants, out):
    result = []
    with Runtime() as runtime:
        for case, records in cases:
            a = sources / f"{case}.drawio"
            source_bytes = a.read_bytes()
            source = source_bytes.decode("utf-8-sig")
            (out / case).mkdir()
            cache = {}
            for record in records:
                item = dict(record)
                result.append(item)
                if record["status"] == "skipped":
                    continue
                b = variants / case / f"{record['variant']}.drawio"
                folder = out / case / record["variant"]
                folder.mkdir(parents=True, exist_ok=False)
                try:
                    variant_bytes = b.read_bytes()
                    item["variant_sha256"] = digest(variant_bytes)
                    item["input_changed"] = variant_bytes != source_bytes
                    report = run(a, b, folder, "reference", runtime=runtime)
                    item["compiled"] = True
                    raw_matches = raw_render_agrees(runtime, source, variant_bytes.decode("utf-8-sig"), report, cache)
                    compared = [page["render"]["pixel_exact"] for page in report["pages"]]
                    diagnostics = [d for p in report["pages"] for d in p["diagnostics"]]
                    item.update(
                        pixel_exact=all(raw_matches), comparator_agrees=raw_matches == compared,
                        normalized_xml_equal=report["normalized_xml_equal"],
                        confirmed=dict(Counter(d["kind"] for d in diagnostics if d["status"] == "confirmed")),
                        diagnostic_counts=report["summary"],
                        report=str((folder / "diff.json").relative_to(out)),
                    )
                    positive = record["category"] != "negative"
                    item["expected_pixels"] = positive
                    item["pass"] = item["input_changed"] and item["comparator_agrees"] and item["pixel_exact"] == positive
                except (OSError, ValueError, ET.ParseError, PlaywrightError) as error:
                    item["error"] = str(error)
                    item["pass"] = False
            write_json(out / case / "results.json", [item for item in result if item["case"] == case])
            print(json.dumps({"case": case, "finished": len(records),
                              "passed": sum(bool(r.get("pass")) for r in result if r["case"] == case)}), flush=True)
    return result


def verify(sources, variants, out, workers):
    cases = work_items(sources, variants)
    input_hashes = {p.stem: digest(p.read_bytes()) for p in sources.glob("*.drawio")}
    frozen = json.loads((sources / "sources.json").read_text())["records"]
    if input_hashes != {r["case"]: r["sha256"] for r in frozen}:
        raise ValueError("held-out inputs changed since sampling")
    out.mkdir(parents=True, exist_ok=False)
    n = min(workers, len(cases))
    records = []
    with ProcessPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(check_shard, cases[i::n], sources, variants, out) for i in range(n)]
        for completed in as_completed(futures):
            records.extend(completed.result())
    if input_hashes != {p.stem: digest(p.read_bytes()) for p in sources.glob("*.drawio")}:
        raise ValueError("a held-out source changed during evaluation")
    summary = {}
    for kind in sorted(CATEGORIES):
        selected = [r for r in records if r["category"] == kind]
        generated = [r for r in selected if r["status"] == "generated"]
        summary[kind] = {
            "generated": len(generated), "skipped": len(selected) - len(generated),
            "compiled": sum(bool(r.get("compiled")) for r in generated),
            "pixel_exact": sum(bool(r.get("pixel_exact")) for r in generated),
            "passed": sum(bool(r.get("pass")) for r in generated),
            "comparator_disagreed": sum(r.get("comparator_agrees") is False for r in generated),
            "normalized_xml_equal": sum(bool(r.get("normalized_xml_equal")) for r in generated),
            "no_diagnostics": sum(r.get("diagnostic_counts") == {} for r in generated),
        }
    write_json(out / "generalization.json", {"summary": summary, "source_hashes_unchanged": True,
                                             "records": sorted(records, key=lambda r: (r["case"], r["variant"]))})
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    choose = commands.add_parser("select")
    choose.add_argument("dataset", type=Path)
    choose.add_argument("out", type=Path)
    choose.add_argument("--seed", type=int, default=2026111107)
    check = commands.add_parser("verify")
    check.add_argument("sources", type=Path)
    check.add_argument("variants", type=Path)
    check.add_argument("out", type=Path)
    check.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    args = parser.parse_args()
    if args.action == "select":
        select(args.dataset, args.out, args.seed)
    else:
        verify(args.sources, args.variants, args.out, args.workers)


if __name__ == "__main__":
    main()
