from pathlib import Path
import sys,json,hashlib,sqlite3,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts';sys.path.insert(0,str(S))
import compiler_svg_general_guard_v3 as compiler
import compiler_svg_scene_quality_ro_v8 as quality
from compiler_svg_source_viewport_iteration_case_v2 import quality_database
run=Path(sys.argv[1]);previous=json.loads((run/'summary.json').read_bytes());identifier=previous['id'];candidate=Path(previous['candidate_file']);old=candidate.read_bytes();claim=Path(previous['claim']);claim_sha=hashlib.sha256(claim.read_bytes()).hexdigest();cfg=compiler.configuration();assert cfg['policy']==previous['configuration_policy']
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:job=db.execute('select * from jobs where id=?',(identifier,)).fetchone()
work=W/'SVG_analytic_QA8_existing_v1'/uuid.uuid4().hex;work.mkdir(parents=True);database,proof,audit=quality_database(job,work);qa_work=W/'prototype/candidate_quality_ro_v1'/('SVG_analytic_QA8_'+identifier[:12]+'_'+uuid.uuid4().hex);qa=quality.verify(identifier,candidate,R,Path(compiler.__file__),qa_work,database=database)
assert candidate.read_bytes()==old and hashlib.sha256(claim.read_bytes()).hexdigest()==claim_sha and compiler.configuration()==cfg
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:assert db.execute('select * from jobs where id=?',(identifier,)).fetchone()==job
result=dict(id=identifier,candidate_file=str(candidate),quality_ok=qa.get('ok'),quality_failures=qa.get('failures'),checks=list(qa.get('checks',{})),quality_report=str(qa_work/'report.json'),normal_frontend_calls=0,candidate_and_claim_unchanged=True,canonical_unchanged=True,source_configuration_unchanged=True,source_core=qa.get('generation_source_core'),work=str(work),model_calls=0,goal_complete=False)
(work/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,ensure_ascii=False))
