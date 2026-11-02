"""Paired frozen evaluation. Never tunes or changes the production repair code."""
import json,sqlite3,sys,traceback
from pathlib import Path
import round2_case_v1 as frozen
from fixed_batch_case_v1 import R,W,raw,sha,save,prepare_originals
def run(path):
 request=json.loads(Path(path).read_bytes());work=Path(request['work']).resolve();identifier=request['id'];phase=request['evaluation_phase']
 result={'id':identifier,'seq':request['seq'],'evaluation_phase':phase,'model_calls':0}
 try:
  if not work.is_relative_to((W/'round2_fixed_v1').resolve()):raise ValueError('heldout_work_outside_owned_root')
  for p,h in request['pins'].items():
   if sha(Path(p).read_bytes())!=h:raise RuntimeError('frozen_evaluation_implementation_changed:'+p)
  if phase=='C':
   # The unchanged mass-program case receives the original first-round error,
   # not phase-B output. B cannot steer or tune its deterministic repair plan.
   result=frozen.run(path);result['evaluation_phase']='C'
  else:
   d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
   try:job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
   finally:d.close()
   source=json.loads(job[4]);expected=request['source']
   if (source['pair_sha256'],source['format'],source['code_sha256'],source['image_sha256'])!=(identifier,expected['format'],expected['code_sha256'],expected['image_sha256']):raise ValueError('heldout_original_source_changed')
   record=prepare_originals(frozen.candidate(job,request['first_result']),source,json.loads(job[11]) if job[11] else None,work)
   report,out,directory=frozen.verify(record,job,work,'untouched_B')
   result.update(full_qualified=bool(out and report.get('state')=='qualified'),quality_report=str((directory/'audit.json').relative_to(R)),failures=report.get('failures'),exception_type=report.get('exception_type'),checks_reached=list(report.get('checks',{})),policy=report.get('policy'),candidate_unchanged=True)
  save(work/'evaluation_result.json',raw(result))
 except Exception as e:
  result.update(evaluation_error=type(e).__name__,detail=str(e)[:5000]);save(work/'evaluation_traceback.txt',traceback.format_exc().encode());save(work/'evaluation_result.json',raw(result))
 return result
if __name__=='__main__':run(sys.argv[1])
