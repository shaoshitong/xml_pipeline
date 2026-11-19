"""Verify teacher replies, enacted tools, lazy SFT examples and archive size."""

import argparse
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
import sqlite3
import threading
import time

from export_sft import encode_completion, materialize
from gateway import parse_reply
from store import Store, canonical


def check_qwen_template(template, sample):
    arguments = {"tools": sample["tools"], "enable_thinking": True}
    prefix = template.render(messages=sample["prompt"], add_generation_prompt=True, **arguments)
    full = template.render(messages=sample["prompt"] + sample["completion"],
                           add_generation_prompt=False, **arguments)
    if not full.startswith(prefix):
        raise ValueError(f"Qwen completion boundary changed at call {sample['teacher_call_id']}")
    target = full[len(prefix):]
    message = sample["completion"][0]
    reasoning = (message.get("reasoning_content") or "").strip()
    if reasoning and reasoning not in target:
        raise ValueError(f"Qwen template dropped target reasoning at call {sample['teacher_call_id']}")
    if prefix.count("<|vision_start|><|image_pad|><|vision_end|>") != len(sample["images"]):
        raise ValueError(f"Qwen image attachment count differs at call {sample['teacher_call_id']}")
    for tool in message.get("tool_calls", []):
        if "<function=" + tool["function"]["name"] + ">" not in target:
            raise ValueError(f"Qwen template dropped a target tool at call {sample['teacher_call_id']}")
        for name, value in tool["function"].get("arguments", {}).items():
            rendered = template.environment.filters["tojson"](value) if isinstance(value, (dict, list)) else str(value)
            if f"<parameter={name}>\n{rendered}\n</parameter>" not in target:
                raise ValueError(f"Qwen template changed tool arguments at call {sample['teacher_call_id']}")
    return {"calls": 1, "target_reasoning_records": bool(reasoning),
            "image_attachments": len(sample["images"]),
            "target_tool_calls": len(message.get("tool_calls", []))}


def open_archive(root):
    root = Path(root)
    store = Store.__new__(Store)
    store.root, store.objects = root / "archive", root / "archive/objects"
    store.lock = threading.RLock()
    store.db = sqlite3.connect("file:" + str(store.root / "ledger.sqlite") + "?mode=ro", uri=True)
    # Audits only read immutable nodes; materialize() copies message structures.
    store.get = lru_cache(maxsize=32768)(store.get)
    return store


def qwen_contexts(root, processor_path, episode=None, limit=None):
    from transformers import Qwen3VLProcessor
    root, processor_path = Path(root), Path(processor_path)
    store = open_archive(root)
    processor = Qwen3VLProcessor.from_pretrained(processor_path, local_files_only=True)
    native_context = json.loads((processor_path / "config.json").read_text())["text_config"]["max_position_embeddings"]
    completed = {path.parent.name for path in (root / "episodes").glob("*/completed.json")}
    rows = store.db.execute("""select id,episode,request,response,json_extract(usage,'$.prompt_tokens')
        from calls where completed=1 and role='generator' and status=200 and error is null
        order by json_extract(usage,'$.prompt_tokens') desc""").fetchall()
    rows = [row for row in rows if row[1] in completed and (episode is None or row[1] == episode)]
    if limit:
        rows = rows[:limit]
    records = []
    for number, ident, request, response, teacher_tokens in rows:
        reply = store.get(response)
        if reply["choices"][0].get("finish_reason") not in ("stop", "tool_calls"):
            continue
        row = materialize(store, {"call_id": number, "episode": ident,
                                 "request_ref": request, "response_ref": response}, decode_images=False)
        kwargs = {"tools": row["tools"], "enable_thinking": True, "tokenize": False}
        prefix = processor.tokenizer.apply_chat_template(row["prompt"], add_generation_prompt=True, **kwargs)
        full = processor.tokenizer.apply_chat_template(row["prompt"] + row["completion"],
                                                       add_generation_prompt=False, **kwargs)
        full_ids, loss_mask, shared_whitespace = encode_completion(processor.tokenizer, prefix, full)
        sizes = [(image.height, image.width) for image in row["images"]]
        vision_tokens = sum(processor._get_num_multimodal_tokens(image_sizes=sizes).num_image_tokens)
        target_tokens = sum(loss_mask)
        prompt_tokens = len(full_ids) - target_tokens + vision_tokens - len(sizes)
        total = prompt_tokens + target_tokens
        records.append({"call_id": number, "episode": ident, "teacher_prompt_tokens": teacher_tokens,
                        "qwen_prompt_tokens": prompt_tokens, "qwen_target_tokens": target_tokens,
                        "images": len(sizes), "vision_tokens": vision_tokens,
                        "masked_boundary_whitespace_tokens": shared_whitespace,
                        "fits_64k": total <= 65536, "fits_native_context": total <= native_context})
    return {"at": time.time(), "calls": len(records), "episodes": len({x["episode"] for x in records}),
            "processor": str(processor_path), "native_context": native_context,
            "fits_64k": sum(x["fits_64k"] for x in records),
            "fits_native_context": sum(x["fits_native_context"] for x in records),
            "max_qwen_prompt_tokens": max((x["qwen_prompt_tokens"] for x in records), default=0),
            "masked_boundary_whitespace_tokens": sum(x["masked_boundary_whitespace_tokens"] for x in records),
            "archive_node_cache": store.get.cache_info()._asdict(),
            "tokenized_completion_boundaries_verified": True,
            "vision_count_method": "Official processor image sizes and placeholder expansion; no model weights loaded",
            "truncation": False, "training_run": False, "records": records}


def verify(root, episode=None, qwen_template=None):
    root = Path(root)
    store = open_archive(root)
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
    template, template_counts = None, Counter()
    if qwen_template:
        from transformers.utils.chat_template_utils import _compile_jinja_template
        template = _compile_jinja_template(Path(qwen_template).read_text())
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
        sample_requested = len(materialized) < 3 or number == rows[-1][0]
        if sample_requested or template is not None:
            row = materialize(store, {"call_id": number, "episode": ident,
                                     "request_ref": request_ref, "response_ref": response_ref})
        if template is not None and response["choices"][0].get("finish_reason") in ("stop", "tool_calls"):
            template_counts.update(check_qwen_template(template, row))
        if sample_requested:
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
    if template is not None:
        result["qwen_template"] = {"file": str(qwen_template), **dict(template_counts),
            "current_completion_reasoning_preserved": True, "completion_prefix_boundary_verified": True,
            "historical_reasoning_policy": "Official Qwen template; full original reasoning remains in the archive",
            "tokenization_and_training_not_run": True}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--episode")
    parser.add_argument("--qwen-template", type=Path)
    parser.add_argument("--qwen-processor", type=Path)
    parser.add_argument("--context-limit", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (qwen_contexts(args.root, args.qwen_processor, args.episode, args.context_limit)
              if args.qwen_processor else verify(args.root, args.episode, args.qwen_template))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
