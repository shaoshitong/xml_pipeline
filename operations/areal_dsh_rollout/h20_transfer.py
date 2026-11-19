"""Send bounded, hash-checked chunks through a control-only bastion route."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess


RECEIVER = """
from pathlib import Path
from hashlib import sha256
import sys
p=Path(sys.argv[1]); offset=int(sys.argv[2]); digest=sys.argv[3]
data=sys.stdin.buffer.read()
assert sha256(data).hexdigest()==digest
assert (p.stat().st_size if p.exists() else 0)==offset
with p.open('ab') as f: f.write(data); f.flush()
print(offset+len(data))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination")
    parser.add_argument("--ssh", required=True, help="Existing SSH command, including destination")
    parser.add_argument("--chunk-mib", type=int, default=4)
    args = parser.parse_args()
    ssh = shlex.split(args.ssh)
    target = args.destination + ".partial"
    stat = "python3 -c " + shlex.quote(
        "from pathlib import Path; p=Path(" + repr(target) + "); print(p.stat().st_size if p.exists() else 0)")
    offset = int(subprocess.check_output(ssh + [stat], timeout=30))
    total = args.source.stat().st_size
    with args.source.open("rb") as stream:
        stream.seek(offset)
        while block := stream.read(args.chunk_mib * 1024 * 1024):
            command = shlex.join(["python3", "-c", RECEIVER, target,
                                  str(offset), sha256(block).hexdigest()])
            result = subprocess.run(ssh + [command], input=block, capture_output=True, timeout=60)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors="replace")[-800:])
            offset = int(result.stdout)
            print(json.dumps({"sent": offset, "total": total}), flush=True)
    assert offset == total
    expected = sha256(args.source.read_bytes()).hexdigest()
    finish = "from pathlib import Path; from hashlib import sha256; p=Path(" + repr(target) + "); "
    finish += "assert sha256(p.read_bytes()).hexdigest()==" + repr(expected) + "; "
    finish += "p.replace(" + repr(args.destination) + "); print('verified')"
    subprocess.run(ssh + ["python3 -c " + shlex.quote(finish)], check=True, timeout=60)


if __name__ == "__main__":
    main()
