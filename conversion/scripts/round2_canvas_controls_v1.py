import json,os,sqlite3,sys,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
def child(work):
 import round2_canvas_repair_v1 as repair
 import fixed_batch_case_v1 as inputs
 identifier='002937254103449d702e89c8cf7f773e01110de0e74c96e66c6fab75ff18166a'
 d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
 try:job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
 finally:d.close()
 record=inputs.prepare_originals(json.loads(job[9]),json.loads(job[4]),json.loads(job[11]),work)
 negative=repair.repair({**record,'source_code_sha256':'0'*64},job,work)
 assert not negative['ok'] and 'source_hash_mismatch' in negative['detail']
 control=repair.repair(record,job,work)
 assert not control['ok'] and 'No current native overflow or missing page metadata' not in control['detail']
 assert 'no_current_overflow_or_missing_page_metadata' in control['detail'],control
 import auto_quality_batch_v4b as qa
 import clip_canvas_render_v4b as clip
 qa.W=work/'qa';clip.OWNER=str((work/'clip').relative_to(R))
 _,report,out,qwork=qa.verify((identifier,job[5],json.dumps(record,ensure_ascii=False),job[4],job[6]))
 assert report['state']=='qualified' and out is not None,report['failures']
 result={'id':identifier,'original_success_control_qualified':True,'no_unneeded_canvas_candidate':True,'source_hash_negative_rejected':True,'negative':negative,'adapter_control':control,'qa_report':str((qwork/'audit.json').relative_to(R)),'model_calls':0}
 (work/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
 if len(sys.argv)>1:child(Path(sys.argv[1]))
 else:
  from initial_conversion_process_v1 import run
  work=W/'round2_canvas_repair_v1/controls'/uuid.uuid4().hex;work.mkdir(parents=True)
  env={k:os.environ[k] for k in ['PATH','HOME','LANG'] if k in os.environ};env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(R/'env')+':'+str(W/'scripts'))
  iso=run([sys.executable,'-B',str(Path(__file__).resolve()),str(work)],work,360,env);(work/'isolation.json').write_text(json.dumps(iso,indent=2))
  result=json.loads((work/'result.json').read_text()) if (work/'result.json').exists() else {'error':iso}
  result.update(process_ok=iso['ok'],cleanup_complete=iso['cleanup_complete'],work=str(work.relative_to(R)))
  (W/'round2_canvas_repair_v1_controls_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
