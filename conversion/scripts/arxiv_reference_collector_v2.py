"""Fixed bounded reference audit worker; no agent/model participates per item."""
from pathlib import Path
import collections,datetime,fcntl,hashlib,json,os,signal,sqlite3,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path[:0]=[str(S),str(R/'env')]
from initial_conversion_process_v1 import run
P=R/'clean/arxiv_research_figures_v1';D=P/'original_PDF_reference_audit_v2';sha=lambda b:hashlib.sha256(b).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(p,data):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(data,ensure_ascii=True,indent=2)+'\n');os.replace(t,p)
def snapshots():
 rows={}
 for name in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
  with sqlite3.connect((P/name/'once.sqlite').as_uri()+'?mode=ro',uri=True) as db:
   for (raw,) in db.execute('select record from pdfs where status=?',('qualified_native_xml_png_pair',)):
    row=json.loads(raw);rows[row['id']]=row
 return rows
def publish(db,policy):
 all_rows=[json.loads(raw) for (raw,) in db.execute('select result from audits where policy=? and result is not null',(policy,))]
 unique={}
 for result in all_rows:
  if result.get('status')!='qualified_registered_original_PDF_visual_profile_v2':continue
  key=sha((result['source_author_XML_sha256']+result['native_PNG_sha256']).encode())
  if key not in unique:
   unique[key]={'id':'arxiv-native-reference-'+key,'quality_profile':'registered_original_PDF_visual_v2',
    'code_file':result['source_author_XML'],'code_sha256':result['source_author_XML_sha256'],
    'image_file':result['native_PNG'],'image_sha256':result['native_PNG_sha256'],
    'source_kind':'author_XML_recovered_by_official_drawio_PDF_import','source_aliases':[],
    'strict_provider_reference_full8_profile':False,'external_models':0,'audit_policy':policy}
  unique[key]['source_aliases'].append({'paper':result['paper'],'source_PDF':result['source_PDF'],
    'source_PDF_sha256':result['source_PDF_sha256'],'audit':result['audit_file']})
 tmp=D/'paired_registered_original_PDF.jsonl.tmp'
 with tmp.open('w') as f:
  for k in sorted(unique):f.write(json.dumps(unique[k],ensure_ascii=True,sort_keys=True)+'\n')
 os.replace(tmp,D/'paired_registered_original_PDF.jsonl')
 status=dict(collections.Counter(r['status'] for r in all_rows));seconds=sum(r.get('seconds',0) for r in all_rows)
 summary={'at_utc':now(),'policy':policy,'source_PDFs_audited':len(all_rows),'unique_registered_pairs':len(unique),
          'states':status,'cumulative_case_seconds':seconds,'cases_per_minute_active':60*len(all_rows)/seconds if seconds else None,
          'pending_reasons':dict(collections.Counter(r.get('reason') or ','.join(r.get('strong_original_reference_raster_gate',{}).get('failures',[])) or r['status'] for r in all_rows if not r['status'].startswith('qualified_'))),
          'normal_generations':0,'official_PDF_import_calls':0,'external_models':0,
          'input_source_recoveries_are_preserved':True,'strict_provider_reference_full8_profile':False}
 atomic(D/'collector_summary.json',summary);return summary
def main():
 D.mkdir(exist_ok=True);lock=(D/'collector.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cfg=json.loads((D/'collector_policy.json').read_text());policy=sha((D/'collector_policy.json').read_bytes())
 for path,digest in cfg['pins'].items():assert sha((R/path).read_bytes())==digest,'Frozen audit code changed: '+path
 db=sqlite3.connect(D/'audits.sqlite');db.execute('pragma journal_mode=WAL')
 db.execute('create table if not exists audits(id text,policy text,status text,request text,result text,primary key(id,policy))');db.commit()
 for ident, in db.execute('select id from audits where policy=? and status=?',(policy,'started')).fetchall():
  result={'id':ident,'status':'pending_prior_audit_interrupted','reason':'Committed prior audit claim preserved; a later audit version may revisit it.','seconds':0}
  db.execute('update audits set status=?,result=? where id=? and policy=?',('pending',json.dumps(result),ident,policy))
 db.commit();stopping=False
 def stop(a,b):
  nonlocal stopping
  stopping=True
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 while not stopping:
  rows=snapshots();processed={x[0] for x in db.execute('select id from audits where policy=?',(policy,))}
  for ident,row in sorted(rows.items()):
   if stopping:break
   if ident in processed:continue
   folder=D/'audits'/policy[:16]/ident;folder.mkdir(parents=True,exist_ok=True)
   request={'id':ident,'policy':policy,'source_PDF_sha256':ident,'author_XML_sha256':row['author_xml_sha256'],
            'native_PNG_sha256':row['image_sha256'],'started_at_utc':now(),'model_calls':0,'normal_generations':0}
   db.execute('insert into audits values(?,?,?,?,?)',(ident,policy,'started',json.dumps(request),None));db.commit();atomic(folder/'request.json',request)
   t=time.perf_counter();work=R/'conversion/arxiv_reference_audit_processes_v2'/policy[:16]/ident
   proc=run(['/home/shaoshitong/anaconda3/bin/python','-u',str(S/'arxiv_reference_case_v2.py'),ident,str(folder)],work,180,
      env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH=str(R/'env')))
   if proc.get('ok') and proc.get('cleanup_complete') and (folder/'audit.json').exists():result=json.loads((folder/'audit.json').read_text())
   else:result={'id':ident,'status':'pending_audit_process_failure','reason':'bounded_case_failed_or_timed_out','seconds':time.perf_counter()-t}
   result.update(audit_file=str((folder/'audit.json').relative_to(R)),bounded_process_wall_seconds=time.perf_counter()-t,
                 bounded_process_cleanup_complete=bool(proc.get('cleanup_complete')),audit_policy=policy)
   atomic(folder/'result.json',result)
   status='qualified' if result['status'].startswith('qualified_') else 'pending'
   db.execute('update audits set status=?,result=? where id=? and policy=?',(status,json.dumps(result,ensure_ascii=True),ident,policy));db.commit()
   report=publish(db,policy);print(json.dumps({'at_utc':now(),'id':ident,'status':result['status'],
       'case_wall_seconds':result['bounded_process_wall_seconds'],'audited':report['source_PDFs_audited'],'qualified_unique':report['unique_registered_pairs']}),flush=True)
  publish(db,policy)
  for _ in range(60):
   if stopping:break
   time.sleep(1)
 db.close()
if __name__=='__main__':main()
