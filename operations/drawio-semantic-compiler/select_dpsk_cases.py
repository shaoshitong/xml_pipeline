"""Freeze 50 distinct accepted canonical diagrams for the independent DPSK run."""

import argparse
from collections import Counter, defaultdict, deque
from hashlib import sha256
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("candidate_ids", type=Path, help="IDs fixed before perturbations are generated")
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=20261112)
    args = parser.parse_args()
    candidates = set(args.candidate_ids.read_text().split())
    rows = [json.loads(line) for line in args.corpus.read_text().splitlines()]
    strata = defaultdict(list)
    sources = set()
    for row in rows:
        if row["id"] not in candidates:
            continue
        case = args.run / "cases" / row["id"]
        result = json.loads((case / "status.json").read_bytes())
        if result["state"] != "accepted" or result["input_sha256"] != row["code_sha256"]:
            raise ValueError(f"Candidate lacks current acceptance evidence: {row['id']}")
        sources.add(result["sources_sha256"])
        if result["cells"] < 5:
            continue
        size = "small" if result["cells"] < 50 else "medium" if result["cells"] < 250 else "large"
        key = (row["source"], size, bool(result["sketch_seeded_cells"]))
        strata[key].append((row["id"], case.resolve() / "canonical.drawio", result["output_sha256"]))
    if len(sources) != 1:
        raise ValueError("Candidate acceptance results were produced by different compiler sources")

    def order(item):
        return sha256(f"{args.seed}:{item[0]}".encode()).digest()

    pools = {key: deque(sorted(group, key=order)) for key, group in sorted(strata.items())}
    selected, seen = [], set()
    coverage = Counter()
    while pools and len(selected) < 50:
        for key in list(pools):
            pool = pools[key]
            while pool:
                case, path, digest = pool.popleft()
                if digest in seen:
                    continue
                with path.open("rb") as stream:
                    actual = sha256(stream.read()).hexdigest()
                if actual != digest:
                    raise ValueError(f"Canonical file differs from acceptance receipt: {case}")
                selected.append({"id": case, "xml": str(path)})
                seen.add(digest)
                coverage[key] += 1
                break
            if not pool:
                del pools[key]
            if len(selected) == 50:
                break
    if len(selected) != 50:
        raise ValueError(f"Expected 50 distinct accepted canonical cases, found {len(selected)}")
    manifest = "".join(json.dumps(row, sort_keys=True) + "\n" for row in selected)
    with args.output.open("x") as stream:
        stream.write(manifest)
    print(json.dumps({"selected": len(selected), "seed": args.seed,
                      "sha256": sha256(manifest.encode()).hexdigest(),
                      "sources_sha256": next(iter(sources)),
                      "strata": [{"source": k[0], "size": k[1], "sketch": k[2], "cases": v}
                                 for k, v in coverage.items()]}))


if __name__ == "__main__":
    main()
