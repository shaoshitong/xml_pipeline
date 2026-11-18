#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=debug
#SBATCH --nodelist=ACD1-63
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:29:00
#SBATCH --job-name=drawio-dsh-diagnose
set -euo pipefail

root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
size=${MODEL_SIZE:-9B}
mode=${DIAGNOSTIC_MODE:-minimal}
source_dir="$root/source/operations/areal_dsh_rollout"
runtime=/tmp/drawio-mou176-20261118/runtime
source "$root/env-setup-runtime.sh"
bash "$source_dir/stage_runtime.sh" "$root" "$runtime"
exec "$root/env/bin/python" -u "$source_dir/launch.py" \
  --root "$root" --runtime "$runtime" --reference "$root/inputs/022/reference.png" \
  --out "$root/diagnostics/$size-022-$mode-$SLURM_JOB_ID" --generator "$size" \
  --reasoning-effort off --diagnose-mode "$mode" --direct-first
