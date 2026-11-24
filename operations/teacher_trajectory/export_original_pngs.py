"""Stage the frozen HKUST author-PNG shortlist with one dedup state across shards."""

import argparse
from collections import Counter, defaultdict
import fcntl
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time

from PIL import Image


ROOT = Path("/backup/shaoshitong/img2code_20261029")
ARXIV = ROOT / "clean/arxiv_research_figures_v1"
TEACHER = ROOT / "evaluation/arxiv_teacher_trajectory_20261120"
PAPERS = ARXIV / "recent_ai_source_expansion_v2/papers"
DATABASE = ARXIV / "embedded_XML_image_inventory_incremental_v3/files.sqlite"
GOLD = TEACHER / "reference-inputs-20261121/private-audit/exclusions.json"
FINGERPRINT = TEACHER / "source-snapshots/74be8f7/operations/teacher_trajectory"
RELEASES = (
    "hf-publication-200/episodes.jsonl",
    "reference-inputs-full-20261121/public/manifest.jsonl",
    "meanflow-reference-supplement-final-20261121/public/manifest.jsonl",
)
NAME = re.compile(r"framework|architecture|pipeline|overview|workflow|system[_-]?model", re.I)
ARXIV_ID = re.compile(r"(?<!\d)\d{4}\.\d{4,5}")
ROW_LIMIT = 838218
EXPECTED_SHORTLIST = 13934


def rows(path):
    with path.open() as stream:
        yield from map(json.loads, stream)


def paper_id(value):
    match = ARXIV_ID.search(str(value))
    return match[0] if match else None


def source_paper(path):
    return paper_id(path.relative_to(PAPERS).parts[0]) if path.is_relative_to(PAPERS) else None


def write_json(path, value):
    staging = path.with_suffix(".tmp")
    staging.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    staging.replace(path)


def release_baselines():
    historic = {row["id"]: row for folder in ("selection", "selection-batch2", "selection-batch3")
                for row in rows(TEACHER / folder / "candidates.jsonl")}
    fingerprints, missing, papers, sizes = [], [], set(), {}
    for release in RELEASES:
        entries = list(rows(TEACHER / release))
        sizes[release] = len(entries)
        for row in entries:
            key = row.get("case_id") or row.get("episode")
            legacy = historic.get(key, {})
            source = row if row.get("phash") is not None else legacy
            ident = paper_id(row.get("paper_id") or row.get("paper") or row.get("arxiv_url")
                             or legacy.get("paper_id") or row.get("reference_record"))
            papers.add(ident)
            hashes = (source.get("sha256") or source.get("reference_sha256"),
                      source.get("decoded_pixel_sha256") or source.get("reference_pixels_sha256"),
                      source.get("phash"))
            if not all(hashes):
                missing.append({"release": release, "case_id": key, "paper_id": ident,
                                "missing": [name for name, value in zip(("sha256", "decoded_pixel_sha256", "phash"), hashes)
                                            if not value]})
            fingerprints.append(hashes)
    if None in papers or len(papers) != 1000 or sum(sizes.values()) != 1000:
        raise ValueError("The three releases must represent exactly 1,000 distinct papers")
    return fingerprints, missing, papers, sizes


def freeze(out):
    gold = json.loads(GOLD.read_text())
    if len(gold["gold_images"]) != 10250 or gold["gold_image_read_failures"]:
        raise ValueError("The verified full gold image fingerprint index is required")
    released, missing, published, sizes = release_baselines()
    references = [(row["sha256"], row["pixel_sha256"], row["phash"]) for row in gold["gold_images"]]
    references.extend(released)
    gold_papers = set(gold["paper_ids"])
    counts = Counter()
    keep = []
    with sqlite3.connect(DATABASE.as_uri() + "?mode=ro", uri=True) as db:
        marker_papers = {source_paper(Path(path)) for path, in db.execute(
            "SELECT path FROM files WHERE rowid <= ? AND status='marker'", (ROW_LIMIT,))}
        for source, in db.execute(
            "SELECT path FROM files WHERE rowid <= ? AND status='checked' AND lower(substr(path,-4))='.png' ORDER BY path",
            (ROW_LIMIT,)):
            path = Path(source)
            if not NAME.search(path.name):
                continue
            ident = source_paper(path)
            if ident is None:
                counts["invalid_paper_id"] += 1
            elif ident in gold_papers:
                counts["gold_paper"] += 1
            elif ident in published:
                counts["released_paper"] += 1
            elif ident in marker_papers:
                counts["known_marker_paper"] += 1
            else:
                keep.append(source)
    if len(keep) != EXPECTED_SHORTLIST:
        raise ValueError(f"Frozen shortlist differs from the verified 13,934 paths: {len(keep)}")
    (out / "shortlist.txt").write_text("\n".join(keep) + "\n")
    write_json(out / "known-fingerprints.json", {"records": references, "gold_byte_hashes": gold["image_sha256"]})
    write_json(out / "plan.json", {
        "inventory": str(DATABASE), "max_inventory_rowid": ROW_LIMIT, "filename_regex": NAME.pattern,
        "shortlist_paths": len(keep), "shortlist_papers": len({source_paper(Path(s)) for s in keep}),
        "pre_shortlist_exclusions": dict(counts), "gold_images": len(gold["gold_images"]),
        "gold_papers": len(gold_papers), "released_papers": len(published),
        "releases": sizes, "missing_release_fingerprints": missing, "hamming_threshold": 7,
    })


class Dedup:
    def __init__(self, known):
        self.raw, self.pixels = set(known["gold_byte_hashes"]), set()
        self.bands = [defaultdict(set) for _ in range(8)]
        for raw, pixel, phash in known["records"]:
            self.add(raw, pixel, phash)

    def add(self, raw, pixels, phash):
        if raw:
            self.raw.add(raw)
        if pixels:
            self.pixels.add(pixels)
        if phash is not None:
            value = int(phash)
            for index, band in enumerate(self.bands):
                band[(value >> (8 * index)) & 255].add(value)

    def nearby(self, value):
        # At Hamming distance <= 7, at least one of the eight bytes is equal.
        return any((value ^ other).bit_count() <= 7 for index, band in enumerate(self.bands)
                   for other in band.get((value >> (8 * index)) & 255, ()))


@lru_cache(maxsize=256)
def provenance(paper_dir):
    path = paper_dir / "provenance.json"
    if not path.is_file():
        return None, {}
    try:
        return str(path), json.loads(path.read_text())
    except (OSError, ValueError):
        return None, {}


def screen(path, dedup, fingerprint):
    try:
        raw = path.read_bytes()
        digest = sha256(raw).hexdigest()
        if digest in dedup.raw:
            return "duplicate_png_sha256", None
        with Image.open(BytesIO(raw)) as source:
            if source.format != "PNG":
                return "not_png", None
            image = source.convert("RGB")
            if any(str(k).casefold() in {"mxfile", "mxgraphmodel", "drawio"} for k in source.info):
                return "embedded_xml_found", None
        pixels = sha256(image.tobytes()).hexdigest()
        if pixels in dedup.pixels:
            return "duplicate_rgb_sha256", None
        phash = fingerprint(image)
        if dedup.nearby(phash):
            return "near_duplicate_phash", None
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return "unreadable_or_undecodable", None
    paper_dir = PAPERS / path.relative_to(PAPERS).parts[0]
    prov_path, metadata = provenance(paper_dir)
    ident = source_paper(path)
    case = "hkust-" + digest[:24]
    row = {"case_id": case, "file": "images/" + case + ".png", "sha256": digest,
           "decoded_pixel_sha256": pixels, "phash": str(phash), "size": list(image.size),
           "paper_id": ident, "arxiv_url": metadata.get("abs_url") or "https://arxiv.org/abs/" + paper_dir.name,
           "original_source_path": str(path), "provenance_path": prov_path,
           "license_urls": metadata.get("license_urls", []), "title": metadata.get("title"),
           "categories": metadata.get("categories", []), "publication_date": metadata.get("publication_date")}
    dedup.add(digest, pixels, phash)
    return "accepted", (row, raw)


def export(out, shard_size, fingerprint):
    if not (out / "plan.json").is_file():
        freeze(out)
    plan = json.loads((out / "plan.json").read_text())
    known = json.loads((out / "known-fingerprints.json").read_text())
    dedup = Dedup(known)
    counts, consumed, batches, total_bytes = Counter(), 0, [], 0
    for shard in sorted(out.glob("shard-*")):
        receipt = json.loads((shard / "receipt.json").read_text())
        for row in rows(shard / "manifest.jsonl"):
            dedup.add(row["sha256"], row["decoded_pixel_sha256"], row["phash"])
        consumed, counts = receipt["shortlist_processed"], Counter(receipt["screen_counts"])
        total_bytes += receipt["png_bytes"]
        batches.append(shard.name)
    inputs = (out / "shortlist.txt").read_text().splitlines()
    stage, entries, data_bytes = None, [], 0
    status = {"phase": "screening", **plan}
    for index, source in enumerate(inputs[consumed:], consumed + 1):
        result, item = screen(Path(source), dedup, fingerprint)
        counts[result] += 1
        if item:
            if stage is None:
                stage = Path(tempfile.mkdtemp(prefix=".building-", dir=out))
                (stage / "images").mkdir()
            row, raw = item
            (stage / row["file"]).write_bytes(raw)
            entries.append(row)
            data_bytes += len(raw)
        if stage and (len(entries) == shard_size or index == len(inputs)):
            shard = out / f"shard-{len(batches) + 1:05d}"
            manifest = stage / "manifest.jsonl"
            manifest.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in entries))
            receipt = {"images": len(entries), "png_bytes": data_bytes, "manifest_bytes": manifest.stat().st_size,
                       "manifest_sha256": sha256(manifest.read_bytes()).hexdigest(),
                       "shortlist_processed": index, "screen_counts": dict(counts)}
            write_json(stage / "receipt.json", receipt)
            stage.rename(shard)
            batches.append(shard.name)
            total_bytes += data_bytes
            print(json.dumps({"shard": str(shard), **receipt}), flush=True)
            stage, entries, data_bytes = None, [], 0
        if index % 128 == 0 or index == len(inputs):
            write_json(out / "progress.json", {**status, "shortlist_processed": index,
                "screen_counts": dict(counts), "ready_shards": batches, "committed_png_bytes": total_bytes})
    write_json(out / "progress.json", {**status, "phase": "complete", "shortlist_processed": len(inputs),
        "screen_counts": dict(counts), "ready_shards": batches, "committed_png_bytes": total_bytes, "finished_at": time.time()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shard-size", type=int, default=128)
    args = parser.parse_args()
    if args.shard_size < 1:
        parser.error("Shard size must be positive")
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    sys.path.insert(0, str(FINGERPRINT))
    from select_figures import fingerprint

    with (args.out / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        export(args.out, args.shard_size, fingerprint)


if __name__ == "__main__":
    main()
