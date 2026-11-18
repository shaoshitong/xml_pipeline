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
declare -px PIP_CACHE_DIR XDG_CACHE_HOME TMPDIR HF_HOME TRITON_CACHE_DIR \
  CUDA_CACHE_PATH FLASHINFER_WORKSPACE_BASE TORCH_EXTENSIONS_DIR NUMBA_CACHE_DIR \
  PYTHONNOUSERSITE > "$base/env-setup-runtime.sh"

if [[ ! -x "$base/env/bin/python" ]]; then
  "$bootstrap" -m venv --system-site-packages "$base/env"
fi
python="$base/env/bin/python"

# Qwen3.5 is present in this release. Its compiled stack pins torch 2.9.1;
# pip installs that version inside the venv, leaving shared torch unchanged.
"$python" -m pip install --only-binary=:all: --index-url "$index" \
  --retries 1 --timeout 30 --report "$base/env-setup-install.json" \
  sglang==0.5.10.post1 torchvision==0.24.1 \
  > "$base/env-setup-install.log" 2>&1

CUDA_VISIBLE_DEVICES='' "$python" - <<'PY' > "$base/env-setup-imports.json"
import importlib
import importlib.metadata as metadata
import json
import sys

modules = ["torch", "transformers", "sglang", "sgl_kernel",
           "sglang.srt.configs.qwen3_5", "sglang.srt.multimodal.processors.qwen_vl"]
loaded = {name: importlib.import_module(name).__file__ for name in modules}
versions = {name: metadata.version(name) for name in (
    "torch", "torchvision", "torchaudio", "transformers", "sglang",
    "sglang-kernel", "flashinfer-python", "triton")}
from transformers import Qwen3_5Config, Qwen3_5ForConditionalGeneration

print(json.dumps({"python": sys.version, "prefix": sys.prefix,
                  "versions": versions, "modules": loaded,
                  "qwen_architecture": Qwen3_5ForConditionalGeneration.__name__}, indent=2))
PY
CUDA_VISIBLE_DEVICES='' "$python" -m sglang.launch_server --help \
  > "$base/env-setup-cli-help.txt" 2> "$base/env-setup-cli-stderr.log"
printf 'Prepared %s\n' "$python"
