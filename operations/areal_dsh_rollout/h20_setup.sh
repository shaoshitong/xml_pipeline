#!/usr/bin/env bash
set -euo pipefail
root=${1:?Usage: h20_setup.sh TASK_ROOT BOOTSTRAP_PYTHON}
bootstrap=${2:?Supply the existing read-only bootstrap Python}
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
export TMPDIR="$root/cache/tmp" PIP_CACHE_DIR="$root/cache/pip"
export XDG_CACHE_HOME="$root/cache/xdg" HF_HOME="$root/cache/huggingface"
export PATH="$root/runtime/node/bin:$root/bin:$PATH"
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$root/controller/source"
index=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
serving="$root/envs/serving/bin/python"
if [[ ! -x "$serving" ]]; then
    "$bootstrap" -m venv --system-site-packages "$root/envs/serving"
fi
"$serving" -m pip install --no-compile --timeout 20 --retries 1 -i "$index" \
    sglang==0.5.10.post1 torch==2.9.1 torchvision==0.24.1 torchaudio==2.9.1 \
    transformers==5.3.0 sglang-kernel==0.4.1 flashinfer-python==0.6.7.post3 \
    triton==3.5.1 playwright==1.58.0 Pillow==11.3.0 setproctitle
tar -xzf "$root/transfer/h20-areal-runtime.tar.gz" -C "$root/controller/source"
controller="$root/controller/env/bin/python"
if [[ ! -x "$controller" ]]; then
    "$serving" -m venv --system-site-packages "$root/controller/env"
fi
export PATH="$root/controller/env/bin:$root/envs/serving/bin:$PATH"
libraries=$("$serving" -c 'import glob,sys; print(":".join(p for base in sys.path for p in glob.glob(base+"/nvidia/*/lib")))')
export LD_LIBRARY_PATH="$libraries${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export DSH_CHROME_TMPDIR="$TMPDIR"
declare -px PATH LD_LIBRARY_PATH TMPDIR XDG_CACHE_HOME HF_HOME PYTHONNOUSERSITE PYTHONDONTWRITEBYTECODE DSH_CHROME_TMPDIR > "$root/runtime-env.sh"
site=$("$controller" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
shared=$("$serving" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
printf '%s\n' "$shared" > "$site/drawio_serving.pth"
"$controller" -m pip install --no-compile --timeout 20 --retries 1 -i "$index" \
    uv_build==0.9.30 torchdata==0.11.0 omegaconf==2.4.0.dev2 hydra-core==1.4.0.dev1 \
    colorlog==6.12.0 aiofiles==25.1.0 awex==0.9.0 tenacity==9.2.1 flask==3.1.3 \
    litellm==1.81.3 openai==3.55.0 anthropic==0.86.0
source_dir="$root/controller/source/AReaL-64a7fcca3936ddf2ab16bb1dd3e776d66ced31ff"
"$controller" -m pip install --no-deps --no-build-isolation --no-compile -e "$source_dir"
if [[ ! -e "$root/renderer/venv" ]]; then
    ln -s "$root/envs/serving" "$root/renderer/venv"
fi
"$serving" - "$root" <<'PY'
from hashlib import sha1, sha256
from pathlib import Path
import importlib.metadata as metadata
import json
import sys

root = Path(sys.argv[1])
source = root / "controller/source/AReaL-64a7fcca3936ddf2ab16bb1dd3e776d66ced31ff"
manifest = json.loads((source / ".areal-source-manifest.json").read_text())
verified = []
for entry in manifest["files"]:
    path = source / entry["path"]
    if path.is_file():
        data = path.read_bytes()
        assert sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == entry["sha"]
        verified.append(entry["path"])
versions = {name: metadata.version(name) for name in (
    "torch", "torchvision", "torchaudio", "transformers", "sglang", "sglang-kernel",
    "flashinfer-python", "triton", "playwright", "Pillow")}
(root / "environment-verification.json").write_text(json.dumps({
    "versions": versions, "python": sys.version, "areal_commit": manifest["commit"],
    "areal_verified_runtime_files": verified,
    "omitted": "AReaL docs, tests, examples, original environments, caches and previous rollouts",
}, indent=2) + "\n")
PY
