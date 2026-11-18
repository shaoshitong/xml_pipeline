#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=debug
#SBATCH --nodelist=ACD1-63
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:29:00
#SBATCH --job-name=drawio-dsh-continue
set -euo pipefail

root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
previous=${PREVIOUS_4B_RUN:?Set PREVIOUS_4B_RUN to the preserved episode}
source_dir="$root/source/operations/areal_dsh_rollout"
runtime=/tmp/drawio-mou176-20261118/runtime
source "$root/env-setup-runtime.sh"
bash "$source_dir/stage_runtime.sh" "$root" "$runtime"

if [[ ! -f "$previous/episode/completed.json" ]]; then
  "$root/env/bin/python" -u "$source_dir/launch.py" \
    --root "$root" --runtime "$runtime" --reference "$root/inputs/022/reference.png" \
    --out "$root/runs/4B-022-instruct-$SLURM_JOB_ID" --generator 4B --rounds 2 \
    --reasoning-effort off --seed-from "$previous" \
    --resume-note "The previous session exhausted context during renderer troubleshooting. The official renderer now works. Keep and inspect your own saved candidate and the reference; repair validity, render and review."
fi

exec "$root/env/bin/python" -u "$source_dir/launch.py" \
  --root "$root" --runtime "$runtime" --reference "$root/inputs/022/reference.png" \
  --out "$root/runs/9B-022-instruct-$SLURM_JOB_ID" --generator 9B --rounds 2 \
  --reasoning-effort off --areal
