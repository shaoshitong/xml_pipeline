"""Close completed B/C results using the bound current-core prior snapshot."""
from pathlib import Path
import json,sys
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
import svg_analytic_iteration_program_v4 as original
from svg_analytic_iteration_program_v4 import checked,check_controls,runtime_controls,preserved_qualified,readrows,results,controller,case,common,raw,sha,asset,immutable,history
P=R/'release/compiler_iterations/programs/svg_complex_symbol_viewport_unseen100_20261102_v7'
ROOT=R/'release/compiler_iterations/closures/svg_complex_symbol_viewport_unseen100_20261102_v7_history_v1'

def correct_current_prior(p):
    import compiler_svg_general_guard_v8 as old_core
    legacy=readrows(p/'prior_candidate_attempts.jsonl')
    history.validate(legacy,old_core.configuration(),root=R)
    snapshot=json.loads((p/'current_source_exclusion_before_reservation.json').read_bytes());reservation=json.loads((p/'reservation.json').read_bytes())
    assert reservation['source_freshness_snapshot_sha256']==sha(raw(snapshot))
    assert reservation['selected_manifest_sha256']==sha((p/'selected.jsonl').read_bytes())
    prior=readrows(p/'once_core_history_prepare.jsonl');assert prior==snapshot['same_core_normal_events']
    compiler,_=case.bindings('svg');history.validate(prior,compiler.configuration(),root=R)
    assert not {r['id']for r in legacy}&{r['id']for r in readrows(p/'selected.jsonl')}
    return prior

def computed_gate_repaired(p):
    freeze = json.loads((p / 'implementation.json').read_bytes())
    protocol = json.loads((p / 'protocol.json').read_bytes())
    checked(protocol['source_pool_summary'])
    check_controls(protocol['controls'])
    if runtime_controls()!=protocol['runtime_dispatch_controls']:raise ValueError('runtime_dispatch_control_evidence_changed')
    preserved=preserved_qualified(p)
    prior=correct_current_prior(p)
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


def main():
    # Old frozen bytes and the failed closing record stay intact. No sample or
    # controller is relaunched, and no quality condition is relaxed.
    controller.check_pins(json.loads((P/'implementation.json').read_bytes())['pins'])
    assert (P/'infrastructure_stop.json').exists()
    failure=json.loads((P/'infrastructure_stop.json').read_bytes());assert failure['reason']=='infrastructure_source_core_attempt_history:preserved_attempt_core_or_original_changed'
    ROOT.mkdir(parents=True,exist_ok=False);gate=computed_gate_repaired(P);assert not gate['approved_units']
    gate['preserved_orchestration_metadata_error']=asset(P/'infrastructure_stop.json');gate['orchestration_metadata_errors']=1;gate['sample_infrastructure_errors']=gate['infrastructure_errors'];immutable(ROOT/'release_gate.json',raw(gate));repair=original.next_repair(P,gate,None)
    summary=dict(stage='round_complete_after_history_metadata_closure_repair',original_program=str(P),B_completed=len(results(controller.FLOOR/(P.name+'_B'))),C_completed=len(results(controller.FLOOR/(P.name+'_C'))),qualified=sum(r['status']=='qualified'for r in results(controller.FLOOR/(P.name+'_C')).values()),mass_released=False,normal_calls=0,new_QA_calls=0,conversion_or_controller_reexecution=False,current_core_prior=asset(P/'once_core_history_prepare.jsonl'),preserved_cross_core_prior=asset(P/'prior_candidate_attempts.jsonl'),bound_freshness_snapshot=asset(P/'current_source_exclusion_before_reservation.json'),original_metadata_error=asset(P/'infrastructure_stop.json'),gate=asset(ROOT/'release_gate.json'),next_repair=asset(P/'next_repair.json'),producer=asset(Path(__file__)),goal_complete=False)
    immutable(ROOT/'summary.json',raw(summary));common.atomic(P/'post_failure_closure.json',dict(summary=asset(ROOT/'summary.json'),release_gate=asset(ROOT/'release_gate.json')));common.atomic(P/'state.json',dict(stage=summary['stage'],post_failure_closure=asset(P/'post_failure_closure.json'),goal_complete=False));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
