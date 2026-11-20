"""Assemble disjoint teacher snapshots without expanding their lossless DAGs."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


def digest(path):
    result = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 ** 2), b""):
            result.update(block)
    return result.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def decisions(part, snapshot):
    root = Path(part["snapshot"])
    manifest = root / "files.json"
    assert digest(manifest) == snapshot["files_manifest_sha256"]
    files = {row["file"]: row["sha256"] for row in json.loads(manifest.read_text())}
    contexts = {}
    for episode in snapshot["episodes"]:
        path = root / "audits" / episode / "context.json"
        assert digest(path) == files[str(path.relative_to(root))]
        report = json.loads(path.read_text())
        contexts.update({(row["episode"], row["call_id"]):
                         {**row, "native_context": report["native_context"]} for row in report["records"]})
    index = root / "run-01/sft-all-decisions.jsonl"
    assert digest(index) == files[str(index.relative_to(root))]
    seen = set()
    with index.open() as stream:
        for line in stream:
            row = json.loads(line)
            key = row["episode"], row["call_id"]
            assert key not in seen and key in contexts
            assert row["target"] == "this completion only" and row["reviewer_is_observation"]
            seen.add(key)
            yield {**row, "decision_id": f"{key[0]}:{key[1]}", "data_part": part["path"],
                   "student_context": contexts[key]}
    assert seen == set(contexts) and len(seen) == snapshot["counts"]["generator_decisions"]


def artifact(record):
    assert Path(record["file"]).stat().st_size == record["bytes"]
    return {key: record[key] for key in ("path", "sha256", "bytes")}


def assemble(args):
    plan = json.loads(args.plan.read_text())
    parts = plan["parts"]
    snapshots = [json.loads((Path(part["snapshot"]) / "snapshot.json").read_text()) for part in parts]
    episodes = [episode for snapshot in snapshots for episode in snapshot["episodes"]]
    if len(episodes) != args.expected_episodes or len(episodes) != len(set(episodes)):
        raise ValueError("Data parts must have disjoint episodes and cover the requested total")
    args.output.mkdir(parents=True, exist_ok=True)
    counts, sources, metadata, records = Counter(), set(), [], []
    temporary = args.output / "sft-all-decisions.jsonl.tmp"
    with temporary.open("w") as stream:
        for part, snapshot in zip(parts, snapshots):
            counts.update(snapshot["counts"])
            for row in decisions(part, snapshot):
                context = row["student_context"]
                counts["student_fits_64k"] += context["fits_64k"]
                counts["student_fits_native_context"] += context["fits_native_context"]
                counts["eligible_fits_native_context"] += row["supervision_eligible"] and context["fits_native_context"]
                stream.write(json.dumps(row) + "\n")
            for episode in snapshot["episodes"]:
                folder = Path(part["snapshot"]) / "run-01/episodes" / episode
                protocol = json.loads((folder / "protocol.json").read_text())
                source = protocol["source"]
                render = json.loads((folder / "render2.json").read_text())
                sources.add(protocol["source_commit"])
                records.append({"episode": episode, "paper": source["paper"],
                                "arxiv_url": source["arxiv_url"], "reference_sha256": source["reference_sha256"],
                                "data_part": part["path"], "extract_dir": part["extract_dir"],
                                "final_xml_sha256": render["xml_sha256"], "final_png_sha256": render["png_sha256"],
                                "fidelity_verified": False})
            metadata.append({**artifact(part), "extract_dir": part["extract_dir"],
                             "episodes": snapshot["episodes"], "counts": snapshot["counts"],
                             "snapshot_source_commit": snapshot["source_commit"]})
    temporary.replace(args.output / "sft-all-decisions.jsonl")
    with (args.output / "episodes.jsonl").open("w") as stream:
        for row in records:
            stream.write(json.dumps(row) + "\n")
    (args.output / "EXTRACT_DATA.txt").write_text(
        "Download and extract on the Linux data/training host; no Mac staging is required.\n"
        f"hf download {args.repo_id} --repo-type dataset --local-dir drawio-release\n"
        "cd drawio-release\npython -m pip install zstandard\npython - <<'PY'\n"
        "import json,pathlib,tarfile,zstandard\n"
        "release=json.loads(pathlib.Path('release-manifest.json').read_text())\n"
        "for part in release['data']['parts']:\n"
        "    root=pathlib.Path(part['extract_dir']);root.mkdir(exist_ok=True)\n"
        "    with open(part['path'],'rb') as raw, zstandard.ZstdDecompressor().stream_reader(raw) as stream:\n"
        "        with tarfile.open(fileobj=stream,mode='r|') as archive:archive.extractall(root,filter='data')\n"
        "PY\n\nEach part has its own run-01/archive/ledger.sqlite and complete reachable object DAG.\n"
        "Use data_part to choose that root before calling export_sft.materialize(store, row).\n"
        "decision_id is episode:local_call_id. Raw call IDs are preserved; they can repeat across parts.\n"
        "Each SFT row supervises one actual generator response. Reviewer messages remain observations.\n"
        "Keep ineligible and overlength rows for audit; do not silently truncate them or train excluded targets.\n")
    code = args.output / "code.tar.gz"
    artifacts = [{"path": code.name, "sha256": digest(code), "bytes": code.stat().st_size},
                 artifact(plan["runtime"]), *[artifact(part) for part in parts]]
    indexes = [{"path": name, "sha256": digest(args.output / name), "bytes": (args.output / name).stat().st_size}
               for name in ("sft-all-decisions.jsonl", "episodes.jsonl")]
    release = {"repo": args.repo_id, "private": True, "source_commit": args.source_commit,
               "artifacts": artifacts, "indexes": indexes,
               "data": {"frozen_audited_episodes": len(episodes), "counts": dict(counts), "parts": metadata,
                        "gold_xml_included": False, "visual_fidelity_certified": False,
                        "history_and_images": "Lossless content-addressed DAGs; no expansion or truncation",
                        "collector_source_commits": sorted(sources)},
               "runtime": json.loads((args.output / "runtime-contract.json").read_text()),
               "workflow": {"generator": "DeepSeek real DSH", "reviewer": "independent DeepSeek image review",
                            "reviewer_trained": False, "generator_rounds": 2, "gold_diff_feedback": False,
                            "sft_unit": "One actual generator API completion, with its full observed context"}}
    save(args.output / "release-manifest.json", release)
    files = [{**row, "file": str(Path(part["file"]))} for row, part in zip(artifacts[2:], parts)]
    files = [{**artifacts[0], "file": str(code)},
             {**artifacts[1], "file": plan["runtime"]["file"]}, *files]
    for name in [*(row["path"] for row in indexes), "EXTRACT_DATA.txt", "RUN_ONE.txt",
                 "rollout-cpu-requirements.txt", "runtime-contract.json", "release-manifest.json"]:
        path = args.output / name
        files.append({"path": name, "file": str(path), "sha256": digest(path), "bytes": path.stat().st_size})
    (args.output / "SHA256SUMS").write_text("".join(row["sha256"] + "  " + row["path"] + "\n" for row in files))
    path = args.output / "SHA256SUMS"
    files.append({"path": path.name, "file": str(path), "sha256": digest(path), "bytes": path.stat().st_size})
    files.sort(key=lambda row: row["path"] == "release-manifest.json")
    save(args.output / "upload-release-files.json", files)
    print(json.dumps({"episodes": len(episodes), "parts": len(parts), "counts": dict(counts),
                      "model_calls": 0, "upload_started": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--expected-episodes", type=int, default=200)
    assemble(parser.parse_args())


if __name__ == "__main__":
    main()
