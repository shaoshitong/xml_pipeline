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


def select(dataset, out, seed, count=12, retained=None):
    profiles = {}
    paths = sorted(dataset.glob("pairs/*/author.drawio"))
    seen_hashes = {digest(path.read_bytes()) for path in paths if path.parent.name in HOLDOUT_EXCLUSIONS}
    rng = random.Random(seed)
    if retained is not None:
        additional = sorted(retained.glob("pairs/*/editable.drawio"))
        rng.shuffle(additional)
        paths.extend(additional[:count * 3])
    for path in paths:
        case = path.parent.name
        if not TOKEN.fullmatch(case) or case in HOLDOUT_EXCLUSIONS:
            continue
        origin = "author" if path.name == "author.drawio" else "retained"
        if retained is not None:
            case = f"{origin}_{case}"
        try:
            stats = profile(path.read_bytes())
        except (ValueError, ET.ParseError):
            continue
        if stats["sha256"] in seen_hashes:
            continue
        seen_hashes.add(stats["sha256"])
        profiles[case] = {"path": str(path), "origin": origin, **stats}

    def choose(bucket, quota):
        if len(bucket) < quota:
            raise ValueError(f"only {len(bucket)} source candidates for a quota of {quota}")
        rng.shuffle(bucket)
        picked = {}
        for stratum, applicable in (
            ("table", lambda p: p["table"]),
            ("math", lambda p: p["math"]),
            ("nested", lambda p: p["nested"] >= 5),
            ("flow", lambda p: p["edges"] >= 5),
        ):
            for case in [c for c in bucket if c not in picked and applicable(profiles[c])][:quota // 4]:
                picked[case] = stratum
        for case in bucket:
            if len(picked) == quota:
                break
            picked.setdefault(case, "other")
        return picked

    author = [case for case, info in profiles.items() if info["origin"] == "author"]
    author_quota = count if retained is None else count * 2 // 5
    chosen = choose(author, author_quota)
    if retained is not None:
        chosen.update(choose([case for case, info in profiles.items() if info["origin"] == "retained"],
                             count - author_quota))
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


def localized_negative(record, diagnostics):
    changed = re.search(r"id='([^']+)'", record.get("detail", ""))
    if changed is None:
        return None
    cell_id = changed.group(1)
    geometry = record["variant"] == "negative_geometry_shift"
    return any(
        d["status"] == "confirmed"
        and (d["kind"].endswith("_moved") if geometry else d["kind"] == "label_changed")
        and all(d[side] and cell_id in d[side]["cell_ids"] for side in ("a", "b"))
        for d in diagnostics
    )


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
                    if not positive:
                        item["changed_cell_localized"] = localized_negative(record, diagnostics)
                except (OSError, ValueError, ET.ParseError, PlaywrightError) as error:
                    item["error"] = str(error)
                    item["pass"] = False
            write_json(out / case / "results.json", [item for item in result if item["case"] == case])
            print(json.dumps({"case": case, "finished": len(records),
                              "passed": sum(bool(r.get("pass")) for r in result if r["case"] == case)}), flush=True)
    return result


def balance_one_per_source(cases, sources, variants):
    counts = Counter()
    available = []
    for case, items in cases:
        source_hash = digest((sources / f"{case}.drawio").read_bytes())
        choices = [r for r in items if r["status"] == "generated"
                   and digest((variants / case / f"{r['variant']}.drawio").read_bytes()) != source_hash]
        if not choices:
            raise ValueError(f"generator produced no transformed XML for {case}")
        available.append((case, choices))
    rng = random.Random(2026111107)
    rng.shuffle(available)
    plan = []
    for case, choices in sorted(available, key=lambda item: len(item[1])):
        selected = min(choices, key=lambda r: (counts[r["variant"]], r["variant"]))
        counts[selected["variant"]] += 1
        plan.append((case, [selected]))
    return sorted(plan)


def verify(sources, variants, out, workers, one_per_source=False):
    cases = work_items(sources, variants)
    input_hashes = {p.stem: digest(p.read_bytes()) for p in sources.glob("*.drawio")}
    frozen = json.loads((sources / "sources.json").read_text())["records"]
    if input_hashes != {r["case"]: r["sha256"] for r in frozen}:
        raise ValueError("held-out inputs changed since sampling")
    out.mkdir(parents=True, exist_ok=False)
    if one_per_source:
        cases = balance_one_per_source(cases, sources, variants)
    write_json(out / "test_plan.json", [r for _, items in cases for r in items])
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
        if kind == "negative":
            summary[kind]["changed_cell_localized"] = sum(r.get("changed_cell_localized") is True for r in generated)
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
    choose.add_argument("--count", type=int, default=12, choices=range(4, 101))
    choose.add_argument("--retained", type=Path, help="add editable sources from the retained dataset")
    check = commands.add_parser("verify")
    check.add_argument("sources", type=Path)
    check.add_argument("variants", type=Path)
    check.add_argument("out", type=Path)
    check.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    check.add_argument("--one-per-source", action="store_true")
    args = parser.parse_args()
    if args.action == "select":
        select(args.dataset, args.out, args.seed, args.count, args.retained)
    else:
        verify(args.sources, args.variants, args.out, args.workers, args.one_per_source)


if __name__ == "__main__":
    main()
