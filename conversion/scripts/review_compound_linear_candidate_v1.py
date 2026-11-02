"""Recheck one immutable candidate after correcting the QA painter frame.

Never reruns a normal or rewrites the original failed QA evidence.
"""
from pathlib import Path
import datetime
import hashlib
import json
import sqlite3
import sys
import time

R=Path('/backup/shaoshitong/img2code_20261029')
sys.path.insert(0,str(R/'conversion/scripts'))
import compiler_svg_general_guard_v17 as core
import compiler_svg_scene_quality_ro_v28 as quality
from compiler_svg_source_viewport_iteration_case_v2 import quality_database
from compiler_svg_general_iteration_case_v2 import publish


def main():
    work=Path(sys.argv[1]).resolve()
    assert work.is_relative_to(R/'conversion/source_compound_linear_quality_review_v1')
    candidate=Path(sys.argv[2]).resolve()
    assert candidate.is_relative_to(R/'clean/compiler_svg_scene_frontend_v21')
    before=candidate.read_bytes();record=json.loads(before);ident=record['id']
    with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        job=db.execute('select*from jobs where id=?',(ident,)).fetchone()
    config=core.configuration();database,owner,owner_audit=quality_database(job,work)
    started=time.monotonic()
    report_dir=R/'conversion/prototype/candidate_quality_ro_v1'/('source_background_rotation_complete_edit_review_'+work.name)
    qa=quality.verify(ident,candidate,R,Path(core.__file__),report_dir,database=database)
    result=dict(id=ident,work=str(work),candidate_file=str(candidate),
                candidate_metadata_sha256=hashlib.sha256(before).hexdigest(),
                normal_conversion_calls=0,quality_ok=qa.get('ok'),
                quality_failures=qa.get('failures'),quality_report=str(report_dir/'report.json'),
                checks=list(qa.get('checks',{})),elapsed_seconds=time.monotonic()-started,
                original_candidate_unchanged=candidate.read_bytes()==before,
                previous_QA_retained=True,model_calls=0,goal_complete=False)
    assert result['original_candidate_unchanged']
    if qa.get('ok'):
        assert set(result['checks']) >= {'structure','resources','render','source','text_paint','fonts','visual','native_editing'}
        result['qualified_manifest']=publish(record,json.loads(job[4]),qa,report_dir)
    assert core.configuration()==config
    with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:
        assert db.execute('select*from jobs where id=?',(ident,)).fetchone()==job
    result['canonical_unchanged']=True
    (work/'summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
