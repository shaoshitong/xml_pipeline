"""Recompile the frozen corpus and record the current canonical XML and IR hashes."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import sys

from close_corpus import source_fingerprint


def compile_case(item):
    from compiler import CompileError, compile_bytes

    root, row = item
    result = {"id": row["id"], "input_sha256": row["code_sha256"]}
    try:
        data = (root / row["code_file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["code_sha256"]:
            raise ValueError("Input differs from the frozen corpus")
        report = compile_bytes(data).report
        result.update(output_sha256=report["output"]["sha256"], ir_sha256=report["ir_sha256"])
    except (CompileError, OSError, ValueError, RuntimeError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("corpus", "root", "source", "out"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    from compiler import COMPILER_VERSION

    data = args.corpus.read_bytes()
    rows = [json.loads(line) for line in data.splitlines() if line.strip()]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate case IDs")
    args.out.mkdir()
    path = args.out / "checks.jsonl"
    errors = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool, path.open("x") as out:
        tasks = ((args.root, row) for row in rows)
        for count, result in enumerate(pool.map(compile_case, tasks, chunksize=4), 1):
            out.write(json.dumps(result, sort_keys=True) + "\n")
            errors += "error" in result
            if count % 512 == 0:
                print(f"Recompiled {count}/{len(rows)}, errors {errors}", flush=True)
    with path.open("rb") as stream:
        checks = hashlib.file_digest(stream, "sha256").hexdigest()
    receipt = {"corpus_sha256": hashlib.sha256(data).hexdigest(), "checks_sha256": checks,
               "compiler": COMPILER_VERSION, "source_fingerprint": source_fingerprint(args.source)[0],
               "expected": len(rows), "verified": len(rows) - errors, "errors": errors}
    (args.out / "summary.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
