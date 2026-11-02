"""One finite batch of the twelve already consumed invisible-edge failures."""
import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
import sqlite3
import sys
import uuid

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sys.path.insert(0,str(W/'scripts'))
SOURCE=W/'compiler_python_invisible_edge_ir_diagnosis_v1/189cc1e9f1d248239f46fddb3fd23e1e/report.json'


def case(task):
    identifier,root=task;work=Path(root)/identifier
    work.mkdir(parents=True,exist_ok=False)
    import compiler_graphviz_visibility_frontend_v1 as frontend
    import compiler_graphviz_visibility_quality_ro_v1 as quality
    job=frontend.job_tuple({'id':identifier})
    result=dict(id=identifier,normal_candidate_attempts=1,model_calls=0)
    support=frontend.static_support({'id':identifier})
    result['support']=support
    if not support.get('supported'):
        result.update(ok=False,stage='source_support',reason=support['reasons'])
    else:
        attempt=frontend.convert(None,job,work/'compiler')
        (work/'frontend_result.json').write_text(json.dumps(attempt,ensure_ascii=False)+'\n')
        result.update(ok=False,stage='conversion',reason=attempt.get('reason'),details=attempt.get('detail'))
        if attempt.get('ok'):
            record=attempt['record'];record_file=Path(attempt['record_file'])
            directory=W/'prototype/candidate_quality_ro_v1'/('graphviz_visibility_dev_'+identifier+'_'+uuid.uuid4().hex)
            checked=quality.verify(identifier,record_file,R,Path(frontend.__file__),directory)
            result.update(ok=checked.get('ok') is True,stage='quality',reason=checked.get('failures'),
                          record_file=str(record_file),quality_report=str(directory/'report.json'),
                          code_file=record['code_file'],image_file=record['image_file'])
    (work/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to((W/'compiler_graphviz_visibility_development_v1').resolve())
    output.mkdir(parents=True,exist_ok=False)
    source=json.loads(SOURCE.read_bytes());cases=[r['id'] for r in source['cases']]
    seen=R/'release/compiler_iterations/development_seen_v1/python_visibility_ir_20261101_v1.jsonl'
    assert len(cases)==12 and set(cases)=={json.loads(line)['id'] for line in seen.read_text().splitlines() if line}
    results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'),max_tasks_per_child=1) as pool:
        tasks={pool.submit(case,(identifier,str(output))):identifier for identifier in cases}
        for future in concurrent.futures.as_completed(tasks):
            identifier=tasks[future]
            try:result=future.result()
            except Exception as exc:result=dict(id=identifier,ok=False,stage='infrastructure',reason=repr(exc))
            results.append(result)
            print(json.dumps({k:result.get(k) for k in ('id','ok','stage','reason')},ensure_ascii=False),flush=True)
    report=dict(source_development_ids=cases,qualified=sum(r['ok'] for r in results),cases=results,
                normal_candidate_attempts_per_id=1,new_heldout_consumed=0,model_calls=0,goal_complete=False)
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'report':str(output/'report.json'),'qualified':report['qualified'],'total':len(results)}),flush=True)


if __name__=='__main__':main()
