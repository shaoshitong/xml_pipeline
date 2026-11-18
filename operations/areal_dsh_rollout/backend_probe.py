"""Bounded SGLang/HF greedy controls; HF GPU generation is a separate explicit mode."""

import argparse
import base64
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def cases(request_path):
    original = json.loads(request_path.read_text())
    images = [deepcopy(part) for message in original["messages"]
              for part in message["content"] if part["type"] == "image_url"]
    titles = [{"role": "user", "content": [*images, {
        "type": "text", "text": "Only list the four large panel titles, left to right."}]}]
    return (("original", original["messages"]), ("panel-titles", titles))


def hf_messages(messages):
    from PIL import Image

    converted = deepcopy(messages)
    for message in converted:
        for index, part in enumerate(message["content"]):
            if part["type"] == "image_url":
                url = part["image_url"]["url"]
                if not url.startswith("data:image/"):
                    raise ValueError("The probe accepts only the original inline image")
                image = Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")
                message["content"][index] = {"type": "image", "image": image}
    return converted


def prepare(processor, model_path, messages, output):
    import torch

    converted = hf_messages(messages)
    text = processor.apply_chat_template(converted, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=False, preserve_thinking=False)
    inputs = processor.apply_chat_template(converted, tokenize=True, add_generation_prompt=True,
                                           enable_thinking=False, preserve_thinking=False,
                                           return_dict=True, return_tensors="pt")
    tensors = {}
    for name, value in inputs.items():
        if torch.is_tensor(value):
            data = value.detach().cpu().contiguous()
            tensors[name] = {"shape": list(data.shape), "dtype": str(data.dtype),
                             "sha256": sha256(data.view(torch.uint8).numpy().tobytes()).hexdigest()}
    result = {"input_tokens": inputs["input_ids"].shape[-1],
              "input_ids": inputs["input_ids"].tolist(),
              "image_grid_thw": inputs["image_grid_thw"].tolist(), "tensors": tensors,
              "rendered_prompt_sha256": sha256(text.encode()).hexdigest(),
              "chat_template_sha256": sha256((model_path / "chat_template.jinja").read_bytes()).hexdigest(),
              "processor_class": type(processor).__name__,
              "image_processor_class": type(processor.image_processor).__name__,
              "image_processor_size": processor.image_processor.size,
              "preprocessing": "HF native defaults; independently compare with SGLang before interpreting differences"}
    save(output / "hf-inputs.json", result)
    return inputs, result


def wait_ready(origin, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(origin + "/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            pass
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"Reviewer did not become ready within {timeout} seconds")


def sg_probe(args, prepared):
    wait_ready(args.origin, args.ready_timeout)
    results = []
    for name, messages, output, inputs, preparation in prepared:
        body = {"model": "Qwen/Qwen3.5-4B", "messages": messages,
                "temperature": 0.0, "top_p": 1.0, "top_k": 1,
                "presence_penalty": 0.0, "repetition_penalty": 1.0, "min_p": 0.0,
                "seed": 42, "max_tokens": 128, "stream": False,
                "tools": [], "tool_choice": "none", "logprobs": True, "top_logprobs": 5,
                "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": False}}
        data = json.dumps(body).encode()
        (output / "sg-request.json").write_bytes(data)
        started = time.monotonic()
        try:
            with urlopen(Request(args.origin + "/v1/chat/completions", data=data,
                                 headers={"Content-Type": "application/json"}), timeout=120) as response:
                raw = response.read()
                (output / "sg-response.json").write_bytes(raw)
                save(output / "sg-response-headers.json", dict(response.headers))
            response = json.loads(raw)
            choice = response["choices"][0]
            logs = (choice.get("logprobs") or {}).get("content") or []
            result = {"case": name, "status": "completed", "seconds": time.monotonic() - started,
                      "usage": response.get("usage"), "finish_reason": choice.get("finish_reason"),
                      "hf_input_tokens": preparation["input_tokens"], "returned_logprob_tokens": len(logs),
                      "content": choice["message"].get("content"),
                      "response_sha256": sha256(raw).hexdigest()}
        except HTTPError as error:
            (output / "sg-error-body.json").write_bytes(error.read())
            result = {"case": name, "status": "http_error", "http_status": error.code}
        except (OSError, URLError) as error:
            result = {"case": name, "status": "transport_error", "error_type": type(error).__name__}
        save(output / "sg-summary.json", result)
        results.append(result)
    return results


def hf_probe(args, processor, prepared):
    import torch
    from transformers import AutoModelForImageTextToText

    model = AutoModelForImageTextToText.from_pretrained(
        args.model_path, local_files_only=True, dtype=torch.bfloat16,
        attn_implementation="sdpa").eval().to("cuda")
    results = []
    for name, messages, output, inputs, preparation in prepared:
        inputs = inputs.to("cuda")
        started = time.monotonic()
        with torch.inference_mode():
            generated = model.generate(**inputs, do_sample=False, num_beams=1,
                                       max_new_tokens=128, repetition_penalty=1.0,
                                       return_dict_in_generate=True, output_logits=True)
        ids = generated.sequences[0, inputs["input_ids"].shape[-1]:].tolist()
        steps = []
        for token, logits in zip(ids, generated.logits, strict=True):
            values, indices = logits[0].float().log_softmax(-1).topk(5)
            steps.append({"token_id": token, "token": processor.tokenizer.decode([token]),
                          "raw_argmax_id": int(indices[0]),
                          "bytes": list(processor.tokenizer.decode([token]).encode()),
                          "top5": [{"token_id": index, "token": processor.tokenizer.decode([index]),
                                    "logprob": value} for index, value in zip(indices.tolist(), values.tolist())]})
        result = {"case": name, "seconds": time.monotonic() - started,
                  "input_tokens": preparation["input_tokens"], "output_token_ids": ids,
                  "content": processor.tokenizer.decode(ids, skip_special_tokens=False), "steps": steps,
                  "backend": "HF BF16 SDPA greedy; no SGLang service or DSH used"}
        save(output / "hf-response.json", result)
        if args.sg_results:
            reference = json.loads((args.sg_results / name / "sg-response.json").read_text())
            logs = reference["choices"][0]["logprobs"]["content"]
            equal = [step["bytes"] == item.get("bytes") for step, item in zip(steps, logs)]
            comparison = {"hf_tokens": len(steps), "sg_tokens": len(logs),
                          "first_token_byte_difference": next((i for i, match in enumerate(equal) if not match), None),
                          "shared_prefix_token_bytes": next((i for i, match in enumerate(equal) if not match), len(equal)),
                          "interpretation": "Differences alone do not establish a backend bug; compare preprocessing and BF16 argmax margins at a shared prefix."}
            save(output / "comparison.json", comparison)
        results.append({"case": name, "output_tokens": len(ids), "seconds": result["seconds"]})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("inputs", "sg", "hf"), required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--request-body", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--origin", default="http://127.0.0.1:30001")
    parser.add_argument("--ready-timeout", type=float, default=300)
    parser.add_argument("--sg-results", type=Path)
    args = parser.parse_args()
    if args.backend != "hf":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from transformers import AutoProcessor

    args.out.mkdir(mode=0o700, parents=True)
    processor = AutoProcessor.from_pretrained(args.model_path, local_files_only=True)
    prepared = []
    for name, messages in cases(args.request_body):
        output = args.out / name
        output.mkdir()
        inputs, preparation = prepare(processor, args.model_path, messages, output)
        prepared.append((name, messages, output, inputs, preparation))
    save(args.out / "probe-summary.json", {"backend": args.backend, "status": "prepared",
         "model_requests_sent": 0, "hf_gpu_executed": False,
         "input_tokens": {name: data["input_tokens"] for name, _, _, _, data in prepared}})
    results = []
    if args.backend == "sg":
        results = sg_probe(args, prepared)
    elif args.backend == "hf":
        results = hf_probe(args, processor, prepared)
    save(args.out / "probe-summary.json", {"backend": args.backend,
         "status": "finished", "model_requests_sent": len(results) if args.backend == "sg" else 0,
         "model_path": str(args.model_path), "max_output_tokens": 128,
         "maximum_sg_model_requests": 2 if args.backend == "sg" else 0,
         "hf_gpu_executed": args.backend == "hf", "results": results})
    print(json.dumps({"backend": args.backend, "out": str(args.out), "results": results}), flush=True)


if __name__ == "__main__":
    main()
