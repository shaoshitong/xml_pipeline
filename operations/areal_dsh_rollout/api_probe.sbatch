#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=acd_u
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:30:00
#SBATCH --job-name=drawio-dpsk-api-probe
set -euo pipefail

root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
source_dir="$root/source/operations/areal_dsh_rollout"
runtime=/tmp/drawio-mou176-20261118/runtime
source "$root/env-setup-runtime.sh"
export ROLLOUT_API_WIRE_AUDIT="$root/api-eval/probe-$SLURM_JOB_ID.api-wire.jsonl"
bash "$source_dir/stage_runtime.sh" "$root" "$runtime"
resume_args=()
if [[ -n "${RESUME_FROM:-}" ]]; then
  resume_args=(--resume-from "$RESUME_FROM")
fi
exec "$root/controller/env/bin/python" -u "$source_dir/external_api_workflow.py" run \
  --root "$root" --runtime "$runtime" --reference "$root/inputs/${CASE_ID:-sanity3}/reference.png" \
  --out "$root/api-eval/probe-$SLURM_JOB_ID" \
  --key-file "$root/private-auth/deepseek-api.key" --proxy http://10.120.48.31:30444 \
  --rounds "${ROUNDS:-1}" --skill-mode full --context-window 1048576 --max-tokens 131072 \
  --reasoning-effort max --timeout "${EPISODE_TIMEOUT:-1200}" \
  --turn-timeout "${TURN_TIMEOUT:-900}" "${resume_args[@]}"
