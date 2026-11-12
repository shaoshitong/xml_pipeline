"""Freeze the current admitted draw.io inputs on HKUST3."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time


LIVE = "clean/arxiv_research_figures_v1/goal500_automatic_admission_v2/current.json"
LOCAL = "clean/arxiv_research_figures_v1/local_drawio_extension_v1/current.json"


def read_snapshot(root, pointer):
    for _ in range(8):
        before = (root / pointer).read_bytes()
        info = json.loads(before)
        spec = info["unified_pairs"] if pointer == LIVE else info
        raw = (root / spec["file"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if before == (root / pointer).read_bytes() and digest == spec["sha256"]:
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
            if len(rows) != spec.get("rows", spec.get("unified_rows")):
                raise ValueError(f"Unexpected row count in {spec['file']}")
            return rows, {
                "pointer": pointer,
                "pointer_sha256": hashlib.sha256(before).hexdigest(),
                "manifest": spec["file"],
                "manifest_sha256": digest,
                "source_rows": len(rows),
                "published_utc": info.get("at_utc"),
            }
        time.sleep(0.5)
    raise ValueError(f"Could not obtain a consistent published snapshot for {pointer}")


def digest_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(root, row):
    case_id = row["id"]
    try:
        if row["format"] != "drawio":
            raise ValueError("Input must be draw.io")
        for field in ("code", "image"):
            path = (root / row[f"{field}_file"]).resolve(strict=True)
            if not path.is_relative_to(root):
                raise ValueError(f"{field} path escapes corpus root")
            expected = row[f"{field}_sha256"]
            if not re.fullmatch("[0-9a-f]{64}", expected) or digest_file(path) != expected:
                raise ValueError(f"{field} hash mismatch")
    except (KeyError, OSError, TypeError, ValueError) as exc:
        return {"id": case_id, "error": str(exc)}
    return None


def write_new(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent) as temp:
        temp.write(data)
        temp.flush()
        Path(temp.name).hardlink_to(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "corpus.jsonl"
    if manifest_path.exists():
        raise FileExistsError(manifest_path)

    live, live_receipt = read_snapshot(root, LIVE)
    extension, local_receipt = read_snapshot(root, LOCAL)
    local = [row for row in extension if row.get("source") == "mac_local_drawio"]
    local_receipt["selected_rows"] = len(local)
    rows = sorted(live + local, key=lambda row: row["id"])
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate pair IDs in the combined admitted manifests")
    if len({(row["code_sha256"], row["image_sha256"]) for row in rows}) != len(rows):
        raise ValueError("Duplicate XML/PNG pairs in the combined admitted manifests")
    keys = ("id", "format", "code_file", "code_sha256", "image_file", "image_sha256")
    failures = []
    print(json.dumps({"stage": "verify_input_files", "expected": len(rows)}), flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for done, error in enumerate(pool.map(lambda row: validate(root, row), rows), 1):
            if error:
                failures.append(error)
            if done % 256 == 0 or done == len(rows):
                print(json.dumps({"verified": done - len(failures), "checked": done,
                                  "failed": len(failures), "total": len(rows)}), flush=True)
    if failures:
        write_new(output / "input_errors.json", (json.dumps(failures, indent=2) + "\n").encode())
        raise ValueError(f"{len(failures)} inputs failed validation")

    manifest = "".join(json.dumps({**{key: row[key] for key in keys},
                                   "source": row.get("source") or "retained_baseline"},
                                  sort_keys=True) + "\n" for row in rows).encode()
    receipt = {"schema": "drawio-semantic-compiler-corpus-v1", "root": str(root),
               "inputs": len(rows), "live": len(live), "local": len(local),
               "manifest": manifest_path.name, "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
               "verified_xml_and_png_hashes": len(rows), "source_snapshots": [live_receipt, local_receipt]}
    write_new(manifest_path, manifest)
    write_new(output / "corpus_receipt.json", (json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
