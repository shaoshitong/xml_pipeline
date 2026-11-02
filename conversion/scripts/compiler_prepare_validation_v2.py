"""Seal one audited unseen cohort and create paired B/C finite validation runs.

No conversion or dispatch is performed by preparation. Source/candidate results
must not have been consumed when this freeze is created.
"""
import argparse
import ast
import json
import os
import sqlite3
from pathlib import Path

import compiler_batch_v2 as controller
import compiler_quality_v2 as quality
import fixed_batch_pipeline_v1 as base
import round2_font_canvas_registration_v1 as registration
from compiler_validation_reservation_v1 import reserve

R=base.R;W=base.W;UNIT='python_graphviz_cached_source_v1'
REQUIRED_POSITIVE_CONTROL_IDS=(
    '18b42bc74a7f5b426ded51e0f676c5d48c849c33c67b08d66ba59e7b8fe28611',
    'e6409913a83b92611e5cc6354f48873ed809d4c0366a87206f582f078cc5d0e8',
    'c367e5d71ab193cd842a3dc9e3570d04984d013061c50e4c60f74d978b6e0e56',
    '9603f6dffd98a2687647decbaa7dce24e53c68ac764014a2124cdd6fd102c865',
    'ca5009341f873e4c7b972da89ccaa0fbd3c7994d485390f56b451a9818cd09ca')


def implementation_pins():
    for name in ('compiler_controls_v2.py','compiler_evaluate_validation_v2.py','compiler_scene_text_v2.py',
                 'compiler_capture_snapshot_v1.py','compiler_validation_reservation_v1.py',
                 'compiler_render_domain_v3.py'):
        if not (W/'scripts'/name).is_file():raise ValueError('missing_required_compiler_control_implementation:'+name)
    pins=base.pins();pins.update(registration.configuration()['pins'])
    todo=[W/'scripts'/name for name in ('compiler_batch_v2.py','compiler_case_v2.py','compiler_quality_v2.py',
          'compiler_scene_v1.py','compiler_scene_text_v2.py','compiler_source_reproduction_v1.py','round2_source_repair_v1.py',
          'round2_canvas_repair_v1.py','round2_font_repair_v1.py','round2_font_canvas_registration_v1.py',
          'svg_convert_v5.py','compiler_prepare_validation_v2.py','compiler_validation_reservation_v1.py',
          'compiler_capture_snapshot_v1.py','compiler_controls_v2.py','compiler_evaluate_validation_v2.py',
          'compiler_render_domain_v3.py')]
    visited=set()
    while todo:
        path=todo.pop().resolve()
        if path in visited or not path.is_file():continue
        visited.add(path);pins[str(path)]=base.sha(path.read_bytes())
        sibling=path.with_suffix('.js')
        if sibling.is_file():pins[str(sibling)]=base.sha(sibling.read_bytes())
        if path.suffix!='.py':continue
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.Import):modules=[alias.name.split('.')[0] for alias in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module:modules=[node.module.split('.')[0]]
            for module in modules:
                imported=W/'scripts'/(module+'.py')
                if imported.is_file():todo.append(imported)
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and '/' not in node.value and node.value.endswith(('.py','.js')):
                imported=W/'scripts'/node.value
                if imported.is_file():todo.append(imported)
    for dirname in ('rendering_paintbounds_strict','rendering_clipbox_strict','rendering_canvas_padding_proof','rendering_fonts'):
        for path in (W/dirname).rglob('*'):
            if path.is_file() and path.suffix in ('.py','.js','.mjs'):
                pins[str(path.resolve())]=base.sha(path.read_bytes())
    graphviz=W/'runtime/graphviz'
    libraries=[graphviz/'bin/dot']+[p.resolve() for p in (graphviz/'lib').rglob('*.so*') if p.is_file()]
    for path in set(libraries):pins[str(path.resolve())]=base.sha(path.read_bytes())
    return pins


def require_render_domain(checks,reason='compiler_render_domain_not_passed'):
    """Every qualified native pair needs the same independent render-domain gate."""
    proof=checks.get('compiler_render_domain')
    if (not isinstance(proof,dict) or proof.get('supported') is not True
            or proof.get('ok') is not True or proof.get('failures')!=[]):
        raise ValueError(reason)


def _proof_asset(reference,clean=False):
    if not isinstance(reference,dict) or set(('file','sha256'))-reference.keys():
        raise ValueError('controls_asset_reference_missing')
    path=Path(reference['file']);path=(path if path.is_absolute() else R/path).resolve(strict=True)
    floor=(R/'clean').resolve() if clean else R.resolve()
    if not path.is_relative_to(floor):raise ValueError('controls_asset_outside_owner')
    blob=path.read_bytes()
    if base.sha(blob)!=reference['sha256']:raise ValueError('controls_asset_hash_changed:'+str(path))
    return path,blob


def _proof_rows(reference):
    _,blob=_proof_asset(reference);rows={}
    for line in blob.splitlines():
        if not line:continue
        row=json.loads(line);identifier=row['control_id']
        if identifier in rows:raise ValueError('duplicate_control_id')
        rows[identifier]=row
    if not rows:raise ValueError('empty_controls_file')
    return rows


def _positive_payloads(result,audit,audit_path,request):
    manifest=result.get('manifest')
    if not isinstance(manifest,dict):raise ValueError('positive_control_missing_manifest')
    for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),
                         ('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),
                         ('metadata_file','metadata_sha256')]:
        _proof_asset(dict(file=manifest[field],sha256=manifest[digest]),clean=True)
    metadata=json.loads(_proof_asset(dict(file=manifest['metadata_file'],sha256=manifest['metadata_sha256']),clean=True)[1])
    _control_record_inputs(metadata,request)
    for font in metadata.get('native_embedded_fonts') or []:
        for file_key,hash_key in [('file','sha256'),('original_file','original_sha256')]:
            _proof_asset(dict(file=font[file_key],sha256=font[hash_key]),clean=True)
    scene=metadata.get('compiler_scene_graphviz_v1')
    if scene:_proof_asset(dict(file=scene['scene_file'],sha256=scene['scene_sha256']),clean=True)
    text=metadata.get('compiler_scene_text_v2') or {}
    _,text_blob=_proof_asset(dict(file=text.get('proof_file'),sha256=text.get('proof_sha256')),clean=True)
    text_proof=json.loads(text_blob)
    for field in ('baseline_record','baseline_xml','baseline_native_info','source_positions'):_proof_asset(text_proof[field],clean=True)
    for field in ('id','code_sha256','image_sha256','source_code_sha256','source_image_sha256'):
        expected=manifest[field]
        if metadata.get(field)!=expected:raise ValueError('positive_control_metadata_identity_changed:'+field)
        if field in ('id','source_code_sha256','source_image_sha256') and result.get(field)!=expected:
            raise ValueError('positive_control_result_identity_changed:'+field)
    if (R/metadata['automatic_quality_audit']).resolve()!=audit_path:
        raise ValueError('positive_control_metadata_audit_changed')
    if metadata.get('automatic_quality_policy')!=audit['policy']:
        raise ValueError('positive_control_metadata_policy_changed')
    if audit.get('input_code_sha256')!=manifest['code_sha256'] or audit.get('new_png_sha256')!=manifest['image_sha256']:
        raise ValueError('positive_control_qa_payload_changed')
    evidence=result.get('source_reproduction_evidence')
    if not evidence or metadata.get('compiler_source_reproduction')!=evidence:
        raise ValueError('positive_control_source_stage_evidence_missing')
    _,blob=_proof_asset(evidence,clean=True);source_stage=json.loads(blob)
    expected_assets={'source_dot','source_svg','cached_execution_audit','cached_returned_png','source_scene',
                     'fresh_source_engine_png','fresh_source_reference_canvas_png','source_text_line_boxes'}
    if (source_stage.get('id')!=result['id'] or source_stage.get('ok') is not True or
            source_stage.get('graphviz_reexecuted') is not True or
            source_stage.get('fresh_vs_cache',{}).get('exact_rgba_pixels_equal') is not True or
            source_stage.get('source_reference_visual',{}).get('ok') is not True or
            not expected_assets<=set(source_stage.get('assets',{}))):
        raise ValueError('positive_control_source_stage_not_passed')
    for asset in source_stage.get('assets',{}).values():_proof_asset(asset,clean=True)
    _proof_asset(source_stage['reference'],clean=True)


def _control_record_inputs(record,request):
    if (record.get('id'),record.get('source_pair_sha256'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(
            request['id'],request['id'],request['source']['code_sha256'],request['source']['image_sha256']):
        raise ValueError('controls_input_record_source_identity_mismatch')
    for field,digest_field in [('code_file','code_sha256'),('image_file','image_sha256'),
                               ('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
        _proof_asset(dict(file=record[field],sha256=record[digest_field]),clean=True)
    from compiler_capture_snapshot_v1 import check_snapshot
    check_snapshot(record,request['source_capture_snapshot'])


def check_controls_proof(proof_file,freeze):
    """Check actual frozen requests, results, QA and payload bytes, not a pass flag."""
    proof_path=Path(proof_file).resolve(strict=True)
    if not proof_path.is_relative_to(R.resolve()):raise ValueError('controls_proof_outside_owner')
    proof_blob=proof_path.read_bytes();proof=json.loads(proof_blob)
    try:identity=controller.check_implementation_identity(freeze)
    except ValueError as error:raise ValueError('controls_proof_implementation_mismatch') from error
    digest=controller.implementation_digest(freeze)
    if (proof.get('schema')!='compiler_controls_proof_v1' or
            proof.get('implementation_identity')!=identity or proof.get('implementation_identity_sha256')!=digest):
        raise ValueError('controls_proof_implementation_mismatch')
    manifest=_proof_rows(proof['controls_manifest']);expectations=_proof_rows(proof['expectations']);outcomes=_proof_rows(proof['outcomes'])
    if not set(manifest)==set(expectations)==set(outcomes):raise ValueError('controls_outcome_identity_set_mismatch')
    counts={'positive':0,'negative':0};evidence=[];positive_ids=set()
    expected_policy=quality.POLICY+':'+freeze['qa_policy_sha256'][:20]
    for identifier,row in manifest.items():
        kind=row.get('kind');expected=expectations[identifier];actual=outcomes[identifier]
        if kind not in counts or expected.get('kind')!=kind or row.get('compiler_unit')!=UNIT:
            raise ValueError('controls_kind_or_unit_mismatch')
        inputs=row.get('input_assets')
        if not isinstance(inputs,list) or not inputs:raise ValueError('controls_input_assets_missing')
        requests=[];source_records=[];checked_inputs={}
        for asset in inputs:
            path,blob=_proof_asset(asset);checked_inputs[path]=blob
            if asset.get('role')=='request':requests.append(json.loads(blob))
            if asset.get('role')=='source_record':source_records.append((asset['sha256'],json.loads(blob)))
        if len(requests)!=1:raise ValueError('controls_require_one_frozen_request')
        request=requests[0];result_path,result_blob=_proof_asset(actual['result']);result=json.loads(result_blob)
        audit_path,audit_blob=_proof_asset(actual['quality_audit']);audit=json.loads(audit_blob)
        _,iso_blob=_proof_asset(actual['isolation']);isolation=json.loads(iso_blob)
        if (isolation.get('ok') is not True or isolation.get('returncode')!=0 or
                isolation.get('cleanup_complete') is not True or isolation.get('deadline_exceeded')):
            raise ValueError('controls_isolation_or_cleanup_failed')
        if (result.get('id'),result.get('compiler_unit'),result.get('source_code_sha256'),result.get('source_image_sha256'))!=(
                request.get('id'),UNIT,request['source']['code_sha256'],request['source']['image_sha256']):
            raise ValueError('controls_request_result_identity_mismatch')
        if request.get('compiler_unit')!=UNIT or request.get('source',{}).get('pair_sha256')!=request.get('id'):
            raise ValueError('controls_request_source_identity_mismatch')
        if request.get('seq')!=result.get('seq') or {
                str(Path(path).resolve()):digest for path,digest in request.get('pins',{}).items()}!=identity['pins']:
            raise ValueError('controls_request_implementation_or_sequence_mismatch')
        if len(source_records)!=1 or source_records[0][0]!=request.get('source_record_sha256'):
            raise ValueError('controls_require_frozen_original_source_record')
        _control_record_inputs(source_records[0][1],request)
        if request.get('development_candidate'):
            candidate_path=Path(request['development_candidate']).resolve(strict=True)
            if candidate_path not in checked_inputs:raise ValueError('controls_candidate_record_not_frozen')
            candidate=json.loads(checked_inputs[candidate_path])
            _control_record_inputs(candidate,request)
        if audit.get('id')!=result['id'] or (R/result['quality_report']).resolve()!=audit_path:
            raise ValueError('controls_result_audit_identity_mismatch')
        if (audit.get('policy')!=expected_policy or result.get('quality_policy')!=expected_policy or
                base.sha(base.raw(audit.get('compiler_quality_bindings')))!=freeze['qa_policy_sha256']):
            raise ValueError('controls_actual_quality_policy_mismatch')
        if result.get('infrastructure_failure') or audit.get('infrastructure_failure') or audit.get('diagnostic_stage')=='infrastructure':
            raise ValueError('controls_infrastructure_failure')
        checks=audit.get('checks',{})
        if kind=='positive':
            if (expected.get('expected_status')!='qualified' or expected.get('expected_failure_stage') is not None or
                    result.get('status')!='qualified' or audit.get('state')!='qualified' or audit.get('failures')):
                raise ValueError('positive_control_not_fully_qualified')
            required={'structure','resources','source','render','text_paint','fonts','visual','native_editing'}
            if not required<=set(checks) or any(checks[key].get('ok') is not True for key in ('source','visual','native_editing')):
                raise ValueError('positive_control_missing_full_quality_checks')
            if checks['fonts'].get('all_rendered_fonts_embedded') is not True:
                raise ValueError('positive_control_fonts_not_portable')
            require_render_domain(checks,'positive_control_compiler_render_domain_not_passed')
            render=checks.get('compiler_text_render') or {}
            if not render.get('supported') or not render.get('ok') or render.get('failures'):
                raise ValueError('positive_control_v2_fresh_text_geometry_not_verified')
            _positive_payloads(result,audit,audit_path,request)
            positive_ids.add(result['id'])
        else:
            stage=expected.get('expected_failure_stage');gate=checks.get(stage,{})
            if (expected.get('expected_status')!='abandoned' or stage not in ('source','structure') or
                    result.get('status')!='abandoned' or audit.get('state')=='qualified' or not audit.get('failures') or
                    gate.get('ok') is not False or not (gate.get('failures') or gate.get('errors'))):
                raise ValueError('negative_control_not_rejected_by_declared_gate')
        counts[kind]+=1;evidence.append(dict(control_id=identifier,kind=kind,result=str(result_path),result_sha256=actual['result']['sha256'],
                                            quality_audit=str(audit_path),quality_audit_sha256=actual['quality_audit']['sha256']))
    if not all(counts.values()):raise ValueError('controls_require_positive_and_negative')
    if not set(REQUIRED_POSITIVE_CONTROL_IDS)<=positive_ids:
        raise ValueError('controls_missing_frozen_v1_positive_regressions')
    return dict(schema=proof['schema'],file=str(proof_path),sha256=base.sha(proof_blob),
                implementation_identity_sha256=digest,counts=counts,infrastructure_errors=0,
                controls_manifest=proof['controls_manifest'],expectations=proof['expectations'],outcomes=proof['outcomes'],verified_outcomes=evidence)


def repair_cohort(audit,prior_gate):
    """Use only the precommitted next30; never refill/reorder after outcomes."""
    summary_path=audit/'compiler_validation_repair_reserve_summary.json'
    summary=json.loads(summary_path.read_bytes())
    paths={'first30_manifest_sha256':'compiler_validation_selected_manifest.jsonl',
           'audit_manifest_sha256':'compiler_validation_audited_reservoir.jsonl',
           'original_protocol_sha256':'compiler_validation_protocol.json',
           'original_pool_sha256':'compiler_validation_reservoir.jsonl',
           'reserve_sha256':'compiler_validation_repair_reserve.jsonl'}
    for key,name in paths.items():
        if base.sha((audit/name).read_bytes())!=summary[key]:raise ValueError('repair_precommit_changed:'+key)
    if summary.get('eligible_rank_interval_inclusive')!=[31,60] or summary.get('reserve_count')!=30:
        raise ValueError('repair_precommit_interval_changed')
    def records(name):return [json.loads(line) for line in (audit/name).read_bytes().splitlines() if line]
    pool=records(paths['original_pool_sha256']);first=records(paths['first30_manifest_sha256'])
    audited=records(paths['audit_manifest_sha256']);selected=records(paths['reserve_sha256'])
    eligible=[row for row in audited if row['audit_disposition']=='eligible_unconsumed_audited_cluster']
    if len(pool)!=500 or len({row['id'] for row in pool})!=500 or eligible!=sorted(eligible,key=lambda row:row['reservoir_rank']):
        raise ValueError('repair_original500_or_rank_order_changed')
    if ([row['id'] for row in first]!=[row['id'] for row in eligible[:30]] or
            [row['id'] for row in selected]!=[row['id'] for row in eligible[30:60]] or
            any(row.get('reserve_order')!=index or row.get('original_eligible_rank')!=index+30
                for index,row in enumerate(selected,1))):
        raise ValueError('repair_cohort_not_precommitted_next30')
    gate_path=Path(prior_gate).resolve(strict=True)
    if not gate_path.is_relative_to((R/'release/compiler_v1').resolve()):raise ValueError('prior_gate_outside_v1_owner')
    gate=json.loads(gate_path.read_bytes());unit=gate.get('units',{}).get(UNIT,{})
    if (gate.get('validation_complete') is not True or unit.get('passed') is not False or
            gate.get('infrastructure_errors')!=0 or UNIT in gate.get('approved_units',[]) or
            len(gate.get('paired_results',[]))!=30 or
            {row['id'] for row in gate['paired_results']}!={row['id'] for row in first}):
        raise ValueError('repair_requires_completed_failed_first30_gate')
    receipt_path,receipt_blob=_proof_asset(gate['source_cohort_seal']);receipt=json.loads(receipt_blob)
    if Path(receipt['audit_run']).resolve()!=audit.resolve():raise ValueError('prior_gate_audit_lineage_changed')
    for phase in ('B','C'):
        task_path=Path(receipt['runs'][phase]['manifest'])
        if not task_path.resolve().is_relative_to((R/'release/compiler_v1').resolve()):raise ValueError('prior_manifest_outside_v1_owner')
        tasks=[json.loads(line) for line in task_path.read_bytes().splitlines() if line]
        if ({row['id'] for row in tasks}!={row['id'] for row in first} or len(tasks)!=30 or
                any(row['selection_manifest_sha256']!=summary['first30_manifest_sha256'] for row in tasks)):
            raise ValueError('prior_gate_first30_manifest_binding_changed')
    lineage=dict(repair_attempt=1,additional_repair_attempts_allowed=0,
                 prior_failed_gate=dict(file=str(gate_path),sha256=base.sha(gate_path.read_bytes())),
                 precommit=dict(file=str(summary_path),sha256=base.sha(summary_path.read_bytes())),
                 rank_interval=[31,60],original_pool_size=500,
                 original_first30_sha256=summary['first30_manifest_sha256'],
                 original_pool_sha256=summary['original_pool_sha256'],
                 original_audit_sha256=summary['audit_manifest_sha256'],
                 original_protocol_sha256=summary['original_protocol_sha256'],
                 original_method=json.loads((audit/'compiler_validation_protocol.json').read_bytes()).get('method'),
                 reserve_sha256=summary['reserve_sha256'],selection_changed_from_outcomes=False)
    return selected,lineage


def prepare(audit_run_id,run_prefix,controls_proof,prior_gate):
    for value in (audit_run_id,run_prefix):
        if not value or not all(ch.isalnum() or ch in '-_' for ch in value):raise ValueError('invalid_validation_run_id')
    audit=R/'release/compiler_validation_v1'/audit_run_id
    summary=json.loads((audit/'compiler_validation_summary.json').read_bytes())
    protocol=json.loads((audit/'compiler_validation_protocol.json').read_bytes())
    for item in summary['files']:
        if base.sha((audit/item['file']).read_bytes())!=item['sha256']:
            raise ValueError('audited_metadata_changed:'+item['file'])
    if summary.get('validation_executions')!=0 or summary.get('outcomes_viewed') is not False:
        raise ValueError('cohort_is_not_unconsumed')
    if protocol.get('audit_budget_exceeded_blocks_all_groups'):
        raise ValueError('cluster_audit_budget_exceeded')
    stats=summary['statistics'].get(UNIT,{})
    if not stats.get('minimum_30_met') or stats.get('selected_validation_clusters')!=30:
        raise ValueError('insufficient_unseen_clusters_for_publication_group')
    selected,lineage=repair_cohort(audit,prior_gate)
    selection=audit/'compiler_validation_repair_reserve.jsonl'
    if len(selected)!=30 or len({row['audit_cluster'] for row in selected})!=30:
        raise ValueError('validation_cohort_cluster_or_count_changed')
    if any(row['support_unit']!=UNIT or row.get('development_overlap') or not row.get('source_hash_verified') for row in selected):
        raise ValueError('validation_cohort_not_audited_unseen_supported_group')
    scene_pin=protocol['predicate_pins']['scene']
    if base.sha(Path(scene_pin['path']).read_bytes())!=scene_pin['sha256']:
        raise ValueError('support_predicate_changed_after_audited_selection')
    seal=R/'release/compiler_v2'/('seal_'+run_prefix)
    phase_runs={phase:str(controller.FLOOR/(run_prefix+'_'+phase)) for phase in ('B','C')}
    if seal.exists() or any(Path(path).exists() for path in phase_runs.values()):
        raise ValueError('validation_preparation_exists_no_automatic_retry')
    config=quality.configuration();freeze=dict(compiler_version='compiler_v2',pins=implementation_pins(),qa_policy_sha256=config['policy_sha256'],
                                               predicate_hashes={UNIT:scene_pin['static_support_ast_sha256']})
    freeze['implementation_identity']=controller.implementation_identity(freeze)
    freeze['implementation_identity_sha256']=controller.implementation_digest(freeze)
    controls=check_controls_proof(controls_proof,freeze)
    d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
    manifests={'B':[],'C':[]}
    try:
        for seq,item in enumerate(selected,1):
            identifier=item['id']
            record=d.execute('select input_record,output_record from jobs where id=?',(identifier,)).fetchone()
            if not record:raise ValueError('missing_validation_job')
            source=json.loads(record[0]);candidate=json.loads(record[1])
            if (source['pair_sha256'],source['format'],source['code_sha256'],source['image_sha256'])!=(identifier,'python',item['source']['code_sha256'],item['source']['image_sha256']):
                raise ValueError('validation_original_identity_changed')
            if base.sha(record[1].encode())!=item['source_record_sha256']:
                raise ValueError('validation_cached_source_record_changed')
            from compiler_capture_snapshot_v1 import seal_snapshot
            snapshot=seal_snapshot(candidate,item['static_support_evidence'])
            common=dict(id=identifier,seq=seq,source=source,compiler_unit=UNIT,cluster=item['audit_cluster'],
                        source_record_sha256=item['source_record_sha256'],
                        source_capture_snapshot=snapshot,
                        selection_manifest_sha256=base.sha(selection.read_bytes()))
            manifests['B'].append(dict(common,evaluation_phase='baseline',
                                       baseline_code_sha256=candidate['code_sha256'],baseline_image_sha256=candidate['image_sha256']))
            manifests['C'].append(dict(common,evaluation_phase='candidate'))
    finally:d.close()
    # Reservation is global across prefixes, units and implementation revisions.
    # A failure after this transaction intentionally leaves the cohort reserved;
    # this function never pretends that reservation consumed validation outcomes.
    reservation=reserve(R/'release/compiler_v1/validation_registry.sqlite',selected,audit=audit,
                        run_prefix=run_prefix,implementation_identity_sha256=freeze['implementation_identity_sha256'],
                        phase_runs=phase_runs,
                        selected_manifest_sha256=base.sha(selection.read_bytes()),
                        protocol_sha256=base.sha((audit/'compiler_validation_protocol.json').read_bytes()),
                        controls_proof_sha256=controls['sha256'])
    seal.mkdir(parents=True,exist_ok=False)
    base.atomic(seal/'reservation.json',base.raw(reservation))
    base.atomic(seal/'controls_verified.json',base.raw(controls))
    receipt=dict(audit_run=str(audit),sealed_at=base.now(),unit=UNIT,selected_clusters=30,
                 matching_population=stats['matching_queued_population'],quality_policy=config,
                 implementation_identity_sha256=freeze['implementation_identity_sha256'],
                 reservation=reservation,controls_proof=controls,repair_lineage=lineage,
                 gate=protocol['release_gate'],phase_definitions={'B':'Unchanged original candidate under the new source-stage/full QA policy; no repairs.',
                 'C':'Frozen compiler conversion and bounded normalization under the same source-stage/full QA policy.'},
                 outcome_dependent_edits_permitted=False,models=0,runs={})
    for phase,rows in manifests.items():
        manifest=seal/(phase+'.jsonl');base.atomic(manifest,b''.join(base.raw(row) for row in rows))
        current=dict(freeze,input_sha256=base.sha(manifest.read_bytes()),
                     validation_reservation_id=reservation['reservation_id'],
                     validation_cohort_sha256=reservation['cohort_sha256'],
                     validation_controls_proof_sha256=controls['sha256'],
                     validation_controls_verified_file=str(seal/'controls_verified.json'),
                     validation_controls_verified_sha256=base.sha((seal/'controls_verified.json').read_bytes()),
                     repair_lineage=lineage,
                     validation_protocol_file=str(audit/'compiler_validation_protocol.json'),
                     validation_protocol_sha256=base.sha((audit/'compiler_validation_protocol.json').read_bytes()))
        file=seal/(phase+'.freeze.json');base.atomic(file,base.raw(current))
        run=Path(phase_runs[phase])
        status=controller.create(run,manifest,file,'validation')
        receipt['runs'][phase]=dict(directory=str(run),manifest=str(manifest),freeze=str(file),counts=status['counts'])
    base.atomic(seal/'receipt.json',base.raw(receipt))
    return {k:v for k,v in receipt.items() if k!='quality_policy'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-run-id',required=True);parser.add_argument('--run-prefix',required=True)
    parser.add_argument('--controls-proof',required=True)
    parser.add_argument('--prior-gate',required=True)
    args=parser.parse_args()
    for value in (args.audit_run_id,args.run_prefix):
        if not value or not all(ch.isalnum() or ch in '-_' for ch in value):parser.error('invalid run ID')
    print(json.dumps(prepare(args.audit_run_id,args.run_prefix,args.controls_proof,args.prior_gate),ensure_ascii=False),flush=True)
