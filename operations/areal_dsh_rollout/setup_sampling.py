"""Create a private HF serving overlay with Qwen precise-coding defaults."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


SAMPLING = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
            "presence_penalty": 0.0, "repetition_penalty": 1.0}
INSTRUCT_SAMPLING = dict(SAMPLING, temperature=0.7, top_p=0.8, presence_penalty=1.5)


def create_overlay(model, output, mode="precise-coding"):
    model, output = model.resolve(), output.resolve()
    if output == model or model in output.parents:
        raise ValueError("Serving overlay must be outside the original model directory")
    config = json.loads((model / "config.json").read_text())
    original = model / "generation_config.json"
    generation = json.loads(original.read_text()) if original.is_file() else {}
    text_config = config.get("text_config", config)
    for key in ("bos_token_id", "eos_token_id", "pad_token_id"):
        token = text_config.get(key, config.get(key))
        if key not in generation and token is not None:
            generation[key] = token
    sampling = INSTRUCT_SAMPLING if mode == "instruct" else SAMPLING
    generation.update(sampling, do_sample=True)
    output.mkdir(parents=True, exist_ok=False)
    for path in model.iterdir():
        if path.name != "generation_config.json":
            (output / path.name).symlink_to(path, target_is_directory=path.is_dir())
    data = (json.dumps(generation, indent=2, sort_keys=True) + "\n").encode()
    (output / "generation_config.json").write_bytes(data)
    return {"source": str(model), "overlay": str(output),
            "generation_config_sha256": sha256(data).hexdigest(),
            "generation_config": generation,
            "loading": "SGLang --sampling-defaults model; explicit request values take priority",
            "presence_penalty": "Not read from generation_config by SGLang; pass --preferred-sampling-params",
            "mode": mode,
            "output_budget": "Set DSH model maxTokens separately; this file does not set it"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("precise-coding", "instruct"), default="precise-coding")
    args = parser.parse_args()
    print(json.dumps(create_overlay(args.model, args.output, args.mode), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
