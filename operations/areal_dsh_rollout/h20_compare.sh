#!/usr/bin/env bash
set -euo pipefail

task_root=$1
run_path=$2
source_commit=$3
python_runtime=$4
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$task_root"
source ./runtime-env.sh
export CUDA_VISIBLE_DEVICES="" DSH_MASK_PROCESS_TITLE=1
export PYTHONPATH="$source_root/h20_bootstrap:$source_root"
exec -a python envs/serving/bin/python "$source_root/h20_compare.py" \
  --root "$task_root" --out "$run_path" --source-commit "$source_commit" \
  --python-runtime-root "$python_runtime"
