import json,sys,sqlite3,hashlib,os,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def child(work):
 import round2_source_repair_v1 as adapter
 request=json.loads((work/'request.json').read_text());db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=20)
 job=db.execute('select * from jobs where id=?',(request['id'],)).fetchone();db.close();record=json.loads(job[9])
 if request.get('negative'):record['source_code_sha256']='0'*64
 result=adapter.repair(record,job,work/'repair');r={'id':job[0],'format':job[2],'negative':request.get('negative',False),'adapter':{k:v for k,v in result.items() if k not in ['record','evidence']}}
 if result.get('ok'):
  import auto_quality_batch_v4b as qa,clip_canvas_render_v4b as clip
  candidate=result['record'];qa.W=work/'qa';clip.OWNER=str((work/'clip_evidence').relative_to(R))
  _,report,out,qa_work=qa.verify((job[0],job[5],json.dumps(candidate,ensure_ascii=False),job[4],job[6]))
  r.update(source_coverage=result['evidence'].get('coverage'),complete_source_profile=result['evidence'].get('complete_source_profile'),unchanged_success_control=result['evidence'].get('unchanged_success_control',False),preserved_font_cells=len(result['evidence'].get('preserved_font_cells',[])),new_native_markers=len(result['evidence'].get('new_native_markers',[])),
    quality_state=report['state'],quality_failures=report['failures'],checks={k:report['checks'].get(k) for k in ['source','fonts','visual','render','native_editing']},qualified=out is not None,quality_work=str(qa_work),candidate_record=candidate['code_file'].rsplit('/',1)[0]+'/candidate_record.json')
 db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=20);after=db.execute('select * from jobs where id=?',(request['id'],)).fetchone();db.close();r['canonical_job_unchanged']=job==after;r['model_calls']=0;write(work/'result.json',r)
def main():
 from initial_conversion_process_v1 import run
 base=W/'prototype/round2_source_smoke_v1'/uuid.uuid4().hex;base.mkdir(parents=True)
 script=base/'smoke.py';script.write_text(Path(__file__).read_text());results=[]
 cases=[('a4e33439f3a8730c07b44311192ea147219b2dd94171599fb0b166771f7f6c29',False),('18b42bc74a7f5b426ded51e0f676c5d48c849c33c67b08d66ba59e7b8fe28611',False),('4ab9f2196a4853f3b2caef589358a90e5054bb6d0ce83943dc99bd41a775e7d7',False),('0024c3bf9f2592b288198d245097c25892f150053241fd787535223bd750de63',False),('18b42bc74a7f5b426ded51e0f676c5d48c849c33c67b08d66ba59e7b8fe28611',True)]
 for index,(identifier,negative) in enumerate(cases):
  work=base/str(index);work.mkdir();write(work/'request.json',{'id':identifier,'negative':negative})
  isolation=run([sys.executable,str(script),'--child',str(work)],work,600,{**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONPATH':str(R/'env')+':'+str(W/'scripts')})
  result=json.loads((work/'result.json').read_text()) if (work/'result.json').exists() else {'id':identifier,'missing_result':True}
  result['isolation']={k:isolation.get(k) for k in ['ok','cleanup_complete','deadline_exceeded','returncode']};result['work']=str(work);results.append(result);print(json.dumps({'case':index,'id':identifier,'adapter_ok':result.get('adapter',{}).get('ok'),'qualified':result.get('qualified'),'isolation':result['isolation']},ensure_ascii=False),flush=True)
 report={'base':str(base),'results':results,'model_calls':0};write(W/'round2_source_smoke_v1.json',report);print(json.dumps({'report':str(W/'round2_source_smoke_v1.json'),'cases':len(results)}))
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--child':child(Path(sys.argv[2]))
 else:main()
