"""Verify corpus closure after a verifier-only correction and targeted rerun."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def source_fingerprint(folder):
    digest = hashlib.sha256()
    paths = sorted(folder.glob("*.py")) + sorted(folder.glob("*.js"))
    files = {}
    for path in paths:
        if not path.name.startswith("test_") and path.name != "controls.py":
            data = path.read_bytes()
            files[path.name] = hashlib.sha256(data).hexdigest()
            digest.update(path.name.encode() + b"\0" + data + b"\0")
    return digest.hexdigest(), files


def check_case(row, primary, retest, fingerprints, current_outputs):
    case = row["id"]
    latest = retest / "cases" / case
    initial = primary / "cases" / case
    folder = latest if (latest / "status.json").is_file() else initial
    source = "retest" if folder == latest else "initial"
    result_path = folder / "status.json"
    try:
        status = read(result_path)
        if (status["id"] != case or status["input_sha256"] != row["code_sha256"]
                or status["sources_sha256"] != fingerprints[source]):
            raise ValueError("status does not match the frozen input and deployed source")
        if status["state"] != "accepted" or not all(status["checks"].values()):
            failed = [key for key, value in status["checks"].items() if not value]
            raise ValueError(f"{status['state']}: {', '.join(failed)}")
        if current_outputs is not None:
            current = current_outputs[case]
            if any(status[k] != current.get(k) for k in ("input_sha256", "output_sha256", "ir_sha256")):
                raise ValueError("Acceptance proof is for a different compilation")
        proof = read(folder / "native.json")
        if (not proof["equal"] or not proof["assets_resolved"] or len(proof["pages"]) != status["pages"]
                or not all(p["model_equal"] and p["pixel_equal"] and p["edit"]["equal"]
                           and p["original_pixel_sha256"] == p["compiled_pixel_sha256"] for p in proof["pages"])):
            raise ValueError("native per-page equality or edit evidence is missing")
        canonical = folder / "canonical.drawio"
        with canonical.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != status["output_sha256"] or canonical.stat().st_size != status["output_bytes"]:
            raise ValueError("canonical artifact differs from the verified output")
        if not all((folder / name).is_file() for name in ("ir.json", "source_map.json", "report.json")):
            raise ValueError("a required compiler artifact is missing")
        return {"id": case, "acceptance": source, "status": str(result_path.resolve()),
                "canonical": str(canonical.resolve()), "canonical_sha256": digest,
                "pages": status["pages"], "cells": status["cells"], "edit_probes": status["edit_probes"],
                "inert_edit_probes": status["inert_edit_probes"], "input_bytes": status["input_bytes"],
                "output_bytes": status["output_bytes"]}, None
    except (OSError, KeyError, TypeError, ValueError) as exc:
        return None, {"id": case, "status": str(result_path.resolve()), "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("corpus", "primary", "retest", "initial_source", "current_source", "out"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--revalidated", type=Path, help="current compiler's independently recompiled hashes")
    args = parser.parse_args()
    initial_hash, initial = source_fingerprint(args.initial_source)
    current_hash, current = source_fingerprint(args.current_source)
    if not initial or not current:
        raise ValueError("Missing deployed compiler source")
    if args.revalidated is None and {k: v for k, v in initial.items() if k != "verify.js"} != {
            k: v for k, v in current.items() if k != "verify.js"}:
        raise ValueError("Recompile the full corpus before reusing evidence after compiler changes")
    fingerprints = {"initial": initial_hash, "retest": current_hash}
    corpus = args.corpus.read_bytes()
    rows = [json.loads(line) for line in corpus.splitlines() if line.strip()]
    corpus_hash = hashlib.sha256(corpus).hexdigest()
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate case IDs")
    if read(args.primary / "EXIT.json")["manifest_cases"] != len(rows):
        raise ValueError("The primary batch has not closed the complete corpus")
    current_outputs = None
    if args.revalidated is not None:
        checked = (args.revalidated / "checks.jsonl").read_bytes()
        receipt = read(args.revalidated / "summary.json")
        if (receipt["corpus_sha256"] != corpus_hash or receipt["source_fingerprint"] != current_hash
                or receipt["checks_sha256"] != hashlib.sha256(checked).hexdigest()):
            raise ValueError("Recompilation evidence does not match the current source and corpus")
        current_outputs = {r["id"]: r for r in map(json.loads, checked.splitlines())}
        if set(current_outputs) != {row["id"] for row in rows}:
            raise ValueError("Recompilation evidence does not cover the frozen corpus")
    args.out.mkdir()
    totals, origins = Counter(), Counter()
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool, (args.out / "accepted.jsonl").open("x") as out:
        work = pool.map(lambda row: check_case(row, args.primary, args.retest, fingerprints, current_outputs), rows)
        for count, (result, error) in enumerate(work, 1):
            if error:
                errors.append(error)
            else:
                out.write(json.dumps(result, sort_keys=True) + "\n")
                origins[result["acceptance"]] += 1
                totals.update({k: v for k, v in result.items() if isinstance(v, int)})
            if count % 512 == 0:
                print(f"Checked {count}/{len(rows)}, errors {len(errors)}", flush=True)
    receipt = {"corpus_sha256": corpus_hash, "expected": len(rows),
               "accepted": sum(origins.values()), "by_verifier_run": dict(origins), "totals": dict(totals),
               "source_fingerprints": fingerprints, "errors": errors}
    (args.out / "summary.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({k: v for k, v in receipt.items() if k != "errors"}), flush=True)
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
