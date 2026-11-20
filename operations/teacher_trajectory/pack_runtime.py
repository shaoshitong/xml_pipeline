"""Package public DSH/renderer assets and CPU dependency pins without logins."""

import argparse
from hashlib import sha256
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess

from packaging.requirements import Requirement


def dependency_pins():
    distributions = metadata.packages_distributions()
    roots = ("PIL", "playwright", "numpy", "cv2", "fitz", "matplotlib", "scipy", "fontTools", "yaml", "zstandard")
    pending = {name for module in roots for name in distributions.get(module, [])}
    pins = {}
    while pending:
        name = pending.pop()
        distribution = metadata.distribution(name)
        canonical = distribution.metadata["Name"].lower().replace("_", "-")
        if canonical in pins:
            continue
        pins[canonical] = distribution.version
        for text in distribution.requires or []:
            requirement = Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.add(requirement.name)
    return [name + "==" + version for name, version in sorted(pins.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True)
    (args.out / "node/bin").mkdir(parents=True)
    shutil.copy2(args.runtime / "node/bin/node", args.out / "node/bin/node")
    (args.out / "dsh").mkdir()
    for name in ("package.json", "package-lock.json"):
        path = args.runtime / "dsh" / name
        if path.is_file():
            shutil.copy2(path, args.out / "dsh" / name)
    shutil.copytree(args.runtime / "dsh/node_modules", args.out / "dsh/node_modules")
    renderer = args.out / "renderer"
    renderer.mkdir()
    shutil.copy2(args.renderer / "draw.war", renderer / "draw.war")
    for name in ("chrome-linux64", "fonts"):
        shutil.copytree(args.renderer / name, renderer / name)
    licenses = args.out / "system-licenses"
    licenses.mkdir()
    for path in Path("/usr/share/doc").glob("*/copyright"):
        if path.parent.name.startswith(("fonts-", "nodejs")):
            shutil.copy2(path, licenses / (path.parent.name + ".txt"))
    pins = dependency_pins()
    (args.out / "rollout-cpu-requirements.txt").write_text("\n".join(pins) + "\n")
    contract = {"platform": platform.platform(), "architecture": platform.machine(),
                "python": platform.python_version(), "system": platform.freedesktop_os_release(),
                "node": subprocess.check_output([str(args.out / "node/bin/node"), "--version"], text=True).strip(),
                "dsh": json.loads((args.out / "dsh/node_modules/@deepseek-ai/dsh/package.json").read_text())["version"],
                "gpu_required": False, "credentials_included": False,
                "system_setup": "Install bubblewrap and run: python -m playwright install-deps chromium",
                "python_dependency_pins": pins}
    (args.out / "runtime-contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    archive = args.out.with_suffix(".tar.gz")
    subprocess.run(["tar", "--format=gnu", "--sort=name", "-czf", str(archive),
                    "-C", str(args.out.parent), args.out.name], check=True)
    digest = sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 ** 2), b""):
            digest.update(block)
    result = {"archive": str(archive), "bytes": archive.stat().st_size, "sha256": digest.hexdigest(),
              "credentials_included": False, "model_weights_included": False, "node": contract["node"], "dsh": contract["dsh"]}
    archive.with_suffix(".gz.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
