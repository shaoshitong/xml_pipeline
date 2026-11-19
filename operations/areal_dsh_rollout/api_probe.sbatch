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
bash "$source_dir/stage_runtime.sh" "$root" "$runtime"
exec "$root/controller/env/bin/python" -u "$source_dir/external_api_workflow.py" run \
  --root "$root" --runtime "$runtime" --reference "$root/inputs/sanity3/reference.png" \
  --out "$root/api-eval/probe-$SLURM_JOB_ID" \
  --key-file "$root/private-auth/deepseek-api.key" --proxy http://10.120.48.31:30444 \
  --rounds 1 --skill-mode full --context-window 1048576 --max-tokens 131072 \
  --reasoning-effort max --timeout 1200 --turn-timeout 900
