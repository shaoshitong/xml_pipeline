"""Resume native-context generation, then own a Reviewer after the shared GPU is free."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import signal
import subprocess
import sys
import time

root = Path('/DATA/disk1/zbw_tmp4/drawio-agent-qwen38')
commit = sys.argv[1]
headroom = int(sys.argv[3]) if len(sys.argv) > 3 else None
source = root / 'source-snapshots' / commit[:7] / 'operations/areal_dsh_rollout'
sys.path.insert(0, str(source))
from h20_eval import environment, gpu_inventory, run_phase, start_server
from launch import ready
from matched_eval import verify_server

out = Path(sys.argv[2])
out.mkdir()
env = environment(root)
assert next(row['memory_used_mib'] for row in gpu_inventory() if row['index'] == 4) < 1024
contract = {'source_commit': commit, 'native_goal': False, 'gold_feedback': False,
    'training': False, 'generator_gpu': 4, 'reviewer_gpu': 6, 'context': 262144,
    'preserve_thinking': True, 'temperature': 1.0, 'completion_retries': 3,
    'compaction_headroom_tokens': headroom,
    'resume_from': sys.argv[4] if len(sys.argv) > 4 else str(root / 'runs/qwen38-controls-09298e7-r3/native/phase1/evaluation')}
services = []
code = 1
phase = 1
try:
    process, log = start_server(root, out / 'generator-server', 'generator',
        'Qwen3.8-27B', '4', 32414, 262144, .85, env, sampling='qwen38')
    services.append((process, log))
    ready(process, 32414, timeout=900)
    contract['generator_pid'] = process.pid
    contract['backend'] = verify_server(32414, 262144, out / 'generator-backend.json')
    (out / 'contract.json').write_text(json.dumps(contract, indent=2))
    print(json.dumps({'ready': 'generator', 'pid': process.pid}), flush=True)
    args = SimpleNamespace(root=root, port=32414, context_window=262144,
        sampling_preset='qwen38', preserve_thinking=True, turn_timeout=21600,
        completion_retries=3, compaction_headroom_tokens=headroom,
        python_runtime_root=Path('/DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm'))
    code = run_phase(args, 1, out, 32415, env, resume_from=Path(contract['resume_from']))
    if code == 0:
        while next(row['memory_used_mib'] for row in gpu_inventory() if row['index'] == 6) >= 1024:
            time.sleep(5)
        process, log = start_server(root, out / 'reviewer-server', 'reviewer',
            'Qwen3.5-4B', '6', 32415, 65536, .40, env, sampling='instruct')
        services.append((process, log))
        ready(process, 32415, timeout=900)
        contract['reviewer_pid'] = process.pid
        contract['reviewer_backend'] = verify_server(32415, 65536, out / 'reviewer-backend.json')
        (out / 'contract.json').write_text(json.dumps(contract, indent=2))
        phase = 2
        code = run_phase(args, 2, out, 32415, env)
    (out / 'result.json').write_text(json.dumps({'exit': code, 'completed_phase': phase if code == 0 else phase - 1}))
finally:
    for process, log in services:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        log.close()
    (out / 'gpu-inventory-after.json').write_text(json.dumps(gpu_inventory(), indent=2))
raise SystemExit(code)
