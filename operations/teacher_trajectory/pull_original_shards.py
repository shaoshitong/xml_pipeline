"""Pull private HKUST PNG shards and expose only checksum-verified directories."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import time


SHARD = re.compile(r"shard-[0-9]{5}")
DIGEST = re.compile(r"[0-9a-f]{64}")


def verify(shard):
    receipt = json.loads((shard / "receipt.json").read_text())
    manifest = (shard / "manifest.jsonl").read_bytes()
    if sha256(manifest).hexdigest() != receipt["manifest_sha256"]:
        raise ValueError("Manifest checksum differs")
    entries = [json.loads(line) for line in manifest.splitlines()]
    if len(entries) != receipt["images"]:
        raise ValueError("Manifest count differs")
    total_bytes = 0
    names = set()
    for row in entries:
        digest = row["sha256"]
        if not DIGEST.fullmatch(digest) or row["case_id"] != "hkust-" + digest[:24]:
            raise ValueError("Unexpected image identity")
        name = "images/" + row["case_id"] + ".png"
        if row["file"] != name or name in names:
            raise ValueError("Unexpected or repeated image path")
        names.add(name)
        image = shard / name
        if image.is_symlink():
            raise ValueError("Unexpected symbolic link")
        with image.open("rb") as stream:
            if sha256(stream.read()).hexdigest() != digest:
                raise ValueError("Original PNG checksum differs")
        total_bytes += image.stat().st_size
    if total_bytes != receipt["png_bytes"]:
        raise ValueError("Total PNG bytes differ")
    return receipt


def pull(args):
    incoming, ready = args.destination / "incoming", args.destination / "ready"
    incoming.mkdir(parents=True, exist_ok=True)
    ready.mkdir(parents=True, exist_ok=True)
    ssh = shlex.split(args.ssh)
    known = {p.name: verify(p) for p in sorted(ready.glob("shard-*"))}
    checksum = set()

    def download(name):
        extra = ["--checksum"] if name in checksum else []
        subprocess.run(
            ["rsync", "-a", "--partial", *extra, "-e", args.ssh,
             f"{args.host}:{args.source / name}", str(incoming) + "/"],
            check=True, timeout=1800)
        receipt = verify(incoming / name)
        (incoming / name).rename(ready / name)
        return receipt

    def write_progress(progress):
        complete = progress["phase"] == "complete" and set(known) == set(progress["ready_shards"])
        images = sum(item["images"] for item in known.values())
        if complete and images != progress["screen_counts"]["accepted"]:
            raise ValueError("Verified image count disagrees with source screening count")
        report = {"source_phase": "complete" if complete else "transferring",
                  "local_ready_shards": sorted(known),
                  "images": images,
                  "png_bytes": sum(item["png_bytes"] for item in known.values()),
                  "source_ready_shards": len(progress["ready_shards"]),
                  "source_screen_counts": progress["screen_counts"],
                  "source_shortlist_processed": progress["shortlist_processed"]}
        pending = args.destination / "progress.tmp"
        pending.write_text(json.dumps(report, indent=2) + "\n")
        pending.replace(args.destination / "progress.json")
        return complete

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while True:
            try:
                progress = json.loads(subprocess.check_output(
                    [*ssh, args.host, "cat " + shlex.quote(str(args.source / "progress.json"))],
                    timeout=30))
                names = [name for name in progress["ready_shards"] if name not in known]
                if any(not SHARD.fullmatch(name) for name in names):
                    raise ValueError("Unexpected shard name")
                if write_progress(progress):
                    return
                transfers = {pool.submit(download, name): name for name in names}
                for future in as_completed(transfers):
                    name = transfers[future]
                    try:
                        known[name] = future.result()
                    except (subprocess.SubprocessError, OSError, ValueError) as exc:
                        if isinstance(exc, ValueError):
                            checksum.add(name)
                        print(f"Retrying {name}: {exc}", flush=True)
                        continue
                    print(json.dumps({"ready": str(ready / name), **known[name]}), flush=True)
                    if write_progress(progress):
                        return
            except (subprocess.SubprocessError, OSError, ValueError) as exc:
                print(f"Retrying private transfer: {exc}", flush=True)
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh", required=True, help="SSH command and options, without host")
    parser.add_argument("--host", required=True)
    parser.add_argument("--source", type=PurePosixPath, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    pull(parser.parse_args())


if __name__ == "__main__":
    main()
