"""Budgeted, gold-blind DeepSeek/DSH collection on the dataset host."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from types import SimpleNamespace
import sys
import time
from xml.etree import ElementTree

from export_sft import export, materialize
from gateway import Provider, PRICING, gateway
from store import Store, snapshot


HERE = Path(__file__).resolve().parent
INTEGRATION = HERE.parent / "areal_dsh_rollout"
sys.path.insert(0, str(INTEGRATION))
from rollout import run_turn, review_payload


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def render(source, output, resources):
    # The renderer changes process-wide Chrome environment and tempfile state.
    # Keep those changes outside the concurrent collector and its gateways.
    result = subprocess.run([sys.executable, str(INTEGRATION / "render.py"), str(source),
                             str(output), "--runtime", str(resources)],
                            capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("Official renderer failed: " + result.stderr[-1200:])
    return json.loads(result.stdout)


def link(source, destination):
    if not destination.exists():
        destination.symlink_to(source)


def prepare(root, dataset):
    runtime = root / "runtime"
    (runtime / "node/bin").mkdir(parents=True, exist_ok=True)
    link(Path("/usr/bin/node"), runtime / "node/bin/node")
    link(dataset / "conversion/runtime/dsh", runtime / "dsh")
    resources = root / "renderer"
    resources.mkdir(exist_ok=True)
    links = {"venv": Path("/home/shaoshitong/anaconda3"),
             "draw.war": dataset / "evaluation/assets/drawio-runtime-v32.6.1/draw.war",
             "chrome-linux64": Path("/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64"),
             "fonts": Path("/usr/share/fonts")}
    for name, source in links.items():
        link(source, resources / name)
    (resources / "lib").mkdir(exist_ok=True)
    (resources / "fonts.conf").write_text(
        '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
        '<dir>/usr/share/fonts</dir><include>/etc/fonts/fonts.conf</include></fontconfig>\n')
    source = resources / "source/conversion"
    for folder in ("drawio_compare", "scripts"):
        (source / folder).mkdir(parents=True, exist_ok=True)
    published = INTEGRATION.parents[1] / "conversion"
    for name in ("runtime.py", "native.js"):
        shutil.copyfile(published / "drawio_compare" / name, source / "drawio_compare" / name)
    name = "arxiv_bulk_official_xml_png_math_v1.py"
    shutil.copyfile(published / "scripts" / name, source / "scripts" / name)
    return runtime, resources


def validate_xml(path):
    raw = path.read_bytes()
    document = ElementTree.fromstring(raw)
    cells = list(document.iter("mxCell"))
    if len(cells) < 10 or not any(cell.get("edge") == "1" for cell in cells):
        raise ValueError("Output lacks a native editable diagram structure")
    for cell in cells:
        style = cell.get("style", "")
        if "shape=image" in style or "image=" in style or "data:image" in style:
            raise ValueError("Raster or flattened image output is not admissible")
    return {"xml_sha256": sha256(raw).hexdigest(), "cells": len(cells)}


def deduplicate_attachments(store, folder):
    checked, linked = 0, 0
    for role in ("generator", "reviewer"):
        objects = folder / role / "home/.dsh/attachments/v1/objects"
        for path in objects.rglob("*"):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            digest = store.blob(raw)
            if digest != path.name:
                raise ValueError("DSH attachment content hash mismatch")
            checked += 1
            canonical = store.objects / digest[:2] / (digest[2:] + ".bin")
            if canonical.is_file() and not os.path.samefile(path, canonical):
                temporary = path.with_suffix(".link")
                os.link(canonical, temporary)
                temporary.replace(path)
                linked += 1
    return {"verified": checked, "shared_image_links": linked}


def run_generation(config, number, session):
    previous = config.resume_note
    remaining = {"timeout": 1, "gateway": 1, "artifact": 1}
    notes = {"timeout": "The previous turn reached its wall-clock limit.",
             "gateway": "The previous turn was interrupted by a gateway connection failure.",
             "artifact": f"The previous turn ended without creating the required round{number}.drawio file."}
    try:
        while True:
            try:
                result = run_turn(config, "generator", number, session)
                if not (config.out / "case" / f"round{number}.drawio").is_file():
                    raise RuntimeError(f"Missing generator artifact round{number}.drawio")
                return result
            except RuntimeError:
                path = config.out / "generator" / f"round{number}" / "status.json"
                state = json.loads(path.read_text()) if path.exists() else {}
                reason = generation_retry_reason(config.out, state)
                if not state.get("session_id") or not remaining.get(reason):
                    raise
                remaining[reason] -= 1
                session = state["session_id"]
                config.resume_note = (previous + "\n" + notes[reason] +
                    " Continue in the same session using your existing draft and observations. "
                    "Finish the requested artifact and final response; do not restart the drawing from scratch.")
    finally:
        config.resume_note = previous


def generation_retry_reason(folder, state):
    if state.get("timed_out"):
        return "timeout"
    if state.get("completed") and not (folder / "case" / f"round{state['round']}.drawio").is_file():
        return "artifact"
    log = folder / "generator" / state.get("log_dir", "") / "stderr.log"
    if log.is_file() and log.read_text().startswith((
            "dsh: SERVER: 502 ", "dsh: TRANSPORT: Stream ended without finish_reason")):
        return "gateway"
    return None


def run_review(config, number, session):
    try:
        return run_turn(config, "reviewer", number, session)
    except RuntimeError:
        path = config.out / "reviewer" / f"round{number}" / "status.json"
        state = json.loads(path.read_text()) if path.exists() else {}
        if state.get("validation_error") != "invalid_reviewer_json":
            raise
    previous = config.resume_note
    config.resume_note = (previous + "\nYour previous review was not valid JSON. Re-emit the complete "
                          "review as one valid JSON object, preserving the same assessment and findings. "
                          "Do not redo the drawing or add new findings for this formatting retry.")
    try:
        return run_turn(config, "reviewer", number, session)
    finally:
        config.resume_note = previous


def episode(args, record, store, provider, runtime, resources):
    ident = record["id"]
    folder = args.root / "episodes" / ident
    completed = folder / "completed.json"
    if completed.is_file():
        return json.loads(completed.read_text())
    folder.mkdir(parents=True, exist_ok=True)
    attempts = folder / "attempts"
    attempts.mkdir(exist_ok=True)
    if (folder / "protocol.json").is_file() and not any(attempts.iterdir()):
        save(attempts / "legacy.json", {"protocol": json.loads((folder / "protocol.json").read_text()),
             "status": json.loads((folder / "status.json").read_text())})
    attempt_file = attempts / f"attempt-{len(list(attempts.glob('attempt-*.json'))) + 1:03d}.json"
    case = folder / "case"
    case.mkdir(exist_ok=True)
    reference = Path(record["reference"])
    if sha256(reference.read_bytes()).hexdigest() != record["reference_sha256"]:
        raise ValueError("Reference image does not match the approved selection")
    shutil.copyfile(reference, case / "reference.png")
    skill = case / ".agents/skills/drawio-reconstruction"
    skill.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(INTEGRATION / "reconstruction_skill.txt", skill / "SKILL.md")
    token = secrets.token_urlsafe(32)
    auth = folder / "generation-auth.json"
    with auth.open("w") as stream:
        os.chmod(auth, 0o600)
        json.dump({"headers": {"Authorization": "Bearer " + token}}, stream)
    services = {role: gateway(store, provider, ident, role, case, token, args.budget, args.episode_cap)
                for role in ("generator", "reviewer")}
    config = SimpleNamespace(
        out=folder, runtime=runtime, render_runtime=resources,
        renderer_python=Path(getattr(args, "renderer_python", "/home/shaoshitong/anaconda3/bin/python")),
        python_runtime_root=Path(getattr(args, "python_runtime_root", "/home/shaoshitong/anaconda3")),
        generator_model="deepseek-flash", reviewer_model="deepseek-flash",
        generator_url=f"http://127.0.0.1:{services['generator'].server_port}/v1",
        reviewer_url=f"http://127.0.0.1:{services['reviewer'].server_port}/v1",
        generator_auth_file=auth, reviewer_auth_file=auth, resume=True,
        reviewer_context_window=1048576,
        generator_session_id=None, seeded=False, resume_note="", skill_mode="full",
        rounds=2, single_self_review=True, reasoning_effort="max", context_window=1048576,
        max_tokens=131072, sampling_preset="model", reviewer_sampling_preset="model",
        seed=None, turn_timeout=1350,
        extra_runtime_mounts=getattr(args, "extra_runtime_mounts", [args.dataset / "conversion/runtime/dsh"]))
    protocol = {"source": record, "generator": "deepseek-flash", "reasoning_effort": "max",
                "reviewer": "independent DeepSeek DSH session, no parameter updates",
                "reviewer_context": 1048576, "reviewer_max_output": 32768,
                "reviewer_training_loss": False, "generation_rounds": 2, "reviews": 1,
                "generator_context": 1048576, "max_output": 131072,
                "stage_timeout_seconds": 1350, "generator_timeout_continuations_per_attempt": 1,
                "generator_gateway_continuations_per_attempt": 1,
                "generator_missing_artifact_continuations_per_attempt": 1,
                "gold_available": False, "gold_feedback": False, "mcp": False,
                "external_areal_string_export": False,
                "lossless_wire_capture": True, "source_commit": args.source_commit,
                "complete_trace_does_not_imply_every_step_is_correct": True}
    save(folder / "protocol.json", protocol)
    status = {"id": ident, "paper": record["paper"], "started": time.time(), "completed": False}
    with store.lock:
        first_call = store.db.execute("select coalesce(max(id),0) from calls").fetchone()[0] + 1
    status["first_call_id_this_attempt"] = first_call
    save(folder / "status.json", status)
    generator, reviewer = None, None
    try:
        for number in (1, 2):
            services["generator"].stage = number
            generator, _ = run_generation(config, number, generator)
            xml = case / f"round{number}.drawio"
            validity = validate_xml(xml)
            metadata = render(xml, case / f"round{number}.png", resources)
            save(folder / f"render{number}.json", {**validity, **metadata})
            save(folder / "progress.json", {"at": time.time(), "generation": number, **validity})
            if number == 1:
                frozen = sha256(xml.read_bytes()).hexdigest()
                reviewer, event = run_review(config, number, reviewer)
                review = review_payload(event)
                save(case / "review1.json", review)
                if sha256(xml.read_bytes()).hexdigest() != frozen:
                    raise RuntimeError("Reviewer changed the candidate")
        status.update(completed=True, generator_session=generator, reviewer_session=reviewer,
                      review_advisory=review["status"], fidelity_verified=False,
                      final_snapshot=snapshot(store, case))
    except Exception as error:
        status.update(error_type=type(error).__name__, error=str(error)[:300])
    finally:
        for service in services.values():
            service.shutdown()
            service.server_close()
        auth.unlink(missing_ok=True)
        status["ended"] = time.time()
        status["attachment_deduplication"] = deduplicate_attachments(store, folder)
        status["decision_export"] = export(store, folder / "sft-decisions.jsonl", ident)
        if status["decision_export"].get("generator_decisions"):
            first = json.loads((folder / "sft-decisions.jsonl").read_text().splitlines()[0])
            row = materialize(store, first)
            status["sft_materialization_check"] = {"prompt_messages": len(row["prompt"]),
                "completion_messages": len(row["completion"]), "images": len(row["images"]),
                "tools": len(row["tools"]), "loss": row["training_loss"]}
        save(folder / "status.json", status)
        save(attempt_file, {"protocol": protocol, "status": status})
        if status["completed"]:
            save(completed, status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "dataset", "manifest", "key-file"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--budget", type=float, default=260)
    parser.add_argument("--episode-cap", type=float, default=8)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--proxy")
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.dataset = args.dataset.resolve()
    args.root.mkdir(parents=True, exist_ok=True)
    lock = (args.root / "collector.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    store = Store(args.root / "archive")
    provider = Provider(args.key_file.read_text().strip(), args.proxy)
    balance = provider.balance()
    original = store.db.execute("select value from metadata where key='balance_at_start'").fetchone()
    if not store.db.execute("select 1 from metadata where key='first_balance'").fetchone():
        store.metadata("first_balance", json.loads(original[0]) if original else balance)
    store.metadata("pricing", PRICING)
    store.metadata("authorized_budget_cny", args.budget)
    store.metadata("balance_at_start", balance)
    if not balance["is_available"]:
        raise RuntimeError("Provider reports no usable balance")
    terminal = args.root / "terminal.json"
    if terminal.is_file():
        terminal.rename(args.root / f"terminal-{int(time.time())}.json")
    runtime, resources = prepare(args.root, args.dataset)
    records = [json.loads(x) for x in args.manifest.read_text().splitlines() if x]
    records = [x for x in records if x.get("visual_approval") == "approved"]
    if args.limit:
        records = records[:args.limit]
    save(args.root / "run.json", {"pid": os.getpid(), "started": time.time(), "manifest": str(args.manifest),
        "budget_cny": args.budget, "workers": args.workers, "source_commit": args.source_commit,
        "episodes": len(records), "initial_balance": balance})
    finished = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {}
        iterator = iter(records)
        while True:
            while len(pending) < args.workers and store.summary()["cost_upper_cny"] < args.budget - 3.2:
                item = next(iterator, None)
                if item is None:
                    break
                pending[pool.submit(episode, args, item, store, provider, runtime, resources)] = item["id"]
            if not pending:
                break
            future = next(as_completed(pending))
            ident = pending.pop(future)
            try:
                result = future.result()
            except Exception as error:
                result = {"id": ident, "completed": False, "error_type": type(error).__name__}
            finished.append(result)
            summary = {"at": time.time(), "episodes_finished": len(finished),
                       "episodes_completed": sum(x["completed"] for x in finished), **store.summary()}
            save(args.root / "collection-summary.json", summary)
            print(json.dumps(summary), flush=True)
    summary = {"ended": time.time(), "episodes_finished_this_run": len(finished),
               "episodes_completed_this_run": sum(x["completed"] for x in finished),
               "final_balance": provider.balance(), **store.summary()}
    save(args.root / "terminal.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
