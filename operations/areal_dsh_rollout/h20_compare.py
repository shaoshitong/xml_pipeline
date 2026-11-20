"""Compare native context and static YaRN with Qwen3.8 defaults and the unchanged one-turn DSH protocol."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

from h20_eval import environment, gpu_inventory, run_phase, start_server
from launch import ready
from matched_eval import CONTEXT, OUTPUT, save, verify_server


def probe(args, env):
    """Separate live-model tool-chain smoke test, excluded from quality comparison."""
    from render import render

    out = args.out / "tool-probe"
    out.mkdir()
    source = out / "host-private-reference.drawio"
    source.write_text('<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<mxCell id="2" value="Probe" vertex="1" parent="1" style="rounded=1;fillColor=#dae8fc;strokeColor=#6c8ebf;">'
        '<mxGeometry x="10" y="10" width="160" height="70" as="geometry"/></mxCell></root></mxGraphModel>')
    reference = out / "reference.png"
    render(source, reference, args.root / "renderer")
    command = [sys.executable, str(Path(__file__).with_name("rollout.py")),
        "--runtime", str(args.root / "runtime"), "--reference", str(reference),
        "--out", str(out / "episode"), "--renderer-python", str(args.root / "renderer/venv/bin/python"),
        "--render-runtime", str(args.root / "renderer"), "--python-runtime-root", str(args.python_runtime_root),
        "--generator-model", "Qwen/Qwen3.8-27B", "--generator-url", "http://127.0.0.1:32414/v1",
        "--rounds", "1", "--context-window", "262144", "--max-tokens", str(OUTPUT),
        "--sampling-preset", "qwen38", "--preserve-thinking", "--skill-mode", "no-skill",
        "--single-self-review", "--turn-timeout", "120"]
    with (out / "probe.log").open("wb") as log:
        result = subprocess.run(command, env=dict(env, CUDA_VISIBLE_DEVICES=""), stdout=log, stderr=log)
    save(out / "result.json", {"exit": result.returncode, "quality_benchmark": False,
         "via_areal": False, "through_real_dsh": True, "gold_exposed": False})
    print(json.dumps({"tool_probe_exit": result.returncode}), flush=True)


def evaluate(args, name, port, context, env):
    out = args.out / name
    out.mkdir()
    options = argparse.Namespace(root=args.root, port=port, context_window=context,
        sampling_preset="qwen38", preserve_thinking=True, turn_timeout=args.turn_timeout,
        python_runtime_root=args.python_runtime_root)
    prior, start = None, 1
    if args.resume_from:
        previous = args.resume_from / name
        result_path = previous / "result.json"
        previous_result = json.loads(result_path.read_text()) if result_path.exists() else {}
        if previous_result.get("exit") == 0:
            result = {**previous_result, "reused_completed_run": str(previous)}
            save(out / "result.json", result)
            return result
        phase1 = previous / "phase1/phase-result.json"
        start = 2 if phase1.exists() and json.loads(phase1.read_text())["exit"] == 0 else 1
        prior = previous / f"phase{start}/evaluation"
        if not (prior / "episode").exists():
            prior = previous / "phase1/evaluation"
    for phase in range(start, 3):
        if code := run_phase(options, phase, out, 32435, env,
                             resume_from=prior if phase == start else None):
            result = {"exit": code, "completed_phase": phase - 1, "failed_phase": phase}
            break
    else:
        result = {"exit": 0, "completed_phase": 2}
    save(out / "result.json", result)
    print(json.dumps({"variant": name, **result}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--python-runtime-root", type=Path, required=True)
    parser.add_argument("--turn-timeout", type=int, default=1350)
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.out.mkdir(parents=True)
    env = environment(args.root)
    inventory = gpu_inventory()
    assert all(row["memory_used_mib"] < 1024 for row in inventory if row["index"] in (4, 5, 6, 7))
    assert shutil.disk_usage(args.root).free > 100 * 1024**3
    contract = {"source_commit": args.source_commit, "gpu_inventory_before": inventory,
        "generator": "Qwen/Qwen3.8-27B", "reviewer": "Qwen/Qwen3.5-4B",
        "reviewer_frozen": True, "reviewer_gpu": 6, "native_goal": False,
        "artifact_completion_gate": "candidate XML required before stage success",
        "preserve_thinking": True, "temperature": 1.0, "max_output": OUTPUT,
        "stage_limit_seconds": args.turn_timeout, "rounds": 2, "reviews": 1,
        "resumed_from": str(args.resume_from) if args.resume_from else None,
        "training": False, "gold_feedback": False, "full_skill": True,
        "reference_sha256": sha256((args.root / "inputs/022/reference.png").read_bytes()).hexdigest(),
        "variants": {"native": {"context": 262144, "yarn": False, "gpus": [4], "tp": 1},
                     "yarn": {"context": CONTEXT, "yarn": True, "gpus": [5], "tp": 1}},
        "comparison_limits": "One image per variant, both TP1. KV capacity differs. Changes from old baseline are sampling and thinking preservation; goal remains disabled."}
    save(args.out / "control-contract.json", contract)
    services = []
    try:
        for name, role, model, devices, port, context, fraction, yarn in (
            ("native-server", "generator", "Qwen3.8-27B", "4", 32414, 262144, 0.85, False),
            ("yarn-server", "generator", "Qwen3.8-27B", "5", 32424, CONTEXT, 0.94, True),
            ("reviewer-server", "reviewer", "Qwen3.5-4B", "6", 32435, 65536, 0.40, False)):
            process, log = start_server(args.root, args.out / name, role, model, devices,
                port, context, fraction, env, yarn=yarn,
                sampling="qwen38" if role == "generator" else "instruct")
            services.append((process, log, name, port, context))
        for process, _, name, port, context in services:
            ready(process, port, timeout=900)
            contract[name] = verify_server(port, context, args.out / name / "backend.json")
            save(args.out / "control-contract.json", contract)
            print(json.dumps({"ready": name, "pid": process.pid}), flush=True)
        if not args.resume_from:
            probe(args, env)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {name: pool.submit(evaluate, args, name, port, context, env)
                       for name, port, context in (("native", 32414, 262144), ("yarn", 32424, CONTEXT))}
            results = {name: future.result() for name, future in futures.items()}
        save(args.out / "result.json", results)
        return int(any(result["exit"] for result in results.values()))
    finally:
        for process, log, *_ in services:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            log.close()
        save(args.out / "gpu-inventory-after.json", gpu_inventory())


if __name__ == "__main__":
    raise SystemExit(main())
