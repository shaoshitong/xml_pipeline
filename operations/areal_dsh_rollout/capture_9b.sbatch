#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=debug
#SBATCH --nodelist=ACD1-63
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:29:00
#SBATCH --job-name=drawio-9b-capture
set -euo pipefail

root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
previous=${PREVIOUS_9B_RUN:?Set PREVIOUS_9B_RUN to avoid duplicate completed captures}
if [[ -f "$previous/collector/capture-audit.json" ]]; then
  exit 0
fi
source_dir="$root/source/operations/areal_dsh_rollout"
runtime=/tmp/drawio-mou176-20261118/runtime
source "$root/env-setup-runtime.sh"
bash "$source_dir/stage_runtime.sh" "$root" "$runtime"
exec "$root/env/bin/python" -u "$source_dir/launch.py" \
  --root "$root" --runtime "$runtime" --reference "$root/inputs/022/reference.png" \
  --out "$root/runs/9B-022-instruct-$SLURM_JOB_ID" --generator 9B --rounds 2 \
  --reasoning-effort off --areal
