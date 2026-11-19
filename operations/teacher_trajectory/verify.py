"""Verify teacher replies, enacted tools, lazy SFT examples and archive size."""

import argparse
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import sqlite3
import threading
import time

from export_sft import materialize
from gateway import parse_reply
from store import Store, canonical


def verify(root, episode=None):
    root = Path(root)
    store = Store.__new__(Store)
    store.root, store.objects = root / "archive", root / "archive/objects"
    store.lock = threading.RLock()
    store.db = sqlite3.connect("file:" + str(store.root / "ledger.sqlite") + "?mode=ro", uri=True)
    query = "select id,episode,role,stage,request,response,wire,status,error,completed from calls"
    rows = store.db.execute(query + (" where episode=?" if episode else "") + " order by id",
                            (episode,) if episode else ()).fetchall()
    objects = {x[0]: x[1] for x in store.db.execute("select id,bytes from objects")}

    @lru_cache(maxsize=None)
    def expanded_size(reference):
        node = json.loads(store.raw(reference))
        if node[0] == "dict":
            return 2 + sum(len(canonical(key)) + 1 + expanded_size(value) for key, value in node[1]) + max(0, len(node[1]) - 1)
        if node[0] == "list":
            return 2 + sum(expanded_size(value) for value in node[1]) + max(0, len(node[1]) - 1)
        if node[0] == "image":
            return len(node[1].encode()) + 3 + 4 * ((objects[node[2]] + 2) // 3)
        return len(canonical(node[1]))

    counts, expected, logical = Counter(), {}, 0
    materialized = []
    for number, ident, role, stage, request_ref, response_ref, wire_ref, status, error, completed in rows:
        counts["recorded_calls"] += 1
        if not completed:
            counts["inflight_calls"] += 1
            continue
        wire = store.raw(wire_ref)
        response = store.get(response_ref)
        if status != 200 or error:
            counts["failed_or_partial_calls"] += 1
            continue
        parsed, _ = parse_reply(wire)
        if canonical(parsed) != canonical(response):
            raise ValueError(f"Raw/structured response differs at call {number}")
        counts["raw_response_roundtrips_verified"] += 1
        logical += expanded_size(request_ref) + expanded_size(response_ref)
        if role != "generator":
            continue
        counts["generator_decisions"] += 1
        message = response["choices"][0]["message"]
        counts["reasoning_records"] += bool(message.get("reasoning_content"))
        expected.setdefault(ident, set()).update(x["id"] for x in message.get("tool_calls", []))
        if len(materialized) < 3 or number == rows[-1][0]:
            row = materialize(store, {"call_id": number, "episode": ident,
                                     "request_ref": request_ref, "response_ref": response_ref})
            materialized.append({"call_id": number, "messages": len(row["prompt"]),
                                 "images": len(row["images"]), "image_modes": [x.mode for x in row["images"]],
                                 "completion_only_loss": row["training_loss"] == "completion_only"})
    execution = {}
    for ident, model_calls in expected.items():
        actual, returned = set(), set()
        for path in (root / "episodes" / ident / "generator").glob("round*/events.jsonl"):
            for line in path.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "tool_call":
                    actual.add(event["callId"])
                if event.get("type") == "tool_result":
                    returned.add(event["callId"])
        execution[ident] = {"model_tool_ids": len(model_calls), "executed_tool_ids": len(actual),
                            "returned_tool_ids": len(returned), "model_and_execution_match": model_calls == actual,
                            "all_execution_results_present": actual == returned}
    counts["object_count"], raw_bytes, packed_bytes = store.db.execute(
        "select count(*),sum(bytes),sum(stored_bytes) from objects").fetchone()
    result = {"at": time.time(), "counts": dict(counts), "tool_execution": execution,
              "materialized_examples": materialized,
              "expanded_request_response_json_bytes": logical,
              "archive_unique_object_bytes": packed_bytes,
              "unique_object_bytes_before_compression": raw_bytes,
              "size_comparison_scope": "All requested calls vs all objects in this archive; excludes SQLite, filesystem blocks and DSH session ledgers",
              "expanded_to_object_byte_ratio": logical / packed_bytes if packed_bytes else None,
              "quality_is_not_certified_by_integrity_checks": True}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--episode")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root, args.episode)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
