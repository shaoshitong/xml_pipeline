"""Launch two independent SGLang models and one bounded DSH rollout on one GPU."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen


HERE = Path(__file__).resolve().parent


def ready(process, port, timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Inference server {port} exited: {process.returncode}")
        try:
            with urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(2)
    raise TimeoutError(f"Inference server {port} did not become ready")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--generator", choices=("4B", "9B"), default="4B")
    parser.add_argument("--rounds", type=int, default=4)
    args = parser.parse_args()
    args.out.mkdir(parents=True)
    processes = []
    logs = []
    environment = dict(os.environ, OMP_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false",
                       HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    try:
        for role, size, port, fraction in [("generator", args.generator, 30000, "0.45"),
                                            ("reviewer", "4B", 30001, "0.35")]:
            model = f"Qwen/Qwen3.5-{size}"
            command = [sys.executable, "-m", "sglang.launch_server", "--model-path",
                       str(args.root / "models" / f"Qwen3.5-{size}"), "--served-model-name", model,
                       "--host", "127.0.0.1", "--port", str(port), "--tp", "1",
                       "--dtype", "bfloat16", "--context-length", "32768",
                       "--max-total-tokens", "32768", "--max-running-requests", "1",
                       "--mem-fraction-static", fraction, "--disable-cuda-graph",
                       "--reasoning-parser", "qwen3", "--tool-call-parser", "qwen3_coder"]
            log = (args.out / f"{role}-server.log").open("wb")
            logs.append(log)
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment)
            processes.append(process)
            ready(process, port)
            audit = args.out / f"{role}-requests.jsonl"
            proxy = subprocess.Popen([sys.executable, str(HERE / "trace_proxy.py"), "--port", str(port + 101),
                                      "--upstream", f"http://127.0.0.1:{port}", "--audit", str(audit)],
                                     stdout=log, stderr=subprocess.STDOUT, env=environment)
            processes.append(proxy)
        command = [sys.executable, str(HERE / "rollout.py"), "--runtime", str(args.root / "runtime"),
                   "--reference", str(args.reference), "--out", str(args.out / "episode"),
                   "--renderer-python", str(args.root / "renderer/venv/bin/python"),
                   "--render-runtime", str(args.root / "renderer"),
                   "--generator-model", f"Qwen/Qwen3.5-{args.generator}", "--rounds", str(args.rounds)]
        result = subprocess.run(command, env=environment)
        (args.out / "launch-result.json").write_text(json.dumps({"exit": result.returncode,
             "generator": args.generator, "reviewer": "4B", "separate_processes": True,
             "reviewer_updated": False, "gpu_visibility": environment.get("CUDA_VISIBLE_DEVICES")}) + "\n")
        raise SystemExit(result.returncode)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
