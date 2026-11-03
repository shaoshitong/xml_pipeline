"""One actual source-core normal; existing source evidence never resets history."""
import sys,json,uuid,sqlite3,hashlib,datetime
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts';sys.path.insert(0,str(S))
import compiler_svg_general_guard_v20 as compiler
import compiler_svg_scene_quality_ro_v31 as quality
from compiler_source_core_attempts_v3 import core_identity
from compiler_mermaid_alpha_qualifications_v2 import find_qualified
from compiler_mermaid_alpha_iteration_overlap_v2 import guard as overlap_guard
from compiler_svg_source_viewport_iteration_case_v2 import quality_database
from compiler_plantuml_engine_canonical_claim_v1 import require_available
from compiler_svg_general_iteration_case_v2 import publish
identifier=sys.argv[1];work=Path(sys.argv[2]);freeze=Path(sys.argv[3]);frozen=json.loads(freeze.read_bytes());cfg=compiler.configuration();assert cfg==frozen['configuration'];core=core_identity(cfg)
for name,digest in frozen['owned'].items():assert hashlib.sha256((S/name).read_bytes()).hexdigest()==digest and not((S/name).stat().st_mode&0o222)
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:job=db.execute('select * from jobs where id=?',(identifier,)).fetchone()
source=json.loads(job[4]);manifest=json.loads(job[11]);assert source['format']=='svg'and source['category']in('scientific_diagram','poster');assert source['pair_sha256']==identifier
assert compiler.static_support(dict(zip(('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid'),job)))['supported']
require_available(dict(zip(('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid'),job)))
assert find_qualified(identifier,source,root=R)is None,'existing qualification must be preserved'
assert not overlap_guard(identifier)['active'],'birth-verified overlapping work must not be repeated'
work.mkdir(parents=True,exist_ok=False);claim=W/compiler.VERSION/'normal_once'/core['key']/(identifier+'.json');claim.parent.mkdir(parents=True,exist_ok=True)
claim_value=dict(id=identifier,source=source,source_core=core,configuration=cfg,work=str(work),normal_attempt_count=1,canonical_raw_row_sha256=hashlib.sha256(json.dumps(list(job)).encode()).hexdigest(),producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),claim_before_normal=True)
with claim.open('xb')as f:f.write((json.dumps(claim_value,sort_keys=True)+'\n').encode())
record=dict(id=identifier,source_pair_sha256=identifier,source_format='svg',category=source['category'],source=source['source'],format='drawio',source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],original_source_code=manifest['source_code'],original_reference=manifest['reference_image'])
result=dict(id=identifier,normal_frontend_calls=1,claim=str(claim),source_core=core,configuration_policy=cfg['policy'],source=source,model_calls=0,goal_complete=False)
try:
 (work/'frontend_result.json').write_text(json.dumps(dict(ok=False,normal_source_conversion_called=True,reason='started_without_terminal_frontend_result')))
 attempt=compiler.convert(record,job,work/'compiler');attempt['normal_source_conversion_called']=True;(work/'frontend_result.json').write_text(json.dumps(attempt,indent=2));result.update(conversion_ok=attempt.get('ok'),conversion_reason=attempt.get('reason'))
 if attempt.get('ok'):
  candidate=Path(attempt['record_file']);before=candidate.read_bytes();database,owner_proof,owner_audit=quality_database(job,work);qa_dir=W/'prototype/candidate_quality_ro_v1'/('SVG_source_whitespace_v23_'+identifier[:10]+'_'+uuid.uuid4().hex);qa=quality.verify(identifier,candidate,R,Path(compiler.__file__),qa_dir,database=database)
  assert candidate.read_bytes()==before;result.update(candidate_file=str(candidate),quality_ok=qa.get('ok'),quality_failures=qa.get('failures'),quality_report=str(qa_dir/'report.json'),checks=list(qa.get('checks',{})),canonical_owner_guard=owner_proof)
  if qa.get('ok'):
   qualified=publish(attempt['record'],source,qa,qa_dir);result['qualified_manifest']=qualified
except Exception as error:result.update(error_type=type(error).__name__,reason=str(error))
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:assert db.execute('select * from jobs where id=?',(identifier,)).fetchone()==job
assert compiler.configuration()==cfg;result['canonical_unchanged']=True;(work/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items()if k not in('source','qualified_manifest')},ensure_ascii=False))
