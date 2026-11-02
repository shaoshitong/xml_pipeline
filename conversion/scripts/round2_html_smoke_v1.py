import argparse,concurrent.futures,json,multiprocessing,os,sqlite3,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
CONTROL='002937254103449d702e89c8cf7f773e01110de0e74c96e66c6fab75ff18166a'
def child(path):
 import fixed_batch_case_v1 as inputs
 import round2_html_repair_v1 as adapter
 req=json.loads(Path(path).read_text());work=Path(req['work']);identifier=req['id']
 d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
 try:job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
 finally:d.close()
 record=inputs.prepare_originals(json.loads(job[9]),json.loads(job[4]),json.loads(job[11]),work)
 negative=adapter.repair({**record,'source_code_sha256':'0'*64},job,work)
 assert not negative['ok'] and 'identity_mismatch' in negative['detail']
 converted=adapter.repair(record,job,work);summary={'id':identifier,'adapter_ok':converted['ok'],'negative_source_hash_rejected':True,'control':identifier==CONTROL,'model_calls':0}
 if not converted['ok']:
  summary.update(reason=converted['reason'],detail=converted['detail'])
  if identifier!=CONTROL:
   (work/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));return summary
  assert 'no_change_required' in converted['detail'],converted
  out=record
 else:
  out=converted['record'];proof=converted['evidence'];summary.update(added_fragments=len(proof['new_editable_text_fragments']),paint_order_changed=proof['paint_order_changed'],source_coverage=proof['source_coverage'],paint_coverage=proof['actual_browser_paint_order'],all_original_payloads_unchanged=proof['all_existing_object_payloads_unchanged'])
  (work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));summary['candidate_record']=str((work/'candidate_record.json').relative_to(R))
 import auto_quality_batch_v4b as qa
 import clip_canvas_render_v4b as clip
 qa.W=work/'qa';clip.OWNER=str((work/'clip').relative_to(R))
 import html_actual_text_alignment as glyph
 previous=glyph.capture_source;glyph.capture_source=lambda r,w,*a,**kw:previous(r,work/'html_capture'/uuid.uuid4().hex,*a,**kw)
 _,report,qualified,qwork=qa.verify((identifier,job[5],json.dumps(out,ensure_ascii=False),job[4],job[6]))
 summary.update(quality_state=report['state'],quality_failures=report['failures'],qualified=qualified is not None,qa_report=str((qwork/'audit.json').relative_to(R)))
 if identifier==CONTROL:assert qualified is not None,report['failures']
 (work/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));return summary
def task(request):
 from initial_conversion_process_v1 import run
 work=Path(request['work']);work.mkdir(parents=True);path=work/'request.json';path.write_text(json.dumps(request))
 env={k:os.environ[k] for k in ['PATH','HOME','LANG'] if k in os.environ};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(R/'env')+':'+str(W/'scripts'))
 iso=run([sys.executable,'-B',str(Path(__file__).resolve()),'--child',str(path)],work,480,env);(work/'isolation.json').write_text(json.dumps(iso,indent=2))
 result=json.loads((work/'result.json').read_text()) if (work/'result.json').exists() else {'id':request['id'],'runtime_failure':iso}
 return {**result,'process_ok':iso['ok'],'cleanup_complete':iso['cleanup_complete'],'work':str(work.relative_to(R))}
def main():
 p=argparse.ArgumentParser();p.add_argument('--child');a=p.parse_args()
 if a.child:return child(a.child)
 rows=json.loads((W/'round2_html_selected_v1.json').read_text());base=W/'round2_html_smoke_v1'/uuid.uuid4().hex;base.mkdir(parents=True)
 requests=[{'id':r['id'],'work':str(base/r['id'])} for r in rows]+[{'id':CONTROL,'work':str(base/CONTROL)}]
 with concurrent.futures.ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:results=list(pool.map(task,requests))
 report={'base':str(base.relative_to(R)),'results':results,'model_calls':0,'all_cleanup_complete':all(r['cleanup_complete'] for r in results)}
 (W/'round2_html_smoke_v1_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
