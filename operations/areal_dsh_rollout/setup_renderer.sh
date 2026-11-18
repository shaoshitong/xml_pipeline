#!/usr/bin/env bash
set -euo pipefail

TASK_ROOT=${1:?Usage: setup_renderer.sh TASK_ROOT}
PYTHON_BIN=${PYTHON_BIN:-/share/anaconda3/envs/vllm017/bin/python3.11}
RENDERER_ROOT="$TASK_ROOT/renderer"
mkdir -p "$RENDERER_ROOT"
if [[ ! -x "$RENDERER_ROOT/venv/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$RENDERER_ROOT/venv"
fi
"$RENDERER_ROOT/venv/bin/python" -m pip install --timeout 8 --retries 1 \
    --index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
    playwright==1.58.0 Pillow==11.3.0

# Supply the official WAR and Linux Chromium as read-only program resources.
# Neither a desktop installation, Node, Xvfb, nor a geometry reimplementation is used.
"$RENDERER_ROOT/venv/bin/python" - "$RENDERER_ROOT" <<'PY'
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
from urllib.request import urlopen

root = Path(sys.argv[1])
packages = {
    "mesa-libgbm-21.1.5-1.el8.x86_64.rpm": "871c1fa6579591f2384e1cb2466b6b6cd4262410ce6b4e7e7fa145363d564a36",
    "libwayland-server-1.19.0-1.el8.x86_64.rpm": "08aec155d604f74dde07a5b21762fdeae37761d8095c77b0ef55d1d4f63a76c2",
}
mirror = "https://mirrors.tuna.tsinghua.edu.cn/centos-vault/8.5.2111/AppStream/x86_64/os/Packages/"
extract = root / "rpm"
lib = root / "lib"
extract.mkdir(exist_ok=True)
lib.mkdir(exist_ok=True)
for name, expected in packages.items():
    package = root / name
    if not package.exists():
        with urlopen(mirror + name, timeout=20) as response:
            package.write_bytes(response.read())
    assert sha256(package.read_bytes()).hexdigest() == expected, name
    producer = subprocess.Popen(["rpm2cpio", str(package)], stdout=subprocess.PIPE)
    result = subprocess.run(["cpio", "-idmu", "--quiet"], cwd=extract, stdin=producer.stdout)
    producer.stdout.close()
    assert producer.wait() == result.returncode == 0, name
for source in (extract / "usr/lib64").glob("*.so*"):
    shutil.copyfile(source, lib / source.name)
(root / "fonts.conf").write_text(
    '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'
    f'<dir>{root / "fonts"}</dir>'
    '<include ignore_missing="yes">/etc/fonts/fonts.conf</include></fontconfig>\n'
)
war = root / "draw.war"
chrome = root / "chrome-linux64" / "chrome"
checksum = sha256(war.read_bytes()).hexdigest()
assert checksum == "44dd56958c8408963457dc98f04d2228408ac145c7aa1d8e6895d9c88d5e42aa", checksum
assert chrome.is_file(), str(chrome)
version = subprocess.check_output([str(chrome), "--version"], text=True,
                                 env={**os.environ, "LD_LIBRARY_PATH": str(lib)}).strip()
manifest = {"drawio_version": "32.6.1", "war_sha256": checksum,
            "chrome_sha256": sha256(chrome.read_bytes()).hexdigest(),
            "chrome_version": version, "system_library_rpms": packages,
            "playwright_version": "1.58.0", "pillow_version": "11.3.0"}
(root / "resource_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, sort_keys=True))
PY
