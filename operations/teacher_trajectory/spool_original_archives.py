"""Keep a bounded local spool of original-image archives for HF publication."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import fcntl
from hashlib import file_digest
import json
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import time

from pull_original_shards import SHARD


def read_json(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def write_json(path, data):
    partial = path.with_suffix(".tmp")
    partial.write_text(json.dumps(data, indent=2) + "\n")
    partial.replace(path)


def remote(args, command):
    return subprocess.check_output(
        [*shlex.split(args.ssh), args.host, shlex.join(map(str, command))], timeout=1800
    ).decode()


def prepare(args, names):
    result = remote(args, [
        "flock", "-x", args.source / "archive_prepare.lock",
        args.remote_python, args.source / "source/pack_original_shards.py",
        "--source", args.source / "export", "--out", args.source / "archives", *names,
    ])
    receipts = {Path(r["name"]).stem: r for r in map(json.loads, result.splitlines())}
    if set(receipts) != set(names):
        raise ValueError("Remote archive names differ from the requested shards")
    for name, receipt in receipts.items():
        write_json(args.out / "receipts" / f"{name}.json", receipt)


def checksum(archive):
    with archive.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def download(args, name, receipt):
    archive = args.out / "ready" / f"{name}.tar"
    if archive.is_file():
        return
    partial = args.out / "incoming" / archive.name
    subprocess.run(
        ["rsync", "-a", "--partial", "--checksum", "-e", args.ssh,
         f"{args.host}:{args.source / 'archives' / archive.name}", str(partial)],
        check=True, timeout=1800,
    )
    if (partial.stat().st_size, checksum(partial)) != (receipt["bytes"], receipt["sha256"]):
        raise ValueError(f"Transferred archive checksum differs for {name}")
    partial.replace(archive)
    print(json.dumps({"ready": name, **receipt}), flush=True)


def release_published(args, receipts):
    published = read_json(args.out / "hf-published.json")
    for item in published.values():
        name = Path(item["name"]).stem
        receipt = receipts.get(name)
        if not receipt or (item["bytes"], item["sha256"]) != (receipt["bytes"], receipt["sha256"]):
            raise ValueError(f"Published archive checksum differs for {name}")
        (args.out / "ready" / f"{name}.tar").unlink(missing_ok=True)
    return {Path(row["name"]).stem for row in published.values()}


def available(args, pending, receipts):
    total = 0
    names = []
    for name in pending:
        size = receipts[name]["bytes"]
        if names and total + size > args.spool_bytes:
            break
        total += size
        names.append(name)
    return names


def run(args):
    for name in ("ready", "incoming", "receipts"):
        (args.out / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while True:
            if not read_json(args.after).get("commit"):
                time.sleep(15)
                continue
            try:
                source = json.loads(remote(args, ["cat", args.source / "export/progress.json"]))
                names = source["ready_shards"]
                if any(not SHARD.fullmatch(name) for name in names):
                    raise ValueError("Source progress contains an invalid shard name")
                receipts = {p.stem: read_json(p) for p in (args.out / "receipts").glob("shard-*.json")}
                done = release_published(args, receipts)
                pending = [name for name in names if name not in done][:args.spool_shards]
                missing = [name for name in pending if name not in receipts]
                if missing:
                    prepare(args, missing)
                    receipts.update({name: read_json(args.out / "receipts" / f"{name}.json") for name in missing})
                ready = available(args, pending, receipts)
                transfers = [pool.submit(download, args, name, receipts[name]) for name in ready]
                for transfer in as_completed(transfers):
                    try:
                        transfer.result()
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        print(f"Retrying shard transfer after {type(error).__name__}", flush=True)
                if source["phase"] == "complete" and set(names) == done:
                    return
            except (OSError, subprocess.SubprocessError) as error:
                print(f"Retrying archive spool after {type(error).__name__}", flush=True)
            time.sleep(15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--source", type=PurePosixPath, required=True)
    parser.add_argument("--remote-python", required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--spool-shards", type=int, default=24)
    parser.add_argument("--spool-bytes", type=int, default=4_000_000_000)
    args = parser.parse_args()
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (args.out / "spool.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args)


if __name__ == "__main__":
    main()
