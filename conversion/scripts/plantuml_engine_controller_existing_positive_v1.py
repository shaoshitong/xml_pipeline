"""Exact frozen controller/child handshake using existing positive, no conversion."""
import json,sqlite3,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
def main(pool):
 import compiler_plantuml_engine_iteration_program_v1 as p
 import compiler_plantuml_engine_iteration_batch_v1 as controller
 import compiler_plantuml_engine_once_v1 as once
 compiler,_=p.case.bindings('plantuml');freeze=p.template(Path(pool));controls=p.control_bundle(compiler);positive=next(r for r in controls['positive_cases']if r['id']=='05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798');identifier=positive['id'];owner=W/'plantuml_engine_controller_existing_positive_v1'/uuid.uuid4().hex;owner.mkdir(parents=True);name='plantuml_engine_existing_positive_'+uuid.uuid4().hex;run=controller.FLOOR/name
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:source=json.loads(db.execute('select input_record from jobs where id=?',(identifier,)).fetchone()[0])
 row={'id':identifier,'seq':1,'source':source,'compiler_unit':compiler.UNITS['plantuml'],'cluster':'existing_consumed_positive_exact_controller','evaluation_phase':'control_positive','existing_development_candidate':positive['candidate']['file']};payload=p.raw(row)+b'\n';manifest=owner/'input.jsonl';manifest.write_bytes(payload);freeze={**freeze,'input_sha256':p.sha(payload)};(owner/'freeze.json').write_bytes(p.raw(freeze));controller.create(run,manifest,owner/'freeze.json','development');before=once.claims(compiler);result=p.run_phase(run,1,900,owner)[identifier];after=once.claims(compiler);snapshot=controller.snapshot(run);work=W/'compiler_iterations'/run.name/('000001_'+identifier);passed=result['status']=='qualified'and not result.get('infrastructure_failure')and before==after and not(work/'frontend_result.json').exists();report={'schema':'official_PlantUML_existing_positive_exact_controller_preflight_v1','passed':passed,'run':str(run),'result':result,'snapshot':snapshot,'all_claims_unchanged':before==after,'no_normal_frontend_call':not(work/'frontend_result.json').exists(),'source_pool':str(pool),'source_pool_summary_sha256':p.sha((Path(pool)/'summary.json').read_bytes()),'new_unseen':0,'model_calls':0,'reserved':False};report['evidence_file']=str(owner/'report.json');(owner/'report.json').write_bytes(p.raw(report));print(json.dumps({'report':str(owner/'report.json'),'passed':passed,'status':result['status'],'reason':result.get('reason'),'no_normal_frontend_call':report['no_normal_frontend_call']}),flush=True)
 if not passed:raise RuntimeError('existing_positive_controller_preflight_failed')
 return report
if __name__=='__main__':main(sys.argv[1])
