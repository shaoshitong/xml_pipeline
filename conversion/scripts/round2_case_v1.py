"""One original ID, bounded deterministic repairs followed by unchanged full QA."""
import importlib,json,sqlite3,traceback,uuid
from pathlib import Path
from fixed_batch_case_v1 import R,W,sha,save,raw,checked,prepare_originals
MODULES={'source':'round2_source_repair_v1','html':'round2_html_repair_v1','canvas':'round2_canvas_repair_v1','font':'round2_font_repair_v1'}
def route(result,fmt):
 if result.get('phase') in ('conversion','input','timeout'):return []
 text=str(result.get('detail') or result.get('quality_failures') or '')
 actions=[]
 if fmt in ('svg','python','plantuml') and any(x in text for x in ['source_coverage_failure','source_arrow','source_connector','invalid_editable_structure','source_object','source_paint_style']):actions.append('source')
 if fmt=='html' and any(x in text for x in ['poster_object_coverage_mismatch','source_paint_object_missing','overlapping_source_css_paint_order_changed','css_stacking_order','word_spans_multiple_lines']):actions.append('html')
 if any(x in text for x in ['Native content requires full tight canvas','Canvas registration needs an independently proven current delta','unregistered_reference_canvas_difference','native_outside_reference_canvas_requires_registered_recovery','unsupported_native_canvas']):actions.append('canvas')
 if 'actual_font_portability_requires_embedding' in text:actions.append('font')
 return actions
def candidate(job,first):
 expected=(first.get('candidate_code_sha256'),first.get('candidate_image_sha256'))
 if job[9]:
  r=json.loads(job[9])
  if expected[0] and (r['code_sha256'],r['image_sha256'])!=expected:raise ValueError('first_candidate_revision_changed')
  return r
 paths=[]
 if first.get('evidence_directory'):paths.append(R/first['evidence_directory']/'native/candidate_record.json')
 paths.extend((R/'clean/fixed_batch_candidates_v1'/job[0][:2]/job[0]).glob('*/conversion.json'))
 for p in paths:
  if p.exists():
   r=json.loads(p.read_bytes())
   if r.get('id')==job[0] and expected[0] and (r.get('code_sha256'),r.get('image_sha256'))==expected:return r
 raise ValueError('no_complete_first_round_candidate_for_repair')
def verify(record,job,work,index):
 import auto_quality_batch_v4b as qa
 import clip_canvas_render_v4b as clip
 import html_actual_text_alignment as glyph
 import round2_font_canvas_registration_v1 as registration
 config=registration.configuration()
 if not hasattr(qa,'_round2_frozen_policy'):qa._round2_frozen_policy=qa.POLICY
 bindings={'frozen_qa_policy':qa._round2_frozen_policy,'registration_policy':config['policy'],'registration_pins':config['pins'],'case_sha256':sha(Path(__file__).read_bytes())}
 qa.registration_record=registration.registration_record;qa.POLICY='round2_full_source_native_quality_v1:'+sha(raw(bindings))[:20]
 qa.W=work/('qa_'+str(index));clip.OWNER=str((work/('clip_'+str(index))).relative_to(R))
 if not hasattr(glyph,'_round2_original_capture'):glyph._round2_original_capture=glyph.capture_source
 glyph.capture_source=lambda record,ignored,*a,**kw:glyph._round2_original_capture(record,work/'html_capture'/uuid.uuid4().hex,*a,**kw)
 _,report,out,directory=qa.verify((job[0],job[5],json.dumps(record,ensure_ascii=False),job[4],job[6]))
 report['round2_quality_bindings']=bindings;save(Path(directory)/'audit.json',raw(report))
 return report,out,Path(directory)
def run(request_path):
 request=json.loads(Path(request_path).read_bytes());work=Path(request['work']).resolve();identifier=request['id'];first=request['first_result'];history=[]
 result={'id':identifier,'seq':request['seq'],'source_code_sha256':request['source']['code_sha256'],'source_image_sha256':request['source']['image_sha256'],'model_calls':0,'round':2,'repair_steps':history,'first_round_reason':first.get('reason')}
 try:
  if not work.is_relative_to((W/'round2_fixed_v1').resolve()):raise ValueError('round2_case_outside_owned_work')
  for path,h in request['pins'].items():
   if sha(Path(path).read_bytes())!=h:raise RuntimeError('infrastructure_pinned_implementation_changed:'+path)
  d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
  try:job=d.execute('select * from jobs where id=?',(identifier,)).fetchone()
  finally:d.close()
  if not job:raise ValueError('missing_original_job')
  source=json.loads(job[4]);s=request['source']
  if (source['pair_sha256'],source['format'],source['category'],source['code_sha256'],source['image_sha256'])!=(identifier,s['format'],s['category'],s['code_sha256'],s['image_sha256']):raise ValueError('original_source_identity_mismatch')
  record=prepare_originals(candidate(job,first),source,json.loads(job[11]) if job[11] else None,work)
  current=first;used=set();out=None;report={};directory=None
  if request.get('control'):
   report,out,directory=verify(record,job,work,0)
  else:
   for index in range(4):
    options=[a for a in route(current,job[2]) if a not in used]
    if not options:break
    action=options[0];used.add(action);step=work/(str(index)+'_'+action);step.mkdir(parents=True)
    module=importlib.import_module(MODULES[action]);attempt=module.repair(record,job,step)
    history.append({'action':action,'ok':attempt.get('ok') is True,'reason':attempt.get('reason'),'detail':attempt.get('detail') or attempt.get('error'),'evidence':str(step.relative_to(R))})
    if not attempt.get('ok'):break
    record=attempt['record'];save(step/'candidate_record.json',raw(record))
    report,out,directory=verify(record,job,work,index)
    if out:break
    if report.get('exception_type') in ('ImportError','ModuleNotFoundError'):raise RuntimeError('infrastructure_qa_import_failure:'+str(report.get('failures')))
    current={'status':'abandoned','detail':report.get('failures',[])}
  if out and report.get('state')=='qualified':
   png=(directory/'fresh.png').read_bytes()
   if sha(png)!=out['image_sha256']:raise ValueError('round2_fresh_png_hash_mismatch')
   save(R/out['image_file'],png)
   from qualified_index_v4 import manifest_row,require_source
   require_source(out,source);manifest,_=manifest_row(out,R)
   result.update(status='qualified',reason='round2_repair_passed_full_qa',manifest=manifest,quality_report=str((directory/'audit.json').relative_to(R)))
  else:result.update(status='abandoned',reason='round2_repair_failed_or_uncovered',detail=report.get('failures') or (history[-1] if history else 'no_eligible_repair'),quality_report=str((directory/'audit.json').relative_to(R)) if directory else None)
  d=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
  try:
   if d.execute('select * from jobs where id=?',(identifier,)).fetchone()!=job:raise RuntimeError('infrastructure_original_job_changed')
  finally:d.close()
 except Exception as e:
  result.update(status='abandoned',reason='round2_case_failed',error_type=type(e).__name__,detail=str(e)[:8000],infrastructure_failure=str(e).startswith('infrastructure_') or isinstance(e,(ImportError,ModuleNotFoundError)))
  save(work/'traceback.txt',traceback.format_exc().encode())
 save(work/'result.json',raw(result));return result
if __name__=='__main__':
 import sys
 run(sys.argv[1])
