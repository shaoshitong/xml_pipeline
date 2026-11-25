"""Stage a deduplicated paper-figure release from cached originals and captions."""

import argparse
import fcntl
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

from export_original_pngs import DATABASE, FINGERPRINT, GOLD, export, release_baselines, rows, source_paper, write_json


OBVIOUS_RESULTS = re.compile(
    r"(?:^|[_. -])tab(?:le)?(?:[0-9]|[_. -]|$)|accuracy[_-]?curve|loss[_-]?curve|"
    r"scatter.?plot|box.?plot|violin.?plot|density.?plot|bar.?chart|line.?plot|"
    r"(?:^|[_. -])plots?(?:[0-9]|[_. -]|$)|histogram|confusion.?matrix|"
    r"combined[_-]?agg|ablation|benchmark[_-]?results",
    re.I,
)


def wait_for_indexes(named, caption):
    paths = (named / "progress.json", caption / "progress.json")
    while not all(
        p.is_file() and json.loads(p.read_text())["phase"] == "complete" for p in paths
    ):
        time.sleep(20)


def add_available(ordered, paths, excluded):
    for source in paths:
        path = Path(source)
        if source_paper(path) in excluded or OBVIOUS_RESULTS.search(path.stem):
            continue
        ordered.setdefault(source)


def prepare(original, named, caption, out, target):
    baseline = json.loads((original / "progress.json").read_text())
    known = json.loads((original / "known-fingerprints.json").read_text())
    sources = set((original / "shortlist.txt").read_text().splitlines())
    for shard in baseline["ready_shards"]:
        for row in rows(original / shard / "manifest.jsonl"):
            known["records"].append((row["sha256"], row["decoded_pixel_sha256"], row["phash"]))
    _, _, released, _ = release_baselines()
    gold = json.loads(GOLD.read_text())
    with sqlite3.connect(DATABASE.as_uri() + "?mode=ro", uri=True) as inventory:
        marker_papers = {
            source_paper(Path(path)) for path, in inventory.execute(
                "SELECT path FROM files WHERE status='marker'"
            )
        }
    excluded = {None} | set(gold["paper_ids"]) | released | marker_papers
    ordered = {}
    named_paths = (
        row["original_source_path"]
        for shard in sorted(named.glob("shard-*"))
        for row in rows(shard / "manifest.jsonl")
    )
    db_path = caption / "figures.sqlite"
    with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as figures:
        diagram = (p for p, in figures.execute("SELECT path FROM figures WHERE priority=0 ORDER BY path"))
        add_available(ordered, diagram, excluded)
        diagram_candidates = len(ordered)
        add_available(ordered, named_paths, excluded)
        preferred_candidates = len(ordered)
        general = (p for p, in figures.execute("SELECT path FROM figures WHERE priority=1 ORDER BY path"))
        add_available(ordered, general, excluded)
    candidates = [path for path in ordered if path not in sources]
    (out / "shortlist.txt").write_text("".join(path + "\n" for path in candidates))
    write_json(out / "known-fingerprints.json", known)
    write_json(out / "plan.json", {
        "baseline_images": baseline["screen_counts"]["accepted"], "target_new_images": target,
        "shortlist_paths": len(candidates), "diagram_caption_candidates": diagram_candidates,
        "preferred_candidates": preferred_candidates, "filename_filter": OBVIOUS_RESULTS.pattern,
        "caption_index": str(db_path),
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--named", type=Path, required=True)
    parser.add_argument("--caption", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target-total", type=int, default=100_000)
    args = parser.parse_args()
    baseline = json.loads((args.original / "progress.json").read_text())
    target = args.target_total - baseline["screen_counts"]["accepted"]
    if baseline["phase"] != "complete" or target < 1:
        parser.error("The original export must be complete and the new target must exceed it")

    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    sys.path.insert(0, str(FINGERPRINT))
    from select_figures import fingerprint
    with (args.out / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not (args.out / "plan.json").is_file():
            wait_for_indexes(args.named, args.caption)
            prepare(args.original, args.named, args.caption, args.out, target)
        export(args.out, 128, fingerprint, target=target, minimum_size=(160, 600))


if __name__ == "__main__":
    main()
