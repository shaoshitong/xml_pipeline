"""One consumed source through the exact case API; no program launch/reservation."""
import json,sqlite3,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))

def main():
 import compiler_plantuml_iteration_case_v1 as case
 import fixed_batch_pipeline_v1 as base
 identifier='741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd';compiler,quality=case.bindings('plantuml');pins={**base.pins(),**compiler.configuration()['pins']}
 for module in (case,quality):pins[str(Path(module.__file__).resolve())]=case.sha(Path(module.__file__).read_bytes())
 pins[str(Path(__file__).resolve())]=case.sha(Path(__file__).read_bytes());owner=W/'compiler_iterations'/('plantuml_v8_direct_case_interface_'+uuid.uuid4().hex);owner.mkdir(parents=True)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:source=json.loads(db.execute('select input_record from jobs where id=?',(identifier,)).fetchone()[0])
 request={'id':identifier,'seq':1,'compiler_unit':compiler.UNITS['plantuml'],'cluster':'already_consumed_development_interface','source':source,'mode':'development','evaluation_phase':'candidate','work':str(owner/'case'),'pins':pins};rp=owner/'request.json';rp.write_bytes(case.raw(request));print(json.dumps({'owner':str(owner),'id':identifier,'program_launched':False,'validation_reserved':False}),flush=True);result=case.run(rp);report={'schema':'plantuml_exact_case_interface_control_v1','id':identifier,'passed':result['status']=='qualified' and not result.get('infrastructure_failure'),'result':result,'model_calls':0,'new_heldout_consumed':0,'program_launched':False,'validation_reserved':False};(owner/'report.json').write_bytes(case.raw(report));print(json.dumps({'report':str(owner/'report.json'),'passed':report['passed'],'status':result['status'],'reason':result.get('reason'),'detail':result.get('detail')}),flush=True)
 if not report['passed']:raise ValueError('exact_plantuml_case_interface_failed')

if __name__=='__main__':main()
