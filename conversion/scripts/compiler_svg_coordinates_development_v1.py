"""Finite already-consumed SVG coordinate controls, no heldout or bulk dispatch."""
import json,sqlite3,sys,uuid,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
IDS=('5b91ae464a6f684b1e0cf5726ffb601db15b63953b7db1cb03ddb0f91017c1fc','629f7997cb820bab07e714011a0a82122bb0847339f405e2d13d90fde1eab433','2431df4c71d41182b3ba570cd45e3c22ff1e7c644b1d63d34b93d0225e349220')

def main():
 import compiler_svg_general_guard_v2 as frontend
 from compiler_svg_scene_quality_ro_v6 import verify
 parent=W/'compiler_svg_scene_frontend_v6/development'/uuid.uuid4().hex;parent.mkdir(parents=True)
 configuration=frontend.configuration();results=[];db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);columns=[r[1] for r in db.execute('pragma table_info(jobs)')]
 print(json.dumps({'development':str(parent),'ids':IDS,'unseen_consumed':0}),flush=True)
 for identifier in IDS:
  snapshot=db.execute('select * from jobs where id=?',(identifier,)).fetchone();job=dict(zip(columns,snapshot));record=json.loads(job['output_record']);work=parent/identifier;attempt=frontend.convert(record,job,work);row={'id':identifier,'converted':attempt['ok'],'reason':attempt.get('reason'),'detail':attempt.get('detail'),'stage':attempt.get('stage'),'full_quality':None,'model_calls':0}
  if attempt['ok']:
   row['record_file']=attempt['record_file'];quality=verify(identifier,attempt['record_file'],R,Path(frontend.__file__),W/'prototype/candidate_quality_ro_v1'/('svg_coordinates_'+identifier[:8]+'_'+uuid.uuid4().hex));row['full_quality']={'ok':quality['ok'],'failures':quality['failures'],'report':quality['evidence_file'],'checks':{k:v.get('ok',True) for k,v in quality['checks'].items()}}
  row['canonical_unchanged']=db.execute('select * from jobs where id=?',(identifier,)).fetchone()==snapshot;results.append(row);(parent/'progress.json').write_bytes(frontend.raw({'results':results}));print(json.dumps(row),flush=True)
 db.close();report={'schema':'svg_coordinates_consumed_development_v1','directory':str(parent),'configuration_unchanged':frontend.configuration()==configuration,'results':results,'unseen_consumed':0,'model_calls':0,'canonical_mutations':0,'no_heldout_or_mass_dispatch':True};(parent/'report.json').write_bytes(frontend.raw(report));print(json.dumps({'report':str(parent/'report.json'),'results':results}),flush=True)

if __name__=='__main__':main()
