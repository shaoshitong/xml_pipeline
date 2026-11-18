"""Run one fresh matched DSH condition against existing independent model services."""

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent


def wait_proxy(process, port):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Audit proxy {port} exited")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Audit proxy {port} did not listen")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "runtime", "reference", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--mode", choices=("full", "no-skill", "minimal"), required=True)
    parser.add_argument("--generator-model", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    args.out.mkdir(parents=True)
    processes, logs = [], []
    started = time.monotonic()
    try:
        for role, port, upstream in (("generator", 30201, 30000), ("reviewer", 30202, 30001)):
            log = (args.out / (role + "-proxy.log")).open("wb")
            logs.append(log)
            process = subprocess.Popen([
                sys.executable, str(HERE / "trace_proxy.py"), "--port", str(port),
                "--upstream", f"http://127.0.0.1:{upstream}", "--capture-raw",
                "--audit", str(args.out / (role + "-requests.jsonl"))],
                stdout=log, stderr=log)
            processes.append(process)
            wait_proxy(process, port)
        common = ["--runtime", str(args.runtime), "--reference", str(args.reference),
                  "--renderer-python", str(args.root / "renderer/venv/bin/python"),
                  "--render-runtime", str(args.root / "renderer"),
                  "--generator-model", args.generator_model,
                  "--generator-url", "http://127.0.0.1:30201/v1",
                  "--reviewer-url", "http://127.0.0.1:30202/v1", "--seed", str(args.seed)]
        if args.mode == "full":
            command = [sys.executable, str(HERE / "rollout.py"), *common,
                       "--out", str(args.out / "episode"), "--rounds", "2",
                       "--skill-mode", "full", "--sampling-preset", "instruct",
                       "--reasoning-effort", "off", "--context-window", "65536",
                       "--max-tokens", "32768", "--turn-timeout", "900"]
        else:
            command = [sys.executable, str(HERE / "ablate_skill.py"), "--mode", args.mode,
                       "--out", str(args.out / "episode"), "--", *common]
        (args.out / "condition.json").write_text(json.dumps({
            "mode": args.mode, "fresh_from_image": True, "seed": args.seed,
            "sampling": "explicit instruct request fields, not server preferred defaults",
            "generator": args.generator_model, "reviewer": "Qwen/Qwen3.5-4B",
            "gold_feedback": False, "command": command}, indent=2) + "\n")
        result = subprocess.run(command)
        (args.out / "condition-result.json").write_text(json.dumps({
            "exit": result.returncode, "seconds": time.monotonic() - started,
            "episode_completed": (args.out / "episode/completed.json").is_file()}) + "\n")
        return result.returncode
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            process.wait(timeout=10)
        for log in logs:
            log.close()


if __name__ == "__main__":
    raise SystemExit(main())
