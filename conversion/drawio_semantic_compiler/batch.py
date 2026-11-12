"""Compile and natively accept every case of a manifest, restartable per case.

    batch.py MANIFEST --out RUN [--root CORPUS_ROOT] [--workers 14]
    batch.py VARIANTS --out RUN --bases SAMPLE [--workers 14]

Each manifest line is a JSON object with an ``id`` and either ``code_file``
(relative to --root, with ``code_sha256``) or ``xml`` (an absolute path).

A variant is a rewrite of a compiled case that claims to mean the same. Its
line may name the case in ``case`` (default: its ``id``); --bases is the sample
manifest that maps each case to its ``canonical.drawio``. A variant is accepted
when it differs from that base, compiles back to the base byte for byte, keeps
every cell ID the editor observes, and paints and edits like the base in the
pinned editor.

Every worker owns one pinned draw.io editor and reuses it across cases. A case
writes ``RUN/cases/<id>/`` atomically, ending with ``status.json``. A restart
skips the cases whose status was produced from the same input bytes by the
same compiler and verifier sources. ``RUN/RUNNING`` exists while the batch
runs, ``RUN/progress.json`` is rewritten as it advances and ``RUN/EXIT.json``
is written when it stops, whatever the reason.
"""

import argparse
from collections import deque
from hashlib import sha256
import json
import multiprocessing
from multiprocessing.connection import wait
import os
from pathlib import Path
import shutil
import signal
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from cli import OUTPUT, write_outputs  # noqa: E402
from compiler import COMPILER_VERSION, compile_bytes, dump  # noqa: E402
from source import CompileError  # noqa: E402

STATUS_SCHEMA = "drawio-semantic-batch-status/1"
ACCEPTED, REJECTED, COMPILE_ERROR, ERROR = "accepted", "rejected", "compile_error", "error"
STATES = (ACCEPTED, REJECTED, COMPILE_ERROR, ERROR)
RECYCLE = 150            # cases served by one browser before it is replaced
BASE_TIMEOUT = 420       # seconds for one case, plus PER_MB for large inputs
PER_MB = 30


def source_digest():
    """Identifies the compiler and verifier that produced a status."""
    digest = sha256()
    for path in sorted(HERE.glob("*.py")) + sorted(HERE.glob("*.js")):
        if not path.name.startswith("test_") and path.name != "controls.py":
            digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def write_json(path, value):
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(dump(value))
    partial.replace(path)


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def load_tasks(manifest, root, bases=None):
    tasks, seen = [], set()
    if bases is not None:
        rows = [json.loads(line) for line in bases.read_text().splitlines() if line.strip()]
        bases = {row["id"]: row["xml"] for row in rows}
    for number, line in enumerate(manifest.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        case = row["id"]
        if case in seen or "/" in case or case.startswith("."):
            raise ValueError(f"{manifest}:{number}: duplicate or unusable case ID {case!r}")
        seen.add(case)
        if "xml" in row:
            source = Path(row["xml"])
        elif root is not None:
            source = root / row["code_file"]
        else:
            raise ValueError(f"{manifest}:{number}: code_file needs --root")
        base = None
        if bases is not None:
            base = bases.get(row.get("case", case))
            if base is None:
                raise ValueError(f"{manifest}:{number}: no base for case {row.get('case', case)!r}")
        tasks.append({"id": case, "source": str(source), "sha256": row.get("code_sha256"), "base": base})
    return tasks


def file_sha256(path):
    digest = sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def fresh(status, task, sources):
    """Whether a stored status still answers for this task."""
    if not status or status.get("schema") != STATUS_SCHEMA or status.get("sources_sha256") != sources:
        return False
    expected = task["sha256"] or file_sha256(task["source"])
    if status.get("input_sha256") != expected or status.get("base") != task["base"]:
        return False
    if task["base"] is not None and status.get("base_sha256") != file_sha256(task["base"]):
        return False
    return status.get("state") in STATES


# ---------------------------------------------------------------- one case

def observed_ids(source_map):
    """The cell names the editor observes, per page."""
    return [sorted((cell["id"], cell["id_roles"]) for cell in page["cells"]
                   if cell.get("id_roles") and "folded_into" not in cell) for page in source_map["pages"]]


def measure_perturbation(result, base):
    """What a variant actually changed relative to its canonical base."""
    pages = result.source_map["pages"]
    cells = [cell for page in pages for cell in page["cells"]]
    kept = [cell for cell in cells if "folded_into" not in cell]
    order = [cell["draw_index"] for page in pages for cell in page["cells"]]
    rules = {}
    for entry in result.report["rules_applied"] + result.report["representation_changes"]:
        rules[entry["rule"]] = rules.get(entry["rule"], 0) + entry["count"]
    return {"source_cells": len(cells), "renamed_ids": sum(cell["original_id"] != cell["id"] for cell in kept),
            "kept_observed_ids": sum(bool(cell.get("id_roles")) for cell in kept),
            "folded_frames": len(cells) - len(kept),
            "records_out_of_draw_order": any(a > b for a, b in zip(order, order[1:])),
            "rules": rules, "base_bytes": len(base)}


def run_case(runtime, task, cases, sources, worker):
    """Compile and verify one case into ``cases/<id>``; returns its status."""
    from native_verify import verify_documents
    started = time.time()
    data = Path(task["source"]).read_bytes()
    status = {"schema": STATUS_SCHEMA, "id": task["id"], "source": task["source"],
              "input_sha256": sha256(data).hexdigest(), "input_bytes": len(data), "base": task["base"],
              "compiler": COMPILER_VERSION, "sources_sha256": sources, "worker": worker, "checks": {}}
    checks = status["checks"]
    checks["input_matches_manifest"] = task["sha256"] in (None, status["input_sha256"])
    staging = cases / f".staging-{worker}-{task['id']}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        result = None
        if checks["input_matches_manifest"]:
            try:
                result = compile_bytes(data)
            except CompileError as error:
                status["state"] = COMPILE_ERROR
                status["diagnostics"] = [d.to_json() for d in error.diagnostics][:50]
        if result is not None:
            write_outputs(staging, result)
            checks.update(result.report["checks"])
            status.update(output_sha256=result.report["output"]["sha256"], output_bytes=len(result.xml),
                          ir_sha256=result.report["ir_sha256"], pages=result.report["pages"],
                          warnings=sum(d["severity"] == "warning" for d in result.report["diagnostics"]))
            base = None
            if task["base"] is not None:
                base = Path(task["base"]).read_bytes()
                status["base_sha256"] = sha256(base).hexdigest()
                checks["converges_to_base_bytes"] = result.xml == base
                checks["differs_from_base"] = data != base
                # The base is this compiler's own output; recompiling it gives its IR and names.
                compiled_base = compile_bytes(base)
                checks["base_is_canonical"] = compiled_base.xml == base
                checks["converges_to_base_ir"] = dump(compiled_base.ir_json) == dump(result.ir_json)
                checks["keeps_observed_ids"] = observed_ids(compiled_base.source_map) == observed_ids(result.source_map)
                checks["same_page_count"] = compiled_base.report["pages"] == result.report["pages"]
                status["perturbation"] = measure_perturbation(result, base)
        if result is not None and checks.get("same_page_count", True):
            # A variant is opened against its base, so one that does not
            # converge still gets the editor's verdict on what it changed.
            native = verify_documents(runtime, data, result, staging, target=base)
            (staging / "native.json").write_bytes(dump(native))
            pages = native["pages"]
            checks.update(native_model_equal=all(p["model_equal"] for p in pages),
                          native_pixels_equal=all(p["pixel_equal"] for p in pages),
                          native_edits_equal=all(p["edit"]["equal"] is True for p in pages),
                          native_assets_equal=all(p["unresolved_assets"]["original"]
                                                  == p["unresolved_assets"]["compiled"] for p in pages))
            status.update(cells=sum(p["cells"] for p in pages), edit_probes=sum(p["edit"]["probes"] for p in pages),
                          inert_edit_probes=sum(p["edit"]["inert"] for p in pages),
                          sketch_seeded_cells=sum(p["sketch_seeded_cells"] for p in pages),
                          assets_resolved=native["assets_resolved"],
                          original_pixel_sha256=[p["original_pixel_sha256"] for p in pages],
                          compiled_pixel_sha256=[p["compiled_pixel_sha256"] for p in pages],
                          runtime=native["runtime"])
        if "state" not in status:
            status["state"] = ACCEPTED if all(checks.values()) else REJECTED
        status.update(seconds=round(time.time() - started, 3), finished_at=now())
        write_json(staging / "status.json", status)
        target = cases / task["id"]
        shutil.rmtree(target, ignore_errors=True)
        staging.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return status


def worker_main(connection, worker, cases, sources):
    os.setsid()
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    from native_verify import open_runtime
    runtime, served = None, 0

    def close():
        nonlocal runtime, served
        if runtime is not None:
            try:
                runtime.__exit__(None, None, None)
            except Exception:
                pass
        runtime, served = None, 0

    while True:
        task = connection.recv()
        if task is None:
            break
        try:
            if served >= RECYCLE:
                close()
            if runtime is None:
                runtime = open_runtime().__enter__()
            served += 1
            status = run_case(runtime, task, Path(cases), sources, worker)
            reply = {key: status.get(key) for key in ("id", "state", "seconds", "checks")}
        except Exception as error:
            close()
            reply = {"id": task["id"], "state": ERROR, "error": f"{type(error).__name__}: {error}"[:2000],
                     "traceback": traceback.format_exc()[-6000:]}
        connection.send(reply)
    close()


# ---------------------------------------------------------------- the batch

def descendants(pid):
    """PIDs below ``pid`` in the process tree, read from /proc."""
    parents = {}
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                with open(f"/proc/{entry}/stat") as handle:
                    parents[int(entry)] = int(handle.read().rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                pass
    found, frontier = [], [pid]
    while frontier:
        parent = frontier.pop()
        children = [child for child, owner in parents.items() if owner == parent]
        found.extend(children)
        frontier.extend(children)
    return found


class Worker:
    def __init__(self, number, cases, sources):
        self.number = number
        self.connection, child = multiprocessing.Pipe()
        self.process = multiprocessing.Process(target=worker_main, args=(child, number, str(cases), sources))
        self.process.start()
        child.close()
        self.task = None
        self.started = None

    def assign(self, task):
        self.task, self.started = task, time.time()
        self.connection.send(task)

    def kill(self):
        pids = descendants(self.process.pid) + [self.process.pid]
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        self.process.join(10)
        self.connection.close()

    def stop(self):
        try:
            self.connection.send(None)
            self.process.join(30)
        except OSError:
            pass
        if self.process.is_alive():
            self.kill()


def record_failure(cases, task, sources, message, attempts, detail=None):
    """A status for a case whose worker failed, timed out or died."""
    target = cases / task["id"]
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir()
    status = {"schema": STATUS_SCHEMA, "id": task["id"], "source": task["source"],
              "input_sha256": task["sha256"] or file_sha256(task["source"]), "base": task["base"],
              "compiler": COMPILER_VERSION, "sources_sha256": sources, "state": ERROR, "error": message,
              "attempts": attempts, "checks": {}, "finished_at": now()}
    if task["base"] is not None:
        status["base_sha256"] = file_sha256(task["base"])
    if detail:
        status["traceback"] = detail
    write_json(target / "status.json", status)


def summarize(tasks, cases, sources):
    """Close the manifest against the stored statuses."""
    counts = {state: 0 for state in STATES}
    counts.update(missing=0, stale=0)
    totals = {"pages": 0, "cells": 0, "edit_probes": 0, "inert_edit_probes": 0, "input_bytes": 0, "output_bytes": 0,
              "sketch_seeded_cells": 0, "cases_with_sketch_seeded_cells": 0, "cases_with_unresolved_assets": 0}
    failed_checks, open_cases = {}, []
    for task in tasks:
        status = read_json(cases / task["id"] / "status.json")
        if status is None:
            counts["missing"] += 1
            open_cases.append({"id": task["id"], "state": "missing"})
            continue
        if not fresh(status, task, sources):
            counts["stale"] += 1
            open_cases.append({"id": task["id"], "state": "stale"})
            continue
        counts[status["state"]] += 1
        for key in ("pages", "cells", "edit_probes", "inert_edit_probes", "input_bytes", "output_bytes",
                    "sketch_seeded_cells"):
            totals[key] += status.get(key) or 0
        totals["cases_with_sketch_seeded_cells"] += bool(status.get("sketch_seeded_cells"))
        totals["cases_with_unresolved_assets"] += status.get("assets_resolved") is False
        if status["state"] != ACCEPTED:
            failed = sorted(key for key, value in status["checks"].items() if not value)
            for key in failed or [status["state"]]:
                failed_checks[key] = failed_checks.get(key, 0) + 1
            open_cases.append({"id": task["id"], "state": status["state"], "failed_checks": failed,
                               "error": status.get("error")})
    return {"schema": "drawio-semantic-batch-summary/1", "compiler": COMPILER_VERSION, "sources_sha256": sources,
            "manifest_cases": len(tasks), "states": counts, "totals": totals, "failed_checks": failed_checks,
            "open_cases": open_cases, "all_accepted": counts[ACCEPTED] == len(tasks), "written_at": now()}


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="run directory")
    parser.add_argument("--root", type=Path, help="directory that code_file paths are relative to")
    parser.add_argument("--bases", type=Path, help="sample manifest of the canonical files the variants must equal")
    parser.add_argument("--workers", type=int, default=14)
    parser.add_argument("--limit", type=int, help="only the first N manifest cases")
    parser.add_argument("--only", type=Path, help="file of case IDs to restrict the run to")
    parser.add_argument("--max-attempts", type=int, default=2, help="tries for a case whose worker failed")
    parser.add_argument("--retry-rejected", action="store_true", help="also redo rejected and uncompilable cases")
    parser.add_argument("--summarize", action="store_true", help="only close the manifest against stored statuses")
    args = parser.parse_args(argv)

    run = args.out.resolve()
    cases = run / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    sources = source_digest()
    tasks = load_tasks(args.manifest, args.root, args.bases)
    if args.only is not None:
        wanted = set(args.only.read_text().split())
        tasks = [task for task in tasks if task["id"] in wanted]
    if args.limit is not None:
        tasks = tasks[:args.limit]
    if args.summarize:
        summary = summarize(tasks, cases, sources)
        write_json(run / "summary.json", summary)
        print(json.dumps({key: summary[key] for key in ("manifest_cases", "states", "totals", "failed_checks",
                                                        "all_accepted")}, ensure_ascii=False))
        return 0 if summary["all_accepted"] else 1

    marker = run / "RUNNING"
    previous = read_json(marker)
    if previous and alive(previous.get("pid", -1)):
        print(f"batch.py: run directory is in use by PID {previous['pid']}", file=sys.stderr)
        return 2
    (run / "EXIT.json").unlink(missing_ok=True)
    started = now()
    write_json(marker, {"pid": os.getpid(), "started_at": started, "argv": sys.argv, "sources_sha256": sources})

    counts = {state: 0 for state in STATES}
    resumed, attempts, pending = 0, {}, deque()
    redo = {ERROR} | ({REJECTED, COMPILE_ERROR} if args.retry_rejected else set())
    for task in tasks:
        status = read_json(cases / task["id"] / "status.json")
        if fresh(status, task, sources) and status["state"] not in redo:
            counts[status["state"]] += 1
            resumed += 1
        else:
            pending.append(task)
    total, todo = len(tasks), len(pending)
    stop = {"signal": None}
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, lambda received, frame: stop.update(signal=received))

    def progress(state):
        write_json(run / "progress.json", {
            "state": state, "pid": os.getpid(), "started_at": started, "updated_at": now(),
            "manifest_cases": total, "resumed_from_earlier_runs": resumed, "to_do_this_run": todo,
            "finished_this_run": finished, "pending": len(pending), "states": counts,
            "running": {str(w.number): {"id": w.task["id"], "seconds": round(time.time() - w.started)}
                        for w in workers if w.task is not None},
            "workers": len(workers), "sources_sha256": sources, "compiler": COMPILER_VERSION})

    def log(text):
        print(f"{now()} {text}", flush=True)

    events = open(run / "events.jsonl", "a")
    workers, finished, written, code = [], 0, 0.0, 1
    log(f"start pid={os.getpid()} cases={total} resumed={resumed} todo={todo} workers={args.workers} "
        f"sources={sources[:16]} compiler={COMPILER_VERSION}")
    try:
        workers = [Worker(number, cases, sources) for number in range(min(args.workers, max(1, todo)))]

        def settle(worker, reply):
            nonlocal finished
            task = worker.task
            worker.task = None
            if reply["state"] == ERROR:
                attempts[task["id"]] = attempts.get(task["id"], 0) + 1
                record_failure(cases, task, sources, reply["error"], attempts[task["id"]], reply.get("traceback"))
                if attempts[task["id"]] < args.max_attempts:
                    pending.append(task)
                    log(f"retry later {task['id']} {reply['error'][:300]}")
                    return
            finished += 1
            counts[reply["state"]] += 1
            failed = sorted(key for key, value in (reply.get("checks") or {}).items() if not value)
            events.write(json.dumps({"at": now(), "id": task["id"], "state": reply["state"],
                                     "seconds": reply.get("seconds"), "failed_checks": failed,
                                     "error": reply.get("error"), "worker": worker.number}) + "\n")
            events.flush()
            log(f"[{finished}/{todo}] {reply['state']} {task['id']} {reply.get('seconds')}s w{worker.number}"
                + (f" failed={failed}" if failed else "") + (f" error={reply['error'][:300]}" if reply.get("error") else ""))

        while stop["signal"] is None and (pending or any(w.task is not None for w in workers)):
            for worker in workers:
                if worker.task is None and pending:
                    worker.assign(pending.popleft())
            busy = {w.connection: w for w in workers if w.task is not None}
            for connection in wait(list(busy), timeout=5):
                worker = busy[connection]
                try:
                    reply = connection.recv()
                except (EOFError, OSError):
                    reply = {"state": ERROR, "error": f"worker died (exit code {worker.process.exitcode})"}
                    worker.kill()
                    workers[workers.index(worker)] = replacement = Worker(worker.number, cases, sources)
                    replacement.task = worker.task
                    worker = replacement
                settle(worker, reply)
            for index, worker in enumerate(workers):
                if worker.task is None:
                    continue
                size = os.path.getsize(worker.task["source"]) / 1e6
                if time.time() - worker.started > BASE_TIMEOUT + PER_MB * size:
                    worker.kill()
                    workers[index] = replacement = Worker(worker.number, cases, sources)
                    replacement.task = worker.task
                    settle(replacement, {"state": ERROR, "error":
                                         f"timed out after {round(time.time() - worker.started)} s"})
            if time.time() - written > 15:
                progress("running")
                written = time.time()
        interrupted = stop["signal"] is not None
        summary = summarize(tasks, cases, sources)
        write_json(run / "summary.json", summary)
        code = 128 + stop["signal"] if interrupted else 0 if summary["all_accepted"] else 1
    except BaseException:
        log("batch failed:\n" + traceback.format_exc())
        code = 3
        raise
    finally:
        for worker in workers:
            if worker.task is not None or code == 3:
                worker.kill()
            else:
                worker.stop()
        final = "interrupted" if stop["signal"] is not None else "failed" if code == 3 else "finished"
        progress(final)
        write_json(run / "EXIT.json", {"exit_code": code, "state": final, "signal": stop["signal"],
                                       "started_at": started, "finished_at": now(), "manifest_cases": total,
                                       "states": counts, "finished_this_run": finished,
                                       "all_accepted": code == 0, "sources_sha256": sources})
        marker.unlink(missing_ok=True)
        events.close()
        log(f"exit code={code} state={final} states={counts}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
