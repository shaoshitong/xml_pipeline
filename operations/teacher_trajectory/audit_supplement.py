"""Verify a reference supplement against current gold, prior splits and source files."""

import argparse
from hashlib import sha256
import itertools
import json
from pathlib import Path
import subprocess
import time

from PIL import Image

from release_inputs import image_record
from select_figures import paper_id, records
from supplement_inputs import gold_index, save, seal


def audit(args):
    root, teacher = args.out.resolve(), args.teacher_root.resolve()
    private = root / "private-audit"
    current = private / "current-gold/selection"
    current.mkdir(parents=True, exist_ok=True)
    gold = gold_index(args.dataset.resolve(), teacher, current)
    prior = {row["id"]: row for name in ("selection", "selection-batch2", "selection-batch3")
             for row in records(teacher / name / "candidates.jsonl")}
    old600_root = teacher / "reference-inputs-full-20261121"
    old600_file = old600_root / "public/manifest.jsonl"
    frozen = json.loads((old600_root / "private-audit/public-files.json").read_text())
    assert sha256(old600_file.read_bytes()).hexdigest() == next(x["sha256"] for x in frozen if x["file"] == "manifest.jsonl")
    six = list(records(old600_file))
    two_file = teacher / "hf-publication-200/episodes.jsonl"
    frozen_two = json.loads((teacher / "hf-publication-200/upload-release-files.json").read_text())
    assert sha256(two_file.read_bytes()).hexdigest() == next(x["sha256"] for x in frozen_two if x["path"] == "episodes.jsonl")
    two = list(records(two_file))
    ids_two, ids_six = {x["episode"] for x in two}, {x["case_id"] for x in six}
    assert len(ids_two) == 200 and len(ids_six) == 600 and ids_two.isdisjoint(ids_six)
    assert ids_two | ids_six == prior.keys()
    draft = teacher / "meanflow-reference-supplement-20261121/private-audit"
    sources = {row["id"]: row for name in ("selection", "replacement-selection")
               for row in records(draft / name / "candidates.jsonl")}
    reviews = [json.loads((draft / name).read_text()) for name in ("type-review-initial.json", "type-review-replacements.json")]
    reviewed = {ident for review in reviews for ident in review["reviewed_ids"]}
    rejected = {ident for review in reviews for ident in review["excluded_ids"]}
    rows = list(records(root / "public/manifest.jsonl"))
    assert len(rows) == 200 and len({x["case_id"] for x in rows}) == 200
    papers = set(gold["paper_ids"]) | {x["paper_id"] for x in prior.values()}
    pdfs = set(gold["pdf_sha256"]) | {x["source_pdf_sha256"] for x in prior.values()}
    hashes = set(gold["image_sha256"]) | {x["sha256"] for x in gold["gold_images"]}
    hashes.update(x["reference_sha256"] for x in prior.values())
    pixels = {x["pixel_sha256"] for x in gold["gold_images"]}
    pixels.update(x["reference_pixels_sha256"] for x in prior.values())
    gold_phash = [int(x["phash"]) for x in gold["gold_images"]]
    two_phash = [int(prior[ident]["phash"]) for ident in ids_two]
    six_phash = [int(prior[ident]["phash"]) for ident in ids_six]
    phashes, cases = [], []
    for row in rows:
        assert row["case_id"] in reviewed - rejected and row["current_figure_type_reviewed"]
        path = root / "public" / row["file"]
        raw, image, digest, pixel, phash = image_record(path)
        with Image.open(path) as source_image:
            assert source_image.format == "PNG" and not source_image.info
        assert digest == row["sha256"] and pixel == row["decoded_pixel_sha256"]
        assert str(phash) == row["phash"] and list(image.size) == row["size"]
        assert row["paper_id"] not in papers and row["source_pdf_sha256"] not in pdfs
        assert digest not in hashes and pixel not in pixels
        source = sources[row["case_id"]]
        assert sha256(Path(source["source_pdf"]).read_bytes()).hexdigest() == row["source_pdf_sha256"]
        tex = Path(source["tex_file"]).read_bytes()
        assert sha256(tex).hexdigest() == source["tex_sha256"]
        assert source["includegraphics"] in tex.decode(errors="replace")
        metadata = json.loads(Path(source["metadata_file"]).read_text())
        assert paper_id(metadata.get("arxiv_id", metadata.get("abs_url"))) == row["paper_id"]
        assert paper_id(row["arxiv_url"]) == row["paper_id"]
        distances = {"gold": min((phash ^ x).bit_count() for x in gold_phash),
                     "previous200": min((phash ^ x).bit_count() for x in two_phash),
                     "previous600": min((phash ^ x).bit_count() for x in six_phash)}
        assert min(distances.values()) > 7
        cases.append({"case_id": row["case_id"], "sha256": digest, "nearest_phash_distance": distances})
        papers.add(row["paper_id"])
        pdfs.add(row["source_pdf_sha256"])
        hashes.add(digest)
        pixels.add(pixel)
        phashes.append(phash)
    for index, case in enumerate(cases):
        distance = min((phashes[index] ^ other).bit_count() for j, other in enumerate(phashes) if j != index)
        assert distance > 7
        case["nearest_phash_distance"]["within_supplement"] = distance
    expected = {row["file"] for row in rows} | {"manifest.jsonl", "exclusion-summary.json", "dedup-audit.json", "SHA256SUMS"}
    actual = {str(path.relative_to(root / "public")) for path in (root / "public").rglob("*") if path.is_file()}
    assert actual <= expected and not any(path.is_symlink() for path in (root / "public").rglob("*"))
    result = {"at": time.time(), "verified_images": 200, "distinct_papers": len({x["paper_id"] for x in rows}),
              "gold_papers": len(gold["paper_ids"]), "gold_images": len(gold["gold_images"]),
              "gold_index_sha256": sha256((current / "exclusions.json").read_bytes()).hexdigest(),
              "previous200_index_sha256": sha256(two_file.read_bytes()).hexdigest(),
              "previous600_manifest_sha256": sha256(old600_file.read_bytes()).hexdigest(),
              "previous600_revision": "412a9e49cafe1701befb56a2de40dcbc46ecc8e1", "excluded_previous_inputs": 800,
              "phash_exclusion_threshold": 7, "source_pdf_tex_and_paper_provenance_verified": True,
              "exact_file_pixel_and_paper_overlaps": 0, "current_type_review_verified": True,
              "minimum_phash_distances": {key: min(x["nearest_phash_distance"][key] for x in cases)
                                          for key in cases[0]["nearest_phash_distance"]},
              "model_calls": 0, "cases": cases}
    assert result["distinct_papers"] == 200
    save(root / "public/dedup-audit.json", result)
    save(private / "independent-supplement-audit.json", result)
    seal(root / "public", private)
    check = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=root / "public", capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert len(list((root / "public/images").glob("*.png"))) == 200
    final = {"at": time.time(), "sha256sum_check_exit": check.returncode,
             "checked_files": len(check.stdout.splitlines()), "published_files": len(expected),
             "source_commit": args.source_commit, "checksum_manifest_sha256": sha256((root / "public/SHA256SUMS").read_bytes()).hexdigest()}
    save(private / "seal-verification.json", final)
    print(json.dumps({**{k: v for k, v in result.items() if k != "cases"}, **final}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "teacher-root", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    audit(parser.parse_args())


if __name__ == "__main__":
    main()
