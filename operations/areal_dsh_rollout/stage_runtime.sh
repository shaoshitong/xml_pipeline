#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT=${1:?Usage: stage_runtime.sh TASK_ROOT LOCAL_RUNTIME}
LOCAL_RUNTIME=${2:?Supply an allocated-node scratch directory}
mkdir -p "$LOCAL_RUNTIME"
if [[ ! -f "$LOCAL_RUNTIME/.ready" ]]; then
    tar -xzf "$TASK_ROOT/runtime/dsh.tar.gz" -C "$LOCAL_RUNTIME"
    if [[ ! -x "$LOCAL_RUNTIME/node/bin/node" ]]; then
        cp -a "$TASK_ROOT/runtime/node-v24.11.1-linux-x64" "$LOCAL_RUNTIME/node"
    fi
    "$LOCAL_RUNTIME/node/bin/node" "$LOCAL_RUNTIME/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js" --version
    touch "$LOCAL_RUNTIME/.ready"
fi
"$LOCAL_RUNTIME/node/bin/node" "$LOCAL_RUNTIME/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js" --version
