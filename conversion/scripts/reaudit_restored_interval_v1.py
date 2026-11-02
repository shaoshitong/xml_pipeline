"""Finite independent full QA of accepted outcomes in the file-change interval."""
import concurrent.futures
import hashlib
import importlib
import json
import multiprocessing
from pathlib import Path
import sqlite3
import sys
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
INCIDENT=W/'incident_recovery_20261101_v1'


def check(case):
    identifier=case['id'];manifest=case['manifest'];record_file=R/manifest['metadata_file']
    record_blob=record_file.read_bytes()
    if hashlib.sha256(record_blob).hexdigest()!=manifest['metadata_sha256']:
        raise ValueError('accepted_record_hash_changed')
    record=json.loads(record_blob)
    if case['format']=='python':
        import compiler_quality_v2 as quality
        with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as database:
            job=database.execute('select * from jobs where id=?',(identifier,)).fetchone()
        report,out,directory=quality.verify(record,job,W/'compiler_v2/incident_reaudit'/identifier/uuid.uuid4().hex,0)
        ok=bool(out and report.get('state')=='qualified' and not report.get('failures'))
        report_file=directory/'audit.json'
    else:
        routes={'svg':'compiler_iteration_case_v1','mermaid':'compiler_mermaid_iteration_case_v1','drawio':'compiler_iteration_case_v2'}
        dispatch=importlib.import_module(routes[case['format']]);frontend,quality=dispatch.bindings(case['format'])
        directory=W/'prototype/candidate_quality_ro_v1'/('incident_reaudit_'+identifier+'_'+uuid.uuid4().hex)
        report=quality.verify(identifier,record_file,R,Path(frontend.__file__),directory)
        dispatch.full_quality(report,record)
        ok=report.get('ok') is True and not report.get('failures')
        report_file=directory/'report.json'
    png=directory/'fresh.png';same=png.exists() and hashlib.sha256(png.read_bytes()).hexdigest()==manifest['image_sha256']
    result={'id':identifier,'format':case['format'],'ok':bool(ok and same),'independent_full_quality':ok,
            'fresh_png_hash_equals_accepted':same,'quality_report':str(report_file.relative_to(R)),
            'failures':report.get('failures',[]),'normal_conversion_repeated':False,'model_calls':0}
    (directory/'restored_interval_reaudit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    source=INCIDENT/'acceptance_interval.json';data=json.loads(source.read_bytes())
    destination=INCIDENT/'accepted_interval_full_reaudit.json'
    if destination.exists():raise ValueError('finite_reaudit_already_recorded')
    pins=json.loads((R/'release/compiler_v2/graphviz_batch_20261101_v2_renderdomain/freeze.json').read_bytes())['pins']
    for name,digest in pins.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('original_pin_not_restored:'+name)
    results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'),max_tasks_per_child=1) as pool:
        futures={pool.submit(check,case):case for case in data['cases']}
        for future in concurrent.futures.as_completed(futures):
            case=futures[future]
            try:result=future.result()
            except Exception as exc:result={'id':case['id'],'format':case['format'],'ok':False,'error':repr(exc)}
            results.append(result)
    report={'schema':'accepted_interval_independent_full_reaudit_v1','source_interval_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'cases':results,'passed':sum(r['ok'] for r in results),'total':len(results),'ok':all(r['ok'] for r in results),
            'accepted_assets_modified':False,'normal_conversions_repeated':0,'model_calls':0}
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'report':str(destination.relative_to(R)),'passed':report['passed'],'total':report['total'],'ok':report['ok']}))


if __name__=='__main__':main()
