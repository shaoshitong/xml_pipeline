"""Publish verified PNG shards to the private HF intake branch."""

import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import sys
import time

from huggingface_hub import CommitOperationAdd, HfApi
from huggingface_hub.errors import HfHubHTTPError
from requests import exceptions

from pack_original_shards import pack
from pull_original_shards import SHARD


REPO = "sst12345/png-to-editable-drawio-20261120"
BRANCH = "meanflow-hkust-intake-20261125"
DIRECTORY = "hkust-arxiv-originals"
COMPLETION = f"{DIRECTORY}/export-complete.json"
DATASET = {"repo_id": REPO, "repo_type": "dataset"}


def write_json(path, data):
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(data, indent=2) + "\n")
    pending.replace(path)


def remote_files(api, paths, revision=BRANCH):
    files = api.get_paths_info(**DATASET, paths=paths, expand=True, revision=revision)
    return {item.path: item for item in files}


def record(local, remote):
    if not remote.lfs or (local["bytes"], local["sha256"]) != (remote.size, remote.lfs.sha256):
        raise ValueError(f"HF checksum or byte count differs for {remote.path}")
    return {**local, "path": remote.path, "commit": remote.last_commit.oid}


def publish_ready(api, root, previous, stage):
    ready = [path for path in sorted((root / "ready").iterdir()) if SHARD.fullmatch(path.name)]
    pending = [path for path in ready if f"{DIRECTORY}/{path.name}.tar" not in previous][:6]
    if not pending:
        return
    local = {f"{DIRECTORY}/{shard.name}.tar": pack(shard, stage) for shard in pending}
    initial = remote_files(api, list(local))
    operations = [CommitOperationAdd(path_in_repo=path, path_or_fileobj=stage / info["name"])
                  for path, info in local.items() if path not in initial]
    for path, item in initial.items():
        record(local[path], item)
    revision = BRANCH
    if operations:
        revision = api.create_commit(**DATASET, revision=BRANCH, operations=operations,
                                     commit_message=f"Publish verified arXiv PNG shards {pending[0].name} to {pending[-1].name}").oid
    actual = remote_files(api, list(local), revision)
    for path, info in local.items():
        previous[path] = record(info, actual[path])
    write_json(root / "hf-published.json", previous)
    print(json.dumps({"commit": revision, "verified_shards": len(previous),
                      "verified_images": sum(item["images"] for item in previous.values())}), flush=True)


def finish(api, root, source, previous):
    files = sorted(previous.values(), key=lambda item: item["path"])
    if [Path(item["name"]).stem for item in files] != source["local_ready_shards"]:
        return False
    if source["images"] != sum(item["images"] for item in files):
        raise ValueError("Published image count disagrees with the verified local count")
    ids = [item["path"] for item in files]
    actual = remote_files(api, ids)
    for item in files:
        record(item, actual[item["path"]])
    data = {"branch": BRANCH, "candidate_paths": source["source_shortlist_processed"],
            "images": source["images"], "png_bytes": source["png_bytes"],
            "screen_counts": source["source_screen_counts"], "shards": files}
    output = root / "export-complete.json"
    write_json(output, data)
    existing = remote_files(api, [COMPLETION]).get(COMPLETION)
    if not existing:
        revision = api.upload_file(**DATASET, revision=BRANCH, path_in_repo=COMPLETION,
                                   path_or_fileobj=output, commit_message="Publish arXiv export completion manifest").oid
        existing = remote_files(api, [COMPLETION], revision)[COMPLETION]
    git_blob = sha1(f"blob {output.stat().st_size}\0".encode() + output.read_bytes()).hexdigest()
    if existing.blob_id != git_blob and (not existing.lfs or existing.lfs.sha256 != sha256(output.read_bytes()).hexdigest()):
        raise ValueError("Remote completion manifest checksum differs")
    print(json.dumps({"complete": existing.last_commit.oid, "shards": len(files),
                      "images": source["images"]}), flush=True)
    return True


def run(root, api):
    if api.whoami()["name"] != "sst12345" or not api.dataset_info(REPO, revision=BRANCH).private:
        raise ValueError("Unexpected HF account or repository visibility")
    stage = root / "hf-stage" / DIRECTORY
    stage.mkdir(parents=True, exist_ok=True)
    ledger = root / "hf-published.json"
    previous = json.loads(ledger.read_text()) if ledger.exists() else {}
    while True:
        try:
            publish_ready(api, root, previous, stage)
            progress = root / "progress.json"
            source = json.loads(progress.read_text()) if progress.exists() else {}
            if source.get("source_phase") == "complete" and finish(api, root, source, previous):
                return
        except HfHubHTTPError as exc:
            status = exc.response.status_code
            if status not in {408, 409, 429, 500, 502, 503, 504}:
                raise
            print(f"Retrying HF request after HTTP {status}", flush=True)
        except (exceptions.ConnectionError, exceptions.Timeout) as exc:
            print(f"Retrying HF request after {type(exc).__name__}", flush=True)
        time.sleep(6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staging", type=Path)
    args = parser.parse_args()
    token = sys.stdin.read().strip()
    if not re.fullmatch(r"hf_[A-Za-z0-9]+", token):
        parser.error("Supply the temporary HF token on stdin")
    run(args.staging, HfApi(token=token))


if __name__ == "__main__":
    main()
