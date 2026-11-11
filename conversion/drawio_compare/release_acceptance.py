"""Audit HKUST3 artifacts and exercise the blind case service against the installed CLI."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import mkdtemp


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "operations"))
import serve_dpsk_blind_render_v1 as service


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def same_artifacts(left, right):
    def hashes(root):
        return {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob("*") if p.is_file()}

    left_hashes, right_hashes = hashes(left), hashes(right)
    changed = sorted(str(p) for p in left_hashes.keys() | right_hashes.keys()
                     if left_hashes.get(p) != right_hashes.get(p))
    if changed:
        raise ValueError(f"replay changed {len(changed)} artifacts: {changed[:10]}")
    return len(left_hashes)


def audit_suite(suite):
    expected = {"id_only", "wrapping", "redundant_defaults", "split_merge", "reverse",
                "branch_removed", "table_grid", "panel_shift", "free_edge", "official_repair",
                "edge_parent_repair", "multi_page_hidden", "fractional_scale",
                "pilot_002", "pilot_012", "pilot_013", "pilot_017", "pilot_022"}
    if set(read(suite / "acceptance.json")) != expected:
        raise ValueError("acceptance suite is incomplete")
    proof_count = 0
    for case in sorted(expected):
        folder = suite / case
        report = read(folder / "diff.json")
        for side in ("A", "B"):
            proof = report["normalization"][side]
            normalized = folder / f"{side}_hat.xml"
            assert hashlib.sha256(normalized.read_bytes()).hexdigest() == proof["sha256"]
            coordinates = read(folder / f"{side}_coordinates.json")
            cell_ids = read(folder / f"{side}_cell_ids.json")
            assert {(p["page"], c["original_id"]) for p in coordinates for c in p["cells"]} == {
                (c["page"], c["original_id"]) for c in cell_ids
            }
            for page in proof["pages"]:
                assert all(page[k] for k in ("pixel_exact", "native_cell_state_exact",
                                              "native_codec_exact", "byte_idempotent"))
                assert page["original_pixel_sha256"] == page["normalized_pixel_sha256"]
                proof_count += 1
        for page in report["pages"]:
            assert (folder / page["overlay"]).stat().st_size
            for d in page["diagnostics"]:
                if d.get("crop"):
                    assert (folder / d["crop"]["path"]).stat().st_size
    return {"cases": len(expected), "source_page_proofs": proof_count}


def audit_failure_attribution():
    sys.path.insert(0, str(REPO / "conversion/scripts"))
    from acceptance import explicit_defaults, flow
    from cli import normalization_error
    from model import decode

    source = explicit_defaults(flow()).decode()
    diagram = decode(source.encode())
    assert diagram.simplifications
    # Inject a failed comparison whose intermediate still preserves the source.
    preserves = lambda intermediate: 'visible="1"' in intermediate
    assert "omit_native_defaults (cells" in str(
        normalization_error(source, 1, diagram.simplifications, preserves, "native cell state"))
    assert "decode_and_reserialize" in str(
        normalization_error(source, 1, diagram.simplifications, lambda _: False, "native cell state"))


def test_skill(fixture, out):
    case = out / "skill_case"
    case.mkdir()
    for source, name in (("input-A.drawio", "seed.drawio"), ("input-B.drawio", "after.drawio"),
                         ("page_001_A.png", "target.png")):
        shutil.copyfile(fixture / source, case / name)
    skill = REPO / "operations/dpsk_skills/blind-diagram-refinement"
    entry = case / "visual_check.py"
    shutil.copyfile(skill / "visual_check.py", entry)
    shutil.copyfile(skill / "SKILL.md", case / "SKILL.md")
    remote = mkdtemp(prefix="drawio_compare_skill_", dir=Path(service.R) / "conversion")

    # This harness runs on HKUST3. Replace only transport so the file queue,
    # broker commands, native renderer and CLI execute as usual.
    def run_local(*args):
        return subprocess.run(args, check=True, text=True, capture_output=True, timeout=135).stdout

    def copy_local(src, dst):
        return shutil.copyfile(str(src).removeprefix("hkust3:"), str(dst).removeprefix("hkust3:"))

    service.ssh, service.scp = run_local, copy_local
    argv = [str(case), remote, "--limit", "2", "--idle-timeout", "90",
            "--drawio-compare", str(REPO / "conversion/scripts/drawio-compare")]
    with ThreadPoolExecutor(max_workers=1) as pool:
        broker = pool.submit(service.main, argv)

        def call(*args, succeeds=True):
            proc = subprocess.run([sys.executable, str(entry), *args], cwd=case,
                                  text=True, capture_output=True, timeout=70)
            result = json.loads(proc.stdout)
            if proc.returncode != int(not succeeds) or result.get("ok") != succeeds:
                raise ValueError(f"unexpected skill reply: {result} {proc.stderr}")
            return result

        try:
            assert call("seed.drawio")["native_gate"]
            assert call("after.drawio", "--against", "seed.drawio")["native_gate"]
            reply = call("compare", "seed.drawio", "after.drawio")
            report = read(case / reply["report_path"])
            page, = report["pages"]
            assert reply["mode"] == report["mode"] == "revision"
            assert page["render"]["pixel_exact"] and len(page["diagnostics"]) == 2
            for d in page["diagnostics"]:
                assert d["kind"] == "edge_binding_changed" and "before" in d and "after" in d
                assert d["edit_probe"]["status"] == "different_motion_class"
                assert d["edit_probe"]["a"]["status"] == "moved"
                assert d["edit_probe"]["b"]["status"] == "stationary"
            assert all((case / p).stat().st_size for p in reply["overlays"])
            shutil.copyfile(case / "seed.drawio", case / "unmeasured.drawio")
            denied = call("compare", "unmeasured.drawio", "after.drawio", succeeds=False)
            assert "previously rendered" in denied["error"]
            return {"report": reply["report_path"], "case": str(case), "remote_run": remote,
                    "summary": reply["summary"], "transport": "local HKUST3",
                    "unmeasured_checkpoint_denied": True}
        finally:
            (case / "service.stop").touch()
            broker.result(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True, help="completed acceptance.py output")
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = audit_suite(args.suite)
    print("suite audit passed", result, flush=True)
    audit_failure_attribution()
    result["failed_rule_attribution"] = True

    a = args.fixtures / "outputs/random100_new540_final_seed20261103100_v1/pairs/022/author.drawio"
    b = args.fixtures / "outputs/dpsk_img2code_max_pilot_20261111/022/round1.drawio"
    replay = out / "pilot_022_replay"
    subprocess.run([sys.executable, str(REPO / "conversion/scripts/drawio-compare"), str(a), str(b),
                    "--mode", "reference", "--out", str(replay)], check=True, timeout=135)
    result["deterministic_artifacts"] = same_artifacts(args.suite / "pilot_022", replay)
    print("deterministic replay passed", result["deterministic_artifacts"], flush=True)

    result["skill"] = test_skill(args.suite / "free_edge", out)
    receipt = out / "release_acceptance.json"
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("release acceptance passed", receipt, flush=True)


if __name__ == "__main__":
    main()
