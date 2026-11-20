"""Release unused candidate reference PNGs without teacher outputs or gold XML."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import time

from PIL import Image

from select_figures import exclusions, fingerprint, records, source_context


def image_record(path):
    raw = path.read_bytes()
    with Image.open(path) as source:
        assert not any("drawio" in key.lower() or "mxfile" in str(value).lower()
                       for key, value in source.info.items())
        image = source.convert("RGB")
    return raw, image, sha256(raw).hexdigest(), sha256(image.tobytes()).hexdigest(), fingerprint(image)


def release(args):
    args.out.mkdir(parents=True)
    audit = args.out / "private-audit"
    audit.mkdir()
    gold = json.loads(args.exclusions_cache.read_text()) if args.exclusions_cache else exclusions(args.dataset, audit)
    assert not gold["gold_image_read_failures"]
    papers, pdfs = set(gold["paper_ids"]), set(gold["pdf_sha256"])
    hashes = set(gold["image_sha256"]) | {x["sha256"] for x in gold["gold_images"]}
    pixels = {x["pixel_sha256"] for x in gold["gold_images"]}
    near = [int(x["phash"]) for x in gold["gold_images"]]
    approved, candidates = {}, {}
    for name in ("selection", "selection-batch2", "selection-batch3"):
        folder = args.teacher_root / name
        candidates.update((row["id"], row) for row in records(folder / "candidates.jsonl"))
        for row in records(folder / "approved.jsonl"):
            assert row["visual_approval"] == "approved" and row["id"] not in approved
            approved[row["id"]] = row
    previous = {row["episode"] for row in records(args.previous)}
    assert len(previous) == 200 and previous <= candidates.keys()
    avoided = previous
    for ident in avoided:
        row = candidates[ident]
        _, _, digest, pixel, phash = image_record(Path(row["reference"]))
        assert digest == row["reference_sha256"] and pixel == row["reference_pixels_sha256"]
        papers.add(row["paper_id"])
        pdfs.add(row["source_pdf_sha256"])
        hashes.add(digest)
        pixels.add(pixel)
        near.append(phash)
    counts, selected = Counter(), []
    public = args.out / "public"
    (public / "images").mkdir(parents=True)
    for row in sorted(candidates.values(), key=lambda x: (-x["complexity"]["score"], x["id"])):
        if row["id"] in avoided:
            counts["previous_or_attempted_case"] += 1
            continue
        if row["paper_id"] in papers or row["source_pdf_sha256"] in pdfs:
            counts["excluded_paper_or_pdf"] += 1
            continue
        raw, image, digest, pixel, phash = image_record(Path(row["reference"]))
        assert digest == row["reference_sha256"] and pixel == row["reference_pixels_sha256"]
        assert str(phash) == row["phash"] and list(image.size) == row["reference_size"]
        if digest in hashes or pixel in pixels or any((phash ^ other).bit_count() <= 7 for other in near):
            counts["exact_pixel_or_near_duplicate"] += 1
            continue
        assert sha256(Path(row["source_pdf"]).read_bytes()).hexdigest() == row["source_pdf_sha256"]
        assert sha256(Path(row["tex_file"]).read_bytes()).hexdigest() == row["tex_sha256"]
        context = source_context(row)
        assert context["paper_metadata"] == row["paper_metadata"]
        assert row["native_xml_absence_evidence"]["reason"] == "official_returned_no_embedded_diagram"
        name = "images/" + row["id"] + ".png"
        (public / name).write_bytes(raw)
        source = str(row["source_pdf"]).split("/source/", 1)[1]
        selected.append({"case_id": row["id"], "file": name, "paper_id": row["paper_id"],
                         "arxiv_url": row["arxiv_url"], "sha256": digest,
                         "decoded_pixel_sha256": pixel, "phash": str(phash),
                         "size": list(image.size), "source_pdf_sha256": row["source_pdf_sha256"],
                         "source_figure": source, "title": row["paper_metadata"]["title"],
                         "license_urls": row["paper_metadata"].get("license_urls", []),
                         "complexity": row["complexity"], "visual_approval": approved.get(row["id"], {}).get("visual_approval", "not_previously_approved"),
                         "historical_review_used_for_exclusion": False})
        papers.add(row["paper_id"])
        hashes.add(digest)
        pixels.add(pixel)
        near.append(phash)
    for name, rows in (("manifest.jsonl", selected), ("pilot.jsonl", selected[:5])):
        (public / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
    summary = {"at": time.time(), "original_candidates": len(candidates), "original_approved": len(approved),
               "prior_rejected_or_unapproved": len(candidates.keys() - approved.keys()),
               "previous_accepted_cases": len(previous), "previous_rollout_failure_is_excluded": False,
               "gold_manifest_rows": gold["gold_records_seen"], "gold_papers": len(gold["paper_ids"]),
               "gold_images": len(gold["gold_images"]), "gold_image_read_failures": 0,
               "near_image_hamming_threshold": 7, "exclusion_counts": dict(counts),
               "verified_image_count": len(selected), "distinct_papers": len(selected),
               "pilot_files": [row["file"] for row in selected[:5]],
               "gold_xml_included": False, "teacher_outputs_included": False,
               "full_source_pdfs_included": False, "transcripts_included": False,
               "requested_new_inputs": 800, "shortfall": max(0, 800 - len(selected)),
               "scope": "Whole remaining readable candidate pool from all three original selection batches; historical review does not filter; no new mining or model calls"}
    (public / "exclusion-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    files = [{"file": str(path.relative_to(public)), "bytes": path.stat().st_size,
              "sha256": sha256(path.read_bytes()).hexdigest()} for path in sorted(public.rglob("*")) if path.is_file()]
    assert len(files) == len(selected) + 3
    (audit / "public-files.json").write_text(json.dumps(files, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "teacher-root", "previous", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--exclusions-cache", type=Path)
    release(parser.parse_args())


if __name__ == "__main__":
    main()
