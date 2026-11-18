#!/usr/bin/env bash
#SBATCH --account=mou176
#SBATCH --partition=acd_u
#SBATCH --exclude=ACD1-24
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --job-name=drawio-frozen-reviewer
set -euo pipefail

root=${TASK_ROOT:-/data/user/mou176/experiments/drawio-areal-dsh-20261118}
export MODEL_SIZE=4B REVIEWER_ONLY=1
exec bash "$root/source/operations/areal_dsh_rollout/services.sbatch"
