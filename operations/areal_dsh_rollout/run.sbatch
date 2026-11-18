#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=debug
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:29:00
#SBATCH --job-name=drawio-dsh-rollout
set -euo pipefail

TASK_ROOT=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
GENERATOR_SIZE=${GENERATOR_SIZE:-4B}
CASE_ID=${CASE_ID:-022}
ROLLOUT_ROUNDS=${ROLLOUT_ROUNDS:-4}
SOURCE_ROOT="$TASK_ROOT/source/operations/areal_dsh_rollout"
LOCAL_RUNTIME="/tmp/drawio-mou176-20261118/runtime"
source "$TASK_ROOT/env-setup-runtime.sh"
export HF_HOME="$TASK_ROOT/cache/huggingface"
export XDG_CACHE_HOME="$TASK_ROOT/cache"
export TRITON_CACHE_DIR="$TASK_ROOT/cache/triton"
export TMPDIR="/tmp/drawio-mou176-20261118/tmp"
mkdir -p "$TMPDIR"
bash "$SOURCE_ROOT/stage_runtime.sh" "$TASK_ROOT" "$LOCAL_RUNTIME"
exec "$TASK_ROOT/env/bin/python" -u "$SOURCE_ROOT/launch.py" \
    --root "$TASK_ROOT" --runtime "$LOCAL_RUNTIME" \
    --reference "$TASK_ROOT/inputs/$CASE_ID/reference.png" \
    --out "$TASK_ROOT/runs/$GENERATOR_SIZE-$CASE_ID-$SLURM_JOB_ID" \
    --generator "$GENERATOR_SIZE" --rounds "$ROLLOUT_ROUNDS"
