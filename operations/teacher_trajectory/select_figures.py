"""Select cached arXiv architecture figures, excluding every known gold paper."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw


PAPER = re.compile(r"(?<!\d)\d{4}\.\d{4,5}(?:v\d+)?")
NAMES = ("framework", "architecture", "pipeline", "overview", "workflow", "system_model")
cv2.setNumThreads(1)


def paper_id(value):
    match = PAPER.search(str(value))
    return re.sub(r"v\d+$", "", match.group()) if match else None


def fingerprint(image):
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    block = cv2.dct(cv2.resize(gray, (32, 32)).astype(np.float32))[:8, :8]
    bits = block > np.median(block.flatten()[1:])
    return int.from_bytes(np.packbits(bits).tobytes(), "big")


def records(path):
    with path.open() as stream:
        for line in stream:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def ledger(root):
    path = root / "clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/once.sqlite"
    return sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True)


def exclusions(root, out):
    arxiv = root / "clean/arxiv_research_figures_v1"
    sources = [root / "clean/accepted_3759_v1/pairs.jsonl",
               arxiv / "goal500_final_delivery_v1/baseline_plus_accepted_new.jsonl"]
    sources += list(arxiv.glob("*/manifest.jsonl"))
    pointer = root / "clean/research_pairs_catalog/current.json"
    sources.append(root / json.loads(pointer.read_text())["index"]["file"])
    papers, pdfs, images, hashes = set(), set(), {}, set()
    count = 0
    for source in sources:
        if not source.is_file():
            continue
        for row in records(source):
            gold = row.get("code_file") or row.get("author_xml_recovered") or row.get("qualified")
            if not gold:
                continue
            count += 1
            papers.update(re.sub(r"v\d+$", "", x) for x in PAPER.findall(json.dumps(row)))
            if row.get("pdf_sha256"):
                pdfs.add(row["pdf_sha256"])
            if row.get("image_sha256"):
                hashes.add(row["image_sha256"])
            image = row.get("image_file")
            if image and (root / image).is_file():
                images[str(root / image)] = row.get("image_sha256")
    db = ledger(root)
    query = "select record from pdfs where status in ('qualified_native_xml_png_pair','recovered_XML_below_complexity_or_wrapper')"
    for (text,) in db.execute(query):
        row = json.loads(text)
        if paper_id(row.get("paper")):
            papers.add(paper_id(row["paper"]))
        pdfs.add(row["id"])
    db.close()
    for folder in ("cached_author_native_inventory_v1", "author_XML_inventory_v1",
                   "embedded_XML_image_inventory_v2", "embedded_XML_image_inventory_v1"):
        p = arxiv / folder
        for name in ("candidates.jsonl", "inventory.json"):
            f = p / name
            if not f.is_file():
                continue
            rows = records(f) if f.suffix == ".jsonl" else json.loads(f.read_text()).get("candidates", [])
            for row in rows:
                papers.update(re.sub(r"v\d+$", "", x) for x in PAPER.findall(json.dumps(row)))
    fingerprints, failures = [], []
    def inspect(item):
        path, recorded = item
        try:
            raw = Path(path).read_bytes()
            image = Image.open(Path(path)).convert("RGB")
            return {"file": path, "sha256": sha256(raw).hexdigest(),
                    "pixel_sha256": sha256(image.tobytes()).hexdigest(),
                    "size": list(image.size), "phash": str(fingerprint(image))}
        except Exception as error:
            return {"file": path, "error": type(error).__name__}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(inspect, images.items()):
            (failures if "error" in row else fingerprints).append(row)
    result = {"at": time.time(), "source_manifests": [str(x) for x in sources if x.is_file()],
              "gold_records_seen": count, "paper_ids": sorted(papers), "pdf_sha256": sorted(pdfs),
              "image_sha256": sorted(hashes), "gold_images": fingerprints,
              "gold_image_read_failures": failures,
              "policy": "whole-paper exclusion plus PDF, image, decoded-pixel and near-image exclusion"}
    (out / "exclusions.json").write_text(json.dumps(result) + "\n")
    print(json.dumps({"stage": "exclusions", "gold_rows": count, "gold_papers": len(papers),
                      "gold_images_checked": len(fingerprints), "image_read_failures": len(failures)}), flush=True)
    return result


def assess(path):
    import fitz
    with fitz.open(path) as document:
        if len(document) != 1:
            return None
        page = document[0]
        width, height = page.rect.width, page.rect.height
        if min(width, height) < 100 or max(width / height, height / width) > 7:
            return None
        text = page.get_text()
        words = text.split()
        numeric = sum(bool(re.fullmatch(r"[\d.,%+−-]+", x)) for x in words) / max(1, len(words))
        rectangles, lines = set(), 0
        for drawing in page.get_drawings():
            for item in drawing["items"]:
                if item[0] == "re" and min(item[1].width, item[1].height) >= 8:
                    rectangles.add(tuple(round(x, 1) for x in item[1]))
                elif item[0] == "l" and abs(item[1] - item[2]) >= 8:
                    lines += 1
        raster = sum(fitz.Rect(x["bbox"]).get_area() for x in page.get_image_info()) / page.rect.get_area()
        if len(rectangles) < 8 or lines < 15 or len(words) < 30 or len(text) < 120 or numeric > .25 or raster > .35:
            return None
        scale = min(2.5, 2200 / max(width, height))
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        stats = {"pdf_rectangles": len(rectangles), "pdf_long_lines": lines,
                 "text_words": len(words), "text_characters": len(text),
                 "numeric_word_fraction": numeric, "raster_area_fraction": raster,
                 "score": min(len(rectangles), 80) + min(lines, 100) * .4 + min(len(words), 200) * .1}
        return image, stats


def source_context(record):
    source = Path(record["source_pdf"])
    paper_root = Path(str(source).split("/source/")[0])
    metadata = paper_root / "provenance.json"
    if not metadata.is_file():
        raise ValueError("No archived arXiv provenance")
    provenance = json.loads(metadata.read_text())
    if paper_id(provenance.get("arxiv_id", provenance.get("abs_url"))) != record["paper_id"]:
        raise ValueError("arXiv provenance paper ID mismatch")
    pattern = re.compile(r"\\includegraphics\s*(?:\[[^\]]*\]\s*)?\{[^}]*" + re.escape(source.stem) + r"(?:\.pdf)?\}")
    for tex in (paper_root / "source").rglob("*.tex"):
        text = tex.read_text(errors="replace")
        match = pattern.search(text)
        if match:
            return {"paper_metadata": provenance, "tex_file": str(tex),
                    "tex_sha256": sha256(tex.read_bytes()).hexdigest(),
                    "includegraphics": match.group(),
                    "tex_context": text[max(0, match.start() - 250):match.end() + 1000]}
    raise ValueError("Source figure is not linked from the archived paper TeX")


def select(args):
    root, out = args.dataset.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(root / "evaluation/assets/pdf_inventory_python_v1"))
    excluded = json.loads((out / "exclusions.json").read_text()) if (out / "exclusions.json").exists() else exclusions(root, out)
    papers, pdfs = set(excluded["paper_ids"]), set(excluded["pdf_sha256"])
    images = set(excluded["image_sha256"]) | {x["sha256"] for x in excluded["gold_images"]}
    pixels = {x["pixel_sha256"] for x in excluded["gold_images"]}
    hashes = [int(x["phash"]) for x in excluded["gold_images"]]
    db = ledger(root)
    predicate = " or ".join("record like ?" for _ in NAMES)
    query = "select record from pdfs where status='unsupported_builtin_import' and (" + predicate + ") limit ?"
    rows = db.execute(query, ["%" + name + "%" for name in NAMES] + [args.scan_limit])
    counts, chosen, seen_papers = Counter(), [], set()
    for manifest in args.exclude_manifest:
        for previous in records(manifest):
            seen_papers.add(previous["paper_id"])
            hashes.append(int(previous["phash"]))
    for (text,) in rows:
        row = json.loads(text)
        counts["examined"] += 1
        paper = paper_id(row["paper"])
        if paper in papers or paper in seen_papers or row["id"] in pdfs:
            counts["excluded_paper_or_pdf"] += 1
            continue
        if row.get("author_xml_recovered") or row.get("reason") != "official_returned_no_embedded_diagram":
            counts["absence_not_proven"] += 1
            continue
        source = root / row["pdf_file"]
        if not source.is_file():
            counts["source_missing"] += 1
            continue
        paper_root = Path(str(source).split("/source/")[0])
        extraction = paper_root / "extraction.json"
        if extraction.is_file() and any(Path(x).suffix.lower() == ".drawio" for x in json.loads(extraction.read_text()).get("extracted", [])):
            counts["paper_contains_drawio"] += 1
            continue
        raw = source.read_bytes()
        if sha256(raw).hexdigest() != row["id"]:
            counts["source_hash_mismatch"] += 1
            continue
        try:
            result = assess(source)
        except Exception as error:
            counts["pdf_error_" + type(error).__name__] += 1
            continue
        if result is None:
            counts["below_diagram_gate"] += 1
            continue
        image, features = result
        phash = fingerprint(image)
        if sha256(image.tobytes()).hexdigest() in pixels or any((phash ^ x).bit_count() <= 7 for x in hashes):
            counts["near_gold_image"] += 1
            continue
        ident = row["id"][:16]
        folder = out / "inputs" / ident
        folder.mkdir(parents=True, exist_ok=True)
        image.save(folder / "reference.png")
        image_sha = sha256((folder / "reference.png").read_bytes()).hexdigest()
        if image_sha in images:
            counts["exact_gold_image"] += 1
            continue
        metadata = next((paper_root / name for name in ("provenance.json", "metadata.json") if (paper_root / name).is_file()), None)
        record = {"id": ident, "paper": row["paper"], "paper_id": paper,
                  "arxiv_url": "https://arxiv.org/abs/" + row["paper"],
                  "source_pdf": str(source), "source_pdf_sha256": row["id"],
                  "metadata_file": str(metadata) if metadata else None,
                  "reference": str(folder / "reference.png"), "reference_sha256": image_sha,
                  "reference_pixels_sha256": sha256(image.tobytes()).hexdigest(),
                  "reference_size": list(image.size), "phash": str(phash),
                  "complexity": features, "native_xml_absence_evidence": row,
                  "visual_approval": "pending", "gold_paper_overlap": False,
                  "gold_near_image_threshold_bits": 7}
        try:
            record.update(source_context(record))
        except ValueError:
            counts["missing_paper_figure_link"] += 1
            continue
        (folder / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
        chosen.append(record)
        seen_papers.add(paper)
        hashes.append(phash)
        if len(chosen) % 10 == 0:
            print(json.dumps({"selected": len(chosen), "counts": dict(counts)}), flush=True)
        if len(chosen) >= args.limit:
            break
    chosen.sort(key=lambda x: -x["complexity"]["score"])
    (out / "candidates.jsonl").write_text("".join(json.dumps(x) + "\n" for x in chosen))
    (out / "selection-summary.json").write_text(json.dumps({"selected": len(chosen), "counts": dict(counts)}, indent=2) + "\n")
    for offset in range(0, len(chosen), 20):
        sheet = Image.new("RGB", (1600, 1200), "white")
        draw = ImageDraw.Draw(sheet)
        for number, item in enumerate(chosen[offset:offset + 20]):
            image = Image.open(item["reference"])
            image.thumbnail((390, 205))
            x, y = number % 4 * 400, number // 4 * 240
            sheet.paste(image, (x, y + 30))
            draw.text((x + 5, y + 3), f"{offset+number:03d} {item['paper']} {item['id'][:6]}", fill="black")
        sheet.save(out / f"contact-{offset//20:02d}.png")
    print(json.dumps({"finished": True, "selected": len(chosen), "counts": dict(counts)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--scan-limit", type=int, default=12000)
    parser.add_argument("--exclude-manifest", action="append", type=Path, default=[])
    select(parser.parse_args())


if __name__ == "__main__":
    main()
