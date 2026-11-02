#!/usr/bin/env python3
"""Refresh a provenance-preserving research-pair catalogue without model calls.

Only manifests and their explicitly referenced payloads are inspected. The
publisher neither converts diagrams nor changes an upstream qualification.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import datetime as dt
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import struct
import sys
import time
import uuid
import xml.etree.ElementTree as ET

from PIL import Image

VERSION = "research_catalog_refresh_v4"
DEFAULT_ROOT = Path("/backup/shaoshitong/img2code_20261029")
CURATION = "clean/complexity_curation_20261102T054553Z_v1/current.json"
CATALOG = "clean/research_pairs_catalog"
ARXIV = "clean/arxiv_research_figures_v1/"
CHART = "clean/matplotlib_plot_pipeline_20261102_v1/"
INPUTS = (
    ("scientific_chart_vector_provider_original", "scientific_chart_provider_original", CHART + "vector_backend_rollout_v6/provider_original_reference_aligned.jsonl"),
    ("scientific_chart_vector_source_replay", "scientific_chart_source_replay", CHART + "vector_backend_rollout_v6/source_replay_aligned.jsonl"),
    ("scientific_chart_vector_SVG_backend", "scientific_chart_source_SVG_backend_replay", CHART + "vector_backend_rollout_v6/source_svg_backend_replay_aligned.jsonl"),
    ("scientific_chart_provider_original", "scientific_chart_provider_original", CHART + "provider_original_reference_aligned.jsonl"),
    ("scientific_chart_source_replay", "scientific_chart_source_replay", CHART + "source_replay_aligned.jsonl"),
    ("scientific_chart_source_replay_repaired", "scientific_chart_source_replay_repaired", CHART + "published_repair_pairs_v3/source_replay_aligned.jsonl"),
    ("arxiv_registered_original_PDF_visual_v2", "arxiv_registered_original_PDF_visual_v2", ARXIV + "original_PDF_reference_audit_v2/paired_registered_original_PDF.jsonl"),
    ("arxiv_author_native_frozen", "arxiv_author_native_source_replay", ARXIV + "author_native_source_replay_v1/published_source_replay_v2/source_replay_aligned.jsonl"),
    ("arxiv_author_native_incremental", "arxiv_author_native_source_replay", ARXIV + "author_native_source_replay_incremental_v1/author_native_source_replay.jsonl"),
)
NOTES = {
    "scientific_chart_source_SVG_backend_replay": "Exact release Python source and all Artist arrays retained; actual source SVG physical-font browser reference passes recorded gates. Provider-original and Agg fidelity are not certified by this profile.",
    "paper_diagrams_and_posters_full8": "Source complexity selection and recorded full8 qualification. RAP references reconstructed HTML templates; original posters are auxiliary.",
    "scientific_chart_provider_original": "Includes dataset-provided original image correspondence under its declared scientific-plot checks.",
    "scientific_chart_source_replay": "Source execution defines the paired image; the dataset image remains auxiliary.",
    "scientific_chart_source_replay_repaired": "Versioned repaired source replay; retains the upstream quality profile.",
    "arxiv_registered_original_PDF_visual_v2": "Registered original PDF raster checks passed; this is not legacy full8 or standalone font portability.",
    "arxiv_author_native_source_replay": "Cold official document replay, edit/restore, resource and runtime font evidence. Original PDF fidelity and standalone font portability are not certified by this profile.",
}
STOP = False
FORCE = False


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def software_sha():
    return sha(Path(__file__).read_bytes())


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("ascii")


def write(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    write(temp, encoded(value))
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stable_bytes(path):
    for _ in range(3):
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns):
            return data
    raise ValueError("changing_input:" + str(path))


def digest_valid(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


class BusyError(RuntimeError):
    pass


@contextlib.contextmanager
def locked(path):
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise BusyError("publisher_lock_held:" + str(path)) from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class Assets:
    def __init__(self, root, previous=None):
        self.root = root.resolve(strict=True)
        self.clean = (root / "clean").resolve(strict=True)
        self.records = {}
        self.cache = {}
        self.previous = {row["file"]: row for row in previous or []}

    def path(self, name, primary=False):
        if not isinstance(name, str) or not name:
            raise ValueError("missing_asset_path")
        logical = Path(name)
        logical = logical if logical.is_absolute() else self.root / logical
        resolved = logical.resolve(strict=True)
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            raise ValueError("asset_outside_task_root:" + str(logical))
        if primary and not resolved.is_relative_to(self.clean):
            raise ValueError("primary_asset_outside_clean:" + str(logical))
        return logical, resolved

    def verify(self, name, digest, *, primary=False, image=False, xml=False):
        if not digest_valid(digest):
            raise ValueError("invalid_asset_sha256:" + str(name))
        logical, path = self.path(name, primary)
        stat = path.stat()
        identity = (str(path), stat.st_ino, stat.st_size, stat.st_mtime_ns)
        data = None
        prior = self.previous.get(str(logical.relative_to(self.root)))
        if prior and prior["resolved_file"] == str(path.relative_to(self.root)) and (prior["inode"], prior["bytes"], prior["mtime_ns"], prior["sha256"]) == (stat.st_ino, stat.st_size, stat.st_mtime_ns, digest):
            self.cache.setdefault(identity, {"sha256": digest, **({"xml_valid": True} if prior.get("xml_valid") else {}), **({"pixels": prior["pixels"]} if "pixels" in prior else {})})
        if identity not in self.cache:
            data = stable_bytes(path)
            self.cache[identity] = {"sha256": sha(data)}
        item = self.cache[identity]
        if item["sha256"] != digest:
            raise ValueError("payload_hash_mismatch:" + str(path))
        if xml and not item.get("xml_valid"):
            data = data if data is not None else stable_bytes(path)
            if sha(data) != digest:
                raise ValueError("payload_changed_during_verification:" + str(path))
            element = ET.fromstring(data)
            if element.tag.rsplit("}", 1)[-1] not in {"mxfile", "mxGraphModel"}:
                raise ValueError("not_drawio_XML:" + str(path))
            item["xml_valid"] = True
        if image and "pixels" not in item:
            data = data if data is not None else stable_bytes(path)
            if sha(data) != digest:
                raise ValueError("payload_changed_during_verification:" + str(path))
            with Image.open(io.BytesIO(data)) as image_object:
                if image_object.format != "PNG":
                    raise ValueError("not_PNG:" + str(path))
                rgba = image_object.convert("RGBA")
                rgba.load()
                item["pixels"] = {
                    "width": rgba.width,
                    "height": rgba.height,
                    "rgba_sha256": sha(struct.pack(">QQ", rgba.width, rgba.height) + rgba.tobytes()),
                }
        after = path.stat()
        if identity[1:] != (after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("payload_changed_during_verification:" + str(path))
        # Store the logical reference as well, to detect changed symlink targets.
        key = str(logical.relative_to(self.root))
        self.records[key] = {
            "file": key, "resolved_file": str(path.relative_to(self.root)),
            "sha256": digest, "inode": stat.st_ino, "bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            **({"xml_valid": True} if item.get("xml_valid") else {}),
            **({"pixels": item["pixels"]} if "pixels" in item else {}),
        }
        return str(path.relative_to(self.root)), item

    def declared_evidence(self, value):
        """Verify explicit path/digest siblings, including packaged resources."""
        if isinstance(value, list):
            for part in value:
                self.declared_evidence(part)
            return
        if not isinstance(value, dict):
            return
        for path_key, hash_key in (("original_source_code", "source_code_sha256"), ("original_reference", "source_image_sha256")):
            if isinstance(value.get(path_key), str) and digest_valid(value.get(hash_key)):
                self.verify(value[path_key], value[hash_key])
        for key, digest in value.items():
            if not key.endswith("_sha256") or not digest_valid(digest):
                continue
            base = key[:-7]
            for candidate in (base, base + "_file", base + "_path"):
                if isinstance(value.get(candidate), str):
                    self.verify(value[candidate], digest)
                    break
        if digest_valid(value.get("sha256")):
            for key in ("file", "portable_asset_file", "original_asset_file"):
                if key in value:
                    self.verify(value[key], value["sha256"])
        for child in value.values():
            if isinstance(child, (list, dict)):
                self.declared_evidence(child)

    def incremental_gate(self, row):
        required = {
            "profile": "author_native_source_replay",
            "quality_state": "verified_under_declared_author_native_source_replay_contract",
            "paired_code_XML_bytes_equal_original_author_XML": True,
            "original_PDF_fidelity": "review_not_certified",
            "provider_original_reference_aligned": False,
            "legacy_full8_qualified": False,
        }
        for key, expected in required.items():
            if row.get(key) != expected:
                raise ValueError("incremental_profile_gate:" + key)
        for name, digest in (
            ("native_replay_proof", "native_replay_proof_sha256"),
            ("asset_audit", "asset_audit_sha256"),
            ("original_author_XML", "original_author_XML_sha256"),
            ("original_PDF_file", "original_PDF_sha256"),
            ("auxiliary_preexisting_native_PNG", "auxiliary_preexisting_native_PNG_sha256"),
            ("old_native_render_edit_proof", "old_native_render_edit_proof_sha256"),
        ):
            self.verify(row.get(name), row.get(digest))
        if row["original_author_XML_sha256"] != row["code_sha256"]:
            raise ValueError("incremental_author_XML_bytes_changed")
        _, proof_path = self.path(row["native_replay_proof"])
        proof = json.loads(stable_bytes(proof_path))
        for key in ("ok", "normalized_model_exact_restore", "mutation_normalized_model_changed", "mutation_actual_RGBA_changed", "restored_actual_RGBA_exact", "restored_PNG_bytes_exact"):
            if proof.get(key) is not True:
                raise ValueError("incremental_native_proof_gate:" + key)
        if proof.get("source_XML_sha256") != row["code_sha256"] or proof.get("source_official_PNG_sha256") != row["image_sha256"]:
            raise ValueError("incremental_native_proof_payload_binding")
        fonts = proof.get("font_observations", {})
        if fonts.get("all_physical_font_bytes_pinned") is not True:
            raise ValueError("incremental_native_proof_fonts_unpinned")
        font_key = lambda f: (f.get("file"), f.get("sha256"))
        if sorted(map(font_key, fonts.get("font_assets", []))) != sorted(map(font_key, row.get("font_dependencies", []))):
            raise ValueError("incremental_native_proof_font_binding")
        old_path = self.path(row["old_native_render_edit_proof"])[1]
        old_proof = json.loads(stable_bytes(old_path))
        edit = old_proof.get("edit_probe", {})
        if not edit.get("mutation_actual_PNG_changed") or not edit.get("restored_actual_PNG_exact"):
            raise ValueError("incremental_original_native_edit_proof_missing")


    def vector_plot_gate(self, row):
        profile = row.get("profile")
        allowed = {"provider_original_reference_aligned", "source_replay_aligned", "source_svg_backend_replay_aligned"}
        if profile not in allowed or row.get("whole_figure_wrapper") is not False or row.get("source_label_glyph_path_substitution") is not False or row.get("all_Artist_arrays_preserved") is not True:
            raise ValueError("vector_plot_profile_or_source_editability_contract")
        self.verify(row["quality_report"], row["quality_report_sha256"])
        quality = json.loads(stable_bytes(self.path(row["quality_report"])[1]))
        if quality.get("ok") is not True or quality.get("profiles", {}).get(profile) is not True:
            raise ValueError("vector_plot_declared_profile_not_qualified")
        for key in ("independent_source_coverage", "source_array_shape_and_count_audit", "structure", "source_SVG_native_gate"):
            if quality.get(key, {}).get("ok") is not True:
                raise ValueError("vector_plot_closed_gate:" + key)
        for key in ("source_font_custom_faces_match", "source_image_assets_complete", "complete_recorded_source_export_and_RNG_contract"):
            if quality.get(key) is not True:
                raise ValueError("vector_plot_source_proof:" + key)
        if quality.get("actual_rendered_text", {}).get("all_source_text_objects_rendered") is not True:
            raise ValueError("vector_plot_actual_source_text_not_complete")
        edit = quality.get("actual_edit_probe", {})
        if edit != row.get("actual_edit_restore_proof") or edit.get("performed") is not True or edit.get("changed_RGBA_pixels", 0) <= 0 or edit.get("restore_RGBA_exact") is not True or edit.get("published_source_XML_unchanged") is not True:
            raise ValueError("vector_plot_actual_native_edit_restore_not_bound")
        if profile == "provider_original_reference_aligned":
            if row.get("provider_original_fidelity_certified") is not True or quality.get("provider_original_reference_gate", {}).get("ok") is not True or row["source_image_sha256"] != row["auxiliary_provider_original_reference_sha256"]:
                raise ValueError("vector_plot_provider_original_not_certified")
        elif profile == "source_replay_aligned":
            if quality.get("fresh_Agg_native_gate", {}).get("ok") is not True or quality.get("fresh_SVG_Agg_gate", {}).get("ok") is not True:
                raise ValueError("vector_plot_Agg_replay_not_certified")
        elif row.get("source_image_origin") != "fresh_release_exact_code_source_SVG_actual_physical_face_browser_view" or row.get("provider_original_fidelity_certified") is not False:
            raise ValueError("vector_plot_SVG_backend_reference_mislabeled")


def inputs(root):
    pointer_path = root / CURATION
    pointer_data = stable_bytes(pointer_path)
    pointer = json.loads(pointer_data)
    main = pointer["views"]["paired_priority_complex"]
    main_path = root / main["file"]
    if not main_path.resolve(strict=True).is_relative_to((root / "clean").resolve(strict=True)):
        raise ValueError("strict_main_manifest_outside_clean")
    main_data = stable_bytes(main_path)
    if sha(main_data) != main["sha256"]:
        raise ValueError("strict_main_manifest_pointer_hash_mismatch")
    result = [("paper_diagrams_and_posters_full8", "paper_diagrams_and_posters_full8", main_path, main_data)]
    for ident, view, relative in INPUTS:
        path = root / relative
        result.append((ident, view, path, stable_bytes(path)))
    signature = sha(encoded({
        "publisher": VERSION,
        "publisher_source_sha256": software_sha(),
        "curation_pointer": {"file": CURATION, "sha256": sha(pointer_data)},
        "inputs": [{"id": ident, "view": view, "file": str(path.relative_to(root)), "sha256": sha(data)} for ident, view, path, data in result],
    }))
    return signature, result


def unchanged(root, signature):
    """Fast no-op only if input hashes AND verified payload identities match."""
    current = root / CATALOG / "current.json"
    if not current.exists():
        return False
    pointer = json.loads(stable_bytes(current))
    if pointer.get("publisher") != VERSION or pointer.get("input_fingerprint") != signature:
        return False
    for key in ("index", "summary", "validation"):
        value = pointer[key]
        if sha(stable_bytes(root / value["file"])) != value["sha256"]:
            raise ValueError("published_catalogue_hash_mismatch:" + key)
    inventory = json.loads(stable_bytes(root / pointer["validation"]["file"]))
    for row in inventory["assets"]:
        logical = root / row["file"]
        resolved = logical.resolve(strict=True)
        stat = resolved.stat()
        if str(resolved.relative_to(root)) != row["resolved_file"] or (stat.st_ino, stat.st_size, stat.st_mtime_ns) != (row["inode"], row["bytes"], row["mtime_ns"]):
            return False
    return True


def previous_assets(root):
    """Reuse content hashes only for unchanged identities verified by this code."""
    if FORCE:
        return []
    current = root / CATALOG / "current.json"
    if not current.exists():
        return []
    pointer = json.loads(stable_bytes(current))
    if pointer.get("publisher_source_sha256") != software_sha():
        return []
    locator = pointer["validation"]
    data = stable_bytes(root / locator["file"])
    if sha(data) != locator["sha256"]:
        raise ValueError("published_catalogue_hash_mismatch:validation")
    return json.loads(data)["assets"]


def refresh(root):
    root = root.resolve(strict=True)
    destination = root / CATALOG
    destination.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with locked(destination / "refresh.lock"):
        signature, source_inputs = inputs(root)
        if unchanged(root, signature):
            result = {"at_utc": now(), "status": "unchanged", "publisher": VERSION, "input_fingerprint": signature, "elapsed_seconds": time.monotonic() - started}
            atomic(destination / "refresh_status.json", result)
            return result
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        name = "snapshot_" + stamp + "_v4_" + signature[:12]
        building = destination / (".building_" + name)
        building.mkdir()
        (building / "input_manifests").mkdir()
        final = destination / name
        assets = Assets(root, previous_assets(root))
        pairs = {}
        manifests = []
        counts = collections.Counter()
        aliases = 0
        for ident, view, path, data in source_inputs:
            rows = [json.loads(line) for line in data.splitlines() if line.strip()]
            copied = building / "input_manifests" / (ident + ".jsonl")
            write(copied, data)
            recorded_copy = final / "input_manifests" / copied.name
            manifests.append({"id": ident, "view": view, "source": str(path.relative_to(root)), "immutable_copy": str(recorded_copy.relative_to(root)), "sha256": sha(data), "rows": len(rows)})
            for number, row in enumerate(rows, 1):
                if row.get("whole_figure_wrapper"):
                    raise ValueError("whole_figure_wrapper_not_allowed:" + ident + ":" + str(number))
                code, _ = assets.verify(row["code_file"], row["code_sha256"], primary=True, xml=True)
                image, pixels = assets.verify(row["image_file"], row["image_sha256"], primary=True, image=True)
                assets.declared_evidence(row)
                if ident.startswith("scientific_chart_vector_"):
                    assets.vector_plot_gate(row)
                if ident == "arxiv_author_native_incremental":
                    assets.incremental_gate(row)
                key = sha((row["code_sha256"] + pixels["pixels"]["rgba_sha256"]).encode("ascii"))
                counts[view] += 1
                if key not in pairs:
                    pairs[key] = {"id": key, "format": "drawio", "code_file": code, "code_sha256": row["code_sha256"], "image_file": image, "image_sha256": row["image_sha256"], "image_pixels": pixels["pixels"], "quality_views": [], "source_records": [], "evidence_profiles_are_not_interchangeable": True}
                else:
                    aliases += 1
                pair = pairs[key]
                if view not in pair["quality_views"]:
                    pair["quality_views"].append(view)
                pair["source_records"].append({"input_id": ident, "manifest": str(recorded_copy.relative_to(root)), "line": number, "source_id": row.get("id"), "source": row.get("source"), "paper": row.get("paper"), "quality_profile": row.get("profile", row.get("quality_profile", row.get("quality_state"))), "raw_source_pair_id": row.get("raw_source_pair_id", row.get("source_pair_sha256")), "complete_upstream_record_preserved_in_manifest": True})
        index = building / "pairs.jsonl"
        write(index, b"".join((json.dumps(pairs[key], ensure_ascii=True, sort_keys=True) + "\n").encode("ascii") for key in sorted(pairs)))
        unique_counts = collections.Counter(view for pair in pairs.values() for view in pair["quality_views"])
        summary = {
            "schema": "research_pair_catalogue_v4", "publisher": VERSION,
            "publisher_source_sha256": software_sha(),
            "at_utc": now(), "input_fingerprint": signature,
            "unique_code_PNG_pairs": len(pairs), "input_rows": sum(counts.values()),
            "unique_declared_source_requests": len({(ref["source"], ref.get("raw_source_pair_id") or ref["source_id"]) for pair in pairs.values() for ref in pair["source_records"]}),
            "multiple_native_versions_of_one_source_are_retained": True,
            "exact_code_RGBA_alias_rows": aliases,
            "input_rows_by_evidence_view": dict(counts), "unique_pairs_by_evidence_view": dict(unique_counts),
            "deduplication": "Exact drawio SHA256 plus exact RGBA PNG pixels and dimensions. No crop, resize, or visual tolerance.",
            "quality_notes": NOTES, "evidence_profiles_are_not_interchangeable": True,
            "input_manifests": manifests, "verified_payload_files": len(assets.records),
            "all_primary_payloads_actual_clean_files": True,
            "semantic_value_individually_certified": False,
            "new_conversions": 0, "new_QA": 0, "external_models": 0,
            "payload_root": str(root), "all_payloads_within_task_root": True,
            "goal_complete": False,
            "elapsed_seconds": time.monotonic() - started,
        }
        write(building / "summary.json", encoded(summary))
        write(building / "validation.json", encoded({"at_utc": now(), "assets": [assets.records[key] for key in sorted(assets.records)], "fast_noop_contract": "Revalidate when any logical/resolved path, inode, size, or mtime changes. Unchanged-stat content tampering requires --force."}))
        # Inputs are frozen above. Producers can publish a newer generation
        # while this immutable snapshot is built; the next poll consumes it.
        for path in building.rglob("*"):
            if path.is_file():
                path.chmod(0o444)
        os.replace(building, final)
        pointer = {"schema": "research_pairs_catalogue_pointer_v4", "publisher": VERSION, "publisher_source_sha256": software_sha(), "at_utc": now(), "snapshot": str(final.relative_to(root)), "input_fingerprint": signature, "unique_code_PNG_pairs": len(pairs), "input_rows_by_evidence_view": dict(counts), "unique_pairs_by_evidence_view": dict(unique_counts), "goal_complete": False}
        for key, filename in (("index", "pairs.jsonl"), ("summary", "summary.json"), ("validation", "validation.json")):
            file = final / filename
            pointer[key] = {"file": str(file.relative_to(root)), "sha256": sha(file.read_bytes()), "bytes": file.stat().st_size}
        pointer["index"]["rows"] = len(pairs)
        atomic(destination / "current.json", pointer)
        result = {"status": "published", **pointer, "elapsed_seconds": time.monotonic() - started}
        atomic(destination / "refresh_status.json", result)
        return result


def main(argv=None):
    global CATALOG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--catalog", default=CATALOG)
    parser.add_argument("--watch", action="store_true", help="Poll manifests until SIGTERM/SIGINT; errors exit nonzero.")
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--force", action="store_true", help="Rehash payloads even when manifest/stat identities are unchanged.")
    args = parser.parse_args(argv)
    selected = Path(args.catalog)
    if selected.is_absolute() or ".." in selected.parts or not str(selected).startswith("clean/research_pairs_catalog"):
        parser.error("catalog_must_be_a_task_owned_clean_catalog_path")
    CATALOG = str(selected)
    if args.interval <= 0:
        parser.error("--interval must be positive")
    if args.force:
        global unchanged, FORCE
        FORCE = True
        unchanged = lambda root, signature: False
    def stop(signum, frame):
        global STOP
        STOP = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        controller_lock = locked(args.root / CATALOG / "watch.lock") if args.watch else contextlib.nullcontext()
        (args.root / CATALOG).mkdir(parents=True, exist_ok=True)
        with controller_lock:
            while not STOP:
                result = refresh(args.root)
                print(json.dumps(result, ensure_ascii=True), flush=True)
                if not args.watch:
                    return 0
                atomic(args.root / CATALOG / "watch_status.json", {"at_utc": now(), "status": "running", "pid": os.getpid(), "last_refresh_status": result["status"], "input_fingerprint": result["input_fingerprint"], "interval_seconds": args.interval})
                deadline = time.monotonic() + args.interval
                while not STOP and time.monotonic() < deadline:
                    time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        stopped = {"at_utc": now(), "status": "stopped_after_current_refresh", "publisher": VERSION, "pid": os.getpid()}
        atomic(args.root / CATALOG / "watch_status.json", stopped)
        print(json.dumps(stopped), flush=True)
        return 0
    except BusyError as error:
        print(json.dumps({"at_utc": now(), "status": "busy", "error": str(error)}), file=sys.stderr)
        return 75
    except Exception as error:
        result = {"at_utc": now(), "status": "failed", "publisher": VERSION, "pid": os.getpid(), "error": type(error).__name__ + ":" + str(error), "publication_uses_atomic_pointer": True}
        try:
            atomic(args.root / CATALOG / "refresh_error.json", result)
            if args.watch:
                atomic(args.root / CATALOG / "watch_status.json", result)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
