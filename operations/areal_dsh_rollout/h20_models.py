"""Download only serving assets on H20 and verify their pinned upstream hashes."""

import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import struct
import time
from urllib.request import urlopen

from huggingface_hub import snapshot_download


def prepare(model, root, endpoint, workers):
    with urlopen(f"{endpoint}/api/models/Qwen/{model}?blobs=true", timeout=20) as response:
        metadata = json.load(response)
    files = [entry for entry in metadata["siblings"] if entry["rfilename"].endswith(
        (".json", ".jinja", ".txt", ".safetensors")) or entry["rfilename"] == "LICENSE"]
    target = root / "models" / model
    target.mkdir(parents=True, exist_ok=True)
    manifest = {"id": metadata["id"], "revision": metadata["sha"], "files": files}
    (target / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"model": model, "revision": metadata["sha"],
                      "expected_bytes": sum(entry["size"] for entry in files)}), flush=True)
    snapshot_download(metadata["id"], revision=metadata["sha"], endpoint=endpoint,
                      local_dir=target, allow_patterns=[entry["rfilename"] for entry in files],
                      max_workers=workers, token=False)
    verified = []
    for entry in files:
        path = target / entry["rfilename"]
        assert path.stat().st_size == entry["size"], path.name
        lfs = entry.get("lfs")
        digest = sha256() if lfs else sha1(f"blob {entry['size']}\0".encode())
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
        expected = lfs["sha256"] if lfs else entry["blobId"]
        assert digest.hexdigest() == expected, path.name
        verified.append({"name": path.name, "bytes": entry["size"], "hash": expected})
    index = json.loads((target / "model.safetensors.index.json").read_text())["weight_map"]
    observed = {}
    for shard in sorted(set(index.values())):
        with (target / shard).open("rb") as stream:
            header_size = struct.unpack("<Q", stream.read(8))[0]
            header = json.loads(stream.read(header_size))
        observed.update({key: shard for key in header if key != "__metadata__"})
    assert observed == index, "Tensor index disagrees with shard headers"
    receipt = {"model": metadata["id"], "revision": metadata["sha"], "files": verified,
               "tensor_count": len(observed), "verified_at": time.time()}
    (target / "verification-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"model": model, "verified": True, "files": len(files)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["Qwen3.8-27B", "Qwen3.5-4B"])
    parser.add_argument("--endpoint", default="https://hf-mirror.com")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    for model in args.models:
        prepare(model, args.root, args.endpoint, args.workers)


if __name__ == "__main__":
    main()
