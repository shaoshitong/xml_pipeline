"""Connect a case in the Mac web profile to its lab verifier over SSH."""

import argparse
from base64 import b64decode, b64encode
from functools import partial
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from checkpoint import MAX_BYTES, read_candidate
from mcp_bridge import serve

ASSETS = {
    "candidate_png": re.compile(r"preview-[0-9a-f]{12}\.png"),
    "diagnostics_file": re.compile(r"structure-[0-9a-f]{12}\.jsonl"),
    "field_diagnostics_file": re.compile(r"fields-[0-9a-f]{12}\.jsonl"),
}


def check_local(case, ssh_alias, command, arguments):
    if not isinstance(arguments, dict) or set(arguments) != {"candidate"}:
        return {"ok": False, "error": "Expected only a candidate filename"}
    name = arguments["candidate"]
    try:
        candidate = read_candidate(case, name)
    except ValueError as error:
        return {"ok": False, "error": str(error)}
    except OSError:
        return {"ok": False, "error": "Write the checkpoint in the configured web case directory first"}
    try:
        proc = subprocess.run(
            ["/usr/bin/ssh", "-oBatchMode=yes", "-oConnectTimeout=6", ssh_alias, command],
            input=candidate, capture_output=True, check=True, timeout=125,
        )
        packet = json.loads(proc.stdout)
        result = packet["result"]
        if result["ok"]:
            encoded = packet["assets"]
            assets = {}
            for field, pattern in ASSETS.items():
                asset = result[field]
                if not pattern.fullmatch(asset):
                    raise ValueError("Unexpected verifier output")
                assets[field] = (asset, b64decode(encoded[asset], validate=True))
            for field, (asset, content) in assets.items():
                path = case / asset
                with path.open("xb") as output:
                    output.write(content)
                result[field] = str(path)
        return {**result, "candidate": name}
    except (OSError, KeyError, TypeError, ValueError, subprocess.SubprocessError):
        return {"ok": False, "error": "Lab verifier unavailable or returned an invalid result"}


def worker(args):
    sys.path[:0] = [str(args.compiler / name) for name in
                   ("drawio_semantic_compiler", "drawio_compare", "scripts")]
    from pilot import verified
    from verifier import Verifier, compile_bytes

    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Checkpoint exceeds 1 MiB")
    record = json.loads(args.manifest.read_text())[args.sample]
    target = verified(args.dataset / record["image_file"], record["image_sha256"])
    gold = compile_bytes(verified(args.dataset / record["code_file"], record["code_sha256"]))
    with TemporaryDirectory(prefix="drawio-web-") as directory:
        case = Path(directory)
        (case / "target.png").write_bytes(target)
        (case / "candidate.drawio").write_bytes(data)
        result = Verifier(case, gold, reveal_structure=True).check({"candidate": "candidate.drawio"})
        result.pop("checks_remaining", None)
        result.pop("candidate", None)
        assets = {result[key]: b64encode((case / result[key]).read_bytes()).decode()
                  for key in ASSETS if result["ok"]}
    print(json.dumps({"result": result, "assets": assets}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    local = modes.add_parser("bridge")
    local.add_argument("--case", required=True, type=Path)
    local.add_argument("--lab", required=True)
    local.add_argument("--worker-command", required=True)
    remote = modes.add_parser("worker")
    for name in ("dataset", "manifest", "compiler"):
        remote.add_argument("--" + name, type=Path, required=True)
    remote.add_argument("--sample", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.mode == "worker":
        worker(args)
    else:
        case = args.case.resolve(strict=True)
        serve(partial(check_local, case, args.lab, args.worker_command),
              f"This verifier is bound to target.png in {case}. Use it only for that image. "
              "Write candidate files in that directory and pass their basenames.")


if __name__ == "__main__":
    main()
