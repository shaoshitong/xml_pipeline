"""Refresh a live SFT index using audited episode coverage and immutable API refs."""

import argparse
from collections import Counter, defaultdict
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time

from export_sft import decision_record, export
from interruption import annotation
from verify import open_archive


def cached_episode(root, audits, ident, calls):
    folder, audit = root / "episodes" / ident, audits / ident
    try:
        passed = json.loads((audit / "passed.json").read_text())
        context = json.loads((audit / "context.json").read_text())
        counts = json.loads((folder / "completed.json").read_text())["decision_export"]
        records = [json.loads(line) for line in (folder / "sft-decisions.jsonl").read_text().splitlines()]
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    numbers = [row["call_id"] for row in records]
    if (len(numbers) != len(set(numbers)) or set(numbers) != {row["call_id"] for row in context["records"]}
            or len(numbers) != passed["generator_decisions"] or len(numbers) != counts["generator_decisions"]
            or len(calls) != counts["recorded_calls"]):
        return None
    by_id = {row[0]: row for row in calls}
    for row in records:
        actual = by_id.get(row["call_id"])
        if (actual is None or (row["episode"], row["stage"], row["request_ref"], row["response_ref"])
                != (actual[1], actual[3], actual[4], actual[5])
                or actual[2] != "generator" or actual[6] != 200 or actual[7] is not None):
            return None
    return counts, set(numbers)


def refresh(root, audits, destination, source_commit):
    started = time.time()
    store = open_archive(root)
    rows = store.db.execute("""select id,episode,role,stage,request,response,status,error,usage
        from calls where completed=1 order by id""").fetchall()
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[1]].append(row)
    records, counts, reused, rescanned = [], Counter(), [], []
    with tempfile.TemporaryDirectory(prefix="sft-index-parts-", dir=destination.parent) as directory:
        for ident, calls in grouped.items():
            cached = cached_episode(root, audits, ident, calls)
            if cached is None:
                part = Path(directory) / (ident + ".jsonl")
                stats = export(store, part, rows=calls)
                records.extend(json.loads(line) for line in part.read_text().splitlines())
                rescanned.append(ident)
            else:
                stats, numbers = cached
                records.extend(decision_record(store, row[0], ident, row[3], row[4], row[5], row[8])
                               for row in calls if row[0] in numbers)
                reused.append(ident)
            counts.update({k: v for k, v in stats.items() if k not in (
                "sft_eligible_generator_decisions", "interrupted_replies_excluded_from_sft")})
            if (len(reused) + len(rescanned)) % 25 == 0:
                print(json.dumps({"stage": "refresh_index", "cached_episodes": len(reused),
                                  "rescanned_episodes": len(rescanned), "decisions": len(records)}), flush=True)
    records.sort(key=lambda row: row["call_id"])
    proofs = {int(path.stem): json.loads(path.read_text())
              for path in (store.root.parent / "annotations").glob("*.json")}
    annotation_at = time.time()
    temporary = destination.with_suffix(".cache-refresh.tmp")
    with temporary.open("w") as stream:
        for row in records:
            row.pop("execution_annotation", None)
            row.update(annotation(store, row, proofs))
            stream.write(json.dumps(row) + "\n")
    counts["sft_eligible_generator_decisions"] = sum(row["supervision_eligible"] for row in records)
    counts["interrupted_replies_excluded_from_sft"] = len(records) - counts["sft_eligible_generator_decisions"]
    temporary.replace(destination)
    result = {"started": started, "at": time.time(), "seconds": time.time() - started,
              "source_commit": source_commit, "snapshot_completed_api_calls": len(rows), "counts": dict(counts),
              "cached_audited_episodes": reused, "rescanned_episodes": rescanned,
              "index": str(destination), "index_bytes": destination.stat().st_size,
              "index_sha256": sha256(destination.read_bytes()).hexdigest(), "model_calls": 0,
              "annotation_snapshot_at": annotation_at, "annotation_snapshot_calls": sorted(proofs),
              "annotation_snapshot_sha256": sha256(json.dumps(proofs, sort_keys=True).encode()).hexdigest(),
              "cache_coverage": "Exact call-ID coverage from Qwen context audit plus current ledger refs"}
    destination.with_suffix(".refresh.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--audits", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    lock = args.output.with_suffix(".refresh.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print(json.dumps(refresh(args.root, args.audits, args.output, args.source_commit)))


if __name__ == "__main__":
    main()
