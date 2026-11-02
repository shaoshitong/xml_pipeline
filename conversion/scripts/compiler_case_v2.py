"""One bounded compiler case, its deterministic normalization and full QA.

Invoked by compiler_batch_v2 in an isolated Linux process tree. No model, SQL
publication or mutation of an original source/candidate is performed.
"""
import json
import sqlite3
import traceback
from pathlib import Path

from fixed_batch_case_v1 import R,W,checked,prepare_originals,raw,save,sha

UNIT='python_graphviz_cached_source_v1'


def run(request_path):
    request=json.loads(Path(request_path).read_bytes())
    work=Path(request['work']).resolve();identifier=request['id'];stage='input'
    source=request['source'];history=[]
    result=dict(id=identifier,seq=request['seq'],compiler_unit=request['compiler_unit'],
                cluster=request.get('cluster'),source_code_sha256=source['code_sha256'],
                source_image_sha256=source['image_sha256'],compiler_version='compiler_v2',
                model_calls=0,normalization_steps=history)
    try:
        if not work.is_relative_to((W/'compiler_v2').resolve()):raise ValueError('compiler_case_outside_owner')
        for path,digest in request['pins'].items():
            if sha(Path(path).read_bytes())!=digest:raise RuntimeError('infrastructure_compiler_pin_changed:'+path)
        d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
        try:job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
        finally:d.close()
        if not job or json.loads(job[4])!=source:raise ValueError('compiler_original_source_identity_changed')
        if request.get('source_record_sha256') and sha((job[9] or '').encode())!=request['source_record_sha256']:
            raise ValueError('compiler_source_capture_record_changed_since_selection')
        if (source['pair_sha256'],source['category'],source['format'])!=(identifier,job[1],job[2]):
            raise ValueError('compiler_input_source_identity_mismatch')
        if request['compiler_unit']!=UNIT:raise ValueError('unsupported_compiler_unit')
        if not job[9]:raise ValueError('compiler_requires_existing_hash_bound_source_capture')
        original=json.loads(job[9]);original=prepare_originals(original,source,json.loads(job[11]) if job[11] else None,work)
        for field,digest in [('code_file','code_sha256'),('image_file','image_sha256')]:checked(original[field],original[digest])
        from compiler_capture_snapshot_v1 import check_snapshot,seal_snapshot
        snapshot=request.get('source_capture_snapshot')
        if snapshot is None:
            if request['mode']!='development':raise RuntimeError('infrastructure_missing_selected_capture_snapshot')
            snapshot=seal_snapshot(original)
        check_snapshot(original,snapshot)
        original={**original,'compiler_source_capture_snapshot':snapshot}
        stage='source_reference'
        from compiler_source_reproduction_v1 import check as reproduce_source
        reproduction=reproduce_source(original,work/'source_reproduction')
        check_snapshot(original,snapshot)
        save(work/'source_reproduction_result.json',raw(reproduction))
        result['source_reproduction_evidence']=reproduction.get('evidence')
        result['source_reproduction_reason']=reproduction.get('reason')
        if reproduction.get('infrastructure_failure'):
            raise RuntimeError('infrastructure_source_reproduction:'+json.dumps(reproduction.get('detail')))
        if not reproduction.get('supported') or not reproduction.get('ok'):
            result.update(status='abandoned',phase=stage,reason=reproduction.get('reason') or 'source_reference_not_reproduced',
                          detail=reproduction.get('source_reference_visual') or reproduction.get('detail'),
                          diagnostic_stage='source_engine_reference_mismatch')
            save(work/'result.json',raw(result));return result
        baseline=request.get('evaluation_phase')=='baseline'
        if baseline and request['mode']=='batch':raise ValueError('baseline_evaluation_not_allowed_in_production_batch')
        if baseline:
            for key in ('code_sha256','image_sha256'):
                if original[key]!=request['baseline_'+key]:raise ValueError('compiler_baseline_revision_changed')
            record=original
        elif request['mode']=='development' and request.get('development_candidate'):
            candidate=Path(request['development_candidate']).resolve(strict=True)
            if not candidate.is_relative_to((R/'clean').resolve()):raise ValueError('development_candidate_outside_clean')
            record=json.loads(candidate.read_bytes())
            if (record.get('id'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(identifier,source['code_sha256'],source['image_sha256']):
                raise ValueError('development_candidate_identity_mismatch')
        else:
            stage='conversion'
            from compiler_scene_text_v2 import convert
            attempt=convert(original,job,work/'frontend')
            save(work/'frontend_result.json',raw(attempt))
            if not attempt.get('ok'):
                result.update(status='abandoned',phase=stage,reason=attempt.get('reason'),detail=attempt,
                              infrastructure_failure=attempt.get('infrastructure_failure') is True)
                save(work/'result.json',raw(result));return result
            record=attempt['record']
        record={**record,'compiler_source_reproduction':reproduction['evidence'],
                'compiler_source_capture_snapshot':snapshot,
                'compiler_quality_phase_v2':'baseline' if baseline else 'candidate'}
        from compiler_quality_v2 import verify,publish
        used=set();stage='quality';report={};out=None;directory=None
        for index in range(3):
            report,out,directory=verify(record,job,work,index)
            result.update(quality_report=str((directory/'audit.json').relative_to(R)),
                          quality_policy=report['policy'],quality_failures=report.get('failures'),
                          diagnostic_stage=report.get('diagnostic_stage'))
            if report.get('infrastructure_failure'):
                raise RuntimeError('infrastructure_compiler_quality:'+json.dumps(report.get('failures')))
            if out and report.get('state')=='qualified' or baseline:break
            text=json.dumps(report.get('failures',[]),ensure_ascii=False)
            action=None
            if 'actual_font_portability_requires_embedding' in text and 'font' not in used:action='font'
            elif any(word in text for word in ('Native content requires full tight canvas','unregistered_reference_canvas_difference',
                    'native_outside_reference_canvas_requires_registered_recovery','unsupported_native_canvas')) and 'canvas' not in used:action='canvas'
            if not action or index==2:break
            used.add(action);step=work/(str(index)+'_'+action);step.mkdir()
            if action=='font':from round2_font_repair_v1 import repair
            else:from round2_canvas_repair_v1 import repair
            attempt=repair(record,job,step)
            history.append(dict(action=action,ok=attempt.get('ok') is True,
                                reason=attempt.get('reason'),detail=attempt.get('detail') or attempt.get('error'),
                                preceding_quality_failures=report.get('failures'),evidence=str(step.relative_to(R))))
            if not attempt.get('ok'):
                result['last_normalization_failure']=history[-1]
                if attempt.get('error_type') in ('ImportError','ModuleNotFoundError'):
                    raise RuntimeError('infrastructure_compiler_normalization_import')
                break
            record=attempt['record'];save(step/'candidate_record.json',raw(record))
        result['candidate_code_sha256']=record['code_sha256'];result['candidate_image_sha256']=record['image_sha256']
        check_snapshot(original,snapshot)
        if out and report.get('state')=='qualified':
            result.update(status='qualified',phase='quality',reason='compiler_passed_full_source_native_quality',
                          manifest=publish(out,report,directory,source))
        else:
            result.update(status='abandoned',phase='quality',reason='compiler_failed_full_quality',
                          detail=result.get('last_normalization_failure') or report.get('failures'))
        d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
        try:
            if d.execute('select * from jobs where id=?',(identifier,)).fetchone()!=job:
                raise RuntimeError('infrastructure_canonical_job_changed')
        finally:d.close()
    except Exception as error:
        result.update(status='abandoned',phase=stage,reason='compiler_case_failed',
                      error_type=type(error).__name__,detail=str(error)[:8000],
                      infrastructure_failure=isinstance(error,(ImportError,ModuleNotFoundError)) or str(error).startswith('infrastructure_'))
        save(work/'traceback.txt',traceback.format_exc().encode())
    save(work/'result.json',raw(result));return result


if __name__=='__main__':
    import sys
    run(sys.argv[1])
