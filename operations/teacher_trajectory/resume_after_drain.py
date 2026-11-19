"""Resume the same budgeted archive after its previous collector drains."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

from audit_completed import collector_alive
from collect import save


def launch(root, receipt_name, argv, env, log_name):
    with (root / log_name).open("ab") as log:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   env=env, start_new_session=True)
    value = {"at": time.time(), "pid": process.pid,
             "startticks": Path(f"/proc/{process.pid}/stat").read_text().split()[21],
             "argv": argv, "log": str(root / log_name)}
    save(root / receipt_name, value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    coordinator = (root / "resume-after-drain.lock").open("a")
    fcntl.flock(coordinator, fcntl.LOCK_EX | fcntl.LOCK_NB)
    receipt = root / "main-launch.json"
    previous = json.loads(receipt.read_text())
    frozen = root / f"main-launch-{previous['pid']}-drained.json"
    save(frozen, previous)
    while collector_alive(frozen):
        save(root / "resume-after-drain-status.json", {"at": time.time(), "phase": "waiting_for_active_episodes",
             "previous_pid": previous["pid"], "source_commit": args.source_commit})
        time.sleep(5)
    if json.loads(receipt.read_text())["pid"] != previous["pid"]:
        raise RuntimeError("A different owner already replaced the collector receipt")
    argv = previous["argv"][:]
    run = Path(argv[argv.index("--root") + 1])
    lock = (run / "collector.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    db = sqlite3.connect("file:" + str(run / "archive/ledger.sqlite") + "?mode=ro", uri=True)
    if db.execute("select count(*) from calls where completed=0").fetchone()[0]:
        raise RuntimeError("Unfinished provider calls remain; inspect their journals before resuming")
    paid = {row[0] for row in db.execute("select distinct episode from calls where role='generator'")}
    failed = set()
    for path in (run / "episodes").glob("*/status.json"):
        value = json.loads(path.read_text())
        if value.get("error_type") and path.parent.name in paid and not (path.parent / "completed.json").exists():
            failed.add(path.parent.name)
    original = Path(argv[argv.index("--manifest") + 1])
    records = [json.loads(line) for line in original.read_text().splitlines() if line]
    records.sort(key=lambda row: row["id"] not in failed)
    manifest = root / "selection" / f"resume-{args.source_commit[:7]}.jsonl"
    manifest.write_text("".join(json.dumps(row) + "\n" for row in records))
    argv[2] = str(Path(__file__).with_name("collect.py"))
    argv[argv.index("--manifest") + 1] = str(manifest)
    argv[argv.index("--source-commit") + 1] = args.source_commit
    lock.close()
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false")
    current = launch(root, "main-launch.json", argv, env, f"main-resumed-{args.source_commit[:7]}.log")
    time.sleep(3)
    if not collector_alive(root / "main-launch.json"):
        raise RuntimeError("Resumed collector exited; inspect its log")
    audit_receipt = root / "audit-follower-launch.json"
    if not collector_alive(audit_receipt):
        old = json.loads(audit_receipt.read_text())
        save(root / f"audit-follower-launch-{old['pid']}-finished.json", old)
        audit_lock = (root / "episode-audits-v1/audit.lock").open("a")
        fcntl.flock(audit_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        audit_lock.close()
        audit_argv = old["argv"][:]
        audit_argv[2] = str(Path(__file__).with_name("audit_completed.py"))
        audit_argv[audit_argv.index("--source-commit") + 1] = args.source_commit
        launch(root, "audit-follower-launch.json", audit_argv, env, "audit-follower.log")
    status = {"at": time.time(), "phase": "resumed", "previous_pid": previous["pid"],
              "current": current, "prioritized_failed_episodes": sorted(failed),
              "same_archive_and_budget": True, "source_commit": args.source_commit}
    save(root / "resume-after-drain-status.json", status)
    save(root / "collector-drain-completion.json", status)
    print(json.dumps(status), flush=True)


if __name__ == "__main__":
    main()
