"""Run two independent, isolated four-generation reconstructions with three reviews."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time

from harness import HERE, run
from pilot import verified

GENERATION = (
    "Use the drawio-reconstruction skill. Work only with target.png and your own case files. "
    "Reconstruct the complete diagram using editable native draw.io objects, labels and connectors. "
    "Write an uncompressed, single-page round{n}.drawio. You may write and run Python programs "
    "to build the XML and inspect image crops. Preserve your own previous checkpoints and scripts. "
    "This is generation {n} of exactly four. "
)
REVIEW = (
    "This is review {n} of exactly three. Read target.png and round{n}.png as images. "
    "Inspect your own round{n}.drawio, including labels, objects, directed endpoints, paths, "
    "groups, positions, colors and typography. Write review{n}.json with concrete remaining "
    "discrepancies, candidate cell IDs, target-image regions and intended fixes. "
    "Keep this turn focused on review and preserve the candidate XML for the next generation. "
)


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def turn(args, arm, phase, prompt, sid, socket_dir=None):
    folder = args.out / arm
    logs = folder / phase
    code = run(args.runtime, args.credentials, args.profile, folder / "case", logs, prompt,
               socket_dir=socket_dir, timeout=1800, session_home=folder / "home",
               session_id=sid, config=args.out / "paired.yml", python_home=args.python_home)
    events = [json.loads(line) for line in (logs / "events.jsonl").read_text().splitlines()
              if line.startswith("{")]
    session = next((e["sessionId"] for e in events if e["type"] == "session"), sid)
    status = {"arm": arm, "phase": phase, "exit": code, "session_id": session,
              "completed": any(e["type"] == "final" for e in events),
              "tool_calls": sum(e["type"] == "tool_call" for e in events)}
    write_json(logs / "status.json", status)
    print(json.dumps(status), flush=True)
    if code or not status["completed"] or not session:
        raise RuntimeError(f"Harness turn failed: {arm}/{phase}")
    return session


def run_arm(args, arm, record):
    from verifier import Service, Verifier, compile_bytes, native, on_white, read_candidate, Runtime

    folder = args.out / arm
    case = folder / "case"
    case.mkdir(parents=True)
    (case / "target.png").write_bytes(verified(args.dataset / record["image_file"], record["image_sha256"]))
    target = on_white(case / "target.png")
    sid = None
    checkpoints = []
    started = time.monotonic()
    verifier = Verifier(case, compile_bytes(verified(args.dataset / record["code_file"],
                                                   record["code_sha256"])), reveal_structure=True)
    for n in range(1, 5):
        prompt = GENERATION.format(n=n)
        if n > 1:
            prompt += f"Read your own round{n-1}.drawio and review{n-1}.json and apply the justified fixes. "
        if n == 4:
            prompt += ("This is the last generation. Write selected.json with "
                       '{"candidate":"round4.drawio"} and give your final answer with remaining uncertainties. ')
        else:
            prompt += "A separate review turn will follow. Finish after writing the XML and a short construction record. "
        sid = turn(args, arm, f"gen-{n}", prompt, sid)
        data = read_candidate(case, f"round{n}.drawio")
        compiled = compile_bytes(data)
        with Runtime() as renderer:
            _, rendered, _ = native(renderer, compiled, target)
        rendered.image.save(case / f"round{n}.png")
        checkpoints.append({"round": n, "sha256": sha256(data).hexdigest(),
                            "bytes": len(data), "render": f"round{n}.png"})
        write_json(folder / "progress.json", {"arm": arm, "generation": n, "session_id": sid,
                                              "elapsed_seconds": round(time.monotonic()-started),
                                              "checkpoints": checkpoints})
        if n < 4:
            prompt = REVIEW.format(n=n)
            if arm == "mcp":
                prompt += (f"Call mcp__drawio__check on round{n}.drawio exactly once, read the relevant "
                           "object and field diagnostic ranges, and use those findings to guide your own review. ")
                with Service(verifier) as directory:
                    sid = turn(args, arm, f"review-{n}", prompt, sid, directory)
            else:
                prompt += "Perform this review yourself using the target and your own rendered image. "
                sid = turn(args, arm, f"review-{n}", prompt, sid)
            if not (case / f"review{n}.json").is_file():
                raise RuntimeError(f"Missing review record: {arm}/{n}")
            if sha256(read_candidate(case, f"round{n}.drawio")).hexdigest() != checkpoints[-1]["sha256"]:
                raise RuntimeError(f"Review changed its generation checkpoint: {arm}/{n}")
    # Host-only final scoring happens after the model's last response.
    result, score = verifier.evaluate(read_candidate(case, "round4.drawio"))
    write_json(folder / "final-feedback.json", result)
    write_json(folder / "verifier-calls.json", verifier.calls)
    result = {"arm": arm, "session_id": sid, "checkpoints": checkpoints, "final": score,
              "mcp_calls": len(verifier.calls), "elapsed_seconds": round(time.monotonic()-started)}
    write_json(folder / "result.json", result)
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "manifest", "runtime", "credentials", "profile", "compiler", "python-home", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    for key, value in vars(args).items():
        setattr(args, key, value.resolve())
    os.umask(0o077)
    args.out.mkdir(parents=True)
    sys.path[:0] = [str(args.compiler / name) for name in
                    ("drawio_semantic_compiler", "drawio_compare", "scripts")]
    records = json.loads(args.manifest.read_text())
    record, = records.values()
    config = (HERE / "headless.yml").read_text()
    config += "\n- id: tool-bash\n  disabled: false\n- id: tool-pwsh\n  disabled: true\n"
    (args.out / "paired.yml").write_text(config)
    write_json(args.out / "protocol.json", {"model": "deepseek-flash", "reasoningEffort": "max",
        "generations_per_arm": 4, "reviews_per_arm": 3, "seconds_per_turn": 1800,
        "independent_sessions": True, "image_sha256": record["image_sha256"]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(run_arm, args, arm, record): arm for arm in ("self", "mcp")}
        results = []
        for future in as_completed(jobs):
            arm = jobs[future]
            try:
                results.append(future.result())
            except Exception as error:
                write_json(args.out / arm / "failure.json", {"arm": arm, "error": type(error).__name__,
                                                             "message": str(error)[:400]})
                raise
    write_json(args.out / "results.json", results)


if __name__ == "__main__":
    main()
