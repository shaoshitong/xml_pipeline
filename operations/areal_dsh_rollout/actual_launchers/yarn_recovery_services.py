"""Own the restored YaRN/Reviewer services for the retained-session continuation."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import signal
import sys

root = Path('/DATA/disk1/zbw_tmp4/drawio-agent-qwen38')
commit = sys.argv[1] if len(sys.argv) > 1 else 'fc8756d8797939277e6484faf4fecb3381418ebd'
source = root / 'source-snapshots' / commit[:7] / 'operations/areal_dsh_rollout'
sys.path.insert(0, str(source))
from h20_eval import environment, gpu_inventory, run_phase, start_server
from launch import ready
from matched_eval import verify_server

out = Path(sys.argv[2]) if len(sys.argv) > 2 else root / 'runs/qwen38-yarn-recovery-fc8756d-r6'
out.mkdir()
env = environment(root)
inventory = gpu_inventory()
reuse_review = len(sys.argv) > 4 and sys.argv[4] == 'reuse-review'
assert all(row['memory_used_mib'] < 1024 for row in inventory if row['index'] in ({5} if reuse_review else {5, 6}))
contract = {'source_commit': commit, 'gpu_inventory_before': inventory,
    'resumed_from': sys.argv[3] if len(sys.argv) > 3 else str(root / 'runs/qwen38-yarn-review-resume-fc8756d-r5/phase2/evaluation'),
    'generator_gpu': 5, 'reviewer_gpu': 6, 'training': False, 'gold_feedback': False,
    'reuse_completed_generator': True, 'reuse_reviewer_session': True, 'native_goal': False}
contract['reuse_saved_review_response'] = reuse_review
services = []
try:
    specifications = (
        ('generator', 'generator', 'Qwen3.8-27B', '5', 32424, 1048576, .94, True),
        ('reviewer', 'reviewer', 'Qwen3.5-4B', '6', 32435, 65536, .40, False))
    for name, role, model, devices, port, context, fraction, yarn in specifications[:1] if reuse_review else specifications:
        process, log = start_server(root, out / (name + '-server'), role, model,
            devices, port, context, fraction, env, yarn=yarn,
            sampling='qwen38' if role == 'generator' else 'instruct')
        services.append((process, log))
        ready(process, port, timeout=900)
        contract[name + '_backend'] = verify_server(port, context, out / (name + '-backend.json'))
        contract[name + '_pid'] = process.pid
        (out / 'contract.json').write_text(json.dumps(contract, indent=2))
        print(json.dumps({'ready': name, 'pid': process.pid}), flush=True)
    args = SimpleNamespace(root=root, port=32424, context_window=1048576,
        sampling_preset='qwen38', preserve_thinking=True, turn_timeout=21600,
        completion_retries=3, python_runtime_root=Path('/DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm'))
    code = run_phase(args, 2, out, 32435, env, resume_from=Path(contract['resumed_from']))
    (out / 'result.json').write_text(json.dumps({'exit': code, 'completed_phase': 2 if code == 0 else 1}))
finally:
    for process, log in services:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except __import__('subprocess').TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        log.close()
    (out / 'gpu-inventory-after.json').write_text(json.dumps(gpu_inventory(), indent=2))
raise SystemExit(code)
