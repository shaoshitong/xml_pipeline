"""Host-private object audit; never expose this program or its outputs to agents."""

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import sys


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def object_ref(obj):
    return {"id": obj.id, "kind": obj.kind, "cell_ids": obj.ids, "label": obj.label}


def audit_page(number, gold, candidate, candidate_empty, gold_empty):
    from compare import compare_page, objects

    gold_objects, _ = objects(gold)
    candidate_objects, _ = objects(candidate)
    span = max((side for snapshot in (gold, candidate) if snapshot.get("bounds")
                for side in snapshot["bounds"][2:]), default=1)
    matches, differences = compare_page(gold, candidate, span)
    pairs = {x.id: (y, status, score) for x, y, status, score in matches}
    issues = defaultdict(list)
    for index, diff in enumerate(differences):
        if diff["a_object"] is not None:
            issues[diff["a_object"].id].append(index)

    slots = []
    for key, obj in gold_objects.items():
        pair = pairs.get(key)
        indices = issues[key]
        confirmed = any(differences[i]["status"] == "confirmed" for i in indices)
        if pair is None:
            status = "A" if candidate_empty else "B"
            reason = "candidate_document_empty" if candidate_empty else "unmatched_not_proven_missing"
        elif pair[1] != "confirmed":
            status, reason = "B", "suspected_correspondence"
        elif confirmed:
            status, reason = "A", "confirmed_difference_under_comparator_contract"
        elif indices:
            status, reason = "B", "unresolved_difference"
        else:
            status, reason = "C", "confirmed_match_with_zero_reported_differences"
        slots.append({"slot": f"gold:P{number:03}:{key}", "side": "gold",
                      "gold": object_ref(obj), "candidate": object_ref(pair[0]) if pair else None,
                      "status": status, "reason": reason, "diff_indices": indices,
                      "match_status": pair[1] if pair else "unmatched",
                      "match_score": pair[2] if pair else None})

    used_candidates = {y.id for _, y, _, _ in matches}
    for key, obj in candidate_objects.items():
        if key in used_candidates:
            continue
        slots.append({"slot": f"candidate:P{number:03}:{key}", "side": "candidate",
                      "gold": None, "candidate": object_ref(obj),
                      "status": "A" if gold_empty else "B",
                      "reason": "gold_document_empty" if gold_empty else "unmatched_not_proven_extra",
                      "diff_indices": [i for i, d in enumerate(differences)
                                       if d["b_object"] is not None and d["b_object"].id == key]})
    raw = [{**diff, "a_object": asdict(diff["a_object"]) if diff["a_object"] else None,
            "b_object": asdict(diff["b_object"]) if diff["b_object"] else None}
           for diff in differences]
    return {"page": number, "gold_objects": len(gold_objects),
            "candidate_objects": len(candidate_objects), "slots": slots,
            "matches": [{"gold": object_ref(x), "candidate": object_ref(y),
                         "status": status, "score": score} for x, y, status, score in matches],
            "raw_structure_diff": raw}


def metric(counts, a, b, c):
    weights = {"a": a, "b": b, "c": c}
    result = {"weights": weights, "weights_status": "unset", "E": None, "R": None,
              "formula": "E=(a*A+b*B)/(a*A+b*B+c*C); R=1-E"}
    if all(value is not None for value in weights.values()):
        numerator = a * counts["A"] + b * counts["B"]
        denominator = numerator + c * counts["C"]
        result["weights_status"] = "user_supplied" if denominator else "undefined_zero_denominator"
        if denominator:
            result.update(E=numerator / denominator, R=1 - numerator / denominator)
    return result


def grade(gold_path, candidate_path, resources, source_root, output, weights):
    conversion = source_root / "conversion"
    sys.path[:0] = [str(conversion / name) for name in
                    ("drawio_semantic_compiler", "drawio_compare", "scripts")]
    os.environ["FONTCONFIG_FILE"] = str(resources / "fonts.conf")
    os.environ["LD_LIBRARY_PATH"] = str(resources / "lib") + ":" + os.environ.get("LD_LIBRARY_PATH", "")
    import arxiv_bulk_official_xml_png_math_v1 as official
    from compiler import compile_bytes
    from compare import objects
    import runtime

    official.WAR = runtime.WAR = resources / "draw.war"
    official.CHROME = runtime.CHROME = str(resources / "chrome-linux64/chrome")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    compiled = [compile_bytes(path.read_bytes()) for path in (gold_path, candidate_path)]
    snapshots = []
    with runtime.Runtime() as editor:
        for name, document in zip(("gold", "candidate"), compiled, strict=True):
            (output / f"{name}.normalized.drawio").write_bytes(document.xml)
            write_json(output / f"{name}.compile.json", document.report)
            write_json(output / f"{name}.source_map.json", document.source_map)
            pages = [editor.call("snapshot", document.xml.decode(), pageNumber=n)
                     for n in range(1, len(document.document.pages) + 1)]
            write_json(output / f"{name}.snapshots.json", pages)
            snapshots.append(pages)
        renderer = editor.metadata

    gold, candidate = snapshots
    empty_gold = not any(objects(page)[0] for page in gold)
    empty_candidate = not any(objects(page)[0] for page in candidate)
    empty = {"cells": [], "bounds": None}
    pages = [audit_page(n + 1, gold[n] if n < len(gold) else empty,
                        candidate[n] if n < len(candidate) else empty,
                        empty_candidate, empty_gold)
             for n in range(max(len(gold), len(candidate)))]
    slots = [slot for page in pages for slot in page["slots"]]
    counted = Counter(slot["status"] for slot in slots)
    counts = {key: counted[key] for key in "ABC"}
    report = {
        "schema": "drawio-object-audit/0.1", "private_host_only": True,
        "scope": "Initial object-level comparator calibration; not a generalized field-level reward.",
        "granularity": {
            "gold_slot": "One mutually exclusive slot per compare.objects semantic object, including zero-diff objects.",
            "object_kinds": ["shape", "label", "panel", "table", "edge"],
            "aggregation": "Associated labels and table members may share one semantic object slot.",
            "candidate_slots": "Unmatched candidate objects receive only A/B, never C.",
            "page_contract": "Pages are compared by index; cross-page correspondence is not inferred.",
            "C_contract": "Comparator-confirmed correspondence and no reported difference; not proof that every native field is equal.",
            "uncertainty": "Threshold-rejected unmatched objects remain B unless the opposite document has no semantic objects.",
            "tolerances": "Existing comparator tolerances and field coverage apply; no pixel/MSE metric is used.",
        },
        "counts": counts, "gold_slots": sum(page["gold_objects"] for page in pages),
        "candidate_unmatched_slots": sum(slot["side"] == "candidate" for slot in slots),
        "metric": metric(counts, *weights), "renderer": renderer,
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "pages": pages,
    }
    write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gold", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    for key in ("a", "b", "c"):
        parser.add_argument("--" + key, type=float)
    args = parser.parse_args()
    report = grade(args.gold, args.candidate, args.runtime, args.source_root, args.out,
                   (args.a, args.b, args.c))
    print(json.dumps({key: report[key] for key in ("schema", "counts", "gold_slots",
                                                "candidate_unmatched_slots", "metric")}, sort_keys=True))


if __name__ == "__main__":
    main()
