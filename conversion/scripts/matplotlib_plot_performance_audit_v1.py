"""Read-only companion: phase-specific timing/throughput/failure summaries."""
from pathlib import Path
import argparse,collections,datetime,json,os,sqlite3,time
D=Path('/backup/shaoshitong/img2code_20261029/clean/matplotlib_plot_pipeline_20261102_v1');cache={}
def birth(pid):
 p=Path('/proc',str(pid),'stat')
 if not p.exists():return None
 f=p.read_text().split(') ',1)[1].split();return f[19] if f[0]!='Z' else None
def read(p):
 if not p.exists():return {}
 st=p.stat();key=(str(p),st.st_ino,st.st_mtime_ns,st.st_size)
 if key not in cache:cache[key]=json.loads(p.read_text())
 return cache[key]
def snapshot():
 db=sqlite3.connect('file:'+str(D/'once.sqlite')+'?mode=ro',uri=True);rows=[]
 for phase,status,record in db.execute('select phase,status,record from cases'):
  r=json.loads(record);r['phase']=phase;r['status']=status;rows.append(r)
 db.close();out={}
 for phase in sorted({r['phase'] for r in rows}):
  allrows=[r for r in rows if r['phase']==phase];terminal=[r for r in allrows if r.get('finished_epoch')];eligible=[r for r in terminal if r['status'] not in {'typed_skip_static_source_domain','preserved_development_capture_no_reexecution'}];qualified=[r for r in eligible if r.get('qualified_pair')];stages={}
  for stage in ['data_loading','capture','IR_native','QA','publication']:
   v=sorted(r['stage_seconds'][stage] for r in terminal if stage in r.get('stage_seconds',{}));stages[stage]={'n':len(v),'total_worker_monotonic_seconds':round(sum(v),3),'mean_seconds':round(sum(v)/len(v),3) if v else None,'p90_seconds':round(v[min(len(v)-1,int(.9*len(v)))],3) if v else None}
  span=max((r['finished_epoch'] for r in eligible),default=0)-min((r['started_epoch'] for r in eligible),default=0);last=sorted(eligible,key=lambda r:r['finished_epoch'])[-50:];window=max((r['finished_epoch'] for r in last),default=0)-min((r['started_epoch'] for r in last),default=0);failures=collections.Counter()
  for r in eligible:
   if r.get('qualified_pair'):continue
   if r.get('reason'):
    reason=r['reason'];family=next((f for f in ['unproved_source_paint','empty_path','unsupported_nonrect_plot_clip_family','unproved_source_browser_physical_font','actual_source_font_face_not_captured','complete_vector_scene_resource_bound','source_execution','Failed to apply op','boxplot','int64'] if f in reason),reason.split(':',2)[0]);failures[family]+=1
   q=read(D/'cases'/r['id']/'native_v4/quality/report.json') or read(D/'cases'/r['id']/'native_v3/quality/report.json') or read(D/'cases'/r['id']/'native_v1/quality/report.json')
   for name in ['source_SVG_native_gate','fresh_Agg_native_gate','fresh_SVG_Agg_gate']:
    for f in q.get(name,{}).get('failures',[]):failures[name+':'+f]+=1
   if q and not q.get('source_image_assets_complete',True):failures['source_image_component_provenance_not_closed']+=1
   if q and not q.get('source_font_custom_faces_match',True):failures['source_font_physical_face_not_closed']+=1
   if q and not q.get('complete_recorded_source_export_and_RNG_contract',True):failures['source_export_RNG_or_array_contract_not_closed']+=1
  ratio=len(qualified)/max(1,len(eligible));analysis=[]
  if len(eligible)>=8 and ratio<.25:analysis.append({'cause':'low_full_QA_pass_rate','qualified_fraction':round(ratio,4),'families':failures.most_common(8),'action':'Retain failed captures; stop new dispatch at frozen rolling40 guard and repair the largest generic family. Do not rerun source or loosen fidelity gates.'})
  for stage,v in stages.items():
   if v['n']>=4 and (v['mean_seconds'] or 0)>30:analysis.append({'cause':'slow_measured_stage','stage':stage,'mean_seconds':v['mean_seconds'],'action':'Inspect this measured stage and source family before extending the fixed domain.'})
  out[phase]={'states':dict(collections.Counter(r['status'] for r in allrows)),'eligible_completed_cases':len(eligible),'qualified_cases':len(qualified),'qualified_fraction':round(ratio,4),'phase_span_seconds':round(span,3),'eligible_cases_per_minute':round(len(eligible)/max(1,span)*60,3),'qualified_cases_per_minute':round(len(qualified)/max(1,span)*60,3),'rolling_last50_eligible_cases_per_minute':round(len(last)/max(1,window)*60,3),'stages':stages,'failure_families':failures.most_common(20),'automatic_common_cause_analysis':analysis}
 result={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'schema':'matplotlib_plot_per_phase_performance_v1','phases':out,'read_only_source_and_once_ledger':True,'model_calls':0};file=D/'performance_by_phase_v3.json';tmp=file.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2)+'\n');os.replace(tmp,file);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--controller-pid',type=int);p.add_argument('--controller-birth');a=p.parse_args()
 while True:
  result=snapshot()
  if not a.controller_pid or birth(a.controller_pid)!=a.controller_birth:break
  time.sleep(30)
 print(json.dumps({'phase_counts':{k:{x:v[x] for x in ['eligible_completed_cases','qualified_cases','qualified_fraction','eligible_cases_per_minute']} for k,v in result['phases'].items()},'file':str(D/'performance_by_phase_v3.json')}))
