"""Run paired image-only and compiler-guided refinement from the same DPSK seed."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time

from harness import run

INITIAL = (
    "Use the drawio-reconstruction skill. Read target.png with the image reader. "
    "Independently reconstruct the entire figure as editable, uncompressed draw.io XML. "
    "Write the file seed.drawio in this directory. Use native shapes, text and bound edges. "
    "Leave uncertainties in your final response."
)
REFINE = (
    "Use the drawio-reconstruction skill. Read target.png and start from seed.drawio. "
    "Call the drawio check MCP on seed.drawio, then open the returned preview as an image. "
    "Independently improve the diagram using the target, candidate renders and any diagnostics. "
    "You have up to three new checkpoints after the seed. Verify each checkpoint with the MCP. "
    "Write selected.json as {\"candidate\": \"filename.drawio\"} for the best checked checkpoint, "
    "including seed.drawio if it remains best. Report visible fixes and unresolved uncertainties."
)


def verified(path, digest):
    content = path.read_bytes()
    if sha256(content).hexdigest() != digest:
        raise ValueError(f"Snapshot checksum mismatch for {path}")
    return content


def seed(args, number, record):
    location = args.out / number / "seed"
    case = location / "case"
    case.mkdir(parents=True)
    (case / "target.png").write_bytes(verified(args.dataset / record["image_file"], record["image_sha256"]))
    code = run(args.runtime, args.credentials, args.profile, case, location / "logs", INITIAL)
    status = {"case": number, "phase": "seed", "exit": code, "candidate": (case / "seed.drawio").is_file()}
    (location / "status.json").write_text(json.dumps(status))
    return status


def wait_seed(folder):
    until = time.monotonic() + 1200
    while time.monotonic() < until:
        events = folder / "logs/events.jsonl"
        if events.exists():
            with events.open() as stream:
                for line in stream:
                    if '"type":"final"' in line:
                        return folder / "case/seed.drawio"
                    if '"type":"error"' in line:
                        raise ValueError("DPSK initial turn failed")
        time.sleep(2)
    raise TimeoutError("DPSK initial turn did not finish")


def refinement(args, number, record, arm):
    from verifier import Service, Verifier, compile_bytes, read_candidate

    location = args.out / number / arm
    case = location / "case"
    case.mkdir(parents=True)
    source = wait_seed(args.out / number / "seed")
    (case / "seed.drawio").write_bytes(read_candidate(source.parent, source.name))
    (case / "target.png").write_bytes(verified(args.dataset / record["image_file"], record["image_sha256"]))
    gold = compile_bytes(verified(args.dataset / record["code_file"], record["code_sha256"]))
    verifier = Verifier(case, gold, reveal_structure=arm == "semantic")
    initial = verifier.check({"candidate": "seed.drawio"})
    seed_digest = sha256((case / "seed.drawio").read_bytes()).hexdigest()
    if not initial["ok"]:
        return {"case": number, "arm": arm, "error": "Initial checkpoint failed",
                "diagnostic": initial, "score": verifier.scores.get(seed_digest)}
    with Service(verifier) as socket_dir:
        code = run(args.runtime, args.credentials, args.profile, case, location / "logs",
                   REFINE, socket_dir=socket_dir)
    try:
        requested = json.loads((case / "selected.json").read_text())["candidate"]
        digest = sha256(read_candidate(case, requested)).hexdigest()
        valid_selection = verifier.checked.get(digest, {}).get("ok", False)
    except (OSError, ValueError, KeyError, TypeError):
        valid_selection = False
    selected = requested if valid_selection else "seed.drawio"
    result = {"case": number, "arm": arm, "exit": code, "selected": selected,
              "selection_verified": bool(valid_selection),
              "seed": verifier.scores[seed_digest],
              "final": verifier.scores[digest if valid_selection else seed_digest],
              "checks": len(verifier.checked), "mcp_calls": len(verifier.calls)}
    (location / "checkpoints.json").write_text(json.dumps(
        {"calls": verifier.calls, "scores": verifier.scores}, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "manifest", "runtime", "credentials", "profile", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--compiler", type=Path, help="Conversion directory of the released compiler")
    parser.add_argument("--phase", choices=("seed", "refine", "all"), default="all")
    parser.add_argument("--jobs", type=int, default=5)
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    if args.phase != "seed":
        if args.compiler is None:
            parser.error("--compiler is required for refinement")
        sys.path[:0] = [str(args.compiler / name) for name in
                        ("drawio_semantic_compiler", "drawio_compare", "scripts")]
    os.umask(0o077)
    records = json.loads(args.manifest.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        if args.phase != "refine":
            results = [pool.submit(seed, args, number, record) for number, record in records.items()]
            for job in as_completed(results):
                print(json.dumps(job.result()), flush=True)
        if args.phase != "seed":
            jobs = {pool.submit(refinement, args, number, record, arm): (number, arm)
                    for number, record in records.items() for arm in ("semantic", "image")}
            results = []
            for job in as_completed(jobs):
                number, arm = jobs[job]
                try:
                    result = job.result()
                except Exception as error:
                    result = {"case": number, "arm": arm, "error": type(error).__name__,
                              "detail": str(error)[:300]}
                (args.out / number / arm / "result.json").write_text(json.dumps(result, indent=2))
                results.append(result)
                print(json.dumps(result), flush=True)
            (args.out / "results.json").write_text(json.dumps(results, indent=2))
            return int(any(r.get("error") or r.get("exit") or not r.get("selection_verified")
                           or not r.get("mcp_calls") for r in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
