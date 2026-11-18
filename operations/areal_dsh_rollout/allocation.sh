#!/usr/bin/env bash
set -euo pipefail
date -Iseconds
hostname
nvidia-smi --query-gpu=index,name,memory.total,memory.used,driver_version --format=csv
sleep "${ALLOCATION_SECONDS:-14400}"
