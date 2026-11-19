"""Index each teacher decision separately; lazily materialize Qwen SFT examples."""

import argparse
import base64
from collections import Counter
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path

from store import Store


def encode_completion(tokenizer, prefix, full):
    """Mask a jointly encoded decision, including BPE whitespace at its boundary."""
    if not full.startswith(prefix):
        raise ValueError("Rendered completion does not extend its prompt")
    encoded = tokenizer(full, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
    boundary, shared_whitespace = len(prefix), 0
    mask = []
    for start, end in encoded["offset_mapping"]:
        if start < boundary < end:
            if not full[start:end].isspace():
                raise ValueError("Completion boundary crosses a non-whitespace token")
            shared_whitespace += 1
        mask.append(int(start >= boundary and end > start))
    return encoded["input_ids"], mask, shared_whitespace


def normalize(messages, decode_images=True):
    from PIL import Image
    # Cached archive nodes may alias identical content across history messages.
    output, images = [deepcopy(message) for message in messages], []
    for message in output:
        for call in message.get("tool_calls", []):
            function = call["function"]
            if isinstance(function["arguments"], str):
                function["arguments"] = json.loads(function["arguments"])
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for index, part in enumerate(content):
            if part.get("type") == "image_url":
                url = part["image_url"]["url"]
                if not url.startswith("data:image/"):
                    raise ValueError("Training image is not archived inline")
                image = Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1])))
                if decode_images:
                    image.load()
                    image = image.copy()
                images.append(image)
                content[index] = {"type": "image"}
    return output, images


def materialize(store, row, decode_images=True):
    request, response = store.get(row["request_ref"]), store.get(row["response_ref"])
    prompt, images = normalize(request["messages"], decode_images)
    completion, response_images = normalize([response["choices"][0]["message"]], decode_images)
    if response_images:
        raise ValueError("Unexpected teacher-generated image output")
    return {"prompt": prompt, "completion": completion, "images": images,
            "tools": request.get("tools", []), "teacher_call_id": row["call_id"],
            "episode": row["episode"], "training_loss": "completion_only"}


def export(store, destination, episode=None):
    query = "select id,episode,role,stage,request,response,status,error,usage from calls where completed=1"
    parameters = ()
    if episode:
        query += " and episode=?"
        parameters = (episode,)
    with store.lock:
        rows = store.db.execute(query + " order by id", parameters).fetchall()
    counts = Counter()
    destination = Path(destination)
    with destination.open("w") as stream:
        for number, ident, role, stage, request_ref, response_ref, status, error, usage in rows:
            counts["recorded_calls"] += 1
            response = store.get(response_ref)
            choices = response.get("choices", [])
            valid = status == 200 and error is None and len(choices) == 1
            valid = valid and choices[0].get("finish_reason") in ("stop", "tool_calls")
            if role != "generator" or not valid:
                counts["reviewer_or_incomplete_calls"] += 1
                continue
            message = choices[0]["message"]
            counts["generator_decisions"] += 1
            counts["with_reasoning"] += bool(message.get("reasoning_content"))
            counts["tool_calls"] += len(message.get("tool_calls", []))
            record = {"schema": "qwen-teacher-decision/1", "call_id": number, "episode": ident,
                      "stage": stage, "request_ref": request_ref, "response_ref": response_ref,
                      "usage": json.loads(usage), "target": "this completion only",
                      "reviewer_is_observation": True, "fidelity_label": "unverified_without_gold",
                      "images_and_history": "lossless DAG references; resolved by materialize()"}
            stream.write(json.dumps(record) + "\n")
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--episode")
    args = parser.parse_args()
    print(json.dumps(export(Store(args.store), args.output, args.episode)))


if __name__ == "__main__":
    main()
