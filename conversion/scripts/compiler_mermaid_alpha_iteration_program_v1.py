"""Finite fresh validation -> verified release -> whole supported-population pass.

Ending this fixed program is a round boundary, never completion of the overall
iterative conversion goal. Its failure report is the input to the next repair.
"""
import argparse
import collections
import fcntl
import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

import compiler_mermaid_alpha_iteration_batch_v1 as controller
import compiler_mermaid_alpha_iteration_case_v1 as case
import fixed_batch_pipeline_v1 as base
import compiler_types_program_v1 as common
from compiler_validation_reservation_v1 import reserve

R, W = controller.R, controller.W
PROGRAMS = R / 'release/compiler_iterations/programs'
raw, sha, atomic, immutable, asset = common.raw, common.sha, common.atomic, common.immutable, common.asset


def owned(path):
    path = Path(path).resolve()
    if not path.is_relative_to(PROGRAMS.resolve()) or path == PROGRAMS.resolve():
        raise ValueError('iteration_program_outside_owner')
    return path


def readrows(path):
    return [json.loads(x) for x in Path(path).read_bytes().splitlines() if x]


def checked(ref):
    return common.checked(ref)


def template(pool):
    compiler, quality = case.bindings('mermaid')
    info = json.loads((pool / 'summary.json').read_bytes())
    config = compiler.configuration()
    if info.get('frontend_module') != compiler.__name__ or info['frozen_implementation'] != config:
        raise ValueError('source_pool_frontend_or_runtime_changed')
    pins = {**base.pins(), **config['pins'], **info['method_pins']}
    for module in (controller, case, quality, common, sys.modules[__name__], importlib.import_module('compiler_validation_reservation_v1'),importlib.import_module('compiler_typed_runtime_failure_v1'),importlib.import_module('compiler_iteration_inventory_v1'),importlib.import_module('compiler_mermaid_alpha_iteration_overlap_v1')):
        p = Path(module.__file__).resolve()
        pins[str(p)] = sha(p.read_bytes())
    for name, digest in info['method_pins'].items():
        if sha(Path(name).read_bytes()) != digest:
            raise ValueError('source_pool_method_changed')
    policy = {'frontend': compiler.__name__, 'source_policy': config['policy'], 'quality_version': quality.VERSION,
              'case_sha256': pins[str(Path(case.__file__).resolve())], 'quality_sha256': pins[str(Path(quality.__file__).resolve())]}
    freeze = dict(pins=pins, qa_policy_sha256=sha(raw(policy)), quality_bindings=policy,
                  predicate_hashes={compiler.UNITS['mermaid']: sha(raw({'frontend_sha256': pins[str(Path(compiler.__file__).resolve())], 'source_pool_method': info['method_pins']}))})
    freeze['implementation_identity'] = controller.implementation_identity(freeze)
    freeze['implementation_identity_sha256'] = controller.implementation_digest(freeze)
    controller.check_pins(pins)
    return freeze


CONTROLS=R/'release/compiler_iterations/controls/mermaid_alpha_layers_controls_20261101_v2/proof.json'


def control_bundle(compiler):
    bundle=json.loads(CONTROLS.read_bytes())
    if bundle.get('schema')!='compiler_mermaid_alpha_controls_v2' or bundle.get('frozen_frontend')!=compiler.configuration():
        raise ValueError('alpha_control_frontend_identity_changed')
    bundle['definition']=asset(CONTROLS)
    return bundle


def check_controls(bundle):
    _,data=checked(bundle['definition']);definition=json.loads(data)
    if {k:v for k,v in bundle.items()if k!='definition'}!=definition:raise ValueError('alpha_control_definition_changed')
    checked(bundle['producer']);checked(bundle['reused_controls_producer']);checked(bundle['qualified_manifest'])
    if bundle.get('source_policy')!='one_editable_rectangle_per_actual_CSS_layer_same_source_order_and_alpha':raise ValueError('alpha_source_layer_policy_changed')
    if len(bundle.get('positive_cases',[]))<3 or len(bundle.get('negative_cases',[]))<4:raise ValueError('alpha_control_count_incomplete')
    if len({r['id']for r in bundle['positive_cases']})!=len(bundle['positive_cases']):raise ValueError('duplicate_alpha_positive_source')
    names={r['name']for r in bundle['negative_cases']}
    if not {'opaque_source_alpha_layer','deleted_source_background_layer','changed_bound_terminal','deleted_source_label'}<=names:raise ValueError('alpha_semantic_mutations_incomplete')
    for role in ('positive','negative'):
        entries=bundle[role+'_cases']
        if sorted(raw(r['qa'])for r in entries)!=sorted(raw(r)for r in bundle[role+'s']):raise ValueError('alpha_control_QA_reference_changed')
        for row in entries:check_control_case(row,role)
    return True


def check_control_case(row,role):
    _,payload=checked(row['candidate']);record=json.loads(payload)
    _,qbody=checked(row['qa']);qa=json.loads(qbody)
    if qa.get('id')!=row['id']or qa.get('input_record_sha256')!=row['candidate']['sha256']:raise ValueError('alpha_control_QA_candidate_identity_changed')
    if (record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(row['id'],row['source_code_sha256'],row['source_image_sha256']):raise ValueError('alpha_control_source_identity_changed')
    for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:checked({'file':record[key],'sha256':record[digest]})
    if role=='positive':case.full_quality(qa,record)
    elif role=='negative':
        profile=qa.get('checks',{}).get('source_preliminary')or qa.get('checks',{}).get('source')or{}
        if not (row.get('actual_XML_and_PNG_rehashed')is True and qa.get('ok')is False and qa.get('failures')and profile.get('ok')is False and any(x.get('reason')=='source_geometry_text_or_paint_changed'for x in profile.get('failures',[]))):raise ValueError('alpha_negative_not_actual_source_rejection')
        if case.runtime_failure(qa.get('failures',[])):raise ValueError('alpha_negative_is_infrastructure_failure')
    else:raise ValueError('unknown_alpha_control_role')


def prepare(pool, run_id):
    pool = Path(pool).resolve(strict=True)
    if not run_id or not all(c.isalnum() or c in '-_' for c in run_id):
        raise ValueError('invalid_iteration_run_id')
    p = owned(PROGRAMS / run_id)
    p.mkdir(parents=True, exist_ok=False)
    freeze = template(pool)
    compiler, _ = case.bindings('mermaid')
    controls = control_bundle(compiler)
    check_controls(controls)
    info = json.loads((pool / 'summary.json').read_bytes())
    selected = readrows(pool / 'selected.jsonl')
    if not selected or (len(selected) < 100 and not info['all_remaining_observed_families_selected']):
        raise ValueError('insufficient_or_incomplete_unseen_cohort')
    for name, value in info['files'].items():
        if sha((pool / name).read_bytes()) != value['sha256']:
            raise ValueError('source_pool_asset_changed:' + name)
    protocol = dict(minimum_major_format_samples=100, actual_samples=len(selected),
                    shortage_exhaustive_exception=len(selected) < 100,
                    minimum_qualified_fraction=.20, minimum_new_qualified=min(5, len(selected)),
                    maximum_regressions=0, maximum_infrastructure_errors=0, maximum_negative_false_acceptances=0,
                    normal_candidate_attempts_per_id_per_version=1,
                    source_pool_summary=asset(pool / 'summary.json'), controls=controls,
                    goal_complete_when_this_program_finishes=False)
    immutable(p / 'implementation.json', raw(freeze))
    immutable(p / 'protocol.json', raw(protocol))
    immutable(p / 'selected.jsonl', (pool / 'selected.jsonl').read_bytes())
    immutable(p / 'supported_population.jsonl', (pool / 'supported_population.jsonl').read_bytes())
    runs = {phase: controller.FLOOR / (run_id + '_' + phase) for phase in ('B', 'C')}
    reservation = reserve(R / 'release/compiler_v1/validation_registry.sqlite', selected, audit=pool, run_prefix=run_id,
                          implementation_identity_sha256=freeze['implementation_identity_sha256'],
                          phase_runs={k: str(v) for k, v in runs.items()},
                          selected_manifest_sha256=sha((p / 'selected.jsonl').read_bytes()),
                          protocol_sha256=sha(raw(protocol)), controls_proof_sha256=sha(raw(controls)))
    immutable(p / 'reservation.json', raw(reservation))
    for phase, run in runs.items():
        rows = [{**x, 'evaluation_phase': 'baseline' if phase == 'B' else 'candidate'} for x in selected]
        data = b''.join(raw(x) for x in rows)
        immutable(p / (phase + '.jsonl'), data)
        phase_freeze = {**freeze, 'input_sha256': sha(data)}
        immutable(p / (phase + '.freeze.json'), raw(phase_freeze))
        controller.create(run, p / (phase + '.jsonl'), p / (phase + '.freeze.json'), 'validation')
    atomic(p / 'state.json', dict(stage='prepared', runs={k: str(v) for k, v in runs.items()}, goal_complete=False))
    return dict(program_dir=str(p), samples_each=len(selected), supported_population=info['counters']['supported_remaining_population'],
                reserved=True, dispatched=False, implementation_identity_sha256=freeze['implementation_identity_sha256'])


def results(run):
    snapshot = controller.snapshot(run)
    if not snapshot['metadata'].get('finished') or snapshot['infrastructure_stop'] or any(k not in base.TERMINAL for k in snapshot['counts']):
        raise RuntimeError('phase_not_terminal_or_infrastructure:' + str(run))
    with sqlite3.connect('file:' + str(run / 'status.sqlite') + '?mode=ro', uri=True) as db:
        rows = db.execute('select id,attempts,result from samples order by seq').fetchall()
    if any(attempts != 1 for _, attempts, _ in rows):
        raise ValueError('phase_repeated_or_missing_attempt')
    return {identifier: json.loads(body) for identifier, _, body in rows}


def computed_gate(p):
    freeze = json.loads((p / 'implementation.json').read_bytes())
    protocol = json.loads((p / 'protocol.json').read_bytes())
    checked(protocol['source_pool_summary'])
    check_controls(protocol['controls'])
    selected = readrows(p / 'selected.jsonl')
    phases = {phase: results(controller.FLOOR / (p.name + '_' + phase)) for phase in ('B', 'C')}
    expected = {x['id'] for x in selected}
    if any(set(rows) != expected for rows in phases.values()):
        raise ValueError('unseen_phase_identity_or_count_mismatch')
    for phase, rows in phases.items():
        for request in selected:
            x = rows[request['id']]
            if (x['source_code_sha256'], x['source_image_sha256'], x['compiler_unit']) != (request['source']['code_sha256'], request['source']['image_sha256'], request['compiler_unit']):
                raise ValueError('unseen_outcome_source_identity_changed')
            if x['status'] == 'qualified':
                manifest = x['manifest']
                _, payload = common.checked({'file': manifest['metadata_file'], 'sha256': manifest['metadata_sha256']}, clean=True)
                qa = json.loads((R / x['quality_report']).read_bytes())
                case.full_quality(qa, json.loads(payload))
    b = {i for i, x in phases['B'].items() if x['status'] == 'qualified'}
    c = {i for i, x in phases['C'].items() if x['status'] == 'qualified'}
    infra = sum(x.get('infrastructure_failure') is True for rows in phases.values() for x in rows.values())
    passed = len(c) / len(selected) >= protocol['minimum_qualified_fraction'] and len(c - b) >= protocol['minimum_new_qualified'] and not b - c and infra == 0
    unit = selected[0]['compiler_unit']
    return dict(implementation_identity=freeze['implementation_identity'], implementation_identity_sha256=freeze['implementation_identity_sha256'],
                approved_units=[unit] if passed else [], controls_passed=True, infrastructure_errors=infra,
                units={unit: dict(passed=passed, samples=len(selected), B_qualified=len(b), C_qualified=len(c),
                                  new_qualified=len(c-b), positive_regressions=len(b-c), full_qualified_rate=len(c)/len(selected))},
                protocol_sha256=sha((p / 'protocol.json').read_bytes()), model_calls=0, goal_complete=False)


def verify_release_gate(path, freeze, units):
    path = Path(path)
    p = owned(path.parent)
    actual = computed_gate(p)
    if json.loads(path.read_bytes()) != actual:
        raise ValueError('release_gate_not_reproducible_from_actual_B_C')
    if actual['implementation_identity'] != controller.implementation_identity(freeze) or not units or not set(units) <= set(actual['approved_units']):
        raise ValueError('batch_contains_unvalidated_iteration_unit')
    return actual


def run_phase(run, workers, timeout, program):
    nonce = uuid.uuid4().hex
    start, ack = run / ('start_' + nonce + '.json'), run / ('ack_' + nonce + '.json')
    argv = [sys.executable, '-B', str(Path(controller.__file__).resolve()), 'run', '--run-id', run.name,
            '--workers', str(workers), '--case-timeout', str(timeout), '--program-start', str(start), '--program-ack', str(ack), '--program-nonce', nonce]
    with (program / (run.name + '.log')).open('ab') as log:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                                 env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    from initial_conversion_process_v1 import identity
    birth = identity(child.pid)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('phase_child_exited_before_handshake')
        try:
            owner = json.loads(start.read_bytes())
            current = identity(child.pid)
            if birth and current and owner['pid'] == child.pid and owner['start_ticks'] == birth['start_ticks'] == current['start_ticks'] and owner['nonce'] == nonce:
                immutable(ack, raw(owner))
                immutable(program / (run.name + '.child.json'), raw(dict(pid=child.pid, start_ticks=birth['start_ticks'], argv=argv)))
                break
        except (OSError, KeyError, ValueError):
            pass
        time.sleep(.05)
    else:
        raise RuntimeError('phase_identity_handshake_timeout_no_automatic_restart')
    if child.wait() != 0:
        raise RuntimeError('phase_process_failed')
    return results(run)


def preserve_current_qualified(p,population):
    """Publish no duplicate when another finite run has qualified a source."""
    from compiler_iteration_inventory_v1 import check_manifest
    wanted={row['id']:row['source']for row in population};root=R/'release/compiler_iterations';paths=[]
    current=root/'current.json'
    if current.exists():
        pointer=json.loads(current.read_bytes());_,body=checked({'file':pointer['inventory'],'sha256':pointer['inventory_sha256']});summary=json.loads(body)
        ref={'file':pointer['qualified_manifest'],'sha256':summary['files']['qualified.jsonl']['sha256']};path,_=checked(ref);paths.append(path)
    for floor in (root/'controls',root/'runs'):
        if floor.exists():paths.extend(directory/'qualified.jsonl'for directory in floor.iterdir()if directory.is_dir()and(directory/'qualified.jsonl').is_file())
    preserved={};cache={}
    for path in paths:
        for old in readrows(path):
            if old.get('id')not in wanted:continue
            check_manifest(R,old['id'],wanted[old['id']],old,cache);preserved.setdefault(old['id'],old)
    immutable(p/'mass_preserved_qualified.jsonl',b''.join(raw(row)for row in preserved.values()))
    return set(preserved)


def build_mass(p, gate):
    freeze = json.loads((p / 'implementation.json').read_bytes())
    selected = {x['id'] for x in readrows(p / 'selected.jsonl')}
    controls=json.loads((p/'protocol.json').read_bytes())['controls'] if (p/'protocol.json').exists() else {}
    processed_controls={x['id'] for x in controls.get('positive_cases',[])}
    population=readrows(p/'supported_population.jsonl')
    preserved=preserve_current_qualified(p,population)
    from compiler_mermaid_alpha_iteration_overlap_v1 import snapshot as active_snapshot
    active=active_snapshot(ignore_runs=(p.name,))
    immutable(p/'mass_live_overlap_snapshot.json',raw(active))
    active_ids=set(active['active'])
    rows = [x for x in population if x['id'] not in selected|processed_controls|preserved|active_ids and x['compiler_unit'] in gate['approved_units']]
    if not rows:
        return None
    for seq, x in enumerate(rows, 1):
        x['seq'] = seq
    payload = b''.join(raw(x) for x in rows)
    immutable(p / 'mass.jsonl', payload)
    freeze = {**freeze, 'input_sha256': sha(payload), 'release_gate': asset(p / 'release_gate.json')}
    immutable(p / 'mass.freeze.json', raw(freeze))
    run = controller.FLOOR / (p.name + '_mass')
    controller.create(run, p / 'mass.jsonl', p / 'mass.freeze.json', 'batch')
    return run


def supervise(p, workers, timeout, nonce):
    p = owned(p)
    with (p / 'program.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze = json.loads((p / 'implementation.json').read_bytes())
        controller.check_pins(freeze['pins'])
        owner = {**controller.process_identity(), 'nonce': nonce, 'argv': sys.argv, 'watch': False}
        atomic(p / 'owner.json', owner)
        common.wait_ack(p / ('launch_ack_' + nonce + '.json'), owner, nonce)
        try:
            for phase in ('B', 'C'):
                atomic(p / 'state.json', dict(stage='validation_' + phase, goal_complete=False))
                run_phase(controller.FLOOR / (p.name + '_' + phase), workers, timeout, p)
            gate = computed_gate(p)
            immutable(p / 'release_gate.json', raw(gate))
            mass = build_mass(p, gate)
            atomic(p / 'state.json', dict(stage='mass' if mass else 'next_iteration_required', mass=str(mass) if mass else None, gate=gate, goal_complete=False))
            if mass:
                run_phase(mass, workers, timeout, p)
            inventories = R / 'release/compiler_iterations' / (p.name + '_final_inventory')
            argv = [sys.executable, '-B', str(W / 'scripts/compiler_iteration_inventory_v1.py'), '--output', str(inventories)]
            with (p / 'inventory.log').open('ab') as log:
                result = subprocess.run(argv, stdout=log, stderr=log)
            if result.returncode:
                raise RuntimeError('round_final_inventory_failed')
            summary = json.loads((inventories / 'summary.json').read_bytes())
            atomic(p / 'summary.json', dict(stage='round_complete_next_repair_required', qualified_total=summary['qualified_total'],
                                           inventory=str(inventories), mass=str(mass) if mass else None, gate=gate,
                                           goal_complete=False, next_action='Analyze all remaining failures and implement the next generic converter version.', model_calls=0))
            atomic(p / 'state.json', dict(stage='round_complete_next_repair_required', goal_complete=False))
        except BaseException as error:
            atomic(p / 'infrastructure_stop.json', dict(reason=str(error), type=type(error).__name__, goal_complete=False))
            raise


def launch(p, workers, timeout):
    p = owned(p)
    if (p / 'launch.json').exists() or (p / 'owner.json').exists():
        raise ValueError('already_launched_inspect_actual_owner_no_duplicate_restart')
    nonce = uuid.uuid4().hex
    argv = [sys.executable, '-B', str(Path(__file__).resolve()), 'supervise', '--program-dir', str(p), '--workers', str(workers), '--case-timeout', str(timeout), '--nonce', nonce]
    with (p / 'supervisor.log').open('ab') as log:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                                 env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
    deadline = time.monotonic() + 10
    from initial_conversion_process_v1 import identity
    birth = identity(child.pid)
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError('program_exited_before_handshake')
        try:
            owner = json.loads((p / 'owner.json').read_bytes())
            now = identity(child.pid)
            if birth and now and owner['pid'] == child.pid and owner['start_ticks'] == birth['start_ticks'] == now['start_ticks'] and owner['nonce'] == nonce:
                immutable(p / ('launch_ack_' + nonce + '.json'), raw(owner))
                result = dict(pid=child.pid, start_ticks=birth['start_ticks'], argv=argv, program_dir=str(p), finite=True, watch=False, goal_complete=False)
                immutable(p / 'launch.json', raw(result))
                return result
        except (OSError, KeyError, ValueError):
            pass
        time.sleep(.05)
    raise RuntimeError('program_launch_observation_timeout_inspect_same_pid_no_restart')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'audit-launch', 'launch', 'supervise', 'evaluate'))
    parser.add_argument('--pool', type=Path)
    parser.add_argument('--inventory',type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--program-dir', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--case-timeout', type=float, default=600)
    parser.add_argument('--nonce')
    args = parser.parse_args()
    if not 1 <= args.workers <= 12 or not 1 <= args.case_timeout <= 1800:
        parser.error('resource_limits')
    if args.action == 'audit-launch':
        from compiler_mermaid_alpha_iteration_pool_v1 import prepare as source_audit
        info=source_audit(args.pool,args.inventory)
        if info['selected']:
            prepared=prepare(args.pool,args.run_id)
            value={'prepared':prepared,'launch':launch(Path(prepared['program_dir']),args.workers,args.case_timeout),'goal_complete':False}
        else:value={'dispatched':False,'next_repair_required':True,'reason':'no_fresh_known_source_family_remaining','goal_complete':False}
    elif args.action == 'prepare':
        value = prepare(args.pool, args.run_id)
    elif args.action == 'launch':
        value = launch(args.program_dir, args.workers, args.case_timeout)
    elif args.action == 'supervise':
        value = supervise(args.program_dir, args.workers, args.case_timeout, args.nonce)
    else:
        value = computed_gate(owned(args.program_dir))
    print(json.dumps(value, ensure_ascii=False))
