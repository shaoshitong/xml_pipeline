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

import svg_analytic_iteration_batch_v3 as controller
import svg_analytic_iteration_case_v3 as case
import fixed_batch_pipeline_v1 as base
import compiler_types_program_v1 as common
import compiler_source_core_attempts_v3 as history
import svg_analytic_source_contract_v3 as contract
from compiler_validation_reservation_v2 import reserve,reserve_fresh
import svg_analytic_cohort_refresh_v3 as refresh

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


def checked(ref, clean=False):
    return common.checked(ref, clean=clean)


def template(pool):
    compiler, quality = case.bindings('svg')
    info = json.loads((pool / 'summary.json').read_bytes())
    config = compiler.configuration()
    if info.get('frontend_module') != compiler.__name__ or info['frozen_implementation'] != config:
        raise ValueError('source_pool_frontend_or_runtime_changed')
    pins = {**base.pins(), **config['pins'], **info['method_pins']}
    for module in (controller, case, quality, common, sys.modules[__name__], importlib.import_module('compiler_validation_reservation_v2'), importlib.import_module('svg_analytic_iteration_controls_v4'),importlib.import_module('compiler_typed_runtime_failure_v1'),importlib.import_module('svg_analytic_iteration_chain_v4'),importlib.import_module('compiler_mermaid_alpha_iteration_overlap_v2'),importlib.import_module('compiler_mermaid_alpha_qualifications_v2'),history):
        p = Path(module.__file__).resolve()
        pins[str(p)] = sha(p.read_bytes())
    for name, digest in info['method_pins'].items():
        if sha(Path(name).read_bytes()) != digest:
            raise ValueError('source_pool_method_changed')
    pins[str(R/contract.CATALOG)]=sha((R/contract.CATALOG).read_bytes())
    for name in ('svg_analytic_source_contract_v3.py','strict_native_canvas_evidence_v1.py','compiler_svg_general_unseen_pool_v3.py','svg_analytic_private_QA_lease_v1.py','svg_analytic_cohort_refresh_v3.py','compiler_validation_identity_alias_v1.py','compiler_validation_sealed_cohort_v1.py','compiler_plantuml_engine_canonical_claim_v1.py'):
        path=W/'scripts'/name;pins[str(path)]=sha(path.read_bytes())

    policy = {'frontend': compiler.__name__, 'source_policy': config['policy'], 'quality_version': quality.VERSION,
              'case_sha256': pins[str(Path(case.__file__).resolve())], 'quality_sha256': pins[str(Path(quality.__file__).resolve())]}
    freeze = dict(pins=pins, qa_policy_sha256=sha(raw(policy)), quality_bindings=policy,
                  predicate_hashes={compiler.UNIT: sha(raw({'frontend_sha256': pins[str(Path(compiler.__file__).resolve())], 'source_pool_method': info['method_pins']}))})
    freeze['implementation_identity'] = controller.implementation_identity(freeze)
    freeze['implementation_identity_sha256'] = controller.implementation_digest(freeze)
    controller.check_pins(pins)
    return freeze


def control_bundle(compiler):
    body=(R/contract.CONTROLS).read_bytes()
    if sha(body)!=contract.CONTROLS_SHA256:raise ValueError('frozen_SVG_analytic_controls_changed')
    bundle=json.loads(body)
    if bundle['frozen_frontend']!=compiler.configuration():raise ValueError('SVG_analytic_source_core_changed')
    return {**bundle,'definition':asset(R/contract.CONTROLS)}

def check_control_case(row,role,configuration=None):
    from svg_analytic_iteration_controls_v4 import check_control_case as actual
    return actual(row,role,configuration)

def check_controls(bundle):
    from svg_analytic_iteration_controls_v4 import check_controls as actual
    return actual(bundle)


RUNTIME_CONTROLS=R/'release/compiler_iterations/controls/svg_actual_shadow_runtime_controls_20261102_v3/proof.json'


def runtime_controls():
    proof=json.loads(RUNTIME_CONTROLS.read_bytes());compiler,_=case.bindings('svg');configuration=compiler.configuration()
    if proof.get('source_configuration')!=configuration or proof.get('source_core')!=history.core_identity(configuration):raise ValueError('SVG_runtime_SOURCE_core_changed')
    if proof.get('schema')!='real_once_safe_SVG_analytic_runtime_dispatch_controls_v1'or not all(proof.get(key)is True for key in ('consumed_normal_prevented_then_next_full_positive','no_infrastructure_stop','each_attempted_once','canonical_original_jobs_unchanged','same_core_normal_history_unchanged'))or proof.get('normal_source_conversion_calls')!=0:raise ValueError('SVG_once_safe_runtime_controls_not_passed')
    checked(proof['producer']);checked(proof['freeze']);checked(proof['input'])
    for path,digest in proof['orchestration_pins'].items():
        if sha(Path(path).read_bytes())!=digest:raise ValueError('SVG_runtime_orchestration_changed')
    _,payload=checked(proof['historical_manual_normal_event']);event=json.loads(payload);history.validate([event],configuration,root=R)
    if event['evidence_kind']!='manual_development'or event['id']!=proof['cases'][0]['id']:raise ValueError('SVG_runtime_guard_not_bound_to_consumed_normal')
    _,before=checked(proof['normal_history_before']);_,after=checked(proof['normal_history_after'])
    if before!=after:raise ValueError('SVG_runtime_controls_reexecuted_normal')
    events=[json.loads(row)for row in before.splitlines()if row]
    expected={row['id']for row in json.loads((R/contract.CATALOG).read_bytes())['entries']if row['source_core_key']==history.core_identity(configuration)['key']}
    if len(events)!=len(expected)or{row['id']for row in events}!=expected or event not in events:raise ValueError('SVG_runtime_normal_history_not_exact_frozen_catalog')
    history.validate(events,configuration,root=R)
    _,payload=checked(proof['source_contract_metadata']);source=json.loads(payload)
    if source.get('actual_pool_constructor_and_program_validator')is not True or source.get('canonical_baseline_and_capture_unchanged')is not True or source['canonical_sha256_before']!=source['canonical_sha256_after']or len({row['id']for row in source['cases']})<5 or any(row.get('supported')is not True or row.get('canonical_job_columns')!=13 for row in source['cases']):raise ValueError('SVG_real_canonical_dictionary_contract_missing')
    cases=proof['cases']
    if len(cases)!=2 or[row['seq']for row in cases]!=[1,2]:raise ValueError('SVG_runtime_controls_not_two_ordered_cases')
    for row in cases:
        _,payload=checked(row['result']);result=json.loads(payload)
        if row['attempts']!=1 or result['id']!=row['id']or row.get('frontend'):raise ValueError('SVG_runtime_controller_reexecuted_normal')
        if row['seq']==1:
            if result.get('status')!='abandoned'or result.get('phase')!='input'or result.get('infrastructure_failure')is not False or not any(str(result.get('detail','')).startswith(prefix)for prefix in history.PRECALL):raise ValueError('SVG_consumed_normal_not_stopped_before_conversion')
        else:
            if result.get('status')!='qualified'or not row.get('existing_positive_no_normal_reexecution'):raise ValueError('SVG_next_existing_positive_not_full_qualified')
            manifest=result['manifest'];_,payload=checked(dict(file=manifest['metadata_file'],sha256=manifest['metadata_sha256']),clean=True);_,qa=checked(row['quality']);case.full_quality(json.loads(qa),json.loads(payload))
    state=controller.snapshot(Path(proof['run']))
    if state['infrastructure_stop']or not state['metadata'].get('finished')or state['dispatch_attempt_counts']!={1:2}:raise ValueError('SVG_runtime_controller_not_once_finished')
    return asset(RUNTIME_CONTROLS)


def validate_source_requests(rows):
    """Validate the exact complete worker source/capture/baseline before reserve."""
    compiler,_=case.bindings('svg');seen=set()
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as database:
        for row in rows:
            if row['id']in seen:raise ValueError('duplicate_source_request_ID')
            seen.add(row['id']);job=database.execute('select*from jobs where id=?',(row['id'],)).fetchone()
            if not job:raise ValueError('selected_canonical_job_missing')
            source=json.loads(job[4]);old=json.loads(job[9])if job[9]else{}
            if row.get('source')!=source or source.get('pair_sha256')!=row['id']:raise ValueError('selected_worker_requires_complete_canonical_source_record')
            if source.get('format')!='svg'or source.get('category')not in ('scientific_diagram',)or row.get('compiler_unit')!=compiler.UNIT:raise ValueError('selected_source_outside_original_SVG_scope')
            if row.get('source_record_sha256')!=sha((job[9]or'').encode()):raise ValueError('selected_baseline_record_snapshot_changed')
            if(row.get('baseline_code_sha256'),row.get('baseline_image_sha256'))!=(old.get('code_sha256'),old.get('image_sha256')):raise ValueError('selected_baseline_asset_snapshot_changed')
            snapshot=row.get('source_capture_snapshot')
            if not isinstance(snapshot,dict):raise ValueError('selected_source_capture_snapshot_missing')
            seed,original=compiler.original({'compiler_source_capture_snapshot':snapshot},job)
            if original!=job or seed['compiler_source_capture_snapshot']!=snapshot:raise ValueError('selected_source_capture_snapshot_changed')
    return True


def prepare(pool, run_id):
    pool = Path(pool).resolve(strict=True)
    if not run_id or not all(c.isalnum() or c in '-_' for c in run_id):
        raise ValueError('invalid_iteration_run_id')
    p = owned(PROGRAMS / run_id)
    if p.exists():raise ValueError('program_directory_already_exists')
    freeze = template(pool)
    compiler, _ = case.bindings('svg')
    controls = control_bundle(compiler)
    check_controls(controls)
    info = json.loads((pool / 'summary.json').read_bytes())
    selected = readrows(pool / 'selected.jsonl')
    if not selected or (len(selected) < 100 and not info['all_remaining_observed_families_selected']):
        raise ValueError('insufficient_or_incomplete_unseen_cohort')
    for name, value in info['files'].items():
        if sha((pool / name).read_bytes()) != value['sha256']:
            raise ValueError('source_pool_asset_changed:' + name)
    population={x['id']:x for x in readrows(pool/'supported_population.jsonl')}
    prior_ids={x['id']for x in readrows(pool/'prior_candidate_attempts.jsonl')}
    for item in selected:
        if item['id']in prior_ids:raise ValueError('prior_SOURCE_candidate_attempt_reentered_validation')
        original=population.get(item['id'])
        if original is None or any(item[k]!=original[k]for k in ('source','source_capture_snapshot','source_record_sha256','baseline_code_sha256','baseline_image_sha256')):
            raise ValueError('selected_capture_or_baseline_not_bound_to_source_population')
        capture=item['source_capture_snapshot'];source=item['source']
        if (capture.get('id'),capture.get('source_code_sha256'),capture.get('source_image_sha256'))!=(item['id'],source['code_sha256'],source['image_sha256']):
            raise ValueError('selected_capture_source_identity_changed')
    validate_source_requests(selected)
    validate_source_requests(readrows(pool/'supported_population.jsonl'))
    # The whole candidate universe was verified before any registry mutation or
    # program mkdir. Re-selection uses this sealed metadata and fresh knowledge.
    seal=json.loads((pool/'sealed_source_components.json').read_bytes())
    refreshed={}
    protocol_base=dict(minimum_major_format_samples=100,
                    minimum_qualified_fraction=.20,minimum_new_qualified=5,
                    maximum_regressions=0,maximum_infrastructure_errors=0,maximum_negative_false_acceptances=0,
                    normal_candidate_attempts_per_id_per_version=1,
                    source_pool_summary=asset(pool/'summary.json'),controls=controls,runtime_dispatch_controls=runtime_controls(),
                    goal_complete_when_this_program_finishes=False,
                    sealed_source_components=asset(pool/'sealed_source_components.json'))
    runs={phase:controller.FLOOR/(run_id+'_'+phase)for phase in ('B','C')}
    bound={}
    def selector(existing,raw_registry):
        snapshot=refresh.knowledge_snapshot(pool,compiler.configuration())
        refreshed['snapshot']=snapshot
        choice=refresh.choose(seal,list(population.values()),snapshot,existing,seed=info['seed'],limit=100)
        if not choice['selected']:raise ValueError('SVG_no_remaining_known_unseen_family_after_atomic_freshness')
        choice['raw_registry_keys_sha256']=sha(raw(sorted(raw_registry)))
        return choice
    def bind_selected(chosen,selection):
        if not chosen:raise ValueError('SVG_no_remaining_known_unseen_family_after_atomic_freshness')
        if len(chosen)<100 and selection['all_remaining_observed_families_selected']is not True:raise ValueError('SVG_incomplete_shortage_cohort_after_atomic_freshness')
        for item in chosen:
            original=population.get(item['id'])
            if original is None or any(item[k]!=original[k]for k in ('source','source_capture_snapshot','source_record_sha256','baseline_code_sha256','baseline_image_sha256')):raise ValueError('SVG_atomic_selected_not_exact_verified_source_population')
        protocol={**protocol_base,'actual_samples':len(chosen),'shortage_exhaustive_exception':len(chosen)<100,
                  'shortage_evidence':dict(eligible_observed_families=selection['eligible_observed_families'],all_eligible_observed_families_selected=selection['all_remaining_observed_families_selected'],source_component_counts=info['source_component_counts']),
                  'selection_under_reservation_write_transaction':selection}
        selected_bytes=b''.join(raw(row)for row in chosen)
        bound.update(protocol=protocol,selected_bytes=selected_bytes)
        return dict(selected_manifest_sha256=sha(selected_bytes),protocol_sha256=sha(raw(protocol)),fresh_source_selection_sha256=sha(raw(selection)),source_freshness_snapshot_sha256=sha(raw(refreshed['snapshot'])))
    reserved=reserve_fresh(R/'release/compiler_v1/validation_registry.sqlite',selector,bind_selected=bind_selected,
                 audit=pool,run_prefix=run_id,implementation_identity_sha256=freeze['implementation_identity_sha256'],
                 phase_runs={k:str(v)for k,v in runs.items()},controls_proof_sha256=sha(raw(controls)))
    selected=reserved['selected'];reservation=reserved['reservation'];protocol=bound['protocol'];snapshot=refreshed['snapshot'];current_prior=snapshot['same_core_normal_events']
    if reservation['selected_manifest_sha256']!=sha(bound['selected_bytes'])or reservation['protocol_sha256']!=sha(raw(protocol)):raise RuntimeError('infrastructure_SVG_reserved_source_bytes_binding_changed')
    # The atomic reservation committed once. Existing reservations are preserved;
    # no failed/stale manifest or prior selected cohort is dispatched.
    p.mkdir(parents=True,exist_ok=False)
    immutable(p/'current_source_exclusion_before_reservation.json',raw(snapshot))
    immutable(p/'atomic_source_selection.json',raw(reserved['selection']))
    immutable(p/'once_core_history_prepare.jsonl',b''.join(raw(row)for row in current_prior))
    immutable(p/'implementation.json',raw(freeze));immutable(p/'protocol.json',raw(protocol))
    immutable(p/'selected.jsonl',bound['selected_bytes'])
    for name in ('supported_population.jsonl','preserved_qualified.jsonl','prior_candidate_attempts.jsonl'):
        immutable(p/name,(pool/name).read_bytes())
    immutable(p/'reservation.json',raw(reservation))
    for phase, run in runs.items():
        rows = [{**x, 'evaluation_phase': 'baseline' if phase == 'B' else 'candidate'} for x in selected]
        data = b''.join(raw(x) for x in rows)
        immutable(p / (phase + '.jsonl'), data)
        phase_freeze = {**freeze, 'input_sha256': sha(data)}
        immutable(p / (phase + '.freeze.json'), raw(phase_freeze))
        controller.create(run, p / (phase + '.jsonl'), p / (phase + '.freeze.json'), 'validation')
    atomic(p / 'state.json', dict(stage='prepared', runs={k: str(v) for k, v in runs.items()}, goal_complete=False))
    return dict(program_dir=str(p), samples_each=len(selected), supported_population=info['counters']['supported_remaining_population'],
                prior_distinct_SOURCE_candidate_attempts=info['prior_same_SOURCE_frontend_distinct_candidate_attempts'],
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
    if runtime_controls()!=protocol['runtime_dispatch_controls']:raise ValueError('runtime_dispatch_control_evidence_changed')
    preserved=preserved_qualified(p)
    prior=prior_attempts(p)
    selected = readrows(p / 'selected.jsonl')
    phases = {phase: results(controller.FLOOR / (p.name + '_' + phase)) for phase in ('B', 'C')}
    expected = {x['id'] for x in selected}
    if expected&{item['id']for item in prior}:raise ValueError('prior_SOURCE_candidate_attempt_reexecuted_in_validation')
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
                preserved_qualified_assets_verified=len(preserved),
                preserved_prior_SOURCE_candidate_attempts=len({item['id']for item in prior}),
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


def preserved_qualified(p):
    carried={x['id']:x for x in readrows(p/'preserved_qualified.jsonl')}if(p/'preserved_qualified.jsonl').exists()else{}
    controls = json.loads((p/'protocol.json').read_bytes()).get('controls',{}) if (p/'protocol.json').exists() else {}
    if controls.get('qualified_manifest'):
        control_path,_=checked(controls['qualified_manifest'])
        carried.update({x['id']:x for x in readrows(control_path)})
    for old in carried.values():
        for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
            common.checked({'file':old[field],'sha256':old[digest]},clean=True)
    return carried


def prior_attempts(p):
    path=p/'prior_candidate_attempts.jsonl'
    if not path.exists():raise ValueError('missing_prior_SOURCE_frontend_attempt_bookkeeping')
    events=readrows(path);compiler,_=case.bindings('svg');history.validate(events,compiler.configuration(),root=R)
    return events


def build_mass(p, gate):
    if not gate.get('approved_units'):return None
    freeze = json.loads((p / 'implementation.json').read_bytes())
    selected = {x['id'] for x in readrows(p / 'selected.jsonl')}
    carried=preserved_qualified(p)
    from svg_analytic_iteration_pool_v4 import fresh_qualified
    compiler,_=case.bindings('svg');latest=fresh_qualified(compiler.configuration());carried.update(latest)
    immutable(p/'mass_fresh_global_qualified.jsonl',b''.join(raw(latest[i])for i in sorted(latest)))
    prior=prior_attempts(p)
    current_prior=history.collect(compiler.configuration(),root=R,catalog=contract.CATALOG);history.validate(current_prior,compiler.configuration(),root=R)
    immutable(p/'mass_once_core_history.jsonl',b''.join(raw(row)for row in current_prior))
    prior_ids={item['id']for item in prior+current_prior}
    population=readrows(p/'supported_population.jsonl')
    omitted=[dict(id=old['id'],state='preserved_qualified_existing_or_control',manifest=old)for old in carried.values()]
    for x in population:
        if x['id'] not in carried:continue
        old=carried[x['id']]
        if (old['source_code_sha256'],old['source_image_sha256'])!=(x['source']['code_sha256'],x['source']['image_sha256']):
            raise ValueError('preserved_control_source_changed')
    immutable(p/'mass_preserved_qualified_controls.jsonl',b''.join(raw(x) for x in omitted))
    immutable(p/'mass_preserved_prior_SOURCE_attempts.jsonl',b''.join(raw(x)for x in prior))
    from compiler_mermaid_alpha_iteration_overlap_v2 import snapshot as active_snapshot
    overlap=active_snapshot(ignore_runs=(p.name,));active=set(overlap['active'])
    immutable(p/'mass_live_overlap_snapshot.json',raw(overlap))
    rows = [x for x in population if x['id'] not in selected and x['id'] not in carried and x['id']not in prior_ids and x['id']not in active and x['compiler_unit'] in gate['approved_units']]
    validate_source_requests(rows)
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


def failure_family(result):
    if case.is_infrastructure(result):return 'runtime_or_environment'
    message=' '.join(case.diagnostic_messages(result)).lower()
    for family,words in [('canvas_and_coordinates',('canvas','viewport','clipping','outside_page')),
                         ('font_and_text',('font','glyph','grapheme','text_shaping')),
                         ('nodes_edges_and_arrows',('invisible','unlaid','node','edge','arrow','terminal','geometry')),
                         ('source_coverage_or_reproduction',('source','coverage','profile','reproduction')),
                         ('visual_alignment',('pixel','ssim','fidelity','foreground'))]:
        if any(word in message for word in words):return family
    return 'needs_generic_converter_diagnosis'


def next_repair(p,gate,mass):
    groups={};outcomes=results(controller.FLOOR/(p.name+'_C'))
    if mass:outcomes.update(results(mass))
    carried=preserved_qualified(p)
    for prior in prior_attempts(p):
        identifier=prior['id']
        if identifier in carried or identifier in outcomes or prior.get('status')=='qualified':continue
        attempt=json.loads(checked(prior['frontend'])[1])if prior.get('frontend')else{}
        stored=json.loads(prior.get('result_json')or'{}')
        if stored.get('status')=='qualified':continue
        detail=attempt.get('detail')or attempt.get('error');reason=attempt.get('reason')or'prior_SOURCE_core_normal_attempt_pending';qa=None
        if prior.get('evidence_kind')=='manual_development':
            declaration=prior['declaration'];_,payload=checked(declaration['receipt']);receipt=json.loads(payload);row=receipt[declaration['rows_key']][declaration['row_index']]
            failures=row.get('failures')or[]
            if failures:reason=failures[0].get('reason')or reason;detail=failures
            qa=row.get('report_file');origin=declaration['receipt']['file']
        else:origin=prior.get('ledger')
        outcomes[identifier]=dict(id=identifier,status='abandoned',reason=reason,detail=detail,quality_report=qa,infrastructure_failure=case.is_infrastructure(attempt),preserved_prior_attempt=True,original_evidence_never_rewritten=origin,normal_reexecution_allowed=False)
    for item in outcomes.values():
        if item['status']=='qualified':continue
        family=failure_family(item);reason=item.get('reason')or'unknown'
        group=groups.setdefault(family,dict(samples=0,reasons=collections.Counter(),examples=[]))
        group['samples']+=1;group['reasons'][reason]+=1
        if len(group['examples'])<5:group['examples'].append(dict(id=item['id'],phase=item.get('phase'),reason=reason,quality_report=item.get('quality_report'),detail=item.get('detail')or item.get('quality_failures')))
    report=dict(schema='SVG_analytic_next_generic_repair_v1',goal_complete=False,gate=gate,
                failure_families=groups,remaining_failures_are_pending=True,model_calls=0,
                next_action='Repair the largest reported source/compiler failure family with finite consumed development cases, retain all quality gates, then audit and reserve a fresh cohort before the next whole-applicable-population pass.')
    immutable(p/'next_repair.json',raw(report));return report


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
            repair=next_repair(p,gate,mass)
            local_outcomes=results(controller.FLOOR/(p.name+'_C'))
            if mass:local_outcomes.update(results(mass))
            atomic(p/'summary.json',dict(stage='round_complete_next_repair_required',round_qualified=sum(row['status']=='qualified'for row in local_outcomes.values()),round_attempted=len(local_outcomes),mass=str(mass)if mass else None,gate=gate,goal_complete=False,next_repair=asset(p/'next_repair.json'),next_action=repair['next_action'],model_calls=0,global_census_owned_by_root=True))
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
    parser.add_argument('action', choices=('prepare', 'audit-prepare', 'launch', 'supervise', 'evaluate'))
    parser.add_argument('--pool', type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--program-dir', type=Path)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--case-timeout', type=float, default=900)
    parser.add_argument('--nonce')
    args = parser.parse_args()
    if not 1 <= args.workers <= 12 or not 1 <= args.case_timeout <= 1800:
        parser.error('resource_limits')
    if args.action == 'audit-prepare':
        from svg_analytic_iteration_pool_v4 import prepare as source_audit
        pool=source_audit(args.pool,args.inventory)
        value=prepare(args.pool,args.run_id)if pool['selected']else dict(program_prepared=False,dispatched=False,source_pool=str(args.pool),source_samples=0,goal_complete=False,next_action='No source-independent known family remains in this exact handler scope; inspect the complete source audit and implement the next repair without claiming unknown families are independent.')
    elif args.action == 'prepare':
        value = prepare(args.pool, args.run_id)
    elif args.action == 'launch':
        value = launch(args.program_dir, args.workers, args.case_timeout)
    elif args.action == 'supervise':
        value = supervise(args.program_dir, args.workers, args.case_timeout, args.nonce)
    else:
        value = computed_gate(owned(args.program_dir))
    print(json.dumps(value, ensure_ascii=False))
