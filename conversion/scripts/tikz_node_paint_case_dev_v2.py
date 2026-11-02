import sys,json,sqlite3,uuid,datetime,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_tikz_node_paint_viewport_v2 as frontend
import compiler_tikz_node_paint_quality_ro_v2 as quality
from compiler_source_core_attempts_v3 import core_identity
identifier=sys.argv[1];run=Path(sys.argv[2]).resolve();assert run.is_relative_to(W/'tikz_node_paint_normal_development_v2');run.mkdir(parents=True,exist_ok=False);config=frontend.configuration();cfg={**config,'unit':frontend.UNITS['tikz']};core=core_identity(cfg)
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
source=json.loads(job[4]);names=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid');support=frontend.static_support(dict(zip(names,job)));assert support['supported'];assert source['format']=='tikz'and source['pair_sha256']==identifier
claimdir=W/frontend.VERSION/'development_once';claimdir.mkdir(parents=True,exist_ok=True);claim=dict(id=identifier,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],configuration=cfg,core=core,source_input_record_sha256=hashlib.sha256(job[4].encode()).hexdigest(),actual_canonical_source=source,normal_frontend_calls_planned=1,purpose='consumed_development_new_SOURCE_core_normal',run=str(run),producer=str(Path(__file__).resolve()),model_calls=0)
with(claimdir/(identifier+'.json')).open('xb')as f:f.write(frontend.raw(claim))
frontend.save(run/'predeclared.json',frontend.raw(claim));record=dict(id=identifier,source_pair_sha256=identifier,category=source['category'],source=source['source'],source_format='tikz',format='drawio',source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'])
normal_work=W/frontend.VERSION/'development'/identifier/uuid.uuid4().hex;attempt=frontend.convert(record,job,normal_work);frontend.save(run/'frontend_result.json',frontend.raw(attempt));out=dict(id=identifier,core=core,configuration_policy=config['policy'],normal_frontend_calls=1,frontend_ok=attempt.get('ok'),reason=attempt.get('reason'),detail=attempt.get('detail'),frontend_work=str(normal_work),frontend_result=str(run/'frontend_result.json'))
if attempt.get('ok'):
 candidate=Path(attempt['record_file']);directory=W/'prototype/candidate_quality_ro_v1'/('tikz_node_paint_dev_'+identifier+'_'+uuid.uuid4().hex);qa=quality.verify(identifier,candidate,R,frontend.__file__,directory);frontend.save(run/'full_quality.json',frontend.raw(qa));out.update(candidate_file=str(candidate),quality_report=str(directory/'report.json'),quality_ok=qa.get('ok'),quality_failures=qa.get('failures'),checks=list(qa.get('checks',{})))
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:assert db.execute('select*from jobs where id=?',(identifier,)).fetchone()==job
out.update(canonical_unchanged=True,model_calls=0,goal_complete=False);frontend.save(run/'summary.json',frontend.raw(out));print(json.dumps(out,ensure_ascii=False))
