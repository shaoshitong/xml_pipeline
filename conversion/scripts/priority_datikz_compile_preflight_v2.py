"""Finite source-only compilation census of all 39 selected DaTikZ diagrams.

Preserves provider PNG provenance; no native conversion or quality claim.
Reuses matching complete source executions after hashing every opened input.
"""
from pathlib import Path
import argparse,collections,concurrent.futures,datetime,hashlib,json,os,sqlite3,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def atomic(p,v):
 q=p.with_suffix(p.suffix+'.tmp');q.write_bytes(raw(v));os.replace(q,p)
def verified_source(row):
 locator=row['source_locator'];data=b''
 if locator.get('resolved_source_code'):
  path=(R/locator['resolved_source_code']).resolve();assert path.is_relative_to(R);data=path.read_bytes()
 if sha(data)!=row['code_sha256_manifest']:
  import pyarrow.parquet as pq
  p=R/locator['clean_file'];index=int(locator['clean_row']);start=0;pf=pq.ParquetFile(p)
  for group in range(pf.num_row_groups):
   n=pf.metadata.row_group(group).num_rows
   if start<=index<start+n:
    value=pf.read_row_group(group,columns=[locator['code_key']],use_threads=False)[locator['code_key']][index-start].as_py();data=value.encode()if isinstance(value,str)else bytes(value);break
   start+=n
 assert sha(data)==row['code_sha256_manifest'],'original_DaTikZ_source_hash_mismatch'
 assert len(data)<=250000,'source_resource_bound'
 return data
def reusable(config):
 out={}
 for version in ['priority_datikz_source_viewport_v1','priority_datikz_source_viewport_v2']:
  for p in (W/version/'program_runs').glob('*/*/source/execution/execution_graph.json'):
   d=json.loads(p.read_bytes())
   if d.get('configuration')!=config or set(d.get('runs',{}))!={'baseline','instrumented'}:continue
   if not all(x['returncode']==0 for x in d['runs'].values())or not all(x.get('pixel_identical')for x in d.get('instrumentation_pdf_pixel_equivalence',[])):continue
   valid=True
   for mode,run in d['runs'].items():
    if sha((p.parent/mode/'source.pdf').read_bytes())!=run['pdf_sha256']:valid=False;break
    for ref in run['opened_inputs'].values():
     if sha(Path(ref['file']).read_bytes())!=ref['sha256']:valid=False;break
   if valid:out[d['source_sha256']]=p
 return out
def one(row,run,configuration,previous):
 from priority_datikz_tex_execution_v3 import compile_execution_graph
 from priority_datikz_execution_binding_v1 import graph_from_events
 from tikz_execution_graph import parse_events
 t=time.monotonic();work=Path(run)/row['id'];work.mkdir(exist_ok=False);atomic(work/'owner.json',dict(pid=os.getpid(),birth_ticks=Path('/proc',str(os.getpid()),'stat').read_text().rsplit(') ',1)[1].split()[19]))
 result=dict(id=row['id'],source=row['source'],original_code_sha256=row['code_sha256_manifest'],original_provider_image_sha256=row['image_sha256_manifest'],provider_original_PNG_fidelity_claimed=False,new_native_conversions=0,new_QA_calls=0,model_calls=0)
 try:
  data=verified_source(row);(work/'original_source.tex').write_bytes(data)
  if previous:
   p=Path(previous);execution=json.loads(p.read_bytes());result['reused_hash_verified_execution']=asset(p);execution_dir=p.parent;result['new_source_compilations']=0
  else:
   execution_dir=work/'execution';execution=compile_execution_graph(data,execution_dir,100);assert execution['configuration']==configuration;result['new_source_compilations']=len(execution.get('runs',{}))
  result['execution_report']=asset(execution_dir/'execution_graph.json')
  compiled=set(execution.get('runs',{}))=={'baseline','instrumented'}and all(r['returncode']==0 for r in execution['runs'].values())
  result['baseline_and_instrumented_compiled']=compiled
  if not compiled:
   result.update(status='source_compilation_failed',reason=execution.get('error','source_compilation_failed'))
  else:
   assert execution.get('instrumentation_pdf_pixel_equivalence')and all(r['pixel_identical']for r in execution['instrumentation_pdf_pixel_equivalence'])
   events=parse_events((execution_dir/'instrumented/source.iic').read_text());graph=graph_from_events(events)
   result.update(status='source_trace_supported'if graph['ok']else'source_trace_unsupported',instrumentation_pixel_identical=True,trace_failures=graph.get('failures',[]),source_PDF=asset(execution_dir/'baseline/source.pdf'),source_PNG=asset(execution_dir/'baseline/actual_Poppler100dpi/source.png'))
   (work/'typed_execution_graph.json').write_bytes(raw(graph))
 except Exception as e:result.update(status='preflight_error',reason=type(e).__name__+':'+str(e)[:3500])
 result['elapsed_seconds']=time.monotonic()-t;atomic(work/'result.json',result);return result
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,required=True);a=parser.parse_args();run=a.run.resolve();assert run.is_relative_to(W/'priority_datikz_compile_preflight_v2');run.mkdir(parents=True,exist_ok=True)
 from priority_datikz_tex_execution_v3 import runtime_configuration
 config=runtime_configuration();input_path=R/'clean/complexity_curation_20261102T054553Z_v1/priority_sources/priority_datikz_targets39_v1.json';all_rows=json.loads(input_path.read_bytes());assert len(all_rows)==39 and len({r['id']for r in all_rows})==39
 parent=W/'priority_datikz_compile_preflight_v1/ba8833b8af794afaaa42ca82c2cbdae1'
 assert json.loads((parent/'summary.json').read_bytes())['finished']
 with sqlite3.connect((parent/'status.sqlite').as_uri()+'?mode=ro',uri=True)as olddb:prior={r['id']:r for r in [json.loads(x[0])for x in olddb.execute('select result from samples')]}
 selected={ident for ident,r in prior.items()if r['status']=='preflight_error' or r['status']=='source_compilation_failed'and'failed:baseline:'in r.get('reason','')and any(p in r.get('reason','')for p in ['tikzmark','stringstrings','pgfopts','environ'])}
 rows=[r for r in all_rows if r['id']in selected];assert len(rows)==11
 for p,digest in config['pins'].items():assert sha(Path(p).read_bytes())==digest
 cache=reusable(config);db=sqlite3.connect(run/'status.sqlite');db.execute('create table samples(id text primary key,status text,attempts integer check(attempts=1),result text)');db.executemany('insert into samples values(?,?,1,null)',[(r['id'],'queued')for r in rows]);db.commit();atomic(run/'freeze.json',dict(input=asset(input_path),configuration=config,producer=asset(Path(__file__)),workers=4,source_only=True));started=time.monotonic();results=[];pending=iter(rows)
 def submit(pool,row):
  db.execute('update samples set status=? where id=?',('running',row['id']));db.commit();return pool.submit(one,row,str(run),config,str(cache[row['code_sha256_manifest']])if row['code_sha256_manifest']in cache else None)
 with concurrent.futures.ProcessPoolExecutor(max_workers=4)as pool:
  futures={submit(pool,r):r['id']for r in [next(pending)for _ in range(4)]}
  while futures:
   done,_=concurrent.futures.wait(futures,return_when=concurrent.futures.FIRST_COMPLETED)
   for f in done:
    ident=futures.pop(f)
    try:result=f.result()
    except Exception as e:result=dict(id=ident,status='preflight_error',reason=type(e).__name__+':'+str(e))
    results.append(result);db.execute('update samples set status=?,result=? where id=?',(result['status'],json.dumps(result),ident));db.commit();atomic(run/'progress.json',dict(completed=len(results),total=len(rows),counts=dict(collections.Counter(r['status']for r in results)),elapsed_seconds=time.monotonic()-started))
    try:row=next(pending)
    except StopIteration:continue
    futures[submit(pool,row)]=row['id']
 assert len(results)==len(rows);assert all(sha(Path(p).read_bytes())==digest for p,digest in config['pins'].items())
 summary=dict(root=str(run),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),completed=len(rows),total=len(rows),finished=True,counts=dict(collections.Counter(r['status']for r in results)),elapsed_seconds=time.monotonic()-started,reused_executions=sum('reused_hash_verified_execution'in r for r in results),new_source_compilations=sum(r.get('new_source_compilations',0)for r in results),new_native_conversions=0,new_QA_calls=0,model_calls=0,provider_original_PNG_fidelity_claimed=False,old_runtimes_unchanged=True,goal_complete=False)
 combined={**prior,**{r['id']:r for r in results}};summary.update(parent_summary=asset(parent/'summary.json'),preserved_parent_results=39-len(rows),combined_total=len(combined),combined_counts=dict(collections.Counter(r['status']for r in combined.values())))
 (run/'combined_results.jsonl').write_text(''.join(json.dumps(combined[k],sort_keys=True)+'\n'for k in sorted(combined)));atomic(run/'summary.json',summary);db.close();print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
