"""Run the existing gold-blind matched DSH evaluation on the authorized H20 GPUs."""

import argparse
from glob import glob
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import time

from external_api_workflow import default_episode
from launch import long_context_overlay, ready
from matched_eval import CONTEXT, OUTPUT, save, verify_server
from setup_sampling import create_overlay


HERE = Path(__file__).resolve().parent


def gpu_inventory():
    raw = subprocess.check_output([
        "nvidia-smi", "--query-gpu=index,uuid,memory.used", "--format=csv,noheader,nounits"], text=True)
    return [{"index": int(index), "uuid": uuid.strip(), "memory_used_mib": int(memory)}
            for index, uuid, memory in (line.split(",") for line in raw.splitlines())]


def environment(root):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false",
               OMP_NUM_THREADS="4", DSH_MASK_PROCESS_TITLE="1")
    env["PYTHONPATH"] = str(HERE / "h20_bootstrap") + ":" + str(HERE)
    env["PATH"] = str(root / "envs/serving/bin") + ":" + str(root / "runtime/node/bin") + ":" + str(root / "bin") + ":" + env["PATH"]
    libraries = [path for base in sys.path for path in glob(base + "/nvidia/*/lib")]
    env["LD_LIBRARY_PATH"] = ":".join(libraries + [env.get("LD_LIBRARY_PATH", "")])
    paths = {"TMPDIR": "tmp", "HF_HOME": "huggingface", "XDG_CACHE_HOME": "xdg",
             "TRITON_CACHE_DIR": "triton", "CUDA_CACHE_PATH": "cuda",
             "FLASHINFER_WORKSPACE_BASE": "flashinfer", "TORCH_EXTENSIONS_DIR": "torch-extensions",
             "TVM_FFI_CACHE_DIR": "tvm-ffi", "NUMBA_CACHE_DIR": "numba"}
    for key, name in paths.items():
        path = root / "cache" / name
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    chrome_tmp = root.parent / "dio-tmp"
    chrome_tmp.mkdir(exist_ok=True)
    env["DSH_CHROME_TMPDIR"] = str(chrome_tmp)
    return env


def run_phase(args, phase, out, reviewer_port, env, *, resume_from=None):
    target = out / f"phase{phase}"
    target.mkdir()
    evaluation = target / "evaluation"
    context = getattr(args, "context_window", CONTEXT)
    preset = getattr(args, "sampling_preset", "precise-coding")
    turn_timeout = getattr(args, "turn_timeout", 1350)
    options = argparse.Namespace(root=args.root, runtime=args.root / "runtime",
        model="Qwen/Qwen3.8-27B", reviewer_url=f"http://127.0.0.1:{reviewer_port}/v1",
        rounds=phase, skill_mode="full", sampling_preset=preset, context_window=context,
        max_tokens=OUTPUT, reasoning_effort="high", turn_timeout=turn_timeout, single_self_review=True)
    episode = default_episode(options)
    episode[0] = str(args.root / "envs/serving/bin/python")
    episode += ["--python-runtime-root", str(args.python_runtime_root)]
    if getattr(args, "preserve_thinking", False):
        episode.append("--preserve-thinking")
    if getattr(args, "qwen38_effort", "xhigh") != "xhigh":
        episode += ["--qwen38-effort", args.qwen38_effort]
    command_file = target / "episode-template.json"
    save(command_file, episode)
    command = [str(args.root / "controller/env/bin/python"), str(HERE / "external_api_workflow.py"),
        "eval", "--root", str(args.root), "--runtime", str(options.runtime),
        "--reference", str(args.root / "inputs/022/reference.png"), "--out", str(evaluation),
        "--episode-command", str(command_file), "--api-url", f"http://127.0.0.1:{args.port}/v1",
        "--model", options.model, "--reviewer-url", options.reviewer_url, "--rounds", str(phase),
        "--context-window", str(context), "--max-tokens", str(OUTPUT), "--reasoning-effort", "high",
        "--skill-mode", "full", "--sampling-preset", preset, "--single-self-review",
        "--turn-timeout", str(turn_timeout), "--timeout", str(max(1500, phase * turn_timeout + 120)),
        "--recovery-policy", ""]
    if resume_from or phase == 2:
        command += ["--resume-from", str(resume_from or out / "phase1/evaluation")]
    phase_env = dict(env, CUDA_VISIBLE_DEVICES="", AREAL_EXTERNAL_TASK_TOKEN=secrets.token_urlsafe(32),
                     ROLLOUT_API_WIRE_AUDIT=str(target / "api-wire.jsonl"))
    with (target / "evaluation.log").open("wb") as log:
        result = subprocess.run(command, env=phase_env, stdout=log, stderr=log)
    save(target / "phase-result.json", {"phase": phase, "exit": result.returncode,
                                       "full_episode": phase == 2, "training": False})
    print(json.dumps({"phase": phase, "exit": result.returncode}), flush=True)
    return result.returncode


def start_server(root, folder, role, model, devices, port, context, fraction, env,
                 *, yarn=False, sampling="precise-coding", extra_args=()):
    folder.mkdir()
    serving = folder / "serving"
    create_overlay(root / "models" / model, serving, sampling)
    if yarn:
        serving = long_context_overlay(serving, folder / "long-context")
    command = [str(root / "envs/serving/bin/python"), "-m", "sglang.launch_server",
        "--model-path", str(serving), "--served-model-name", "Qwen/" + model,
        "--host", "127.0.0.1", "--port", str(port), "--tp", str(len(devices.split(","))),
        "--dtype", "bfloat16", "--context-length", str(context), "--max-total-tokens", str(context),
        "--max-running-requests", "1", "--cuda-graph-max-bs", "1",
        "--mem-fraction-static", str(fraction), "--max-mamba-cache-size", "16",
        "--sampling-defaults", "model", "--reasoning-parser", "qwen3",
        "--tool-call-parser", "qwen3_coder", "--preferred-sampling-params",
        json.dumps({"min_p": 0.0, "presence_penalty": 0.0 if role == "generator" else 1.5,
                    "repetition_penalty": 1.0})]
    log = (folder / "server.log").open("wb")
    command.extend(extra_args)
    process = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True,
        env=dict(env, CUDA_VISIBLE_DEVICES=devices, SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN="1",
                 DSH_QWEN38_PARSER_COMPAT="1" if role == "generator" else "0"))
    return process, log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--python-runtime-root", required=True, type=Path)
    parser.add_argument("--port", type=int, default=32404)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.out.mkdir(parents=True)
    env = environment(args.root)
    inventory = gpu_inventory()
    used = {4, 5, 6}
    assert all(row["memory_used_mib"] < 1024 for row in inventory if row["index"] in used)
    assert {row["index"] for row in inventory if row["index"] in used} == used
    assert shutil.disk_usage(args.root).free > 100 * 1024**3
    contract = {"generator": "Qwen/Qwen3.8-27B", "reviewer": "Qwen/Qwen3.5-4B",
        "generator_context": CONTEXT, "generator_max_output": OUTPUT,
        "reviewer_context": 65536, "reviewer_max_output": 32768,
        "stage_limit_seconds": 1350, "rounds": 2, "reviews": 1, "training": False,
        "gold_feedback": False, "fresh_from_image": True, "full_skill": True,
        "single_self_review": True, "preserve_thinking": False,
        "model_template_reasoning_effort": "xhigh", "generator_tensor_parallel": 2,
        "qwen38_tool_boundary": "tokenizer-declared <tool_call> interruption of reasoning",
        "generator_gpus": [4, 5], "reviewer_gpus": [6], "authorized_gpus": [4, 5, 6, 7],
        "gpu_inventory_before": inventory, "source_commit": args.source_commit,
        "reference_sha256": sha256((args.root / "inputs/022/reference.png").read_bytes()).hexdigest(),
        "source_hashes": {p.name: sha256(p.read_bytes()).hexdigest()
                          for p in HERE.iterdir() if p.is_file()},
        "output_storage": "User-authorized H20 data disk for this short evaluation"}
    save(args.out / "matched-contract.json", contract)
    processes, logs = [], []
    try:
        for role, model, devices, port, context, fraction in (
            ("generator", "Qwen3.8-27B", "4,5", args.port, CONTEXT, 0.85),
            ("reviewer", "Qwen3.5-4B", "6", args.port + 1, 65536, 0.40)):
            folder = args.out / role
            process, log = start_server(args.root, folder, role, model, devices, port, context,
                fraction, env, yarn=role == "generator",
                sampling="precise-coding" if role == "generator" else "instruct")
            logs.append(log)
            processes.append(process)
            ready(process, port, timeout=900)
            contract[role + "_backend"] = verify_server(port, context, folder / "backend.json")
            save(args.out / "matched-contract.json", contract)
            print(json.dumps({"ready": role, "pid": process.pid}), flush=True)
        for phase in (1, 2):
            if code := run_phase(args, phase, args.out, args.port + 1, env):
                save(args.out / "result.json", {"exit": code, "completed_phase": phase - 1,
                     "failed_phase": phase, "training": False})
                return code
        save(args.out / "result.json", {"exit": 0, "completed_phase": 2, "training": False})
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for log in logs:
            log.close()
        save(args.out / "gpu-inventory-after.json", gpu_inventory())


if __name__ == "__main__":
    raise SystemExit(main())
