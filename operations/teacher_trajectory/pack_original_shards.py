"""Create and checksum archives of verified arXiv PNG shards."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
import tarfile

from pull_original_shards import SHARD, verify


def normalize(info):
    info.mtime = info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o644
    return info


def pack(shard, out):
    receipt = verify(shard)
    manifest = shard / "manifest.jsonl"
    entries = [json.loads(line) for line in manifest.read_text().splitlines()]
    archive = out / f"{shard.name}.tar"
    pending = archive.with_suffix(".tar.part")
    with tarfile.open(pending, "w", format=tarfile.PAX_FORMAT) as tar:
        for relative in ["manifest.jsonl", *(row["file"] for row in entries)]:
            tar.add(shard / relative, arcname=f"{shard.name}/{relative}",
                    recursive=False, filter=normalize)
    with tarfile.open(pending) as tar:
        for row in entries:
            with tar.extractfile(f'{shard.name}/{row["file"]}') as image:
                if file_digest(image, "sha256").hexdigest() != row["sha256"]:
                    raise ValueError("Archive image checksum differs")
        with tar.extractfile(f"{shard.name}/manifest.jsonl") as archived_manifest:
            if file_digest(archived_manifest, "sha256").hexdigest() != receipt["manifest_sha256"]:
                raise ValueError("Archive manifest checksum differs")
    pending.replace(archive)
    with archive.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    return {"name": archive.name, "bytes": archive.stat().st_size, "sha256": digest,
            "images": receipt["images"], "manifest_sha256": receipt["manifest_sha256"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("shards", nargs="+")
    args = parser.parse_args()
    if any(not SHARD.fullmatch(name) for name in args.shards):
        parser.error("Expected shard names like shard-00001")
    args.out.mkdir(mode=0o700, parents=True, exist_ok=True)
    for name in args.shards:
        print(json.dumps(pack(args.source / name, args.out)), flush=True)


if __name__ == "__main__":
    main()
