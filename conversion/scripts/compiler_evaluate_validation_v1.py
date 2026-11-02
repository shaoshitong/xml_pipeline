"""Apply preregistered release gates to actual complete paired B/C ledgers."""
import argparse
import collections
import json
import math
import sqlite3
from pathlib import Path

import compiler_batch_v1 as controller
import compiler_prepare_validation_v1 as prepare
import fixed_batch_pipeline_v1 as base

R=base.R;W=base.W;UNIT='python_graphviz_cached_source_v1'


def asset(path):
    path=Path(path).resolve(strict=True)
    if not path.is_relative_to(R.resolve()):raise ValueError('validation_evidence_outside_owner')
    return dict(file=str(path),sha256=base.sha(path.read_bytes()))


def rows(run,phase,freeze):
    run=Path(run);status=controller.snapshot(run)
    if not status['metadata'].get('finished') or any(key not in base.TERMINAL for key in status['counts']):
        raise ValueError('validation_phase_not_complete:'+phase)
    if status['infrastructure_stop']:raise ValueError('validation_phase_infrastructure_stopped:'+phase)
    selected=[json.loads(line) for line in (run/'targets.jsonl').read_bytes().splitlines() if line]
    if base.sha((run/'targets.jsonl').read_bytes())!=freeze['input_sha256']:
        raise ValueError('validation_targets_changed:'+phase)
    d=sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)
    stored=d.execute('select seq,id,source,status,attempts,result from samples order by seq').fetchall();d.close()
    if len(stored)!=len(selected):raise ValueError('validation_ledger_count_mismatch')
    result={};expected_policy='compiler_source_ir_and_full_native_quality_v1:'+freeze['qa_policy_sha256'][:20]
    for expected,(seq,identifier,body,status,attempts,outcome) in zip(selected,stored):
        task=json.loads(body);record=json.loads(outcome)
        if task!=expected or seq!=task['seq'] or identifier!=task['id'] or attempts!=1 or status!=record['status']:
            raise ValueError('validation_dispatch_or_identity_changed:'+phase)
        if task.get('evaluation_phase')!=('baseline' if phase=='B' else 'candidate'):
            raise ValueError('validation_phase_definition_changed')
        for key,expected_value in [('id',identifier),('compiler_unit',UNIT),('seq',seq),
                ('source_code_sha256',task['source']['code_sha256']),('source_image_sha256',task['source']['image_sha256']),
                ('cluster',task['cluster'])]:
            if record.get(key)!=expected_value:raise ValueError('validation_result_identity_changed:'+key)
        if not record.get('case_cleanup_complete') or record.get('model_calls')!=0:
            raise ValueError('validation_process_or_model_invariant_failed')
        quality_file=R/record['quality_report'] if record.get('quality_report') else None
        quality=json.loads(quality_file.read_bytes()) if quality_file else None
        if quality:
            if quality.get('id')!=identifier or quality.get('policy')!=expected_policy or record.get('quality_policy')!=expected_policy:
                raise ValueError('validation_actual_quality_policy_mismatch')
            if base.sha(base.raw(quality.get('compiler_quality_bindings')))!=freeze['qa_policy_sha256']:
                raise ValueError('validation_quality_bindings_changed')
        if status=='qualified':
            if not quality or quality.get('state')!='qualified' or quality.get('failures'):
                raise ValueError('qualified_result_missing_full_qa')
            checks=quality['checks'];required={'structure','resources','source','render','text_paint','fonts','visual','native_editing'}
            if not required<=set(checks) or any(checks[key].get('ok') is not True for key in ('source','visual','native_editing')):
                raise ValueError('qualified_result_missing_checks')
            if checks['fonts'].get('all_rendered_fonts_embedded') is not True:
                raise ValueError('qualified_result_unportable_fonts')
            manifest=record['manifest']
            for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),
                                 ('original_reference','source_image_sha256'),('metadata_file','metadata_sha256')]:
                path=(R/manifest[field]).resolve(strict=True)
                if not path.is_relative_to((R/'clean').resolve()) or base.sha(path.read_bytes())!=manifest[digest]:
                    raise ValueError('qualified_payload_missing_or_changed:'+field)
            if (manifest['id'],manifest['source_code_sha256'],manifest['source_image_sha256'])!=(identifier,task['source']['code_sha256'],task['source']['image_sha256']):
                raise ValueError('qualified_source_identity_changed')
            if quality['input_code_sha256']!=manifest['code_sha256'] or quality['new_png_sha256']!=manifest['image_sha256']:
                raise ValueError('qualified_qa_is_not_bound_to_actual_pair')
            if not record.get('source_reproduction_evidence'):
                raise ValueError('qualified_source_stage_proof_missing')
        result[identifier]=dict(task=task,result=record,quality=quality,
                                result_file=asset(W/'compiler_v1'/run.name/(str(seq).zfill(6)+'_'+identifier)/'result.json'),
                                quality_file=asset(quality_file) if quality_file else None)
    return result


def decision(pairs,controls_passed=True):
    clusters={row['cluster'] for row in pairs};n=len(pairs)
    qualified=sum(row['C']=='qualified' for row in pairs)
    new=sum(row['C']=='qualified' and row['B']!='qualified' for row in pairs)
    regressions=sum(row['B']=='qualified' and row['C']!='qualified' for row in pairs)
    infra=sum(bool(row.get('infrastructure_failure')) for row in pairs)
    result=dict(audited_clusters=len(clusters),samples=n,baseline_qualified=sum(row['B']=='qualified' for row in pairs),
                full_qualified=qualified,full_qualified_rate=qualified/n if n else 0,
                new_qualified_clusters=new,positive_regressions=regressions,infrastructure_errors=infra)
    result['passed']=bool(n>=30 and len(clusters)==n and qualified/n>=.20 and new>=5 and regressions==0 and infra==0 and controls_passed)
    return result


def evaluate(seal_directory):
    seal=Path(seal_directory).resolve(strict=True)
    if not seal.is_relative_to((R/'release/compiler_v1').resolve()):raise ValueError('validation_seal_outside_owner')
    receipt=json.loads((seal/'receipt.json').read_bytes());freezes={}
    for phase in ('B','C'):
        freezes[phase]=json.loads(Path(receipt['runs'][phase]['freeze']).read_bytes())
        controller.check_pins(freezes[phase]['pins']);controller.check_implementation_identity(freezes[phase])
    if controller.implementation_identity(freezes['B'])!=controller.implementation_identity(freezes['C']):
        raise ValueError('paired_validation_implementation_differs')
    freeze=freezes['C']
    proof=receipt.get('controls_proof') or freeze.get('controls_proof')
    if not proof:raise ValueError('validation_controls_proof_missing')
    proof_path=proof['file'] if isinstance(proof,dict) else proof
    if isinstance(proof,dict) and asset(proof_path)['sha256']!=proof['sha256']:
        raise ValueError('validation_controls_proof_changed')
    controls=prepare.check_controls_proof(proof_path,freeze)
    phases={phase:rows(receipt['runs'][phase]['directory'],phase,freezes[phase]) for phase in ('B','C')}
    if set(phases['B'])!=set(phases['C']):raise ValueError('paired_validation_ids_differ')
    pairs=[];reasons=collections.Counter();baseline_reasons=collections.Counter();a_stats=collections.Counter()
    old=sqlite3.connect('file:'+str(R/'release/round2_fixed_v1/repair_pass_20261101_0627/status.sqlite')+'?mode=ro',uri=True)
    try:
        for identifier,c in phases['C'].items():
            b=phases['B'][identifier]
            for key in ('id','source','compiler_unit','cluster','source_record_sha256','source_capture_snapshot'):
                if b['task'][key]!=c['task'][key]:raise ValueError('paired_source_or_capture_differs:'+key)
            row=dict(id=identifier,cluster=c['task']['cluster'],B=b['result']['status'],C=c['result']['status'],
                     infrastructure_failure=bool(b['result'].get('infrastructure_failure') or c['result'].get('infrastructure_failure')),
                     B_evidence=b['result_file'],C_evidence=c['result_file'])
            original=old.execute('select first_result from samples where id=?',(identifier,)).fetchone()
            if original:
                first=json.loads(original[0])
                if (first.get('candidate_code_sha256'),first.get('candidate_image_sha256'))==(
                        b['task']['baseline_code_sha256'],b['task']['baseline_image_sha256']):
                    row['A_original_status']=first['status'];a_stats['same_candidate_revision']+=1
                    if first['status']!='qualified' and row['B']=='qualified':a_stats['B_only_qualification_without_conversion']+=1
                else:a_stats['A_revision_not_comparable']+=1
            else:a_stats['A_record_unavailable']+=1
            reasons[c['result'].get('diagnostic_stage') or c['result'].get('reason') or c['result']['status']]+=1
            baseline_reasons[b['result'].get('diagnostic_stage') or b['result'].get('reason') or b['result']['status']]+=1
            pairs.append(row)
    finally:old.close()
    metrics=decision(pairs,True)
    metrics['provenance_or_cluster_audit_passed']=True
    gate=dict(schema='compiler_release_gate_v1',at=base.now(),approved_units=[UNIT] if metrics['passed'] else [],
              implementation_identity=controller.implementation_identity(freeze),implementation_identity_sha256=controller.implementation_digest(freeze),
              controls_passed=True,controls_evidence=controls,infrastructure_errors=metrics['infrastructure_errors'],
              units={UNIT:metrics},paired_results=pairs,validator_only_effects=dict(a_stats),
              candidate_failure_categories=dict(reasons),baseline_failure_categories=dict(baseline_reasons),
              source_cohort_seal=asset(seal/'receipt.json'),validation_complete=True,
              statistics_scope='Descriptive results for preregistered operational input clusters; hidden generator independence and unbiased full-population yield are not established.',
              no_outcome_dependent_threshold_changes=True,model_calls=0)
    base.atomic(seal/'release_gate.json',base.raw(gate))
    return dict(gate=str(seal/'release_gate.json'),passed=metrics['passed'],unit=UNIT,metrics=metrics,
                candidate_failure_categories=dict(reasons),validator_only_effects=dict(a_stats))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seal-directory',required=True)
    args=parser.parse_args();print(json.dumps(evaluate(args.seal_directory),ensure_ascii=False),flush=True)
