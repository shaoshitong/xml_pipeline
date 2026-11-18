#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=debug
#SBATCH --nodelist=ACD1-63
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:29:00
#SBATCH --job-name=drawio-diagnostic-services
set -euo pipefail

root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
size=${MODEL_SIZE:-4B}
source_dir="$root/source/operations/areal_dsh_rollout"
source "$root/env-setup-runtime.sh"
role_args=()
if [[ ${REVIEWER_ONLY:-0} == 1 ]]; then role_args=(--reviewer-only); fi
bash "$source_dir/stage_runtime.sh" "$root" /tmp/drawio-mou176-20261118/runtime
exec "$root/env/bin/python" -u "$source_dir/launch.py" \
  --root "$root" --runtime /tmp/drawio-mou176-20261118/runtime \
  --reference "$root/inputs/022/reference.png" \
  --out "$root/services/$size-$SLURM_JOB_ID" --generator "$size" \
  --reasoning-effort off --serve-only "${role_args[@]}"
