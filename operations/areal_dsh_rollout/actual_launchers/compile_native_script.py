"""Compile an unchanged model-authored script in a private copy; not an agent success."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path('/DATA/disk1/zbw_tmp4/drawio-agent-qwen38')
source = root / 'runs/qwen38-native-budget-2db2b87-r5/phase1/evaluation/episode/case'
out = root / 'runs/qwen38-native-script-diagnostic'
out.mkdir()
body = (source / 'gen_round1.py').read_bytes()
case = out / 'case'
shutil.copytree(source, case)
(case / 'gen_round1.py').write_bytes(body)
python_runtime = Path('/DATA/disk1/zbw_tmp4/rdm-sets/envs/rdm')
renderer_python = root / 'renderer/venv/bin/python'
command = [str(root / 'bin/bwrap'), '--unshare-all', '--new-session', '--die-with-parent',
    '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
    '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
    '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
    '--ro-bind', str(root / 'renderer/venv'), str(root / 'renderer/venv'),
    '--ro-bind', str(python_runtime), str(python_runtime), '--bind', str(case), '/case',
    '--setenv', 'HOME', '/tmp', '--setenv', 'LANG', 'C.UTF-8', '--chdir', '/case',
    '--', str(renderer_python), '/case/gen_round1.py']
result = subprocess.run(command, capture_output=True, text=True, timeout=30,
    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
receipt = {'script_sha256': sha256(body).hexdigest(), 'script_unchanged': True,
    'actor_episode_completed': False, 'host_compilation_diagnostic': True,
    'active_case_mounted': False, 'gold_feedback': False, 'exit': result.returncode,
    'stdout': result.stdout, 'stderr': result.stderr}
(out / 'execution.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt), flush=True)
if result.returncode:
    raise SystemExit(result.returncode)
sys.path.insert(0, str(root / 'source-snapshots/2db2b87/operations/areal_dsh_rollout'))
from render import render
os.environ['DSH_CHROME_TMPDIR'] = str(root.parent / 'dio-tmp')
metadata = render(case / 'round1.drawio', case / 'round1.png', root / 'renderer')
(out / 'render.json').write_text(json.dumps(metadata, indent=2))
print(json.dumps(metadata), flush=True)
