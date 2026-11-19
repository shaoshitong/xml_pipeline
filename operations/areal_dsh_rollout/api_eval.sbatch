#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=acd_u
#SBATCH --exclude=ACD1-24
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --job-name=drawio-dpsk-areal-eval
set -euo pipefail

root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
source_dir="$root/source/operations/areal_dsh_rollout"
runtime=/tmp/drawio-mou176-20261118/runtime
output="$root/api-eval/job-$SLURM_JOB_ID"
source "$root/env-setup-runtime.sh"
bash "$source_dir/stage_runtime.sh" "$root" "$runtime"
mkdir -p "$output"
"$root/env/bin/python" -u "$source_dir/launch.py" \
  --root "$root" --runtime "$runtime" --reference "$root/inputs/022/reference.png" \
  --out "$output/reviewer" --generator 4B --reasoning-effort off \
  --serve-only --reviewer-only > "$output/reviewer-driver.log" 2>&1 &
reviewer_pid=$!
cleanup() {
  touch "$output/reviewer/STOP"
  wait "$reviewer_pid" || true
}
trap cleanup EXIT
"$root/env/bin/python" - "$output/reviewer/services-ready.json" "$reviewer_pid" <<'PY'
import os,sys,time
from pathlib import Path
ready,pid=Path(sys.argv[1]),int(sys.argv[2])
deadline=time.monotonic()+600
while not ready.exists():
    os.kill(pid,0)
    if time.monotonic()>deadline:
        raise TimeoutError("Frozen Reviewer did not become ready")
    time.sleep(1)
PY

for case_id in ${CASE_IDS:-sanity3 022}; do
  "$root/controller/env/bin/python" -u "$source_dir/external_api_workflow.py" run \
    --root "$root" --runtime "$runtime" --reference "$root/inputs/$case_id/reference.png" \
    --out "$output/$case_id" --key-file "$root/private-auth/deepseek-api.key" \
    --proxy http://10.120.48.31:30444 --rounds 2 --skill-mode full \
    --context-window 65536 --max-tokens 32768 --reasoning-effort max \
    --timeout 2700 --turn-timeout 900
done
