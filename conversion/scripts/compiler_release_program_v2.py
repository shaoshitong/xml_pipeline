"""Prepare, start and finish one finite, hash-bound compiler-v2 release.

Preparation only reads the source index, cached source captures and prior ledgers.
It never executes a source, converter, renderer or model. The detached supervisor
starts the actual compiler_batch_v2 CLI once, waits for it, exports once and exits.
All dataset access and all generated manifests stay under the HKUST data root.
"""
import argparse
import ast
import collections
import concurrent.futures
import contextlib
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

import compiler_batch_v2 as controller
import compiler_capture_snapshot_v1 as capture
import compiler_evaluate_validation_v2 as evaluator
import compiler_prepare_validation_v2 as validation
import compiler_scene_v1 as scene
import fixed_batch_pipeline_v1 as base

R=base.R
W=base.W
UNIT='python_graphviz_cached_source_v1'
EXPECTED=131904
EXPECTED_PYTHON=13801
INPUT_SHA='361bce924762d14481da9b541cfbcf0f6879f97618fbc750922ac1c918a70a85'
CATEGORIES={'poster':24743,'scientific_diagram':107161}
FIRST=R/'release/fixed_batch_v1/initial_screen_20261031_1717'
ASSETS=(('code_file','code_sha256'),('image_file','image_sha256'),
        ('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),
        ('metadata_file','metadata_sha256'))


def load(path):return json.loads(Path(path).read_bytes())
def lines(path):
    with Path(path).open('rb') as stream:
        for line in stream:
            if line.strip():yield json.loads(line)


def owned(path,floor=None):
    path=Path(path).resolve()
    floor=(Path(floor) if floor is not None else controller.FLOOR).resolve()
    if path==floor or not path.is_relative_to(floor):raise ValueError('release_path_outside_owner:'+str(path))
    return path


def asset(path):
    path=owned(path,R)
    return dict(file=str(path),sha256=file_sha(path))


def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def checked_asset(reference):
    if not isinstance(reference,dict) or not isinstance(reference.get('file'),str):
        raise ValueError('release_missing_asset_reference')
    path=owned(reference['file'],R)
    if not path.is_file() or file_sha(path)!=reference.get('sha256'):
        raise ValueError('release_asset_changed:'+str(path))
    return path


def write_rows(path,rows):
    path=Path(path)
    if path.exists():raise ValueError('release_export_already_exists:'+str(path))
    with path.open('xb') as stream:
        for row in rows:stream.write(base.raw(row))
        stream.flush();os.fsync(stream.fileno())
    return asset(path)


def _predicate_digest():
    function=next(n for n in ast.parse(Path(scene.__file__).read_text()).body
                  if isinstance(n,ast.FunctionDef) and n.name=='static_support')
    return base.sha(ast.dump(function,include_attributes=False).encode())


def verify_gate(seal_directory,gate_file=None):
    """Re-read the actual paired outcomes and controls; no gate flag is trusted."""
    seal=owned(seal_directory)
    gate_path=owned(gate_file or seal/'release_gate.json')
    if gate_path!=seal/'release_gate.json':raise ValueError('release_gate_not_in_supplied_seal')
    gate=load(gate_path);receipt_path=seal/'receipt.json';receipt=load(receipt_path)
    if (gate.get('schema')!='compiler_release_gate_v2' or gate.get('validation_complete') is not True
            or gate.get('no_outcome_dependent_threshold_changes') is not True or gate.get('model_calls')!=0
            or gate.get('source_cohort_seal')!=asset(receipt_path)):
        raise ValueError('release_gate_missing_completed_seal_binding')
    freezes={};phases={}
    for phase in ('B','C'):
        spec=receipt['runs'][phase]
        frozen=owned(spec['freeze']);manifest=owned(spec['manifest']);run=owned(spec['directory'])
        if frozen.parent!=seal or manifest.parent!=seal:
            raise ValueError('release_validation_files_outside_seal')
        freeze=load(frozen);controller.check_pins(freeze['pins']);controller.check_implementation_identity(freeze)
        if (file_sha(manifest)!=freeze['input_sha256'] or load(run/'freeze.json')!=freeze
                or (run/'targets.jsonl').read_bytes()!=manifest.read_bytes()):
            raise ValueError('release_validation_freeze_or_targets_changed:'+phase)
        freezes[phase]=freeze;phases[phase]=evaluator.rows(run,phase,freeze)
    freeze=freezes['C'];identity=controller.implementation_identity(freeze)
    digest=controller.implementation_digest(freeze)
    if (controller.implementation_identity(freezes['B'])!=identity
            or gate.get('implementation_identity')!=identity
            or gate.get('implementation_identity_sha256')!=digest
            or receipt.get('implementation_identity_sha256')!=digest
            or freeze['predicate_hashes'].get(UNIT)!=_predicate_digest()):
        raise ValueError('release_gate_or_predicate_implementation_mismatch')
    if set(phases['B'])!=set(phases['C']):raise ValueError('release_paired_ids_changed')
    check_frozen_captures([row['task'] for row in phases['C'].values()])
    # This is the actual precommitted, source-audited unseen cohort, not a new
    # sample selected from the now-visible outcomes.
    audit=owned(receipt['audit_run'],R/'release/compiler_validation_v1')
    summary=load(audit/'compiler_validation_summary.json')
    for reference in summary['files']:
        if file_sha(audit/reference['file'])!=reference['sha256']:
            raise ValueError('release_unseen_audit_metadata_changed')
    if summary.get('outcomes_viewed') is not False or summary.get('validation_executions')!=0:
        raise ValueError('release_cohort_was_not_audited_before_outcomes')
    lineage=receipt.get('repair_lineage') or {}
    prior=checked_asset(lineage.get('prior_failed_gate'))
    selected,recomputed_lineage=validation.repair_cohort(audit,prior)
    if lineage!=recomputed_lineage or freeze.get('repair_lineage')!=lineage:
        raise ValueError('release_precommitted_cohort_lineage_changed')
    selected_by_id={row['id']:row for row in selected}
    if len(selected_by_id)!=len(selected) or set(selected_by_id)!=set(phases['C']):
        raise ValueError('release_gate_not_for_precommitted_unseen_cohort')
    proof=receipt.get('controls_proof')
    controls=validation.check_controls_proof(checked_asset(proof),freeze)
    if gate.get('controls_evidence')!=controls or gate.get('controls_passed') is not True:
        raise ValueError('release_gate_actual_controls_changed')
    pairs=[]
    for identifier,c in phases['C'].items():
        b=phases['B'][identifier];selected_row=selected_by_id[identifier]
        for key in ('id','source','compiler_unit','cluster','source_record_sha256','source_capture_snapshot'):
            if b['task'][key]!=c['task'][key]:raise ValueError('release_paired_source_changed:'+key)
        task=c['task']
        if (task['cluster']!=selected_row['audit_cluster'] or selected_row.get('development_overlap')
                or not selected_row.get('source_hash_verified') or selected_row.get('support_unit')!=UNIT
                or selected_row.get('audit_disposition')!='eligible_unconsumed_audited_cluster'):
            raise ValueError('release_cohort_unseen_cluster_audit_not_passed')
        pairs.append(dict(id=identifier,cluster=task['cluster'],B=b['result']['status'],C=c['result']['status'],
                          infrastructure_failure=bool(b['result'].get('infrastructure_failure') or c['result'].get('infrastructure_failure')),
                          B_evidence=b['result_file'],C_evidence=c['result_file']))
    recorded={row['id']:row for row in gate.get('paired_results',[])}
    if len(recorded)!=len(pairs) or any(any(recorded.get(row['id'],{}).get(k)!=v for k,v in row.items()) for row in pairs):
        raise ValueError('release_gate_paired_evidence_changed')
    metrics=evaluator.decision(pairs,True);reported=gate.get('units',{}).get(UNIT,{})
    if (any(reported.get(k)!=v for k,v in metrics.items()) or metrics['passed'] is not True
            or reported.get('provenance_or_cluster_audit_passed') is not True
            or gate.get('infrastructure_errors')!=0 or UNIT not in gate.get('approved_units',[])):
        raise ValueError('release_gate_threshold_regression_or_infrastructure_failed')
    candidate=dict(freeze,release_gate=asset(gate_path))
    controller.release_gate(candidate,{UNIT})
    return dict(seal=str(seal),gate=asset(gate_path),receipt=asset(receipt_path),freeze=freeze,
                controls=controls,candidate_rows=phases['C'],metrics=metrics)


def check_manifest_assets(manifest,source=None):
    if source is not None and (manifest.get('id'),manifest.get('source_code_sha256'),manifest.get('source_image_sha256'))!=(
            source['pair_sha256'],source['code_sha256'],source['image_sha256']):
        raise ValueError('release_qualified_source_identity_changed')
    for field,digest in ASSETS:
        locator=manifest[field]
        if not isinstance(locator,str) or Path(locator).is_absolute() or '..' in Path(locator).parts:
            raise ValueError('release_qualified_asset_invalid_locator:'+field)
        path=(R/locator).resolve(strict=True)
        if not path.is_relative_to((R/'clean').resolve()) or file_sha(path)!=manifest[digest]:
            raise ValueError('release_qualified_asset_outside_clean_or_changed:'+field)


def _validate_outcome(task,result,freeze,audit_assets=True):
    controller.validate_case_result(result,controller.task_identity(task))
    if result.get('model_calls')!=0 or result.get('case_cleanup_complete') is not True:
        raise ValueError('release_prior_conversion_process_or_model_invariant_failed')
    if result.get('infrastructure_failure'):raise ValueError('release_prior_conversion_infrastructure_failure')
    if result['status']=='qualified':
        if audit_assets:check_manifest_assets(result['manifest'],task['source'])
        report=load(R/result['quality_report'])
        expected='compiler_source_ir_and_full_native_quality_v2:'+freeze['qa_policy_sha256'][:20]
        if (report.get('id')!=task['id'] or report.get('policy')!=expected or result.get('quality_policy')!=expected
                or report.get('state')!='qualified' or report.get('failures')
                or base.sha(base.raw(report.get('compiler_quality_bindings')))!=freeze['qa_policy_sha256']):
            raise ValueError('release_prior_conversion_quality_identity_changed')
        checks=report.get('checks',{})
        required={'structure','resources','source','render','text_paint','fonts','visual','native_editing'}
        if (not required<=set(checks) or any(checks[key].get('ok') is not True for key in ('source','visual','native_editing'))
                or checks['fonts'].get('all_rendered_fonts_embedded') is not True):
            raise ValueError('release_prior_conversion_full_quality_checks_missing')
        evaluator.require_render_domain(checks)
        evaluator.require_candidate_text_render('C',checks)


def prior_conversions(proof,exclude_run=None):
    """Only real conversions with this entire frozen implementation consume IDs.

    B is unchanged-candidate evaluation. A development_candidate request uses an
    artificial candidate and does not consume the original source's conversion.
    Frontend-only probes cannot acquire this full pipeline identity.
    """
    freeze=proof['freeze'];identity=controller.implementation_identity(freeze);found={}
    def add(task,result,origin,evidence):
        if task.get('evaluation_phase')=='baseline' or task.get('development_candidate'):return
        _validate_outcome(task,result,freeze)
        identifier=task['id']
        row=dict(id=identifier,task=task,result=result,origin=origin,evidence=evidence)
        if identifier in found:
            if found[identifier]['result']!=result:raise ValueError('release_duplicate_real_frozen_conversion:'+identifier)
            return
        found[identifier]=row
    for identifier,row in proof['candidate_rows'].items():
        add(row['task'],row['result'],'validation_C',row['result_file'])
    proof_paths={Path(proof['controls']['file']).resolve()}
    for directory in sorted(controller.FLOOR.iterdir()):
        if not directory.is_dir() or directory.resolve()==Path(exclude_run or '/').resolve():continue
        frozen=directory/'freeze.json'
        if not frozen.is_file():continue
        other=load(frozen)
        try:same=controller.implementation_identity(other)==identity
        except (ValueError,KeyError,TypeError):same=False
        if not same:continue
        controller.check_pins(other['pins'])
        if (directory/'proof.json').is_file():proof_paths.add((directory/'proof.json').resolve())
        if not (directory/'status.sqlite').is_file():continue
        snap=controller.snapshot(directory)
        if snap['supervisor_live']:raise ValueError('release_other_same_implementation_run_live:'+str(directory))
        with contextlib.closing(sqlite3.connect('file:'+str(directory/'status.sqlite')+'?mode=ro',uri=True)) as db:
            for seq,identifier,body,status,attempts,outcome in db.execute(
                    'select seq,id,source,status,attempts,result from samples where attempts>0 order by seq'):
                task=json.loads(body)
                if task.get('evaluation_phase')=='baseline' or task.get('development_candidate'):continue
                if status not in base.TERMINAL or attempts!=1 or outcome is None:
                    raise ValueError('release_prior_conversion_not_cleanly_terminal:'+identifier)
                result=json.loads(outcome)
                if result.get('status')!=status or seq!=task['seq'] or identifier!=task['id']:
                    raise ValueError('release_prior_ledger_identity_changed')
                add(task,result,'prior_'+snap['metadata']['mode'],asset(directory/'targets.jsonl'))
    for proof_path in sorted(proof_paths):
        controls=validation.check_controls_proof(proof_path,freeze)
        control_manifest={r['control_id']:r for r in lines(checked_asset(controls['controls_manifest']))}
        for outcome in controls['verified_outcomes']:
            item=control_manifest[outcome['control_id']]
            # Artificial negative-corrupted candidate controls are evidence of
            # rejection, never a disposition of the untouched original sample.
            if item['kind']!='positive':continue
            requests=[a for a in item['input_assets'] if a.get('role')=='request']
            if len(requests)!=1:raise ValueError('release_control_request_missing')
            task=load(checked_asset(requests[0]));result=load(outcome['result'])
            # Controls' isolated execution proof is independently verified above.
            result={**result,'case_cleanup_complete':True}
            add(task,result,'positive_control',dict(file=outcome['result'],sha256=outcome['result_sha256']))
    return [found[key] for key in sorted(found)]


def first_qualified(first_run):
    """Read one completed hash-bound index snapshot, despite atomic replacement.

    The returned reference is historical provenance. Its path may advance after
    these bytes have been copied into our own immutable preparation snapshot.
    """
    first=owned(first_run,R/'release/fixed_batch_v1')
    payload=None;reference={};target=None
    for attempt in range(5):
        summary=load(first/('summary.json' if (first/'summary.json').is_file() else 'progress.json'))
        reference=summary.get('files',{}).get('qualified',{})
        locator=Path(reference.get('file',''))
        target=(locator if locator.is_absolute() else R/locator).resolve()
        if target.parent!=first or target.name not in ('qualified.jsonl','inprogress.qualified.jsonl'):
            raise ValueError('release_first_qualified_snapshot_outside_first_owner')
        candidate=target.read_bytes()
        if base.sha(candidate)==reference.get('sha256'):
            payload=candidate;break
        # The first controller publishes its index before its summary. Retry
        # only this finite metadata read; never wait for more conversions.
        if attempt<4:time.sleep(.1)
    if payload is None:raise ValueError('release_first_qualified_snapshot_not_hash_bound')
    result={}
    for line in payload.splitlines():
        if not line.strip():continue
        row=json.loads(line)
        if row['id'] in result:raise ValueError('release_duplicate_first_qualified_id')
        result[row['id']]=row
    if len(result)!=reference.get('records'):raise ValueError('release_first_qualified_snapshot_count_changed')
    return result,dict(file=str(target),sha256=base.sha(payload))


def first_policy(first_run):
    """Immutable first-run policy/source identity, excluding moving progress."""
    first=owned(first_run,R/'release/fixed_batch_v1')
    with contextlib.closing(sqlite3.connect('file:'+str(first/'status.sqlite')+'?mode=ro',uri=True)) as db:
        meta=base.metadata(db)
    pins=load(first/'owner.json').get('pins')
    if (meta.get('policy')!='fixed_program_single_initial_screen_v1' or meta.get('input_manifest_sha256')!=INPUT_SHA
            or meta.get('total')!=EXPECTED or meta.get('full_scope') is not True or meta.get('model_calls')!=0
            or meta.get('categories')!=CATEGORIES or not isinstance(pins,dict) or not pins):
        raise ValueError('release_first_run_policy_or_source_scope_not_frozen')
    base.ensure_pins(pins)
    return dict(policy=meta['policy'],input_manifest_sha256=meta['input_manifest_sha256'],total=meta['total'],
                full_scope=True,categories=meta['categories'],model_calls=0,pins=pins)


def read_source_index(manifest):
    manifest=owned(manifest,R);sources=[];seen=set();categories=collections.Counter();python_count=0
    digest=hashlib.sha256()
    with manifest.open('rb') as stream:
        for line in stream:
            digest.update(line)
            if not line.strip():continue
            source=json.loads(line)
            if source.get('category') not in CATEGORIES:continue
            identifier=source['pair_sha256']
            if identifier in seen:raise ValueError('release_duplicate_source_id')
            seen.add(identifier);sources.append(source);categories[source['category']]+=1
            python_count+=source['format']=='python'
    if digest.hexdigest()!=INPUT_SHA:raise ValueError('release_authoritative_source_index_hash_changed')
    if len(sources)!=EXPECTED or dict(categories)!=CATEGORIES or python_count!=EXPECTED_PYTHON:
        raise ValueError('release_authoritative_source_scope_changed')
    return sources


def inspect_sources(sources,jobs_db,io_workers):
    """Read-only per-thread connections, verified indexed ID lookups only."""
    if not 1<=io_workers<=16:raise ValueError('release_io_workers_must_be_1_to_16')
    jobs_db=owned(jobs_db,W);local=threading.local();connections=[];guard=threading.Lock()
    def connection():
        if not hasattr(local,'db'):
            db=sqlite3.connect('file:'+str(jobs_db)+'?mode=ro',uri=True,timeout=30,check_same_thread=False)
            db.execute('pragma query_only=ON')
            plan=db.execute('explain query plan select input_record,output_record from jobs where id=?',('0'*64,)).fetchall()
            if not any('SEARCH jobs' in row[3] and ('INDEX' in row[3] or 'PRIMARY KEY' in row[3]) for row in plan):
                db.close();raise ValueError('release_canonical_id_lookup_is_not_indexed')
            local.db=db
            with guard:connections.append(db)
        return local.db
    def inspect(source):
        identifier=source['pair_sha256']
        job=connection().execute('select input_record,output_record from jobs where id=?',(identifier,)).fetchone()
        if not job:return dict(id=identifier,supported=False,reasons=['canonical_source_record_absent'])
        if json.loads(job[0])!=source:raise ValueError('release_source_input_record_differs_from_index:'+identifier)
        if not job[1]:return dict(id=identifier,supported=False,reasons=['cached_python_source_capture_absent'])
        record=json.loads(job[1]);support=scene.static_support(record)
        if support.get('supported') is not True:
            return dict(id=identifier,supported=False,reasons=support.get('reasons') or ['static_source_predicate_rejected'])
        if (record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(
                identifier,source['code_sha256'],source['image_sha256']):
            raise ValueError('release_cached_source_record_identity_changed:'+identifier)
        raw_record=job[1].encode() if isinstance(job[1],str) else bytes(job[1])
        return dict(id=identifier,supported=True,source_record_sha256=base.sha(raw_record),
                    source_capture_snapshot=capture.seal_snapshot(record,support),static_support_evidence=support)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=io_workers) as executor:
            return {row['id']:row for row in executor.map(inspect,(s for s in sources if s['format']=='python'))}
    finally:
        for db in connections:db.close()


def check_frozen_captures(tasks,jobs_db=None):
    """A previously passing gate cannot outlive its frozen source/capture bytes."""
    path=owned(jobs_db or W/'jobs.sqlite',W)
    with contextlib.closing(sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=30)) as db:
        db.execute('pragma query_only=ON')
        plan=db.execute('explain query plan select input_record,output_record from jobs where id=?',('0'*64,)).fetchall()
        if not any('SEARCH jobs' in row[3] and ('INDEX' in row[3] or 'PRIMARY KEY' in row[3]) for row in plan):
            raise ValueError('release_canonical_id_lookup_is_not_indexed')
        for task in tasks:
            job=db.execute('select input_record,output_record from jobs where id=?',(task['id'],)).fetchone()
            if not job or json.loads(job[0])!=task['source'] or not job[1]:
                raise ValueError('release_frozen_gate_source_input_changed:'+task['id'])
            blob=job[1].encode() if isinstance(job[1],str) else bytes(job[1])
            if base.sha(blob)!=task['source_record_sha256']:
                raise ValueError('release_frozen_gate_output_record_changed:'+task['id'])
            capture.check_snapshot(json.loads(blob),task['source_capture_snapshot'])


def prepare(seal_directory,run,gate_file=None,manifest=None,jobs_db=None,first_run=None,io_workers=8):
    run=owned(run)
    if run.exists():raise ValueError('release_run_already_exists_no_overwrite')
    proof=verify_gate(seal_directory,gate_file)
    source_path=Path(manifest or R/'release/manifest.jsonl')
    sources=read_source_index(source_path)
    first_directory=owned(first_run or FIRST,R/'release/fixed_batch_v1')
    first_identity=first_policy(first_directory)
    first,first_reference=first_qualified(first_directory)
    prior=prior_conversions(proof,exclude_run=run);by_id={row['id']:row for row in prior}
    scope_ids={s['pair_sha256'] for s in sources}
    if not set(first)<=scope_ids or not set(by_id)<=scope_ids:raise ValueError('release_prior_result_outside_authoritative_scope')
    supported=inspect_sources(sources,jobs_db or W/'jobs.sqlite',io_workers)
    targets=[];dispositions=[]
    for seq,source in enumerate(sources,1):
        identifier=source['pair_sha256'];old=by_id.get(identifier);accepted=first.get(identifier)
        row=dict(seq=seq,id=identifier,format=source['format'],category=source['category'],
                 source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],
                 converted_by_current_v2=old is not None)
        if accepted and (accepted['source_code_sha256'],accepted['source_image_sha256'])!=(source['code_sha256'],source['image_sha256']):
            raise ValueError('release_first_qualified_source_identity_changed:'+identifier)
        if old:
            if old['task']['source']!=source:raise ValueError('release_prior_source_input_record_changed:'+identifier)
            row.update(version_status=old['result']['status'],version_origin=old['origin'],version_evidence=old['evidence'])
        if old and old['result']['status']=='qualified':row.update(disposition='version_qualified',reason='same_frozen_v2_already_fully_qualified')
        elif accepted:row.update(disposition='preexisting_qualified',reason='preserved_frozen_first_run_qualification')
        elif old:row.update(disposition='version_failed',reason=old['result'].get('reason') or 'same_frozen_v2_already_attempted')
        elif source['format']!='python':
            row.update(disposition='validation_group_blocked',reason='format_has_no_approved_compiler_v2_unit:'+source['format'])
        elif not supported[identifier]['supported']:
            row.update(disposition='unsupported',reason='cached_python_graphviz_source_predicate_rejected',
                       support_reasons=supported[identifier]['reasons'])
        else:
            item=supported[identifier]
            target=dict(seq=len(targets)+1,id=identifier,source=source,source_input_record=source,
                        source_input_record_sha256=base.sha(base.raw(source)),compiler_unit=UNIT,
                        cluster='production_id:'+identifier,source_record_sha256=item['source_record_sha256'],
                        source_capture_snapshot=item['source_capture_snapshot'],
                        static_support_evidence=item['static_support_evidence'])
            targets.append(target);row.update(disposition='queued_batch',reason='approved_source_unit_frozen_for_one_finite_attempt',batch_seq=target['seq'])
        dispositions.append(row)
    if not targets:raise ValueError('release_no_undispatched_supported_targets')
    # No run/dispatch is created before all scope and gate checks above pass.
    controller.check_pins(proof['freeze']['pins'])
    if first_policy(first_directory)!=first_identity:raise ValueError('release_first_run_policy_changed_during_preparation')
    preparations=controller.FLOOR/('preparation_'+run.name)
    preparations.mkdir(parents=True,exist_ok=False)
    input_reference=write_rows(preparations/'targets.jsonl',targets)
    freeze=copy.deepcopy(proof['freeze'])
    freeze.update(input_sha256=input_reference['sha256'],release_gate=proof['gate'])
    base.atomic(preparations/'freeze.json',base.raw(freeze))
    first_snapshot=write_rows(preparations/'first_qualified.jsonl',(first[key] for key in sorted(first)))
    prior_snapshot=write_rows(preparations/'prior_results.jsonl',prior)
    scope=write_rows(preparations/'dispositions.jsonl',dispositions)
    plan=dict(schema='compiler_finite_release_plan_v2',at=base.now(),run=str(run),seal=proof['seal'],gate=proof['gate'],
              sealed_receipt=proof['receipt'],implementation_identity_sha256=controller.implementation_digest(freeze),
              source_index=asset(source_path),source_scope_total=len(sources),python_sources_examined=len(supported),
              supported_population=sum(row['supported'] for row in supported.values()),targets=input_reference,
              freeze=asset(preparations/'freeze.json'),first_snapshot=first_snapshot,first_original=first_reference,
              first_run=str(first_directory),first_policy=first_identity,first_original_is_historical_provenance=True,
              prior_snapshot=prior_snapshot,scope=scope,queued_count=len(targets),
              counts=dict(collections.Counter(r['disposition'] for r in dispositions)),
              source_predicate='compiler_scene_v1.static_support',io_workers=io_workers,
              selection='Entire authoritative supported source unit; no outcome-dependent easy-sample filter.',
              artificial_negative_controls_consume_original_ids=False,model_calls=0,finite=True)
    base.atomic(preparations/'plan.json',base.raw(plan))
    auxiliary=dict(schema='compiler_release_auxiliary_receipt_v1',at=base.now(),plan=asset(preparations/'plan.json'),
                   program=dict(file=str(Path(__file__).resolve()),sha256=file_sha(__file__)),
                   conversion_implementation_identity_sha256=controller.implementation_digest(freeze),
                   conversion_code_modified=False)
    base.atomic(preparations/'auxiliary_receipt.json',base.raw(auxiliary))
    snapshot=controller.create(run,preparations/'targets.jsonl',preparations/'freeze.json','batch')
    base.atomic(run/'release_preparation.json',base.raw(dict(plan=asset(preparations/'plan.json'),
                auxiliary_receipt=asset(preparations/'auxiliary_receipt.json'))))
    return dict(run=str(run),plan=str(preparations/'plan.json'),queued=len(targets),scope_total=len(sources),
                supported_population=plan['supported_population'],counts=plan['counts'],snapshot=snapshot,launched=False)


def read_plan(run,revalidate_gate=True,revalidate_prior=False):
    run=owned(run);link=load(run/'release_preparation.json')
    plan=load(checked_asset(link['plan']));aux=load(checked_asset(link['auxiliary_receipt']))
    if aux.get('plan')!=link['plan'] or Path(aux['program']['file']).resolve()!=Path(__file__).resolve() or file_sha(__file__)!=aux['program']['sha256']:
        raise ValueError('release_auxiliary_program_or_plan_changed')
    if plan.get('schema')!='compiler_finite_release_plan_v2' or Path(plan['run']).resolve()!=run:
        raise ValueError('release_plan_run_identity_changed')
    # first_original names a moving first-controller index. Only first_snapshot
    # belongs to this frozen input receipt and remains hash-checked here.
    for key in ('gate','sealed_receipt','source_index','targets','freeze','first_snapshot','prior_snapshot','scope'):
        checked_asset(plan[key])
    freeze=load(run/'freeze.json')
    if load(checked_asset(plan['freeze']))!=freeze or file_sha(run/'targets.jsonl')!=plan['targets']['sha256']:
        raise ValueError('release_created_ledger_inputs_changed')
    controller.check_pins(freeze['pins']);controller.check_implementation_identity(freeze)
    if controller.implementation_digest(freeze)!=plan['implementation_identity_sha256']:
        raise ValueError('release_created_ledger_implementation_changed')
    if revalidate_gate:
        proof=verify_gate(plan['seal'],plan['gate']['file'])
        if proof['gate']!=plan['gate'] or proof['receipt']!=plan['sealed_receipt']:
            raise ValueError('release_gate_changed_since_preparation')
        if revalidate_prior:
            current=prior_conversions(proof,exclude_run=run)
            if current!=list(lines(checked_asset(plan['prior_snapshot']))):
                raise ValueError('release_real_conversion_inventory_changed_since_preparation')
    return plan,freeze


def process_identity(pid):
    from initial_conversion_process_v1 import identity
    value=identity(pid)
    if not value:raise RuntimeError('release_process_birth_identity_unavailable')
    argv=[s.decode(errors='replace') for s in Path('/proc',str(pid),'cmdline').read_bytes().split(b'\0') if s]
    return dict(pid=pid,start_ticks=value['start_ticks'],state=value['state'],argv=argv)


def process_live(owner):
    try:
        actual=process_identity(owner['pid'])
        return actual['state']!='Z' and actual['start_ticks']==owner['start_ticks'] and actual['argv']==owner['argv']
    except (OSError,ValueError,KeyError,RuntimeError):return False


def fresh_ledger(run):
    snap=controller.snapshot(run);total=snap['metadata']['total']
    if (snap['metadata'].get('mode')!='batch' or snap['metadata'].get('finished') or snap['supervisor_live']
            or snap['counts']!={'queued':total} or snap['dispatch_attempt_counts']!={0:total}
            or snap['infrastructure_stop'] or (run/'owner.json').exists()):
        raise ValueError('release_launch_requires_fresh_undispatched_ledger')
    expected=list(lines(run/'targets.jsonl'))
    with contextlib.closing(sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)) as db:
        stored=db.execute('select seq,id,source,status,attempts from samples order by seq').fetchall()
    if (len(expected)!=total or len(stored)!=total or snap['metadata']['units']!=[UNIT]
            or snap['metadata']['input_sha256']!=file_sha(run/'targets.jsonl')
            or snap['metadata']['freeze_sha256']!=base.sha(base.raw(load(run/'freeze.json')))
            or any((seq,identifier,status,attempts)!=(task['seq'],task['id'],'queued',0)
                   or json.loads(body)!=task for task,(seq,identifier,body,status,attempts) in zip(expected,stored))):
        raise ValueError('release_fresh_ledger_does_not_match_frozen_targets')
    return snap


def launch(run,workers,timeout,python=None):
    run=owned(run);timeout=float(timeout)
    if not 1<=workers<=24 or not 1<=timeout<=1800:raise ValueError('release_invalid_resource_limits')
    with (run/'release_launch.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (run/'release_launch.json').exists():raise ValueError('release_already_launched_no_automatic_retry')
        plan,freeze=read_plan(run,revalidate_prior=True);fresh_ledger(run)
        work=controller.WORK/run.name
        if work.exists():raise ValueError('release_worker_directory_already_exists')
        token=uuid.uuid4().hex
        command=[str(Path(python or sys.executable).resolve()),'-B',str(Path(__file__).resolve()),'_supervise',
                 '--run',str(run),'--workers',str(workers),'--case-timeout',str(timeout),'--token',token]
        receipt=dict(at=base.now(),token=token,run=str(run),workers=workers,case_timeout_seconds=timeout,
                     command=command,plan_sha256=load(run/'release_preparation.json')['plan']['sha256'],
                     implementation_identity_sha256=controller.implementation_digest(freeze),finite=True,model_calls=0)
        base.atomic(run/'release_launch.json',base.raw(receipt))
        try:
            with (run/'release_program.log').open('xb') as log:
                child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                       start_new_session=True,close_fds=True)
            deadline=time.monotonic()+55
            while time.monotonic()<deadline:
                if (run/'release_error.json').exists():raise RuntimeError('release_start_failed:'+str(load(run/'release_error.json')))
                if (run/'release_child.json').exists():
                    owner=load(run/'release_child.json');snap=controller.snapshot(run)
                    if owner.get('token')!=token:raise RuntimeError('release_child_start_token_changed')
                    if (process_live(owner['owner']) and snap['supervisor_live']
                            and snap['owner'].get('pid')==owner['owner']['pid']
                            and snap['owner'].get('start_ticks')==owner['owner']['start_ticks']):
                        return dict(started=True,run=str(run),wrapper=load(run/'release_wrapper.json'),child=owner,
                                    snapshot=snap,log=str(run/'release_program.log'),finite=True)
                if child.poll() is not None:
                    if (run/'release_final/summary.json').is_file():return dict(started=True,already_finished=True,summary=load(run/'release_final/summary.json'))
                    raise RuntimeError('release_supervisor_exited_before_verified_start')
                time.sleep(.1)
            raise RuntimeError('release_start_handshake_timed_out_inspect_recorded_owner')
        except BaseException as error:
            base.atomic(run/'release_launch_error.json',base.raw(dict(at=base.now(),detail=repr(error))))
            raise


def supervise(run,workers,timeout,token):
    run=owned(run);launch_receipt=load(run/'release_launch.json')
    if (launch_receipt['token'],launch_receipt['workers'],launch_receipt['case_timeout_seconds'])!=(token,workers,timeout):
        raise ValueError('release_wrapper_launch_identity_mismatch')
    interrupted=[];child=None
    def stop(signum,frame):
        interrupted.append(signum)
        if child is not None and child.poll() is None:child.send_signal(signum)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        with (controller.FLOOR/'finite_release_program.lock').open('a+') as global_lock:
            fcntl.flock(global_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            read_plan(run,revalidate_prior=True);fresh_ledger(run)
            wrapper=dict(at=base.now(),token=token,owner=process_identity(os.getpid()),finite=True,watch=False,model_calls=0)
            base.atomic(run/'release_wrapper.json',base.raw(wrapper))
            command=[sys.executable,'-B',str(Path(controller.__file__).resolve()),'run','--run-id',run.name,
                     '--workers',str(workers),'--case-timeout',str(timeout)]
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,close_fds=True)
            owner=process_identity(child.pid)
            base.atomic(run/'release_child.json',base.raw(dict(at=base.now(),token=token,owner=owner,command=command)))
            returncode=child.wait()
            completion=dict(at=base.now(),token=token,owner=owner,command=command,returncode=returncode,
                            interrupted_signals=interrupted,child_reaped=True)
            base.atomic(run/'release_child_completion.json',base.raw(completion))
            if returncode!=0 or interrupted:raise RuntimeError('release_controller_interrupted_or_nonzero_exit')
            result=finalize(run)
            base.atomic(run/'release_wrapper_complete.json',base.raw(dict(at=base.now(),token=token,summary=asset(run/'release_final/summary.json'))))
            return result
    except BaseException as error:
        base.atomic(run/'release_error.json',base.raw(dict(at=base.now(),token=token,detail=repr(error),finalized=False)))
        raise


def _terminal_batch(run,freeze):
    snap=controller.snapshot(run)
    if (not snap['metadata'].get('finished') or snap['infrastructure_stop'] or snap['supervisor_live']
            or any(status not in base.TERMINAL for status in snap['counts'])
            or snap['dispatch_attempt_counts']!={1:snap['metadata']['total']}):
        raise ValueError('release_cannot_finalize_incomplete_interrupted_or_infrastructure_run')
    expected=list(lines(run/'targets.jsonl'));results=[];processed_reference=asset(run/'processed.jsonl')
    with contextlib.closing(sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)) as db:
        stored=db.execute('select seq,id,source,status,attempts,result from samples order by seq').fetchall()
    if len(stored)!=len(expected):raise ValueError('release_final_ledger_count_changed')
    for task,(seq,identifier,body,status,attempts,outcome) in zip(expected,stored):
        result=json.loads(outcome)
        if task!=json.loads(body) or (seq,identifier,status,attempts)!=(task['seq'],task['id'],result['status'],1):
            raise ValueError('release_final_ledger_identity_changed')
        _validate_outcome(task,result,freeze,audit_assets=False)
        results.append(dict(id=identifier,task=task,result=result,origin='batch',evidence=processed_reference))
    return results


def merge_first_snapshots(plan,scope):
    """Preserve our copy, add fresh first accepts under the same frozen policy."""
    original={row['id']:row for row in lines(checked_asset(plan['first_snapshot']))}
    if first_policy(plan['first_run'])!=plan['first_policy']:
        raise ValueError('release_latest_first_run_policy_changed')
    latest,reference=first_qualified(plan['first_run'])
    if first_policy(plan['first_run'])!=plan['first_policy']:
        raise ValueError('release_latest_first_run_policy_changed_during_snapshot')
    sources={row['id']:row for row in scope}
    for snapshot in (original,latest):
        for identifier,manifest in snapshot.items():
            source=sources.get(identifier)
            if source is None or (manifest.get('source_code_sha256'),manifest.get('source_image_sha256'))!=(
                    source['source_code_sha256'],source['source_image_sha256']):
                raise ValueError('release_latest_first_qualified_source_identity_changed:'+identifier)
    combined={**original,**latest}
    provenance=dict(schema='compiler_first_snapshot_merge_v1',at=base.now(),first_run=plan['first_run'],
                    frozen_policy=plan['first_policy'],original_copied_snapshot=plan['first_snapshot'],
                    original_index_at_preparation=plan['first_original'],latest_completed_index=reference,
                    mutable_index_references_are_historical_provenance=True,original_records=len(original),
                    latest_records=len(latest),preserved_union_records=len(combined),
                    new_first_qualified_ids_since_preparation=len(set(latest)-set(original)))
    return combined,provenance


def staging_directories(run):
    return [p for p in sorted(Path(run).glob('.release_final.staging_*'))
            if p.is_dir() and not p.is_symlink() and p.resolve().parent==Path(run).resolve()]


def fsync_directory(path):
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
    try:os.fsync(fd)
    finally:os.close(fd)


def staged_reference(reference,final):
    """Hashes come from staging bytes; published references name final paths."""
    return dict(file=str(final/Path(reference['file']).name),sha256=reference['sha256'])


def finalize(run):
    run=owned(run)
    with (run/'release_finalize.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        plan,freeze=read_plan(run)
        completion=load(run/'release_child_completion.json');launched=load(run/'release_launch.json')
        child=load(run/'release_child.json')
        command=completion.get('command',[])
        if (completion.get('token')!=launched.get('token') or completion.get('returncode')!=0
                or completion.get('child_reaped') is not True or completion.get('interrupted_signals')
                or child.get('token')!=launched.get('token') or child.get('owner')!=completion.get('owner')
                or child.get('command')!=command or completion.get('owner',{}).get('argv')!=command
                or process_live(completion['owner']) or len(command)!=10
                or command[1:6]!=['-B',str(Path(controller.__file__).resolve()),'run','--run-id',run.name]
                or command[6:]!=['--workers',str(launched['workers']),'--case-timeout',str(launched['case_timeout_seconds'])]):
            raise ValueError('release_finalize_requires_clean_actual_controller_completion')
        final=run/'release_final'
        if final.is_symlink():raise ValueError('release_final_destination_is_not_owned_directory')
        if (final/'summary.json').is_file():
            summary=load(final/'summary.json')
            if (summary.get('schema')!='compiler_finite_release_summary_v2' or summary.get('run')!=str(run)
                    or summary.get('input_sha256')!=freeze['input_sha256']
                    or summary.get('implementation_identity_sha256')!=controller.implementation_digest(freeze)
                    or summary.get('gate')!=plan['gate']):
                raise ValueError('release_existing_final_summary_identity_changed')
            for reference in summary['files'].values():checked_asset(reference)
            return summary
        batch=_terminal_batch(run,freeze)
        prior=list(lines(checked_asset(plan['prior_snapshot'])));scope=list(lines(checked_asset(plan['scope'])))
        qualified,first_merge=merge_first_snapshots(plan,scope)
        versions={row['id']:row for row in prior}
        for row in batch:
            if row['id'] in versions:raise ValueError('release_batch_repeated_already_consumed_id')
            versions[row['id']]=row
        for identifier,row in versions.items():
            if row['result']['status']=='qualified':qualified[identifier]=row['result']['manifest']
        scope_ids={row['id'] for row in scope}
        if len(scope)!=EXPECTED or len(scope_ids)!=EXPECTED or not set(qualified)<=scope_ids or not set(versions)<=scope_ids:
            raise ValueError('release_final_full_scope_identity_changed')
        asset_count=0
        for row in scope:
            identifier=row['id'];version=versions.get(identifier)
            if identifier in qualified:
                m=qualified[identifier]
                if (m['source_code_sha256'],m['source_image_sha256'])!=(row['source_code_sha256'],row['source_image_sha256']):
                    raise ValueError('release_final_qualified_source_changed')
                check_manifest_assets(m);asset_count+=len(ASSETS)
                row.update(disposition='version_qualified' if version and version['result']['status']=='qualified' else 'preexisting_qualified',
                           reason='actual_clean_payloads_hash_verified',qualified=True)
            elif version:
                row.update(disposition='version_failed',reason=version['result'].get('reason') or 'frozen_v2_attempt_failed',qualified=False)
            elif row['disposition']=='queued_batch':raise ValueError('release_undispatched_target_cannot_be_called_final')
            if version:row.update(converted_by_current_v2=True,version_status=version['result']['status'],version_origin=version['origin'])
        # An older implementation might have exposed an interrupted final
        # directory. Preserve it as unpublished evidence, then rebuild from the
        # already terminal ledgers. No conversion can be dispatched here.
        if final.exists() or final.is_symlink():
            if final.is_symlink() or not final.is_dir():
                raise ValueError('release_final_destination_is_not_owned_directory')
            os.rename(final,run/('.release_final.staging_legacy_'+uuid.uuid4().hex))
            fsync_directory(run)
        interrupted_stages=[str(path) for path in staging_directories(run)]
        stage=run/('.release_final.staging_'+uuid.uuid4().hex)
        stage.mkdir(exist_ok=False)
        files={}
        files['qualified']=staged_reference(write_rows(stage/'qualified.jsonl',(qualified[k] for k in sorted(qualified))),final)
        files['failed']=staged_reference(write_rows(stage/'failed.jsonl',(versions[k]['result'] for k in sorted(versions) if versions[k]['result']['status']=='abandoned')),final)
        files['processed']=staged_reference(write_rows(stage/'processed.jsonl',(row for row in scope if row['id'] in qualified or row['id'] in versions)),final)
        files['dispositions']=staged_reference(write_rows(stage/'dispositions.jsonl',scope),final)
        audit=dict(at=base.now(),ok=True,qualified_payloads_verified=len(qualified),file_hash_checks=asset_count,
                   required_final_fields=[field for field,_ in ASSETS],all_payloads_under=str(R/'clean'),
                   first_run_original_preserved=True,model_calls=0)
        base.atomic(stage/'asset_audit.json',base.raw(audit))
        files['asset_audit']=staged_reference(asset(stage/'asset_audit.json'),final)
        base.atomic(stage/'first_snapshot_provenance.json',base.raw(first_merge))
        files['first_snapshot_provenance']=staged_reference(asset(stage/'first_snapshot_provenance.json'),final)
        removed=[];work=controller.WORK/run.name
        if work.is_dir() and not work.is_symlink() and work.resolve().parent==controller.WORK.resolve():
            try:work.rmdir();removed.append(str(work))
            except OSError:pass
        summary=dict(schema='compiler_finite_release_summary_v2',at=base.now(),finished=True,finite=True,
                     run=str(run),input_sha256=freeze['input_sha256'],
                     scope_total=EXPECTED,qualified=len(qualified),processed_ids=sum(r['id'] in qualified or r['id'] in versions for r in scope),
                     current_v2_converted=len(versions),batch_converted=len(batch),
                     failed_attempts=sum(r['result']['status']=='abandoned' for r in versions.values()),
                     counts=dict(collections.Counter(row['disposition'] for row in scope)),files=files,
                     implementation_identity_sha256=controller.implementation_digest(freeze),gate=plan['gate'],
                     first_snapshot_merge=dict(latest_records=first_merge['latest_records'],
                         new_first_qualified_ids_since_preparation=first_merge['new_first_qualified_ids_since_preparation']),
                     recovered_from_unpublished_staging=interrupted_stages,
                     empty_new_owned_directories_removed=removed,model_calls=0,
                     interpretation='Qualified data preserves first-run accepts and prefers a fully qualified v2 result by ID. Failed attempts remain explicit; unsupported and validation-blocked IDs were never converted by this program.')
        controller.check_pins(freeze['pins'])
        base.ensure_pins(plan['first_policy']['pins'])
        for reference in files.values():
            if Path(reference['file']).parent!=final or file_sha(stage/Path(reference['file']).name)!=reference['sha256']:
                raise ValueError('release_staged_export_changed_before_publication')
        base.atomic(stage/'summary.json',base.raw(summary))
        fsync_directory(stage)
        if final.exists() or final.is_symlink():raise ValueError('release_final_destination_appeared_before_publication')
        os.rename(stage,final)
        fsync_directory(run)
        return summary


def status(run):
    run=owned(run);snap=controller.snapshot(run)
    plan=load(checked_asset(load(run/'release_preparation.json')['plan']))
    wrapper=load(run/'release_wrapper.json') if (run/'release_wrapper.json').is_file() else None
    terminal=sum(snap['counts'].get(key,0) for key in base.TERMINAL)
    elapsed=None;eta=None
    if (run/'release_launch.json').is_file():
        import datetime
        elapsed=max(0,time.time()-datetime.datetime.fromisoformat(load(run/'release_launch.json')['at']).timestamp())
        if terminal and elapsed:eta=elapsed*(snap['metadata']['total']-terminal)/terminal
    return dict(run=str(run),snapshot=snap,scope_total=plan['source_scope_total'],queued_at_prepare=plan['queued_count'],
                wrapper_live=bool(wrapper and process_live(wrapper['owner'])),elapsed_seconds=elapsed,
                estimated_remaining_seconds=eta,eta_basis='Observed completed cases per elapsed second; descriptive estimate only.',
                log=str(run/'release_program.log'),final_summary=str(run/'release_final/summary.json') if (run/'release_final/summary.json').is_file() else None,
                unpublished_finalization_staging=[str(path) for path in staging_directories(run)],
                error=load(run/'release_error.json') if (run/'release_error.json').is_file() else None)


def cli():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','launch','finalize','status','_supervise'))
    parser.add_argument('--run',required=True);parser.add_argument('--seal-directory');parser.add_argument('--gate')
    parser.add_argument('--manifest');parser.add_argument('--jobs-db');parser.add_argument('--first-run')
    parser.add_argument('--io-workers',type=int,default=8);parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--case-timeout',type=float,default=600);parser.add_argument('--python');parser.add_argument('--token')
    args=parser.parse_args()
    if args.action=='prepare':
        if not args.seal_directory:parser.error('prepare requires --seal-directory')
        result=prepare(args.seal_directory,args.run,args.gate,args.manifest,args.jobs_db,args.first_run,args.io_workers)
    elif args.action=='launch':result=launch(args.run,args.workers,args.case_timeout,args.python)
    elif args.action=='finalize':result=finalize(args.run)
    elif args.action=='status':result=status(args.run)
    else:result=supervise(args.run,args.workers,args.case_timeout,args.token)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':cli()
