"""Run one phase of a budget-matched, gold-blind three-model DSH evaluation."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener
from urllib.parse import urlsplit


HERE = Path(__file__).resolve().parent
CONTEXT = 1048576
OUTPUT = 131072


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def get_json(port, endpoint):
    with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/{endpoint}", timeout=20) as response:
        return json.load(response)


def verify_server(port, context, output):
    info = get_json(port, "server_info")
    model = get_json(port, "model_info")
    capacities = [state.get("memory_usage", {}).get("token_capacity")
                  for state in info.get("internal_states", [])]
    capacity = min((value for value in capacities if value is not None), default=None)
    save(output, {"server": info, "model": model})
    if info["context_length"] != context or capacity is None or capacity < context:
        raise RuntimeError(f"Port {port} did not provision the requested context: {context}, KV capacity: {capacity}")
    if not model["has_image_understanding"]:
        raise RuntimeError(f"Port {port} did not enable vision")
    config = json.loads((Path(model["model_path"]) / "config.json").read_text())
    return {"context_length": info["context_length"], "kv_capacity": capacity,
            "has_image_understanding": True, "model_path": model["model_path"],
            "rope_parameters": config["text_config"]["rope_parameters"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--model", choices=("4B", "9B", "deepseek-flash"), required=True)
    parser.add_argument("--phase", type=int, choices=(1, 2), required=True)
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--reviewer-url", help="Reuse an owned frozen Reviewer service for an API-only second phase")
    args = parser.parse_args()
    if args.api_only and (args.model != "deepseek-flash" or args.phase == 2 and not args.reviewer_url):
        parser.error("API-only phase two requires the existing frozen Reviewer URL")
    out = args.root / "matched" / args.batch / args.model / f"phase{args.phase}"
    out.mkdir(parents=True)
    reference = args.root / "inputs/022/reference.png"
    contract = {"model": args.model, "phase": args.phase, "context_window": CONTEXT,
                "max_tokens": OUTPUT, "case": "022", "reference_sha256": sha256(reference.read_bytes()).hexdigest(),
                "fresh_from_image": args.phase == 1, "gold_feedback": False, "training": False,
                "reviewer": "Qwen/Qwen3.5-4B", "reviewer_context": 65536, "reviewer_max_tokens": 32768,
                "reviewer_frozen": True, "skill_mode": "full", "single_self_review": True,
                "stage_seconds_limit": 1350, "rounds_after_both_phases": 2, "reviews_after_both_phases": 1,
                "source_commit": os.environ.get("MATCHED_COMMIT"),
                "source_hashes": {name: sha256((HERE / name).read_bytes()).hexdigest() for name in
                    ("rollout.py", "external_api_workflow.py", "launch.py", "dsh_profiles.py",
                     "reconstruction_skill.txt", "render.py", "setup_sampling.py")}}
    save(out / "matched-contract.json", contract)
    env = dict(os.environ, ROLLOUT_API_WIRE_AUDIT=str(out / "api-wire.jsonl"))
    local = args.model != "deepseek-flash"
    generator_port = 34000 + int(os.environ["SLURM_JOB_ID"]) % 12000 * 2
    reviewer_port = generator_port + 1
    service_out = out / "services"
    service = [str(args.root / "env/bin/python"), str(HERE / "launch.py"),
               "--root", str(args.root), "--runtime", str(args.runtime), "--reference", str(reference),
               "--out", str(service_out), "--serve-only", "--generator", args.model if local else "4B",
               "--context-window", str(CONTEXT if local else 65536), "--reviewer-context-window", "65536",
               "--generator-mem-fraction", "0.70", "--reviewer-mem-fraction", "0.45",
               "--generator-port", str(generator_port), "--reviewer-port", str(reviewer_port),
               "--mamba-cache-size", "16",
               "--reasoning-effort", "high" if local else "off"]
    service += ["--long-context-yarn"] if local else ["--reviewer-only"]
    process = None
    try:
        if not args.api_only:
            with (out / "services.log").open("wb") as log:
                process = subprocess.Popen(service, stdout=log, stderr=log, env=env)
            deadline = time.monotonic() + 600
            while not (service_out / "services-ready.json").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Matched model services did not become ready")
                time.sleep(1)
            contract["reviewer_backend"] = verify_server(reviewer_port, 65536, out / "reviewer-backend.json")
            if local:
                contract["generator_backend"] = verify_server(generator_port, CONTEXT, out / "generator-backend.json")
        if args.api_only and args.phase == 2:
            reviewer = urlsplit(args.reviewer_url)
            if reviewer.hostname != "127.0.0.1" or reviewer.path != "/v1":
                raise ValueError("The reused Reviewer must be the owned loopback API")
            contract["reviewer_backend"] = verify_server(reviewer.port, 65536, out / "reviewer-backend.json")
            contract["reused_reviewer_url"] = args.reviewer_url
        contract["api_only_first_generation"] = args.api_only and args.phase == 1
        save(out / "matched-contract.json", contract)
        print(json.dumps({"phase": "backend_verified", "model": args.model,
                          "context": CONTEXT, "max_output": OUTPUT}), flush=True)
        mode = "eval" if local else "run"
        command = [str(args.root / "controller/env/bin/python"), str(HERE / "external_api_workflow.py"), mode,
                   "--root", str(args.root), "--runtime", str(args.runtime), "--reference", str(reference),
                   "--out", str(out / "evaluation"), "--model", f"Qwen/Qwen3.5-{args.model}" if local else args.model,
                   "--rounds", str(args.phase), "--context-window", str(CONTEXT), "--max-tokens", str(OUTPUT),
                   "--reasoning-effort", "high" if local else "max", "--skill-mode", "full",
                   "--reviewer-url", args.reviewer_url or f"http://127.0.0.1:{reviewer_port}/v1",
                   "--sampling-preset", "precise-coding" if local else "model", "--single-self-review",
                   "--timeout", "1500", "--turn-timeout", "1350", "--recovery-policy", ""]
        if local:
            env["AREAL_EXTERNAL_TASK_TOKEN"] = secrets.token_urlsafe(32)
            command += ["--api-url", f"http://127.0.0.1:{generator_port}/v1"]
        else:
            command += ["--key-file", str(args.root / "private-auth/deepseek-api.key"),
                        "--proxy", "http://10.120.48.31:30444"]
        if args.phase == 2:
            command += ["--resume-from", str(out.parent / "phase1/evaluation")]
        with (out / "evaluation.log").open("wb") as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=log)
        save(out / "phase-result.json", {"exit": result.returncode, "phase": args.phase,
                                         "full_episode": args.phase == 2, "training": False})
        return result.returncode
    except Exception as error:
        save(out / "infrastructure-failure.json", {"error": type(error).__name__, "detail": str(error)})
        raise
    finally:
        if process is not None:
            if service_out.exists():
                (service_out / "STOP").touch()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=30)


if __name__ == "__main__":
    raise SystemExit(main())
