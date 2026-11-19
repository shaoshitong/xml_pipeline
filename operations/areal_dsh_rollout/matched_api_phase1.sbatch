#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=debug
#SBATCH --nodelist=ACD1-63
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --time=00:29:00
#SBATCH --job-name=drawio-matched-api
set -euo pipefail
root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
runtime=/tmp/drawio-mou176-20261118/runtime
source "$root/env-setup-runtime.sh"
source_dir=${MATCHED_SOURCE:-$root/source/operations/areal_dsh_rollout}
bash "$source_dir/stage_runtime.sh" "$root" "$runtime"
reviewer_args=()
if [[ -n "${REVIEWER_URL:-}" ]]; then reviewer_args=(--reviewer-url "$REVIEWER_URL"); fi
exec "$root/env/bin/python" -u "$source_dir/matched_eval.py" --root "$root" --runtime "$runtime" \
  --batch "$MATCHED_BATCH" --model deepseek-flash --phase "${MATCHED_PHASE:-1}" --api-only "${reviewer_args[@]}"
