"""Finite autonomous audit -> existing positive control -> unseen100 -> mass launch.

No external model, agent watch, or source rewrite. Completion of this process
means the fixed program was handed off; conversion goal remains active.
"""
import argparse, json, os, subprocess, sys, time, traceback, uuid, hashlib
from pathlib import Path
R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
sys.path.insert(0, str(W / 'scripts'))
ROOT = W / 'drawio_author_fixed_chain_v2'
CONTROLS = R / 'release/compiler_iterations/controls/drawio_author_raw_template_native_controls_20261101_v3/proof.json'
CONTROL_SHA = '31c173b9942b5f4ffc5206f3d8887590c502def6b97d1c01e264dedc6bff5bbc'
from compiler_types_program_v1 import raw, sha, atomic, immutable
from initial_conversion_process_v1 import identity
PIPELINE = ('drawio_author_iteration_case_v2.py', 'drawio_author_iteration_batch_v2.py', 'drawio_author_iteration_program_v2.py', 'drawio_author_unseen_pool_v2.py', 'drawio_author_source_once_v2.py', 'drawio_author_request_contract_v2.py', 'drawio_author_runtime_dispatch_v2.py', 'compiler_mermaid_alpha_iteration_overlap_v2.py', 'compiler_validation_reservation_v1.py', 'compiler_iteration_inventory_v1.py', 'initial_conversion_process_v1.py','compiler_plantuml_engine_canonical_claim_v1.py','drawio_author_version_quality_ro_v3.py','drawio_author_iteration_control_check_v2.py','drawio_author_quality_contract_v2.py')

def check(pins):
    for (path, digest) in pins.items():
        if sha(Path(path).read_bytes()) != digest:
            raise RuntimeError('infrastructure_chain_implementation_changed:' + path)

def current_inventory():
    pointer = json.loads((R / 'release/compiler_iterations/current.json').read_bytes())
    path = R / pointer['inventory']
    payload = path.read_bytes()
    if sha(payload) != pointer['inventory_sha256']:
        raise RuntimeError('current_inventory_pointer_hash_changed')
    summary = json.loads(payload)
    qualified = R / pointer['qualified_manifest']
    if sha(qualified.read_bytes()) != summary['files']['qualified.jsonl']['sha256'] or summary['accepted_integrity_errors']:
        raise RuntimeError('current_complete_inventory_not_verified')
    return (path.parent, {'summary': str(path), 'summary_sha256': sha(payload), 'qualified_manifest': str(qualified), 'qualified_manifest_sha256': sha(qualified.read_bytes()), 'qualified_total': summary['qualified_total']})

def launch(run_id):
    if not run_id or any((not (c.isalnum() or c in '-_') for c in run_id)):
        raise ValueError('invalid_run_id')
    work = ROOT / run_id
    work.mkdir(parents=True, exist_ok=False)
    controls = CONTROLS.read_bytes()
    if sha(controls) != CONTROL_SHA:
        raise ValueError('frozen_control_bundle_changed')
    bundle = json.loads(controls)
    pins = dict(bundle['frozen_frontend']['pins'])
    pins[str(CONTROLS)] = CONTROL_SHA
    for name in PIPELINE:
        path = W / 'scripts' / name
        pins[str(path)] = sha(path.read_bytes())
    pins[str(Path(__file__).resolve())] = sha(Path(__file__).read_bytes())
    from drawio_author_iteration_control_check_v2 import configuration as claim_control_pins
    pins.update(claim_control_pins())
    check(pins)
    import compiler_mermaid_alpha_iteration_overlap_v2 as overlap
    if str(Path(overlap.__file__).resolve())not in pins:raise ValueError('author_live_overlap_not_pinned')
    (inventory, proof) = current_inventory()
    protocol = {'schema': 'author_metadata_native_autonomous_finite_chain_v1', 'run_id': run_id, 'pins': pins, 'source_inventory': str(inventory), 'inventory_proof': proof, 'source_pool': str(R / 'release/compiler_iterations/source_pools' / run_id), 'workers': 4, 'case_timeout_seconds': 900, 'unseen_requested': 100, 'goal_complete': False, 'model_calls': 0}
    immutable(work / 'freeze.json', raw(protocol))
    nonce = uuid.uuid4().hex
    argv = [sys.executable, '-B', str(Path(__file__).resolve()), 'supervise', '--work', str(work), '--nonce', nonce]
    with (work / 'chain.log').open('ab') as log:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    birth = identity(child.pid)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('chain_exited_before_handshake')
        try:
            owner = json.loads((work / 'owner.json').read_bytes())
            current = identity(child.pid)
            if birth and current and (owner['pid'] == child.pid) and (owner['start_ticks'] == birth['start_ticks'] == current['start_ticks']) and (owner['nonce'] == nonce):
                immutable(work / ('ack_' + nonce + '.json'), raw(owner))
                result = {'pid': child.pid, 'start_ticks': birth['start_ticks'], 'work': str(work), 'source_pool': protocol['source_pool'], 'intended_program_dir': str(R / 'release/compiler_iterations/programs' / run_id), 'ready_file': str(work / 'ready.json'), 'failure_file': str(work / 'failure.json'), 'handshake_complete': True, 'watch': False, 'workers': 4, 'case_timeout_seconds': 900, 'goal_complete': False}
                immutable(work / 'launch.json', raw(result))
                return result
        except (FileNotFoundError, ValueError, KeyError):
            pass
        time.sleep(0.05)
    raise RuntimeError('chain_handshake_timeout_inspect_same_owner_no_restart')

def supervise(work, nonce):
    work = Path(work).resolve()
    assert work.is_relative_to(ROOT)
    protocol = json.loads((work / 'freeze.json').read_bytes())
    check(protocol['pins'])
    owner = {**identity(os.getpid()), 'nonce': nonce, 'argv': sys.argv}
    atomic(work / 'owner.json', owner)
    from compiler_types_program_v1 import wait_ack
    wait_ack(work / ('ack_' + nonce + '.json'), owner, nonce)
    stage = 'source_audit'
    atomic(work / 'state.json', {'stage': stage, 'goal_complete': False})
    try:
        import drawio_author_unseen_pool_v2 as pool
        import drawio_author_iteration_program_v2 as program
        from drawio_author_runtime_dispatch_v2 import main as controller_preflight
        info = pool.prepare(Path(protocol['source_pool']), Path(protocol['source_inventory']))
        check(protocol['pins'])
        if not info['selected']:
            atomic(work / 'ready.json', {'stage': 'next_repair_required', 'reason': 'no_fresh_independent_source_components', 'source_pool': protocol['source_pool'], 'goal_complete': False, 'model_calls': 0})
            return
        stage = 'actual_semantic_negative_then_existing_positive_controller_preflight'
        atomic(work / 'state.json', {'stage': stage, 'goal_complete': False})
        control = controller_preflight(Path(protocol['source_pool']))
        check(protocol['pins'])
        if not control['ordinary_semantic_failure_does_not_stop_next_case'] or not control['no_normal_frontend_calls']:
            raise RuntimeError('existing_controller_positive_failed_or_reconverted')
        stage = 'prepare_and_launch'
        atomic(work / 'state.json', {'stage': stage, 'goal_complete': False})
        prepared = program.prepare(Path(protocol['source_pool']), protocol['run_id'])
        check(protocol['pins'])
        started = program.launch(Path(prepared['program_dir']), 4, 900)
        ready = {'stage': 'fixed_validation_program_launched', 'source_pool': protocol['source_pool'], 'source_audit_selected': info['selected'], 'supported_remaining_population': info['counters']['supported_remaining_population'], 'controller_preflight': control['evidence_file'], 'prepared': prepared, 'program_launch': started, 'workers': 4, 'case_timeout_seconds': 900, 'passes_gate_then_automatically_all_applicable_mass': True, 'failure_requires_next_generic_repair': True, 'goal_complete': False, 'model_calls': 0}
        atomic(work / 'ready.json', ready)
        atomic(work / 'state.json', {'stage': 'handed_off_to_fixed_program', 'program_dir': prepared['program_dir'], 'goal_complete': False})
        print(json.dumps(ready), flush=True)
    except BaseException as error:
        failure = {'stage': stage, 'type': type(error).__name__, 'reason': str(error), 'traceback': traceback.format_exc(), 'goal_complete': False, 'next_action': 'Repair generic compiler/orchestration cause without stopping format; inspect exact evidence before any new launch.', 'model_calls': 0}
        atomic(work / 'failure.json', failure)
        atomic(work / 'state.json', {'stage': 'finite_chain_needs_repair', 'goal_complete': False})
        raise
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['launch', 'supervise'])
    p.add_argument('--run-id')
    p.add_argument('--work')
    p.add_argument('--nonce')
    a = p.parse_args()
    if a.action == 'launch':
        print(json.dumps(launch(a.run_id)), flush=True)
    else:
        supervise(a.work, a.nonce)
