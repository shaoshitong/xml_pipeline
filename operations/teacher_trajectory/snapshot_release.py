"""Freeze audited teacher episodes and replay one case without model requests."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
import time

from refresh_index import refresh
from verify import open_archive, verify


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def copy_tree(source, target):
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if path.is_symlink() or "__pycache__" in relative.parts:
            continue
        if path.is_file():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if "attachments" in relative.parts and "objects" in relative.parts:
                os.link(path, destination)
            else:
                shutil.copy2(path, destination)


def copy_object(job, source, destination):
    digest, node = job
    path = source / digest[:2] / (digest[2:] + ".bin")
    packed = path.read_bytes() if path.is_file() else path.with_suffix(".gz").read_bytes()
    if not path.is_file():
        import gzip
        path = path.with_suffix(".gz")
        raw = gzip.decompress(packed)
    else:
        raw = packed
    if sha256(raw).hexdigest() != digest:
        raise ValueError("Snapshot object hash mismatch: " + digest)
    target = destination / digest[:2] / path.name
    try:
        os.link(path, target)
    except FileExistsError:
        pass
    children = []
    if node:
        value = json.loads(raw)
        if value[0] == "dict":
            children = [(ref, True) for _, ref in value[1]]
        elif value[0] == "list":
            children = [(ref, True) for ref in value[1]]
        elif value[0] == "image":
            children = [(value[2], False)]
    return digest, children, {"id": digest, "packed_sha256": sha256(packed).hexdigest(),
                              "stored_bytes": len(packed), "file": str(target.relative_to(destination))}


def build(args):
    args.output.mkdir(parents=True)
    run = args.output / "run-01"
    archive = run / "archive"
    archive.mkdir(parents=True)
    source = open_archive(args.run)
    selected = sorted(p.parent.name for p in args.audits.glob("*/passed.json")
                      if (args.run / "episodes" / p.parent.name / "completed.json").is_file())
    if not selected:
        raise ValueError("No completed and audited episodes to freeze")
    db = sqlite3.connect(archive / "ledger.sqlite")
    source.db.backup(db)
    db.execute("create temp table selected(id text primary key)")
    db.executemany("insert into selected values(?)", [(x,) for x in selected])
    pending_calls = db.execute("select id from calls where episode in (select id from selected) and completed!=1").fetchall()
    if pending_calls:
        raise RuntimeError(f"Cannot freeze episodes with pending provider replies: {pending_calls}")
    db.execute("delete from calls where episode not in (select id from selected) or completed!=1")
    db.execute("delete from metadata where key in ('first_balance','balance_at_start')")
    db.commit()
    pending = set()
    for request, response, wire, artifacts in db.execute("select request,response,wire,artifacts from calls"):
        pending.update([(request, True), (response, True), (wire, False), (artifacts, True)])
        pending.update((ref, False) for ref in source.get(artifacts).values())
    for ident in selected:
        folder = args.run / "episodes" / ident
        final = json.loads((folder / "completed.json").read_text())["final_snapshot"]
        pending.add((final, True))
        pending.update((ref, False) for ref in source.get(final).values())
        copy_tree(folder, run / "episodes" / ident)
        copy_tree(args.audits / ident, args.output / "audits" / ident)
        for attachment in folder.glob("*/home/.dsh/attachments/v1/objects/**/*"):
            if attachment.is_file():
                pending.add((attachment.name, False))
    for path in (args.run / "annotations").glob("*.json"):
        number = int(path.stem)
        if db.execute("select 1 from calls where id=?", (number,)).fetchone():
            (run / "annotations").mkdir(exist_ok=True)
            shutil.copy2(path, run / "annotations" / path.name)
    for path in args.run.parent.glob("main*.log"):
        shutil.copy2(path, args.output / path.name)
    objects = archive / "objects"
    for number in range(256):
        (objects / f"{number:02x}").mkdir(parents=True)
    seen, manifests = set(), {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool, (args.output / "objects.jsonl").open("w") as manifest:
        while pending:
            batch = list(pending)[:4096]
            pending.difference_update(batch)
            seen.update(batch)
            results = pool.map(lambda job: copy_object(job, source.objects, objects), batch)
            for digest, children, record in results:
                pending.update(child for child in children if child not in seen)
                if digest not in manifests:
                    manifests[digest] = record
                    manifest.write(json.dumps(record) + "\n")
            manifest.flush()
            save(args.output / "progress.json", {"at": time.time(), "objects": len(manifests),
                 "pending_nodes": len(pending), "stored_bytes": sum(x["stored_bytes"] for x in manifests.values())})
    db.execute("create temp table retained(id text primary key)")
    db.executemany("insert into retained values(?)", [(x,) for x in manifests])
    db.execute("delete from objects where id not in (select id from retained)")
    db.commit()
    db.execute("vacuum")
    db.execute("pragma journal_mode=delete")
    db.close()
    copy_tree(args.source, args.output / "code")
    environment = args.output / "environment"
    environment.mkdir()
    pins = sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions() if d.metadata.get("Name")})
    (environment / "controller-requirements.txt").write_text("\n".join(pins) + "\n")
    renderer_python = args.renderer / "venv/bin/python"
    code = "import importlib.metadata as m;print('\\n'.join(sorted({d.metadata['Name']+'=='+d.version for d in m.distributions() if d.metadata.get('Name')})))"
    (environment / "renderer-requirements.txt").write_bytes(subprocess.check_output([str(renderer_python), "-c", code]))
    assets = [args.runtime / "node/bin/node", args.renderer / "draw.war",
              args.renderer / "chrome-linux64/chrome",
              args.runtime / "dsh/node_modules/@deepseek-ai/dsh/package.json"]
    asset_pins = [{"path": str(p), "sha256": sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in assets]
    for name in ("package.json", "package-lock.json"):
        path = args.runtime / "dsh" / name
        if path.is_file():
            shutil.copy2(path, environment / ("dsh-" + name))
    copy_tree(args.processor, environment / "qwen-processor")
    save(environment / "contract.json", {"python": sys.version, "platform": platform.platform(),
         "architecture": platform.machine(), "live_rollout_backend": "Linux bubblewrap network and filesystem namespaces",
         "apple_silicon_live_rollout_validated": False, "source_commit": args.source_commit,
         "node_version": subprocess.check_output([str(args.runtime / "node/bin/node"), "--version"], text=True).strip(),
         "dsh_version": json.loads(assets[-1].read_text())["version"], "runtime_asset_pins": asset_pins,
         "pins_scope": "Installed controller Python distributions; no wheels, model weights or credentials"})
    counts = refresh(run, args.output / "audits", run / "sft-all-decisions.jsonl", args.source_commit)["counts"]
    files = []
    for path in args.output.rglob("*"):
        if path.is_file() and "objects" not in path.relative_to(args.output).parts:
            files.append({"file": str(path.relative_to(args.output)), "sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size})
    save(args.output / "files.json", files)
    result = {"at": time.time(), "source_commit": args.source_commit, "episodes": selected,
              "objects": len(manifests), "stored_object_bytes": sum(x["stored_bytes"] for x in manifests.values()),
              "counts": counts, "model_calls": 0, "upload_performed": False,
              "fidelity_verified": False, "original_archive": str(args.run),
              "objects_manifest_sha256": sha256((args.output / "objects.jsonl").read_bytes()).hexdigest(),
              "files_manifest_sha256": sha256((args.output / "files.json").read_bytes()).hexdigest()}
    save(args.output / "snapshot.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "episodes"}), flush=True)


def replay(args):
    manifest = json.loads((args.snapshot / "snapshot.json").read_text())
    episode = args.episode or manifest["episodes"][0]
    if episode not in manifest["episodes"]:
        raise ValueError("Episode is outside this snapshot")
    args.output.mkdir(parents=True)
    run = args.output / "run-01"
    run.mkdir()
    for name in ("archive", "episodes"):
        (run / name).symlink_to((args.snapshot / "run-01" / name).resolve())
    copy_tree(args.snapshot / "run-01/annotations", run / "annotations")
    for path in args.snapshot.glob("main*.log"):
        shutil.copy2(path, args.output / path.name)
    result = verify(run, episode, args.snapshot / "environment/qwen-processor/chat_template.jinja")
    tools = result["tool_execution"][episode]
    results_accounted = tools.get("all_execution_results_accounted", tools["all_execution_results_present"])
    if not tools["all_model_tools_accounted"] or not results_accounted:
        raise ValueError("Offline replay has unmatched tools or results")
    net = Path("/proc/self/ns/net")
    result.update(episode=episode, model_calls=0, training_started=False,
                  network_namespace=str(net.readlink()) if net.is_symlink() else None)
    save(args.output / "replay.json", result)
    print(json.dumps({"episode": episode, "counts": result["counts"], "model_calls": 0,
                      "all_tools_accounted": True, "qwen_template": result["qwen_template"],
                      "network_namespace": result["network_namespace"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("build")
    for name in ("run", "audits", "source", "processor", "output", "runtime", "renderer"):
        freeze.add_argument("--" + name, type=Path, required=True)
    freeze.add_argument("--source-commit", required=True)
    freeze.add_argument("--workers", type=int, default=8)
    check = sub.add_parser("replay")
    check.add_argument("--snapshot", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--episode")
    args = parser.parse_args()
    build(args) if args.command == "build" else replay(args)


if __name__ == "__main__":
    main()
