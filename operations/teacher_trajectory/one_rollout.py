"""Run one image through real DeepSeek DSH sessions using a portable runtime."""

import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from xml.etree import ElementTree

from collect import episode, save
from gateway import Provider
from store import Store


HERE = Path(__file__).resolve().parent


def resources(runtime, output):
    target = output / "renderer"
    target.mkdir(exist_ok=True)
    assets = runtime / "renderer"
    for name in ("draw.war", "chrome-linux64", "fonts"):
        destination = target / name
        if not destination.exists():
            destination.symlink_to((assets / name).resolve())
    if not (target / "venv").exists():
        (target / "venv").symlink_to(Path(sys.prefix).resolve())
    (target / "lib").mkdir(exist_ok=True)
    source = HERE.parents[1] / "conversion"
    for folder, name in (("drawio_compare", "runtime.py"), ("drawio_compare", "native.js"),
                         ("scripts", "arxiv_bulk_official_xml_png_math_v1.py")):
        destination = target / "source/conversion" / folder / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / folder / name, destination)
    config = ElementTree.Element("fontconfig")
    ElementTree.SubElement(config, "dir").text = str(assets / "fonts")
    ElementTree.SubElement(config, "include").text = "/etc/fonts/fonts.conf"
    (target / "fonts.conf").write_text(ElementTree.tostring(config, encoding="unicode") + "\n")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True,
                        help="Extracted Linux x86_64 runtime containing node/, dsh/ and renderer/")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--budget-cny", type=float, default=12)
    parser.add_argument("--key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--source-commit", default="portable-one-rollout")
    parser.add_argument("--check", action="store_true", help="Check runtime and sandbox without a model request")
    args = parser.parse_args()
    args.image, args.runtime, args.out = args.image.resolve(), args.runtime.resolve(), args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    lock = (args.out / "one-rollout.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    renderer = resources(args.runtime, args.out)
    subprocess.run(["bwrap", "--unshare-net", "--ro-bind", "/", "/", "--", "/bin/true"], check=True)
    subprocess.run([str(args.runtime / "node/bin/node"), "--version"], check=True)
    for path in (args.image, renderer / "draw.war", renderer / "chrome-linux64/chrome",
                 args.runtime / "dsh/node_modules/@deepseek-ai/dsh/lib/bin.js"):
        if not path.is_file():
            parser.error("Required runtime/input file is missing: " + str(path))
    if args.check:
        print(json.dumps({"runtime_checked": True, "model_calls": 0, "gpu_required": False}))
        return
    key = os.environ.get(args.key_env)
    if not key:
        parser.error("Set the API key environment variable " + args.key_env)
    digest = sha256(args.image.read_bytes()).hexdigest()
    record = {"id": digest[:16], "paper": None, "origin": "user_supplied_image",
              "reference": str(args.image), "reference_sha256": digest,
              "admitted_to_arxiv_teacher_training_pool": False}
    config = SimpleNamespace(root=args.out, dataset=args.runtime, budget=args.budget_cny,
        episode_cap=args.budget_cny, source_commit=args.source_commit,
        renderer_python=Path(sys.executable), python_runtime_root=Path(sys.base_prefix),
        extra_runtime_mounts=[Path(sys.prefix).resolve()])
    store = Store(args.out / "archive")
    result = episode(config, record, store, Provider(key), args.runtime, renderer)
    save(args.out / "one-rollout-result.json", result)
    print(json.dumps({"completed": result["completed"], "case": str(args.out / "episodes" / record["id"] / "case"),
                      "cost": store.summary(), "fidelity_verified": False}))
    if not result["completed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
