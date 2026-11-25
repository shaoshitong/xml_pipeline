"""Stage more author PNGs after the frozen original-image export."""

import argparse
from collections import Counter
import fcntl
import json
from pathlib import Path
import re
import sqlite3
import sys

from PIL import Image

from export_original_pngs import (
    DATABASE, FINGERPRINT, GOLD, export, release_baselines, rows, source_paper, write_json,
)


PREFERRED = re.compile(
    r"flow.?chart|block.?diagram|system.?design|model.?structure|schematic|diagram|"
    r"arch(?:itecture)?[_-]?overview|process.?flow|method(?:ology)?|proposed.?approach",
    re.I,
)
RELATED = re.compile(r"approach|proposed|network|roadmap|processing|module|protocol|system|workflow", re.I)


def shortlist(db, original, excluded_papers):
    counts = Counter()
    candidates = []
    for source, in db.execute(
        "SELECT path FROM files WHERE status='checked' AND lower(substr(path,-4))='.png' ORDER BY path"
    ):
        if source in original:
            continue
        path = Path(source)
        preferred = PREFERRED.search(path.name) is not None
        if not preferred and not RELATED.search(path.name):
            continue
        paper = source_paper(path)
        if paper is None or paper in excluded_papers:
            counts["excluded_paper"] += 1
            continue
        try:
            with Image.open(path) as image:
                width, height = image.size
                if image.format != "PNG" or min(width, height) < 160 or max(width, height) < 600:
                    counts["small_or_not_png"] += 1
                    continue
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            counts["unreadable_header"] += 1
            continue
        candidates.append((not preferred, source))
        counts["preferred_name" if preferred else "related_name"] += 1
    return [source for _, source in sorted(candidates)], dict(counts)


def prepare(original, out):
    stats = json.loads((original / "progress.json").read_text())
    if stats["phase"] != "complete":
        raise ValueError("The original export must be complete before taking its dedup baseline")
    scanned = set((original / "shortlist.txt").read_text().splitlines())
    known = json.loads((original / "known-fingerprints.json").read_text())
    originals = [row for shard in stats["ready_shards"] for row in rows(original / shard / "manifest.jsonl")]
    if len(originals) != stats["screen_counts"]["accepted"]:
        raise ValueError("The original shard manifests do not match the export count")
    known["records"].extend((r["sha256"], r["decoded_pixel_sha256"], r["phash"]) for r in originals)
    gold = json.loads(GOLD.read_text())
    _, _, published_papers, _ = release_baselines()
    with sqlite3.connect(DATABASE.as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        db.execute("BEGIN")
        snapshot = db.execute("SELECT max(rowid) FROM files").fetchone()[0]
        marker_papers = {source_paper(Path(path)) for path, in db.execute(
            "SELECT path FROM files WHERE status='marker'"
        )}
        candidates, counts = shortlist(db, scanned, set(gold["paper_ids"]) | published_papers | marker_papers)

    (out / "shortlist.txt").write_text("".join(source + "\n" for source in candidates))
    write_json(out / "known-fingerprints.json", known)
    write_json(out / "plan.json", {
        "source_inventory": str(DATABASE), "max_inventory_rowid": snapshot,
        "baseline_manifest_images": len(originals), "baseline_candidate_paths": len(scanned),
        "preferred_filename_regex": PREFERRED.pattern, "related_filename_regex": RELATED.pattern,
        "min_short_side": 160, "min_long_side": 600, "shortlist_paths": len(candidates),
        "shortlist_papers": len({source_paper(Path(source)) for source in candidates}),
        "candidate_counts": counts,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    sys.path.insert(0, str(FINGERPRINT))
    from select_figures import fingerprint
    with (args.out / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if not (args.out / "plan.json").exists():
            prepare(args.original, args.out)
        export(args.out, 128, fingerprint)


if __name__ == "__main__":
    main()
