"""Mine a disjoint reference supplement from the project's existing arXiv cache."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time
from types import SimpleNamespace

from select_figures import exclusions, ledger, records, select


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def gold_index(dataset, teacher, output):
    cache = teacher / "reference-inputs-20261121/private-audit/exclusions.json"
    gold = json.loads(cache.read_text())
    previous = json.loads((teacher / "fresh-gold-disjointness-audit.json").read_text())
    expected = {row["file"]: row["sha256"] for row in previous["source_hashes"]}
    arxiv = dataset / "clean/arxiv_research_figures_v1"
    sources = {Path(name) for name in gold["source_manifests"]}
    sources.update(arxiv.glob("*/manifest.jsonl"))
    catalog = json.loads((dataset / "clean/research_pairs_catalog/current.json").read_text())
    sources.add(dataset / catalog["index"]["file"])
    sources.update(Path(name) for name in expected)
    changed = [str(path) for path in sources if not path.is_file()
               or sha256(path.read_bytes()).hexdigest() != expected.get(str(path))]
    db = ledger(dataset)
    native = {json.loads(row[0])["id"] for row in db.execute(
        "select record from pdfs where status in ('qualified_native_xml_png_pair','recovered_XML_below_complexity_or_wrapper')")}
    db.close()
    missing = native - set(gold["pdf_sha256"])
    reused = not changed and not missing
    if reused:
        shutil.copy2(cache, output / "exclusions.json")
    else:
        gold = exclusions(dataset, output)
    assert not gold["gold_image_read_failures"]
    save(output.parent / "gold-cache-validation.json", {
        "at": time.time(), "reused_verified_image_fingerprints": reused,
        "changed_source_files": changed, "current_native_pdf_ids": len(native),
        "native_ids_missing_from_previous_cache": len(missing),
        "exclusions_sha256": sha256((output / "exclusions.json").read_bytes()).hexdigest()})
    return gold


def prepare(args):
    args.out.mkdir(parents=True)
    audit = args.out / "private-audit"
    selection = audit / "selection"
    selection.mkdir(parents=True)
    teacher, dataset = args.teacher_root.resolve(), args.dataset.resolve()
    gold = gold_index(dataset, teacher, selection)
    manifests = [teacher / name / "candidates.jsonl" for name in ("selection", "selection-batch2", "selection-batch3")]
    previous = {row["id"]: row for path in manifests for row in records(path)}
    old600_root = teacher / "reference-inputs-full-20261121"
    old600 = old600_root / "public/manifest.jsonl"
    files = json.loads((old600_root / "private-audit/public-files.json").read_text())
    expected = next(row["sha256"] for row in files if row["file"] == "manifest.jsonl")
    assert sha256(old600.read_bytes()).hexdigest() == expected
    six = list(records(old600))
    two = list(records(teacher / "hf-publication-200/episodes.jsonl"))
    assert len(previous) == 800 and len(six) == 600 and len(two) == 200
    assert {row["case_id"] for row in six}.isdisjoint(row["episode"] for row in two)
    assert {row["case_id"] for row in six} | {row["episode"] for row in two} == previous.keys()
    assert all(row["sha256"] == previous[row["case_id"]]["reference_sha256"] for row in six)
    if not args.selection:
        select(SimpleNamespace(dataset=dataset, out=selection, limit=args.limit, scan_limit=args.scan_limit,
                               exclude_manifest=manifests, reference_pool=True))
    selections = args.selection or [selection / "candidates.jsonl"]
    reviews = [json.loads(path.read_text()) for path in args.visual_review]
    rejected = {ident for review in reviews for ident in review["excluded_ids"]}
    reviewed = {ident for review in reviews for ident in review["reviewed_ids"]}
    source_rows = [row for path in selections for row in sorted(records(path), key=lambda item: item["id"])]
    papers = set(gold["paper_ids"]) | {row["paper_id"] for row in previous.values()}
    pdfs = set(gold["pdf_sha256"]) | {row["source_pdf_sha256"] for row in previous.values()}
    hashes = set(gold["image_sha256"]) | {row["sha256"] for row in gold["gold_images"]}
    hashes.update(row["reference_sha256"] for row in previous.values())
    pixels = {row["pixel_sha256"] for row in gold["gold_images"]}
    pixels.update(row["reference_pixels_sha256"] for row in previous.values())
    near = [int(row["phash"]) for row in gold["gold_images"]] + [int(row["phash"]) for row in previous.values()]
    public = args.out / "public"
    (public / "images").mkdir(parents=True)
    result = []
    for row in source_rows:
        if row["id"] in rejected:
            continue
        assert not reviews or row["id"] in reviewed
        image = Path(row["reference"])
        digest = sha256(image.read_bytes()).hexdigest()
        assert digest == row["reference_sha256"]
        assert row["paper_id"] not in papers and row["source_pdf_sha256"] not in pdfs
        assert digest not in hashes and row["reference_pixels_sha256"] not in pixels
        phash = int(row["phash"])
        assert all((phash ^ value).bit_count() > 7 for value in near)
        name = "images/" + row["id"] + ".png"
        shutil.copy2(image, public / name)
        attempted = any((teacher / run / "episodes" / row["id"]).exists()
                        for run in ("run-01", "replacement-run-01"))
        result.append({"case_id": row["id"], "file": name, "paper_id": row["paper_id"],
                       "arxiv_url": row["arxiv_url"], "sha256": digest,
                       "decoded_pixel_sha256": row["reference_pixels_sha256"], "phash": row["phash"],
                       "size": row["reference_size"], "source_pdf_sha256": row["source_pdf_sha256"],
                       "source_figure": str(row["source_pdf"]).split("/source/", 1)[1],
                       "title": row["paper_metadata"]["title"],
                       "license_urls": row["paper_metadata"].get("license_urls", []),
                       "complexity": row["complexity"], "historical_review": None,
                       "previous_rollout_attempted": attempted, "tex_figure_link_verified": True,
                       "historical_review_or_complexity_used_for_exclusion": False,
                       "current_figure_type_reviewed": row["id"] in reviewed})
        papers.add(row["paper_id"])
        pdfs.add(row["source_pdf_sha256"])
        hashes.add(digest)
        pixels.add(row["reference_pixels_sha256"])
        near.append(phash)
        if len(result) == args.limit:
            break
    (public / "manifest.jsonl").write_text("".join(json.dumps(row) + "\n" for row in result))
    scans = [json.loads((path.parent / "selection-summary.json").read_text()) for path in selections]
    counts = Counter()
    for scan in scans:
        counts.update(scan["counts"])
    summary = {"at": time.time(), "requested_images": args.limit, "verified_image_count": len(result),
               "distinct_papers": len({row["paper_id"] for row in result}), "previous_accepted_cases": 200,
               "previous_reference_images": 600, "prior_reference_revision": "412a9e49cafe1701befb56a2de40dcbc46ecc8e1",
               "gold_manifest_rows": gold["gold_records_seen"], "gold_papers": len(gold["paper_ids"]),
               "gold_images": len(gold["gold_images"]), "gold_image_read_failures": 0,
               "phash_hamming_exclusion_threshold": 7, "scan_counts": dict(counts), "scan_passes": scans,
               "current_figure_types_reviewed": len(reviewed), "non_framework_figures_rejected": len(rejected),
               "candidate_images_not_published": len(source_rows) - len(result),
               "unused_readable_candidates_after_target": len(source_rows) - len(rejected) - len(result),
               "shortfall": max(0, args.limit - len(result)), "complexity_used_for_filtering": False,
               "gold_xml_included": False, "full_source_pdfs_included": False, "transcripts_included": False,
               "model_calls": 0, "source": "Existing cached arXiv framework/architecture/pipeline figures with verified paper provenance and TeX figure links"}
    save(public / "exclusion-summary.json", summary)
    files = [{"file": str(path.relative_to(public)), "bytes": path.stat().st_size,
              "sha256": sha256(path.read_bytes()).hexdigest()} for path in sorted(public.rglob("*")) if path.is_file()]
    assert len(files) == len(result) + 2
    save(audit / "public-files.json", files)
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "teacher-root", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--scan-limit", type=int, default=12000)
    parser.add_argument("--selection", action="append", type=Path)
    parser.add_argument("--visual-review", action="append", type=Path, default=[])
    prepare(parser.parse_args())


if __name__ == "__main__":
    main()
