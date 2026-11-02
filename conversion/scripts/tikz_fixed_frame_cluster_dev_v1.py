"""Finite, previously consumed 21-case TikZ coordinate development only."""
import concurrent.futures,io,json,pathlib,sqlite3,subprocess,sys,uuid
R=pathlib.Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
METADATA=R/'conversion/compiler_tikz_v3_metadata100_ro/8d4dacf8783b4b31829f1317d409a31a/report.json'
rows=json.loads(METADATA.read_bytes())['rows'];allowed={r['id']:r['failure_class'] for r in rows if r['failure_class'] in ['relative_screen_offset','padding_paint']}

def one(id,base):
 assert id in allowed
 from PIL import Image
 import compiler_tikz_source_viewport_v1 as c
 from auto_quality_common_v4 import image_quality
 from tikz_pdf_glyph_layout_v1 import validate
 from compiler_tikz_source_viewport_quality_ro_v1 import actual_fonts
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30) as d:job=d.execute('select * from jobs where id=?',(id,)).fetchone()
 result=c.convert({},job,base/id);out={k:v for k,v in result.items() if k not in ['record','source_reproduction']};out.update(id=id,old_failure_class=allowed[id],source_reference_ok=result.get('source_reproduction',{}).get('ok'),independent_full_QA=False)
 if result.get('ok'):
  r=result['record'];xml=c.checked(r[c.FIELD]['files']['candidate_xml']).decode();reference=c.checked(r[c.FIELD]['files']['original_reference']);r,contract=c.registration_record(r,reference,xml,R);info=r['render'];expected=json.loads(c.checked(r[c.FIELD]['files']['source_glyph_positions']));plan=info['export_plan']
  for row in expected.values():
   for ch in row['chars']:ch['x']+=plan['dx'];ch['y']+=plan['dy']
  try:
   out['source_native_glyphs']=validate(expected,info);out['actual_fonts']=actual_fonts(info);out['visual']=image_quality(reference,c.checked(r[c.FIELD]['files']['candidate_png']),r,info['actual_text_positions']);out['producer_all_gates_ok']=out['visual']['ok'];out['export_plan']=plan
  except Exception as e:out.update(producer_all_gates_ok=False,producer_gate_error=str(e))
 (base/(id+'.summary.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2));return out

if __name__=='__main__':
 if '--one' in sys.argv:
  try:one(sys.argv[2],pathlib.Path(sys.argv[3]))
  except Exception as e:print(str(e),file=sys.stderr);raise
 else:
  base=W/'compiler_tikz_source_viewport_v1/development'/('fixed_frame_cluster21_'+uuid.uuid4().hex);base.mkdir(parents=True)
  # The two concurrent complete-QA controls are separately retained; replay
  # the other 19 original consumed C100 cases here. No new IDs are selected.
  ids=sorted(allowed)
  (base/'plan.json').write_text(json.dumps({'allowed_consumed21':allowed,'executing21':ids,'new_heldout':0,'models':0,'independent_full_QA':False},indent=2))
  def run(id):
   p=subprocess.run([sys.executable,__file__,'--one',id,str(base)],capture_output=True,timeout=360)
   (base/(id+'.stderr')).write_bytes(p.stderr);f=base/(id+'.summary.json')
   if f.exists():return json.loads(f.read_bytes())
   out={'id':id,'ok':False,'process_returncode':p.returncode,'error':p.stderr.decode(errors='replace')[-3000:]};f.write_text(json.dumps(out));return out
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   results=list(pool.map(run,ids))
  result={'base':str(base),'count':len(results),'converted':sum(x.get('ok',False) for x in results),'producer_all_gates_ok':sum(x.get('producer_all_gates_ok',False) for x in results),'independent_full_QA':False,'results':results,'models':0,'new_heldout':0};(base/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='results'}),flush=True)
