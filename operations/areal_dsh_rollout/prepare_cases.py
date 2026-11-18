"""Copy selected private manifest cases directly from the source host to the target."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shlex
import subprocess


RECEIVE = """import pathlib,sys,hashlib
p=pathlib.Path(sys.argv[1]); p.parent.mkdir(parents=True,exist_ok=True)
data=sys.stdin.buffer.read()
assert hashlib.sha256(data).hexdigest()==sys.argv[2]
p.write_bytes(data)
print(str(p),len(data),hashlib.sha256(data).hexdigest())
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--target-root", required=True, type=Path)
    parser.add_argument("--control", required=True)
    parser.add_argument("--host", default="mou176@hpc3login.hpc.hkust-gz.edu.cn")
    parser.add_argument("--ids", nargs="+", required=True)
    args = parser.parse_args()
    records = json.loads(args.manifest.read_text())
    for case_id in args.ids:
        record = records[case_id]
        for key, folder, filename in [("image", "inputs", "reference.png"),
                                       ("code", "private", "gold.drawio")]:
            data = (args.source_root / record[f"{key}_file"]).read_bytes()
            digest = sha256(data).hexdigest()
            assert digest == record[f"{key}_sha256"]
            target = args.target_root / folder / case_id / filename
            command = shlex.join(["python3", "-c", RECEIVE, str(target), digest])
            subprocess.run(["ssh", "-S", args.control, args.host, command], input=data, check=True)


if __name__ == "__main__":
    main()
