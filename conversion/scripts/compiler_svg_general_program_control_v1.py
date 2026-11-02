"""One old-seen full conversion through the sealed general SVG controller.
No heldout reservation or canonical job write. Finite, one worker, one attempt.
"""
import json,sys,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_svg_general_iteration_program_v1 as program
import compiler_svg_general_iteration_batch_v1 as batch
from compiler_types_program_v1 import raw,sha,immutable,atomic
POOL=R/'release/compiler_iterations/source_pools/svg_general_scene_v5_guard_20261101_v1'
RUN='svg_general_scene_v5_guard_interface_control_20261101_v1'
ID='439a6bea95761b950a3dafcce60b9aa9b6d9ede89115740df2b48bc2d1e6becc'

def main():
 owner=program.owned(program.PROGRAMS/RUN);owner.mkdir(parents=True,exist_ok=False);freeze=program.template(POOL);compiler,_=program.case.bindings('svg')
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:source=json.loads(db.execute('select input_record from jobs where id=?',(ID,)).fetchone()[0])
 payload=raw({'seq':1,'id':ID,'source':source,'compiler_unit':compiler.UNITS['svg'],'evaluation_phase':'candidate','cluster':'already_seen_development_interface_control'})
 immutable(owner/'targets.jsonl',payload);freeze['input_sha256']=sha(payload);immutable(owner/'freeze.json',raw(freeze));run=batch.FLOOR/RUN;batch.create(run,owner/'targets.jsonl',owner/'freeze.json','development')
 results=program.run_phase(run,1,900,owner);row=results[ID];out={'schema':'general_svg_actual_fixed_program_interface_control_v1','id':ID,'source_already_seen':True,'unseen_consumed':0,'model_calls':0,'canonical_mutations':0,'run':str(run),'result':row,'passed':row['status']=='qualified' and not row.get('infrastructure_failure'),'freeze':program.asset(owner/'freeze.json')};atomic(owner/'report.json',out);print(json.dumps({k:v for k,v in out.items() if k!='result'}),flush=True)
 if not out['passed']:raise ValueError('actual_generic_svg_controller_positive_failed')
if __name__=='__main__':main()
