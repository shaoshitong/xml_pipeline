"""Audit finished teacher episodes without accessing a model API or gold XML."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from collect import save
from export_sft import export
from verify import open_archive


def collector_alive(receipt):
    value = json.loads(receipt.read_text())
    path = Path(f"/proc/{value['pid']}/stat")
    try:
        fields = path.read_text().split()
    except FileNotFoundError:
        return False
    return fields[2] != "Z" and fields[21] == value["startticks"]


def audit(args, folder):
    target = args.out / folder.name
    target.mkdir(exist_ok=True)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS="1",
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false")
    command = [sys.executable, str(Path(__file__).with_name("verify.py")),
               "--root", str(args.root), "--episode", folder.name]
    try:
        for name, option, resource in (("integrity", "--qwen-template", args.template),
                                       ("context", "--qwen-processor", args.processor)):
            output = target / (name + ".json")
            if output.exists():
                continue
            with (target / (name + ".log")).open("w") as log:
                subprocess.run(command + [option, str(resource), "--output", str(output)],
                               env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=900)
        integrity = json.loads((target / "integrity.json").read_text())
        context = json.loads((target / "context.json").read_text())
        expected = sum(bool(x.strip()) for x in (folder / "sft-decisions.jsonl").read_text().splitlines())
        tools = integrity["tool_execution"][folder.name]
        accounted = tools.get("all_model_tools_accounted", tools["model_and_execution_match"])
        if not accounted or not tools["all_execution_results_present"]:
            raise ValueError("Recorded model tools do not match executed tools and results")
        if expected != context["calls"] or expected != integrity["qwen_template"]["calls"]:
            raise ValueError("SFT targets differ from context or template audit coverage")
        indexed = export(open_archive(args.root), folder / "sft-decisions.jsonl", folder.name)
        save(target / "passed.json", {"at": time.time(), "episode": folder.name,
             "source_commit": args.source_commit, "generator_decisions": expected,
             "sft_eligible_generator_decisions": indexed["sft_eligible_generator_decisions"],
             "interrupted_replies_excluded_from_sft": indexed["interrupted_replies_excluded_from_sft"],
             "fits_64k": context["fits_64k"], "fits_native_context": context["fits_native_context"],
             "fidelity_verified": False})
    except Exception as error:
        save(target / "failed.json", {"at": time.time(), "episode": folder.name,
             "error_type": type(error).__name__, "error": str(error), "source_commit": args.source_commit})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "out", "processor", "template", "collector-receipt"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lock = (args.out / "audit.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    while True:
        completed = sorted(p.parent for p in (args.root / "episodes").glob("*/completed.json"))
        pending = [p for p in completed if not (args.out / p.name / "passed.json").exists()
                   and not (args.out / p.name / "failed.json").exists()]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(lambda folder: audit(args, folder), pending))
        passed = [json.loads(p.read_text()) for p in args.out.glob("*/passed.json")]
        failed = [json.loads(p.read_text()) for p in args.out.glob("*/failed.json")]
        alive = collector_alive(args.collector_receipt)
        summary = {"at": time.time(), "collector_alive": alive, "completed_episodes": len(completed),
                   "audited_episodes": len(passed), "failed_audits": failed,
                   "generator_decisions": sum(x["generator_decisions"] for x in passed),
                   "sft_eligible_generator_decisions": sum(
                       x.get("sft_eligible_generator_decisions", x["generator_decisions"]) for x in passed),
                   "interrupted_replies_excluded_from_sft": sum(
                       x.get("interrupted_replies_excluded_from_sft", 0) for x in passed),
                   "fits_64k": sum(x["fits_64k"] for x in passed),
                   "fits_native_context": sum(x["fits_native_context"] for x in passed),
                   "fidelity_verified": False}
        save(args.out / "summary.json", summary)
        print(json.dumps(summary), flush=True)
        if not alive:
            latest = {p.parent.name for p in (args.root / "episodes").glob("*/completed.json")}
            if latest == {p.name for p in completed}:
                break
            continue
        time.sleep(15)


if __name__ == "__main__":
    main()
