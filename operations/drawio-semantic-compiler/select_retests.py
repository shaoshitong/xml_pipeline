"""Select cases whose current compilation needs a new native acceptance proof."""

import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recompiled", type=Path)
    parser.add_argument("primary", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--primary-finished", action="store_true")
    args = parser.parse_args()
    with args.recompiled.open() as stream:
        current = [json.loads(line) for line in stream if line.strip()]
    if args.primary_finished:
        terminal = json.loads((args.primary / "EXIT.json").read_bytes())
        if terminal["manifest_cases"] != len(current):
            raise ValueError("The primary run has not closed the complete corpus")
    counts = Counter()
    with args.output.open("x") as out:
        for row in current:
            case = row["id"]
            path = args.primary / "cases" / case / "status.json"
            if "error" in row:
                reason = "recompilation_error"
            elif not path.is_file():
                reason = "missing" if args.primary_finished else "pending"
            else:
                status = json.loads(path.read_bytes())
                if status["state"] != "accepted" or not all(status["checks"].values()):
                    reason = "previous_rejection"
                elif any(status.get(k) != row[k] for k in ("input_sha256", "output_sha256", "ir_sha256")):
                    reason = "different_canonical_output"
                else:
                    reason = "identical_with_native_proof"
            counts[reason] += 1
            if reason not in ("pending", "identical_with_native_proof"):
                out.write(case + "\n")
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
