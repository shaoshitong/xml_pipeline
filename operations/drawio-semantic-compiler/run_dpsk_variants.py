"""Run the pinned DPSK-authored transformations concurrently on the lab node."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


def load_generator(path, output):
    spec = importlib.util.spec_from_file_location("dpsk_variant_generator", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUTPUT_DIRECTORY = str(output)
    return module


def generate(task):
    index, row, generator_path, output, seed = task
    generator = load_generator(generator_path, output)
    base = Path(row["xml"]).read_bytes()
    variant, metadata = generator._generate_candidate(base, row, index, seed)
    if variant == base:
        raise ValueError(f"No actual transformation for {row['id']}")
    candidate = output / (row["id"] + ".drawio")
    record = generator._build_variants_record(row, candidate.name, variant, metadata)
    actual = sha256(variant).hexdigest()
    if record["output_sha256"] != actual:
        raise ValueError(f"Generator receipt does not match the output for {row['id']}")
    generator._atomic_write(candidate, variant)
    proof = {"id": row["id"], "xml": str(candidate), "code_sha256": actual}
    return record, proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generator", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", default="20261112")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    path = args.generator.resolve(strict=True)
    output = args.output.resolve()
    generator = load_generator(path, output)
    rows = generator._load_manifest(args.manifest)
    output.mkdir()
    work = ((index, row, path, output, args.seed) for index, row in enumerate(rows))
    with ProcessPoolExecutor(max_workers=args.workers) as pool, (output / "variants.jsonl").open("x") as variants, (
            output / "verify.jsonl").open("x") as proofs:
        for count, (record, proof) in enumerate(pool.map(generate, work), 1):
            variants.write(json.dumps(record, sort_keys=True) + "\n")
            proofs.write(json.dumps(proof, sort_keys=True) + "\n")
            print(f"Generated {count}/{len(rows)} {proof['id']}", flush=True)
    print(json.dumps({"cases": len(rows), "generator_sha256": sha256(path.read_bytes()).hexdigest(),
                      "variant_manifest": str(output / "verify.jsonl")}), flush=True)


if __name__ == "__main__":
    main()
