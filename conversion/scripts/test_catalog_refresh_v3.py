#!/usr/bin/env python3
"""Small filesystem integration fixtures; no dataset download or remote access."""
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from PIL import Image, PngImagePlugin

FILE = Path(__file__).with_name("research_catalog_refresh_v3.py")
SPEC = importlib.util.spec_from_file_location("publisher", FILE)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clean = self.root / "clean"
        self.clean.mkdir()
        self.manifests = {}
        for ident, view, relative in publisher.INPUTS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
            self.manifests[ident] = path
        main = self.clean / "curated_fixture" / "main.jsonl"
        main.parent.mkdir()
        self.manifests["main"] = main
        self.main = self.pair("main", "red")
        self.frozen = self.pair("frozen", "blue")
        self.rows("main", [self.main])
        self.rows("arxiv_author_native_frozen", [self.frozen])

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return relative, publisher.sha(data)

    def pair(self, ident, color):
        code = ('<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" value="' + ident + '" vertex="1" parent="1"><mxGeometry x="1" y="1" width="20" height="10" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>').encode()
        buffer = io.BytesIO()
        Image.new("RGBA", (24, 16), color).save(buffer, format="PNG")
        code_file, code_sha = self.payload("clean/fixture/" + ident + "/diagram.drawio", code)
        image_file, image_sha = self.payload("clean/fixture/" + ident + "/image.png", buffer.getvalue())
        return {"id": ident, "source": "fixture_scientific_diagram", "code_file": code_file, "code_sha256": code_sha, "image_file": image_file, "image_sha256": image_sha, "whole_figure_wrapper": False}

    def incremental(self, ident="new"):
        row = self.pair(ident, "green")
        row.update(profile="author_native_source_replay", quality_state="verified_under_declared_author_native_source_replay_contract", paired_code_XML_bytes_equal_original_author_XML=True, original_PDF_fidelity="review_not_certified", provider_original_reference_aligned=False, legacy_full8_qualified=False, original_author_XML=row["code_file"], original_author_XML_sha256=row["code_sha256"], auxiliary_preexisting_native_PNG=row["image_file"], auxiliary_preexisting_native_PNG_sha256=row["image_sha256"], font_dependencies=[])
        base = "clean/fixture/" + ident + "/"
        for name, digest, content in (
            ("original_PDF_file", "original_PDF_sha256", b"%PDF-small-fixture"),
            ("asset_audit", "asset_audit_sha256", b'{"issues":[]}'),
            ("old_native_render_edit_proof", "old_native_render_edit_proof_sha256", publisher.encoded({"edit_probe": {"mutation_actual_PNG_changed": True, "restored_actual_PNG_exact": True}})),
        ):
            row[name], row[digest] = self.payload(base + name, content)
        proof = {key: True for key in ("ok", "normalized_model_exact_restore", "mutation_normalized_model_changed", "mutation_actual_RGBA_changed", "restored_actual_RGBA_exact", "restored_PNG_bytes_exact")}
        proof.update(source_XML_sha256=row["code_sha256"], source_official_PNG_sha256=row["image_sha256"], font_observations={"all_physical_font_bytes_pinned": True, "font_assets": []})
        row["native_replay_proof"], row["native_replay_proof_sha256"] = self.payload(base + "proof.json", publisher.encoded(proof))
        return row

    def rows(self, ident, rows):
        path = self.manifests[ident]
        path.write_bytes(b"".join((json.dumps(row) + "\n").encode() for row in rows))
        if ident == "main":
            pointer = self.root / publisher.CURATION
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_bytes(publisher.encoded({"views": {"paired_priority_complex": {"file": str(path.relative_to(self.root)), "sha256": publisher.sha(path.read_bytes())}}}))

    def current(self):
        return json.loads((self.root / publisher.CATALOG / "current.json").read_bytes())

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(FILE), "--root", str(self.root), *args], capture_output=True, text=True)

    def test_incremental_addition_dynamic_main_and_quality_profiles(self):
        first = publisher.refresh(self.root)
        self.assertEqual(first["unique_code_PNG_pairs"], 2)
        row = self.incremental()
        self.rows("arxiv_author_native_incremental", [row])
        # Same exact payload with another quality view merges without promoting
        # the source-replay view into original-PDF or full8 qualification.
        self.rows("scientific_chart_provider_original", [self.main])
        extra = self.pair("new_main", "yellow")
        self.rows("main", [self.main, extra])
        second = publisher.refresh(self.root)
        self.assertEqual(second["unique_code_PNG_pairs"], 4)
        summary = json.loads((self.root / second["summary"]["file"]).read_bytes())
        self.assertEqual(summary["input_rows_by_evidence_view"]["arxiv_author_native_source_replay"], 2)
        pairs = [json.loads(line) for line in (self.root / second["index"]["file"]).read_bytes().splitlines()]
        added = next(pair for pair in pairs if pair["code_sha256"] == row["code_sha256"])
        self.assertEqual(added["quality_views"], ["arxiv_author_native_source_replay"])
        source = added["source_records"][0]
        copied_row = json.loads((self.root / source["manifest"]).read_bytes().splitlines()[source["line"] - 1])
        self.assertEqual(copied_row, row)
        main_pair = next(pair for pair in pairs if pair["code_sha256"] == self.main["code_sha256"])
        self.assertCountEqual(main_pair["quality_views"], ["paper_diagrams_and_posters_full8", "scientific_chart_provider_original"])

    def test_unchanged_inputs_do_not_create_snapshot(self):
        first = publisher.refresh(self.root)
        second = publisher.refresh(self.root)
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(self.current()["snapshot"], first["snapshot"])
        self.assertEqual(len(list((self.root / publisher.CATALOG).glob("snapshot_*"))), 1)

    def test_PNG_encoding_aliases_merge_only_with_exact_RGBA(self):
        alias = dict(self.main, id="same_pixels_different_PNG_encoding")
        buffer = io.BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("fixture", "different encoded bytes, same pixels")
        Image.new("RGBA", (24, 16), "red").save(buffer, format="PNG", pnginfo=metadata)
        alias["image_file"], alias["image_sha256"] = self.payload("clean/fixture/alias.png", buffer.getvalue())
        self.assertNotEqual(alias["image_sha256"], self.main["image_sha256"])
        self.rows("scientific_chart_provider_original", [alias])
        result = publisher.refresh(self.root)
        self.assertEqual(result["unique_code_PNG_pairs"], 2)
        summary = json.loads((self.root / result["summary"]["file"]).read_bytes())
        self.assertEqual(summary["exact_code_RGBA_alias_rows"], 1)

    def test_changed_payload_rejected_without_moving_current(self):
        first = publisher.refresh(self.root)
        path = self.root / self.main["image_file"]
        path.write_bytes(b"corrupt PNG")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("payload_hash_mismatch", result.stderr)
        self.assertEqual(self.current()["snapshot"], first["snapshot"])

    def test_corrupt_incremental_evidence_refused(self):
        first = publisher.refresh(self.root)
        row = self.incremental()
        (self.root / row["native_replay_proof"]).write_bytes(b"{}")
        self.rows("arxiv_author_native_incremental", [row])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("payload_hash_mismatch", result.stderr)
        self.assertEqual(self.current()["snapshot"], first["snapshot"])

    def test_force_rehash_detects_same_stat_content_tampering(self):
        first = publisher.refresh(self.root)
        path = self.root / self.main["code_file"]
        original = path.stat()
        path.write_bytes(path.read_bytes().replace(b'value="main"', b'value="pain"'))
        os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
        result = self.run_cli("--force")
        self.assertEqual(result.returncode, 1)
        self.assertIn("payload_hash_mismatch", result.stderr)
        self.assertEqual(self.current()["snapshot"], first["snapshot"])

    def test_false_native_edit_proof_cannot_be_rehashed_into_acceptance(self):
        row = self.incremental()
        proof_path = self.root / row["native_replay_proof"]
        proof = json.loads(proof_path.read_bytes())
        proof["restored_actual_RGBA_exact"] = False
        proof_path.write_bytes(publisher.encoded(proof))
        row["native_replay_proof_sha256"] = publisher.sha(proof_path.read_bytes())
        self.rows("arxiv_author_native_incremental", [row])
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("incremental_native_proof_gate", result.stderr)
        self.assertFalse((self.root / publisher.CATALOG / "current.json").exists())

    def test_concurrent_publisher_lock_is_explicit_and_non_mutating(self):
        first = publisher.refresh(self.root)
        with (self.root / publisher.CATALOG / "refresh.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_cli()
        self.assertEqual(result.returncode, 75)
        self.assertIn('"status": "busy"', result.stderr)
        self.assertEqual(self.current()["snapshot"], first["snapshot"])

    def test_watch_picks_up_new_manifest_and_drains_on_term(self):
        process = subprocess.Popen([sys.executable, str(FILE), "--root", str(self.root), "--watch", "--interval", "0.05"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 8
            while not (self.root / publisher.CATALOG / "current.json").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(self.current()["unique_code_PNG_pairs"], 2)
            self.rows("arxiv_author_native_incremental", [self.incremental()])
            while self.current()["unique_code_PNG_pairs"] != 3 and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(self.current()["unique_code_PNG_pairs"], 3)
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertIn("stopped_after_current_refresh", stdout)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
