"""Read-only XML audit of existing native qualifications; never inspect pixels."""
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys

import native_source_dynamic_label_guard_v1 as guard

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
OUTPUT=R/'release/compiler_iterations/audits/native_core2_qualified_variable_source_audit_20261101_v1/proof.json'


def run():
    import compiler_iteration_inventory_v1 as inventory
    import compiler_mermaid_alpha_qualifications_v2 as qualifications
    import compiler_types_program_v1 as common
    scope,_=inventory.read_scope(R);native={identifier:source for identifier,source in scope.items()if source['format']=='drawio'}
    if len(native)!=1539:raise ValueError('native_source_audit_scope_not_1539')
    manifests=qualifications.ledger_manifests(root=R,identifiers=set(native))
    current=json.loads((R/'release/compiler_iterations/current.json').read_bytes());summary=R/current['inventory'];info=json.loads(summary.read_bytes());qualified=summary.parent/'qualified.jsonl'
    if common.sha(summary.read_bytes())!=current['inventory_sha256']or common.sha(qualified.read_bytes())!=info['files']['qualified.jsonl']['sha256']:raise ValueError('qualified_source_audit_inventory_changed')
    manifests.extend(row for line in qualified.read_bytes().splitlines()if line for row in[json.loads(line)]if row['id']in native)
    control=R/'release/compiler_iterations/controls/native_materialized_text_node_controls_20261101_v2/proof.json';control_blob=control.read_bytes()
    if common.sha(control_blob)!='61ba2f673a2c11252ade9f102217892ba7317b3115f1f669461339d0145399da':raise ValueError('native_control2_manifest_changed')
    control_ref=json.loads(control_blob)['qualified_manifest'];_,payload=common.checked(control_ref)
    manifests.extend(json.loads(line)for line in payload.splitlines()if line)
    unique={}
    for manifest in manifests:unique.setdefault((manifest['id'],manifest['metadata_sha256'],manifest['code_sha256']),manifest)
    cases=[];affected=[];methods=Counter();jobs={}
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True,timeout=30)as db:
        db.execute('pragma query_only=ON');db.execute('begin')
        for identifier in sorted({key[0]for key in unique}):
            job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
            if job is None:raise ValueError('qualified_source_audit_canonical_job_missing')
            jobs[identifier]=job
    for _,manifest in sorted(unique.items()):
        identifier=manifest['id'];job=jobs[identifier];source=json.loads(job[4]);input_manifest=json.loads(job[11]);source_path=(R/input_manifest['source_code']).resolve(strict=True);source_blob=source_path.read_bytes()
        if not source_path.is_relative_to(R)or common.sha(source_blob)!=source['code_sha256']:raise ValueError('qualified_source_audit_original_payload_changed')
        _,metadata=common.checked(dict(file=manifest['metadata_file'],sha256=manifest['metadata_sha256']),clean=True);record=json.loads(metadata)
        if(record['id'],record['source_code_sha256'],record['source_image_sha256'])!=(identifier,source['code_sha256'],source['image_sha256']):raise ValueError('qualified_source_audit_metadata_original_identity_changed')
        _,candidate_blob=common.checked(dict(file=manifest['code_file'],sha256=manifest['code_sha256']),clean=True)
        before=guard.label_records(source_blob.decode('utf-8-sig'));after=guard.label_records(candidate_blob.decode('utf-8-sig'));indexed={(row['page'],row['cell'],row['wrapper_depth']):row for row in after};changes=[]
        for row in before:
            if not row['placeholders_enabled']:continue
            dynamic=any(guard._PATTERN.search(text)for text in row['labels'].values())or row['direct_placeholder_present']
            if not dynamic:continue
            candidate=indexed.get((row['page'],row['cell'],row['wrapper_depth']))
            if candidate is None:changes.append(dict(page=row['page'],cell=row['cell'],reason='original_dynamic_object_missing'));continue
            if row['direct_placeholder_present']and(row['direct_placeholder_key']!=candidate['direct_placeholder_key']or not candidate['placeholders_enabled']):changes.append(dict(page=row['page'],cell=row['cell'],reason='native_placeholder_property_role_changed'))
            for field,text in row['labels'].items():
                wanted=Counter(match.group()for match in guard._PATTERN.finditer(text));got=Counter(match.group()for match in guard._PATTERN.finditer(candidate['labels'].get(field,'')))
                lost=wanted-got
                if lost:changes.append(dict(page=row['page'],cell=row['cell'],field=field,reason='original_native_label_expression_removed_or_expanded',lost_expression_sha256_counts={guard.sha(token.encode()):count for token,count in sorted(lost.items())},source_label_sha256=guard.sha(text.encode()),candidate_label_sha256=guard.sha(candidate['labels'].get(field,'').encode())))
        method=record.get('conversion_method');policy=record.get('native_source_repair_v1',{}).get('policy');methods[str(method)]+=1
        observed=dict(id=identifier,metadata=common.asset(R/manifest['metadata_file']),source_code=dict(file=str(source_path),sha256=source['code_sha256']),candidate_code=dict(file=manifest['code_file'],sha256=manifest['code_sha256']),conversion_method=method,source_font_policy=policy,source_core2_or_control2=method=='compiler_native_source_repair_frontend_v2'or policy=='original_native_complete_text_node_materialized_backend_physical_faces_v2'or identifier in{json.loads(line)['id']for line in payload.splitlines()if line},original_dynamic_objects=sum(row['placeholders_enabled']and(any(guard._PATTERN.search(text)for text in row['labels'].values())or row['direct_placeholder_present'])for row in before),raw_expression_binding_changes=changes)
        cases.append(observed)
        if changes:affected.append(observed)
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        if any(db.execute('select*from jobs where id=?',(identifier,)).fetchone()!=job for identifier,job in jobs.items()):raise ValueError('qualified_source_audit_canonical_job_changed')
    proof=dict(schema='native_core2_qualified_variable_source_audit_v1',producer=common.asset(Path(__file__)),source_guard=common.asset(Path(guard.__file__)),scope_native_sources=1539,qualified_originals=len(jobs),qualified_versions=len(cases),conversion_methods=dict(methods),cases=cases,affected=affected,affected_versions=len(affected),source_core2_or_control2_affected_versions=sum(row['source_core2_or_control2']for row in affected),complete=True,source_only=True,reference_pixels_read=False,candidate_pixels_read=False,quality_reports_read=False,normal_source_conversion_calls=0,model_calls=0,qualified_ledgers_modified=False,canonical_original_jobs_unchanged=True,goal_complete=False)
    OUTPUT.parent.mkdir(parents=True,exist_ok=False);common.immutable(OUTPUT,common.raw(proof));return common.asset(OUTPUT)


if __name__=='__main__':
    print(json.dumps(run(),sort_keys=True))
