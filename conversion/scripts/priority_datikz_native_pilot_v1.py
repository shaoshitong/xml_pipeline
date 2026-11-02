"""Three finite development conversions, with isolated identity DBs and full QA."""
from pathlib import Path
import argparse,collections,concurrent.futures,datetime,hashlib,json,os,sqlite3,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def case(task,run):
 import priority_datikz_source_viewport_v3 as core
 import priority_datikz_source_replay_quality_v4 as quality
 t=time.monotonic();raw_id=task['raw_id'];work=Path(run)/raw_id;work.mkdir();(work/'owner.json').write_bytes(raw(dict(pid=os.getpid(),birth_ticks=Path('/proc',str(os.getpid()),'stat').read_text().rsplit(') ',1)[1].split()[19])))
 config=core.configuration();core_key=sha(raw(config));claim=W/core.VERSION/'normal_once'/core_key/(raw_id+'.json');claim.parent.mkdir(parents=True,exist_ok=True)
 with claim.open('xb')as f:f.write(raw(dict(raw_id=raw_id,source_code_sha256=task['source']['code_sha256'],source_profile=task['source'],work=str(work),core_policy=config['policy'],claim_before_normal=True)))
 with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:canonical=db.execute('select * from jobs where id=?',(raw_id,)).fetchone()
 result=dict(raw_id=raw_id,id=task['source']['pair_sha256'],source_core_policy=config['policy'],claim=asset(claim),normal_calls=1,model_calls=0,goal_complete=False,provider_original_PNG_fidelity_claimed=False)
 try:
  record=dict(id=result['id'],source_record=task['source'],original_source_code=task['code']['file'],original_reference=task['image']['file'])
  native_work=W/core.VERSION/'program_runs'/Path(run).name/raw_id
  attempt=core.convert(record,None,native_work);(work/'frontend_result.json').write_bytes(raw(attempt));result.update(conversion_ok=bool(attempt.get('ok')),reason=attempt.get('reason'),detail=attempt.get('detail'))
  if attempt.get('ok'):
   candidate=Path(attempt['record_file']);before=candidate.read_bytes();database=work/'quality_identity.sqlite'
   with sqlite3.connect(database)as db:
    db.execute('create table jobs(id text primary key,category text,format text,source text,input_record text,state text,route text,attempts integer,updated_at text,output_record text,error text,input_manifest text,worker_pid integer)')
    source=task['source'];manifest=dict(source_code=task['code']['file'],reference_image=task['image']['file']);db.execute('insert into jobs values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(result['id'],'scientific_diagram','tikz',source['source'],json.dumps(source),'quality_review','priority_datikz_native_development',0,datetime.datetime.now(datetime.timezone.utc).isoformat(),None,None,json.dumps(manifest),None))
   qa_dir=W/'prototype/candidate_quality_ro_v1'/('priority_datikz_native_v3_'+uuid.uuid4().hex);qa=quality.verify(result['id'],candidate,R,Path(core.__file__),qa_dir,database=database)
   assert candidate.read_bytes()==before;result.update(candidate=asset(candidate),quality_ok=qa.get('ok'),quality_failures=qa.get('failures'),quality_report=asset(qa_dir/'report.json'),checks=list(qa.get('checks',{})),qualified_not_published=bool(qa.get('ok')))
 except Exception as e:result.update(error_type=type(e).__name__,reason=str(e)[:2800])
 with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:assert db.execute('select * from jobs where id=?',(raw_id,)).fetchone()==canonical
 assert core.configuration()==config;result.update(canonical_unchanged=True,elapsed_seconds=time.monotonic()-t);(work/'summary.json').write_bytes(raw(result));return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();run=a.run.resolve();assert run.is_relative_to(W/'priority_datikz_native_pilot_v1');run.mkdir(parents=True,exist_ok=True)
 import priority_datikz_source_viewport_v3 as core
 from priority_datikz_execution_binding_v1 import executed_plain_text,graph_from_events
 from tikz_execution_graph import parse_events
 parent=W/'priority_datikz_compile_preflight_v3/fbc7cf0db68d445e8f6e48797e91d2d3';summary=json.loads((parent/'summary.json').read_bytes());assert summary['finished'];rows=list(map(json.loads,(parent/'combined_results.jsonl').read_text().splitlines()));candidates=[]
 for row in rows:
  if row['status']!='source_trace_supported':continue
  execution=R/row['execution_report']['file'];assert sha(execution.read_bytes())==row['execution_report']['sha256'];directory=execution.parent;graph=graph_from_events(parse_events((directory/'instrumented/source.iic').read_text()))
  try:
   for node in graph['nodes']:executed_plain_text(node['expanded_label_tex'])
  except Exception:continue
  if len(graph['nodes'])<6 or len(graph['edges'])<5:continue
  candidates.append((len(graph['nodes'])+len(graph['edges']),row,directory))
 candidates.sort(key=lambda x:(-x[0],x[1]['id']));selected=candidates[:3];assert selected,'no_supported_plain_label_development_source'
 targets={r['id']:r for r in json.loads((R/'clean/complexity_curation_20261102T054553Z_v1/priority_sources/priority_datikz_targets39_v1.json').read_bytes())};tasks=[]
 for score,row,directory in selected:
  data=(directory/'baseline/original_source.tex').read_bytes();png=(R/row['source_PNG']['file']).read_bytes();assert sha(data)==row['original_code_sha256']and sha(png)==row['source_PNG']['sha256']
  identifier=sha(raw(dict(profile='DaTikZ_current_pinned_TeXLive2025_Poppler100dpi_source_replay_v3',raw_id=row['id'],code=sha(data),PNG=sha(png))))
  root=R/'clean/datikz_current_runtime_source_replay_inputs_v3'/identifier;root.mkdir(parents=True,exist_ok=False);(root/'original_source.tex').write_bytes(data);(root/'source.png').write_bytes(png)
  source=dict(source=targets[row['id']]['source'],category='scientific_diagram',format='tikz',pair_sha256=identifier,code_sha256=sha(data),image_sha256=sha(png),profile='tikz_current_runtime_source_replay_aligned',source_image_origin='fresh_release_exact_source_private_TeXLive2025_Poppler100dpi',raw_source_pair_id=row['id'],original_provider_code_sha256=row['original_code_sha256'],original_provider_image_sha256=row['original_provider_image_sha256'],original_source_locator=targets[row['id']]['source_locator'],source_execution=row['execution_report'],original_provider_PNG_fidelity_asserted=False)
  (root/'source_record.json').write_bytes(raw(source));tasks.append(dict(raw_id=row['id'],source=source,code=asset(root/'original_source.tex'),image=asset(root/'source.png'),source_selection_score=score))
 (run/'freeze.json').write_bytes(raw(dict(configuration=core.configuration(),producer=asset(Path(__file__)),parent_preflight_summary=asset(parent/'summary.json'),tasks=tasks,development_only=True,automatic_rollout=False)))
 results=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=3)as pool:
  for result in pool.map(case,tasks,[str(run)]*len(tasks)):
   results.append(result);(run/'progress.json').write_bytes(raw(dict(completed=len(results),total=len(tasks),results=results)))
 summary=dict(root=str(run),finished=True,total=len(tasks),results=results,normal_calls=len(tasks),model_calls=0,goal_complete=False,development_only=True,automatic_rollout=False)
 (run/'summary.json').write_bytes(raw(summary));print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
