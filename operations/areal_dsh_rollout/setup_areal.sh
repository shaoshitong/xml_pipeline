#!/usr/bin/env bash
set -euo pipefail

base=${1:?Usage: setup_areal.sh REMOTE_EXPERIMENT_ROOT PINNED_SOURCE_ARCHIVE}
archive=${2:?Pass the verified AReaL source archive}
commit=64a7fcca3936ddf2ab16bb1dd3e776d66ced31ff
root="$base/controller"
source_dir="$root/source/AReaL-$commit"
index=${DSH_PYPI_INDEX:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}
bootstrap="$base/env/bin/python"

mkdir -p "$root/source" "$root/cache/tmp"
export PIP_CACHE_DIR="$root/cache/pip" XDG_CACHE_HOME="$root/cache"
export TMPDIR="$root/cache/tmp" HF_HOME="$base/cache/huggingface"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export PIP_DISABLE_PIP_VERSION_CHECK=1 CUDA_VISIBLE_DEVICES=""
export LITELLM_LOCAL_MODEL_COST_MAP=True HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
unset PYTHONPATH PYTHONHOME

if [[ ! -d "$source_dir" ]]; then
  tar -xzf "$archive" -C "$root/source"
fi
if [[ ! -x "$root/env/bin/python" ]]; then
  "$bootstrap" -m venv --system-site-packages "$root/env"
fi
python="$root/env/bin/python"
export PATH="$root/env/bin:$PATH"
site=$("$python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
shared_site=$("$bootstrap" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
printf '%s\n' "$shared_site" > "$site/drawio_serving_packages.pth"

"$python" - "$source_dir" "$commit" <<'PY' > "$root/source-verification.json"
from hashlib import sha1, sha256
import json
from pathlib import Path
import sys

root, commit = Path(sys.argv[1]), sys.argv[2]
manifest = json.loads((root / ".areal-source-manifest.json").read_text())
assert manifest["commit"] == commit
verified = []
for entry in manifest["files"]:
    data = (root / entry["path"]).read_bytes()
    blob = sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert blob == entry["sha"], entry["path"]
    verified.append({"path": entry["path"], "sha256": sha256(data).hexdigest()})
print(json.dumps({"commit": commit, "files": verified}, indent=2))
PY

# Reuse the real serving stack, without resolving AReaL's optional training
# dependencies or installing another copy of Torch/CUDA packages.
"$python" -m pip install --no-compile --index-url "$index" --retries 0 --timeout 20 \
  --report "$root/dependency-install.json" \
  uv_build==0.9.30 torchdata==0.11.0 \
  omegaconf==2.4.0.dev2 hydra-core==1.4.0.dev1 \
  colorlog==6.12.0 aiofiles==25.1.0 awex==0.9.0 \
  tenacity==9.2.1 flask==3.1.3 litellm==1.81.3 \
  > "$root/dependency-install.log" 2>&1
"$python" -m pip install --no-deps --no-build-isolation --no-compile \
  --report "$root/areal-install.json" -e "$source_dir" \
  > "$root/areal-install.log" 2>&1
declare -px PATH PIP_CACHE_DIR XDG_CACHE_HOME TMPDIR HF_HOME \
  PYTHONNOUSERSITE PYTHONDONTWRITEBYTECODE CUDA_VISIBLE_DEVICES \
  LITELLM_LOCAL_MODEL_COST_MAP HF_HUB_OFFLINE TRANSFORMERS_OFFLINE \
  > "$root/env-setup-runtime.sh"

"$python" - "$commit" <<'PY' > "$root/import-audit.json" 2> "$root/import-stderr.log"
from hashlib import sha256
import importlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import torch

modules = (
    "areal", "areal.api.cli_args", "areal.infra.controller.rollout_controller",
    "areal.infra.scheduler.local", "areal.engine.sglang_remote",
    "areal.experimental.openai.proxy.workflow",
    "areal.experimental.openai.proxy.proxy_rollout_server",
)
loaded = {}
for name in modules:
    module = importlib.import_module(name)
    path = Path(module.__file__)
    loaded[name] = {"path": str(path), "sha256": sha256(path.read_bytes()).hexdigest()}
assert not torch.cuda.is_initialized(), "Static import initialized CUDA"
versions = {name: metadata.version(name) for name in (
    "areal", "torch", "transformers", "sglang", "torchdata", "omegaconf",
    "hydra-core", "awex", "aiohttp", "openai", "anthropic", "litellm",
    "flask", "tenacity", "colorlog", "aiofiles", "uv_build")}
print(json.dumps({"commit": sys.argv[1], "python": sys.executable,
                  "versions": versions, "modules": loaded,
                  "torch_path": torch.__file__, "cuda_initialized": False,
                  "controller_initialized": False, "optimizer_started": False}, indent=2))
PY

printf 'Prepared static-import controller environment: %s\n' "$python"
