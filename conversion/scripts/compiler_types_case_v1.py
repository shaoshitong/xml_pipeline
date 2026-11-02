"""One bounded existing-IR compiler pass; unchanged full format-specific QA.

The original per-format frontend's native IR is checked against original source.
Each deterministic source/HTML/font/canvas pass is attempted at most once. B
and C have exactly the same full source/native/pixel/editability validator.
"""
import importlib
import json
from pathlib import Path
import sqlite3
import traceback

from fixed_batch_case_v1 import R,W,raw,save,sha,checked,prepare_originals
from round2_case_v1 import candidate,verify,route,MODULES

FORMATS=('drawio','html','svg','mermaid','plantuml','tikz')
VERSION='typed_bounded_existing_native_ir_compiler_v1'


def unit(fmt):
    if fmt not in FORMATS:raise ValueError('unsupported_source_format')
    return fmt+'_existing_native_ir_v1'


def static_support(job):
    if not isinstance(job,dict):
        columns=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
        job=dict(zip(columns,job))
    reasons=[]
    if job.get('format') not in FORMATS:reasons.append('format_outside_remaining_scope')
    if job.get('category') not in ('scientific_diagram','poster'):reasons.append('category_outside_scope')
    try:
        r=json.loads(job['output_record']) if isinstance(job.get('output_record'),str) else job.get('output_record')
        s=json.loads(job['input_record']) if isinstance(job.get('input_record'),str) else job['input_record']
        if not r or r.get('format')!='drawio' or not all(r.get(k) for k in ('code_file','code_sha256','image_file','image_sha256')):
            reasons.append('no_existing_native_ir')
        elif (r.get('id'),r.get('source_pair_sha256'),r.get('source_format'),r.get('source_code_sha256'),r.get('source_image_sha256'))!=(job['id'],job['id'],job['format'],s['code_sha256'],s['image_sha256']):
            reasons.append('existing_ir_source_identity_not_bound')
    except (ValueError,KeyError,TypeError):reasons.append('invalid_source_or_ir_metadata')
    return dict(supported=not reasons,unit=unit(job['format']) if job.get('format') in FORMATS else None,reasons=reasons,
                scope='Existing source-bound native IR; source completeness and all quality gates are rechecked per case, never assumed from metadata.')


def run(path):
    q=json.loads(Path(path).read_bytes());identifier=q['id'];work=Path(q['work']).resolve()
    result=dict(id=identifier,seq=q['seq'],compiler_unit=q['compiler_unit'],cluster=q.get('cluster'),
                source_code_sha256=q['source']['code_sha256'],source_image_sha256=q['source']['image_sha256'],
                compiler_version='compiler_types_v1',model_calls=0,repair_steps=[])
    stage='input'
    try:
        if not work.is_relative_to((W/'compiler_types_v1').resolve()):raise ValueError('typed_case_outside_owner')
        for name,digest in q['pins'].items():
            if sha(Path(name).read_bytes())!=digest:raise RuntimeError('infrastructure_typed_pin_changed:'+name)
        db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
        try:job=db.execute('select * from jobs where id=?',(identifier,)).fetchone()
        finally:db.close()
        if not job or json.loads(job[4])!=q['source']:raise ValueError('typed_original_source_identity_changed')
        if q['compiler_unit']!=unit(job[2]):raise ValueError('typed_source_unit_mismatch')
        if q.get('source_record_sha256') and sha((job[9] or '').encode())!=q['source_record_sha256']:
            raise RuntimeError('infrastructure_selected_native_ir_changed')
        support=static_support(job)
        if not support['supported']:raise ValueError('typed_unsupported:'+json.dumps(support['reasons']))
        record=prepare_originals(candidate(job,q.get('first_result',{})),q['source'],json.loads(job[11]) if job[11] else None,work)
        if q.get('development_candidate'):
            p=Path(q['development_candidate']).resolve(strict=True)
            if not p.is_relative_to((R/'clean').resolve()):raise ValueError('development_candidate_outside_clean')
            record=json.loads(p.read_bytes())
        baseline=q.get('evaluation_phase')=='baseline'
        if baseline and q.get('mode')=='batch':raise ValueError('baseline_in_production_forbidden')
        if baseline and not q.get('development_candidate'):
            if (record['code_sha256'],record['image_sha256'])!=(q['baseline_code_sha256'],q['baseline_image_sha256']):
                raise ValueError('typed_baseline_revision_changed')
        for field,digest in (('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')):
            checked(record[field],record[digest])
        used=set();report={};out=None;directory=None;stage='quality'
        for index in range(5):
            report,out,directory=verify(record,job,work,index)
            result.update(quality_report=str((directory/'audit.json').relative_to(R)),quality_policy=report['policy'],
                          quality_failures=report.get('failures'),candidate_code_sha256=record['code_sha256'],candidate_image_sha256=record['image_sha256'])
            if report.get('exception_type') in ('ImportError','ModuleNotFoundError') or 'infrastructure_' in json.dumps(report.get('failures',[])):
                raise RuntimeError('infrastructure_typed_quality:'+json.dumps(report.get('failures')))
            if out and report.get('state')=='qualified' or baseline or q.get('negative_control') or index==4:break
            options=[a for a in route({'status':'abandoned','detail':report.get('failures',[])},job[2]) if a not in used]
            if not options:break
            action=options[0];used.add(action);step=work/(str(index)+'_'+action);step.mkdir(parents=True,exist_ok=False)
            attempt=importlib.import_module(MODULES[action]).repair(record,job,step)
            result['repair_steps'].append(dict(action=action,ok=attempt.get('ok') is True,reason=attempt.get('reason'),
                                              detail=attempt.get('detail') or attempt.get('error'),evidence=str(step.relative_to(R))))
            if not attempt.get('ok'):
                if attempt.get('error_type') in ('ImportError','ModuleNotFoundError'):raise RuntimeError('infrastructure_typed_pass_import')
                break
            record=attempt['record'];save(step/'candidate_record.json',raw(record))
        if out and report.get('state')=='qualified':
            png=(directory/'fresh.png').read_bytes()
            if sha(png)!=out['image_sha256']:raise RuntimeError('infrastructure_typed_fresh_image_drift')
            save(R/out['image_file'],png)
            from qualified_index_v4 import manifest_row,require_source
            require_source(out,q['source']);manifest=manifest_row(out,R)[0]
            result.update(status='qualified',phase='quality',reason='typed_compiler_passed_full_unchanged_qa',manifest=manifest)
        else:result.update(status='abandoned',phase='quality',reason='typed_compiler_failed_or_unsupported',detail=report.get('failures') or result['repair_steps'])
        db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
        try:
            if db.execute('select * from jobs where id=?',(identifier,)).fetchone()!=job:raise RuntimeError('infrastructure_authoritative_native_ir_changed')
        finally:db.close()
    except Exception as e:
        result.update(status='abandoned',phase=stage,reason='typed_case_failed',error_type=type(e).__name__,detail=str(e)[:5000],
                      infrastructure_failure=isinstance(e,(ImportError,ModuleNotFoundError)) or str(e).startswith('infrastructure_'))
        save(work/'traceback.txt',traceback.format_exc().encode())
    save(work/'result.json',raw(result));return result


if __name__=='__main__':
    import sys
    run(sys.argv[1])
