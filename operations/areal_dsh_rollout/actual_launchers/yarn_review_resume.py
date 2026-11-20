"""Resume the rejected Reviewer response; reuse completed generation and live services."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys

root = Path('/DATA/disk1/zbw_tmp4/drawio-agent-qwen38')
source = root / 'source-snapshots/09298e7/operations/areal_dsh_rollout'
sys.path.insert(0, str(source))
from h20_eval import environment, run_phase

previous = root / 'runs/qwen38-controls-09298e7-r3/yarn/phase2/evaluation'
out = root / 'runs/qwen38-yarn-review-resume-09298e7-r4'
out.mkdir()
(out / 'contract.json').write_text(json.dumps({
    'source_commit': '09298e7f00fd920e71b7bb406d7cf9e4c2cf4031',
    'resume_from': str(previous), 'recovery_reason': 'invalid_reviewer_json',
    'reuse_completed_generator': True, 'reuse_reviewer_session': True,
    'own_live_servers_only': True, 'gold_feedback': False, 'training': False,
}, indent=2))
args = SimpleNamespace(root=root, port=32424, context_window=1048576,
    sampling_preset='qwen38', preserve_thinking=True, turn_timeout=21600,
    python_runtime_root=Path('/DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm'))
code = run_phase(args, 2, out, 32435, environment(root), resume_from=previous)
(out / 'result.json').write_text(json.dumps({'exit': code, 'completed_phase': 2 if code == 0 else 1}))
raise SystemExit(code)
