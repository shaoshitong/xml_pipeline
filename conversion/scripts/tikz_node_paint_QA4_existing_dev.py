import sys,json,sqlite3,uuid,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_tikz_node_paint_viewport_v2 as frontend
import compiler_tikz_node_paint_quality_ro_v4 as quality
run=Path(sys.argv[1]);old=json.loads((run/'summary.json').read_bytes());identifier=old['id'];candidate=Path(old['candidate_file']);blob=candidate.read_bytes();claim=W/frontend.VERSION/'development_once'/(identifier+'.json');claimsha=hashlib.sha256(claim.read_bytes()).hexdigest();config=frontend.configuration();assert config['policy']==old['configuration_policy']
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
directory=W/'prototype/candidate_quality_ro_v1'/('tikz_node_paint_QA4_existing_'+identifier+'_'+uuid.uuid4().hex);qa=quality.verify(identifier,candidate,R,frontend.__file__,directory)
assert candidate.read_bytes()==blob and hashlib.sha256(claim.read_bytes()).hexdigest()==claimsha
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:assert db.execute('select*from jobs where id=?',(identifier,)).fetchone()==job
result=dict(id=identifier,quality_ok=qa.get('ok'),quality_failures=qa.get('failures'),checks=list(qa.get('checks',{})),quality_report=str(directory/'report.json'),candidate_file=str(candidate),source_core_policy_unchanged=True,candidate_unchanged=True,normal_frontend_calls=0,samecore_normal_claim_unchanged=True,canonical_unchanged=True,model_calls=0,goal_complete=False);(run/'QA4_existing_candidate_summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
