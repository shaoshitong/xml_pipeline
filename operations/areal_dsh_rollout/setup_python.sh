#!/usr/bin/env bash
set -euo pipefail

base=${1:?Usage: setup_python.sh REMOTE_EXPERIMENT_ROOT}
bootstrap=${BOOTSTRAP_PYTHON:-/share/anaconda3/envs/vllm017/bin/python}
index=${DSH_PYPI_INDEX:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}
export PIP_CACHE_DIR="$base/cache/pip" XDG_CACHE_HOME="$base/cache"
export TMPDIR="$base/cache/tmp" HF_HOME="$base/cache/huggingface"
export TRITON_CACHE_DIR="$base/cache/triton" CUDA_CACHE_PATH="$base/cache/cuda"
export FLASHINFER_WORKSPACE_BASE="$base/cache/flashinfer"
export TORCH_EXTENSIONS_DIR="$base/cache/torch-extensions"
export NUMBA_CACHE_DIR="$base/cache/numba"
export PYTHONNOUSERSITE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
unset PYTHONPATH PYTHONHOME
mkdir -p "$TMPDIR"

if [[ ! -x "$base/env/bin/python" ]]; then
  "$bootstrap" -m venv --system-site-packages "$base/env"
fi
python="$base/env/bin/python"

# Qwen3.5 is present in this release. Its compiled stack pins torch 2.9.1;
# pip installs that version inside the venv, leaving shared torch unchanged.
"$python" -m pip install --no-compile --only-binary=:all: --index-url "$index" \
  --retries 1 --timeout 30 --report "$base/env-setup-install.json" \
  sglang==0.5.10.post1 torchvision==0.24.1 \
  > "$base/env-setup-install.log" 2>&1

libraries=$("$python" - <<'PY'
import glob
import sys
print(":".join(path for root in sys.path for path in glob.glob(root + "/nvidia/*/lib")))
PY
)
export LD_LIBRARY_PATH="$libraries${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
declare -px PIP_CACHE_DIR XDG_CACHE_HOME TMPDIR HF_HOME TRITON_CACHE_DIR \
  CUDA_CACHE_PATH FLASHINFER_WORKSPACE_BASE TORCH_EXTENSIONS_DIR NUMBA_CACHE_DIR \
  PYTHONNOUSERSITE LD_LIBRARY_PATH > "$base/env-setup-runtime.sh"

"$python" - <<'PY' > "$base/env-setup-imports.json"
import importlib
import importlib.metadata as metadata
import json
import sys

modules = ["torch", "transformers", "sglang", "sglang.srt.configs.qwen3_5"]
loaded = {name: importlib.import_module(name).__file__ for name in modules}
gpu_imports = {"status": "passed"}
try:
    for name in ("sgl_kernel", "sglang.srt.multimodal.processors.qwen_vl"):
        loaded[name] = importlib.import_module(name).__file__
except ImportError as error:
    if "libcuda.so.1" not in str(error):
        raise
    gpu_imports = {"status": "requires_gpu_node", "reason": "libcuda.so.1 unavailable"}
versions = {name: metadata.version(name) for name in (
    "torch", "torchvision", "torchaudio", "transformers", "sglang",
    "sglang-kernel", "flashinfer-python", "triton")}
from transformers import Qwen3_5Config, Qwen3_5ForConditionalGeneration

print(json.dumps({"python": sys.version, "prefix": sys.prefix,
                  "versions": versions, "modules": loaded,
                  "gpu_imports": gpu_imports,
                  "qwen_architecture": Qwen3_5ForConditionalGeneration.__name__}, indent=2))
PY
"$python" -m sglang.launch_server --help \
  > "$base/env-setup-cli-help.txt" 2> "$base/env-setup-cli-stderr.log"
printf 'Prepared %s\n' "$python"
