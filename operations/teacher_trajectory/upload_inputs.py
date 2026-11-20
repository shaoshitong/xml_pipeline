"""Upload reference images to a separate prefix, preserving the existing release."""

import argparse
from functools import partial
from hashlib import sha1, sha256
import json
from pathlib import Path
import sys
import threading
import time

from huggingface_hub import HfApi, configure_http_backend

from publish_hf import UploadSession


def signature(item):
    return item.size, item.lfs.sha256 if item.lfs else item.blob_id


def publish(args):
    token = sys.stdin.readline().strip()
    assert token.startswith("hf_")
    configure_http_backend(partial(UploadSession, args.proxy, bool(args.proxy), {},
                                   threading.Lock(), args.audit / "network-state.json"))
    api = HfApi(token=token)
    assert api.whoami()["name"] == args.repo_id.split("/")[0]
    before = api.repo_info(args.repo_id, repo_type="dataset", files_metadata=True)
    assert before.private and not any(item.rfilename.startswith(args.prefix + "/") for item in before.siblings)
    baseline = {item.rfilename: signature(item) for item in before.siblings}
    pilot = [json.loads(line) for line in (args.folder / "pilot.jsonl").read_text().splitlines()]
    commit = api.upload_folder(repo_id=args.repo_id, repo_type="dataset", folder_path=args.folder,
                               path_in_repo=args.prefix, allow_patterns=[row["file"] for row in pilot] + ["pilot.jsonl"],
                               commit_message="Publish five verified unused reference images")
    print(json.dumps({"pilot_ready": True, "repo_id": args.repo_id, "revision": commit.oid,
                      "files": [args.prefix + "/" + row["file"] for row in pilot]}), flush=True)
    (args.audit / "pilot-upload.json").write_text(json.dumps({"revision": commit.oid, "files": pilot}, indent=2) + "\n")
    commit = api.upload_folder(repo_id=args.repo_id, repo_type="dataset", folder_path=args.folder,
                               path_in_repo=args.prefix, commit_message="Publish all verified unused reference inputs")
    after = api.repo_info(args.repo_id, repo_type="dataset", revision=commit.oid, files_metadata=True)
    assert after.private
    remote = {item.rfilename: item for item in after.siblings}
    assert all(signature(remote[name]) == value for name, value in baseline.items())
    files = json.loads((args.audit / "public-files.json").read_text())
    for record in files:
        path = args.folder / record["file"]
        raw = path.read_bytes()
        assert sha256(raw).hexdigest() == record["sha256"]
        item = remote[args.prefix + "/" + record["file"]]
        assert item.size == record["bytes"]
        expected = record["sha256"] if item.lfs else sha1(("blob " + str(len(raw))).encode() + b"\0" + raw).hexdigest()
        assert signature(item)[1] == expected
    summary = json.loads((args.folder / "exclusion-summary.json").read_text())
    result = {"at": time.time(), "repo_id": args.repo_id, "private": after.private,
              "revision": commit.oid, "prefix": args.prefix, "verified_files": len(files),
              "verified_image_count": summary["verified_image_count"], "total_bytes": sum(x["bytes"] for x in files),
              "prior_release_files_preserved": len(baseline), "pilot_revision": json.loads((args.audit / "pilot-upload.json").read_text())["revision"],
              "pilot_files": [args.prefix + "/" + row["file"] for row in pilot],
              "exclusion_summary": summary, "temporary_token_revocation_pending": True}
    (args.audit / "hf-upload-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("folder", "audit"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--proxy")
    publish(parser.parse_args())


if __name__ == "__main__":
    main()
