import argparse,concurrent.futures,json,multiprocessing,os,sqlite3,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
def child(request_path):
 import fixed_batch_case_v1 as inputs
 import round2_canvas_repair_v1 as adapter
 req=json.loads(Path(request_path).read_text());work=Path(req['work']);identifier=req['id']
 d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
 try:job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
 finally:d.close()
 record=json.loads((R/req['record_file']).read_text()) if req.get('record_file') else json.loads(job[9]);source=json.loads(job[4]);manifest=json.loads(job[11]);record=inputs.prepare_originals(record,source,manifest,work)
 result=adapter.repair(record,job,work);summary={'id':identifier,'format':job[2],'adapter_ok':result['ok'],'model_calls':0}
 if not result['ok']:summary.update(reason=result['reason'],detail=result['detail'])
 else:
  out=result['record'];(work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
  summary['evidence']=result['evidence'];summary['candidate_record']=str((work/'candidate_record.json').relative_to(R))
  import auto_quality_batch_v4b as qa
  import clip_canvas_render_v4b as clip
  qa.W=work/'qa';clip.OWNER=str((work/'clip').relative_to(R))
  import html_actual_text_alignment as glyph
  prior=glyph.capture_source;glyph.capture_source=lambda r,w,*a,**kw:prior(r,work/'html'/uuid.uuid4().hex,*a,**kw)
  _,report,qualified,qa_work=qa.verify((identifier,job[5],json.dumps(out,ensure_ascii=False),job[4],job[6]))
  summary.update(quality_state=report['state'],quality_failures=report['failures'],qualified=qualified is not None,qa_report=str((qa_work/'audit.json').relative_to(R)))
 (work/'smoke_result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));return summary
def task(request):
 from initial_conversion_process_v1 import run
 work=Path(request['work']);work.mkdir(parents=True,exist_ok=False);path=work/'request.json';path.write_text(json.dumps(request))
 env={k:os.environ[k] for k in ['PATH','HOME','LANG','LC_ALL'] if k in os.environ};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(R/'env')+':'+str(W/'scripts'))
 iso=run([sys.executable,'-B',str(Path(__file__).resolve()),'--child',str(path)],work,480,env)
 (work/'isolation.json').write_text(json.dumps(iso,indent=2))
 p=work/'smoke_result.json';r=json.loads(p.read_text()) if p.exists() else {'id':request['id'],'runtime_failure':iso}
 return {**r,'process_ok':iso['ok'],'cleanup_complete':iso['cleanup_complete'],'work':str(work.relative_to(R))}
def main():
 p=argparse.ArgumentParser();p.add_argument('--child');a=p.parse_args()
 if a.child:return child(a.child)
 selected=json.loads((W/'round2_canvas_repair_v1/selected.json').read_text())
 # Fixed first case per observed source type, plus second HTML as an independent
 # shape/text class. No iterative easier-case search after these fixed cases.
 chosen=[r for r in selected if r['id'] in [selected[0]['id'],selected[2]['id'],selected[4]['id'],selected[5]['id'],selected[6]['id']]]
 base=W/'round2_canvas_repair_v1/smoke'/uuid.uuid4().hex;base.mkdir(parents=True)
 requests=[{'id':r['id'],'work':str(base/r['id'])} for r in chosen]
 with concurrent.futures.ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:results=list(pool.map(task,requests))
 report={'base':str(base.relative_to(R)),'selected_count':len(chosen),'results':results,'model_calls':0,'all_cleanup_complete':all(r.get('cleanup_complete') for r in results)}
 path=W/'round2_canvas_repair_v1_smoke_report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
