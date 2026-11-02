"""Four download threads + four deterministic native-import workers on HKUST.

Only acquisition/orchestration changes. PDF import, author XML, rendering and
native-edit validation use the pinned, previously verified official importer.
"""
from pathlib import Path
import collections, concurrent.futures as cf, datetime, fcntl, hashlib, json, os
import queue, re, sqlite3, subprocess, sys, threading, time, urllib.parse, uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
sys.path[:0]=[str(S),str(R/'env'),str(R/'evaluation/assets/pdf_inventory_python_v1')]
import requests
import arxiv_sourceonly_bulk_200_v1_1 as native
import arxiv_sourceonly_expansion_v2 as inventory
import fitz
P=R/'clean/arxiv_research_figures_v1';CONTROL=P/'transport_performance_v3'
PROXY='socks5h://127.0.0.1:60453';BUDGET=512*1024**3
sha=lambda b:hashlib.sha256(b).hexdigest();now=native.now
local=threading.local();real_run=subprocess.run;OriginalRenderer=native.OfficialXmlPng

def node_timed(args,*a,**kw):
 t=time.perf_counter()
 try:return real_run(args,*a,**kw)
 finally:
  owner=getattr(local,'owner',None)
  if owner and isinstance(args,list) and args and str(args[0]).endswith('/node'):
   owner.metric('official_PDF_import',time.perf_counter()-t)
subprocess.run=node_timed

class TimedRenderer(OriginalRenderer):
 def __init__(self):
  t=time.perf_counter();super().__init__();local.owner.metric('browser_cold_start',time.perf_counter()-t)
 def render(self,*a,**kw):
  t=time.perf_counter()
  try:return super().render(*a,**kw)
  finally:local.owner.metric('automatic_native_render_resource_edit_restore_validation',time.perf_counter()-t)
native.OfficialXmlPng=TimedRenderer

def connect(path):
 db=sqlite3.connect(path,timeout=30);db.execute('pragma journal_mode=WAL');db.execute('pragma busy_timeout=30000');return db

class NativeWorker:
 def __init__(self,owner):
  self.owner=owner;self.db=connect(owner.D/'once.sqlite');self.renderer=None;self.reuse=owner.reuse
 def emit(self,event,**kw):self.owner.emit(event,**kw)
 def summary(self,*a,**kw):return {}
 def process(self,path,paper,root):
  ident=sha(path.read_bytes())
  with self.owner.hash_lock(ident):
   if self.db.execute('select 1 from pdfs where id=?',(ident,)).fetchone():
    self.owner.metric('PDF_hash_reuse',0);return
   t=time.perf_counter()
   # Unmodified, pinned builtin import and complete native-edit validator.
   native.Pipeline.pdf(self,path,paper,root)
   self.owner.metric('PDF_case_inclusive',time.perf_counter()-t)
   row=self.db.execute('select status,record from pdfs where id=?',(ident,)).fetchone()
   if row:
    status,raw=row;record=json.loads(raw)
    with self.owner.mu:self.owner.pdf_counts[status]+=1;self.owner.official_calls+=record.get('official_calls',0)
    if status=='qualified_native_xml_png_pair':self.owner.publish_manifest()
   try:
    t=time.perf_counter()
    with fitz.open(path) as doc:metadata=doc.metadata or {}
    self.owner.metric('PDF_metadata_parse',time.perf_counter()-t)
    creator=(metadata.get('creator') or metadata.get('producer') or 'unknown')[:160]
    with self.owner.mu:self.owner.creators[creator]+=1
   except Exception:pass

class State:
 def __init__(self,D,profile):
  self.D=D;self.profile=profile;D.mkdir(parents=True,exist_ok=True);native.D=D
  self.lock=(D/'program.lock').open('a');fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  self.mu=threading.RLock();self.publish_lock=threading.Lock();self.limiter=threading.Lock()
  self.next_request=0.;self.stats=collections.defaultdict(lambda:{'count':0,'seconds':0.})
  self.hash_locks={};self.creators=collections.Counter();self.started=time.perf_counter();self.last_save=0.
  self.db=connect(D/'once.sqlite')
  self.db.execute('create table if not exists papers(id text primary key,status text,record text)')
  self.db.execute('create table if not exists pdfs(id text primary key,status text,record text)')
  # Interrupted PDF claims are retained and never invoke the official importer twice.
  for ident,raw in self.db.execute("select id,record from pdfs where status='attempt_started'").fetchall():
   r=json.loads(raw);r.update(status='interrupted_import_not_repeated',reason='Prior committed once claim retained during transport migration.')
   self.db.execute('update pdfs set status=?,record=? where id=?',(r['status'],native.enc(r),ident))
  self.db.commit();self.pdf_counts=collections.Counter(dict(self.db.execute('select status,count(*) from pdfs group by status')))
  self.paper_counts=collections.Counter(dict(self.db.execute('select status,count(*) from papers group by status')))
  self.official_calls=sum(json.loads(r[0]).get('official_calls',0) for r in self.db.execute('select record from pdfs'))
  self.net_bytes=0;self.active=None;self.events=(D/'events.v3.jsonl').open('a',buffering=1)
  self.reuse={};self.inherited_ids=set();self._inherit()
  self.pdf_queue=queue.Queue(maxsize=32);self.workers=[]
  for i in range(4):
   thread=threading.Thread(target=self.worker_loop,name='native-'+str(i));thread.start();self.workers.append(thread)
  self.emit('parallel_pipeline_started',profile=profile,pid=os.getpid(),download_threads=4,native_import_workers=4,
            route='arxiv -> VPS -> HKUST3',Mac_in_data_path=False,external_models=0)
 def _inherit(self):
  if self.profile!='recent_AI':return
  old=P/'new_bulk_200_v1/once.sqlite'
  with sqlite3.connect(old.as_uri()+'?mode=ro',uri=True) as db:
   self.inherited_ids={r[0].split('v')[0] for r in db.execute('select id from papers')}
   rows=db.execute('select id,status,record from pdfs').fetchall()
  for ident,status,raw in rows:
   r=json.loads(raw);r.update(prior_official_calls=r.get('official_calls',0),official_calls=0,imported_history=True,
       reused_once_ledger=str(old.relative_to(R)))
   cur=self.db.execute('insert or ignore into pdfs values(?,?,?)',(ident,status,native.enc(r)))
   if cur.rowcount:self.pdf_counts[status]+=1
  self.db.commit()
 def hash_lock(self,ident):
  with self.mu:return self.hash_locks.setdefault(ident,threading.Lock())
 def metric(self,name,seconds,amount=1):
  with self.mu:self.stats[name]['count']+=amount;self.stats[name]['seconds']+=seconds
 def emit(self,event,**kw):
  with self.mu:
   text=native.enc({'at_utc':now(),'event':event,**kw});self.events.write(text+'\n');print(text,flush=True)
 def worker_loop(self):
  local.owner=self;worker=NativeWorker(self)
  try:
   while True:
    task=self.pdf_queue.get()
    if task is None:self.pdf_queue.task_done();break
    path,paper,root,future=task
    try:worker.process(path,paper,root);future.set_result(True)
    except BaseException as e:future.set_exception(e)
    finally:self.pdf_queue.task_done()
  finally:
   if worker.renderer:worker.renderer.close()
   worker.db.close()
 def session(self):
  if not hasattr(local,'http'):
   local.http=requests.Session();local.http.trust_env=False
   local.http.proxies={'http':PROXY,'https':PROXY}
   local.http.headers['User-Agent']='img2code-bounded-AI-source-harvest/3.0 (4workers;max3fulltextrequests/sec)'
  return local.http
 def request(self,url,stream=False,headers=None,api=False):
  # Legacy metadata API remains serial with >=3.2s spacing. Full-text uses
  # <=3 starts/s, within the official harvesting guidance (4/s bursts).
  t=time.perf_counter()
  with self.limiter:
   time.sleep(max(0,self.next_request-time.monotonic()));self.next_request=time.monotonic()+(3.2 if api else .34)
  self.metric('request_rate_limit_wait',time.perf_counter()-t)
  t=time.perf_counter();response=self.session().get(url,stream=stream,headers=headers,timeout=(12,25))
  self.metric('HTTP_headers_or_metadata_response',time.perf_counter()-t);response.raise_for_status();return response
 def download(self,paper):
  ident=paper['versioned_id'];target=self.D/'papers'/ident;target.mkdir(parents=True,exist_ok=True)
  archive=target/'source.archive'
  if archive.exists():return {'archive':str(archive),'cached':True}
  t=time.perf_counter()
  try:
   metadata=target/'provenance.json'
   if not metadata.exists():
    with self.request(paper['abs_url']) as response:body=response.content
    if len(body)>2*1024**2:raise ValueError('abstract_metadata_over2MiB')
    (target/'abstract.html').write_bytes(body);resolved=native.metadata_from_abs(body.decode(errors='replace'),ident)
    native.once(metadata,dict(paper,**{k:v for k,v in resolved.items() if k not in paper or k=='license_urls'}))
   part=target/'source.archive.part';offset=part.stat().st_size if part.exists() else 0
   assert offset<=128*1024**2,'prior_partial_above128MiB'
   overlap=min(65536,offset);expected=b''
   if overlap:
    with part.open('rb') as f:f.seek(offset-overlap);expected=f.read(overlap)
   start=offset-overlap;journal=target/'source_attempt.json'
   if not journal.exists():native.once(journal,{'url':'https://arxiv.org/src/'+ident,'at_utc':now(),'source_attempts':1,'version':'parallel_v3'})
   attempts=target/'download_attempts.v3.jsonl';prior=attempts.read_text().splitlines() if attempts.exists() else []
   assert len(prior)<3,'bounded_source_download_attempts_exhausted'
   with attempts.open('a') as f:f.write(native.enc({'at_utc':now(),'attempt':len(prior)+1,'preserved_offset':offset,
                          'overlap_verified_before_append':overlap,'transport':'direct_VPS_HKUST3'})+'\n')
   headers={'Range':'bytes='+str(start)+'-'} if offset else None
   with self.request('https://arxiv.org/src/'+ident,stream=True,headers=headers) as response:
    ct=response.headers.get('Content-Type','').lower()
    native.once(target/('source_response_headers.v3.'+str(len(prior)+1)+'.json'),
                {'content_type':ct,'content_length':response.headers.get('Content-Length'),
                 'content_range':response.headers.get('Content-Range'),'response_url':response.url,'at_utc':now()})
    if 'application/pdf' in ct:raise ValueError('typed_skip_src_endpoint_PDF_content_type_before_body')
    if offset:
     match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
     assert response.status_code==206 and match and int(match[1])==start,'range_resume_not_confirmed'
     total=int(match[3])
    else:total=int(response.headers.get('Content-Length') or 0)
    if total>128*1024**2:raise ValueError('typed_skip_source_ContentLength_above128MiB')
    skip=overlap;verified=0;received=0;net_seconds=0.;stream_start=time.perf_counter();iterator=response.iter_content(256*1024)
    with part.open('ab' if offset else 'wb') as out:
     while True:
      tick=time.perf_counter()
      try:block=next(iterator)
      except StopIteration:break
      elapsed=time.perf_counter()-tick;net_seconds+=elapsed;self.metric('source_HTTP_body_receive',elapsed)
      if not block:continue
      received+=len(block)
      with self.mu:
       self.net_bytes+=len(block)
       if self.net_bytes>BUDGET:raise ValueError('source_network_budget_reached')
      if offset==0 and received==len(block) and block.startswith(b'%PDF-'):raise ValueError('typed_skip_src_endpoint_PDF_only_first_chunk')
      if skip:
       size=min(len(block),skip);assert block[:size]==expected[verified:verified+size],'resume_overlap_does_not_match_original'
       verified+=size;skip-=size;block=block[size:]
      if block:out.write(block)
      if out.tell()>128*1024**2:raise ValueError('typed_skip_source_above128MiB')
      wall=time.perf_counter()-stream_start
      if wall>90 and received/wall<64*1024:raise requests.exceptions.ConnectionError('network_source_below64KiB_s_for90s')
     out.flush();os.fsync(out.fileno())
    assert not skip,'short_resume_overlap'
    if total:assert part.stat().st_size==total,'incomplete_source_content_length'
   os.replace(part,archive)
   native.once(target/'source_receipt.json',{'url':'https://arxiv.org/src/'+ident,'sha256':sha(archive.read_bytes()),
       'bytes':archive.stat().st_size,'at_utc':now(),'resumed_prior_bytes':offset,'new_transport':'arxiv_VPS_HKUST3'})
   self.metric('source_archives_downloaded',time.perf_counter()-t)
   self.emit('source_download_complete',paper=ident,bytes=archive.stat().st_size,new_bytes=received,
             preserved_prior_bytes=offset,seconds=time.perf_counter()-t,body_receive_seconds=net_seconds)
   self.save();return {'archive':str(archive),'cached':False}
  except Exception as e:
   self.metric('source_download_failures',time.perf_counter()-t)
   reason=type(e).__name__+':'+str(e)[:1000]
   self.emit('source_download_failed',paper=ident,reason=reason);self.save()
   return {'error':reason,'network_failure':isinstance(e,(requests.ConnectionError,requests.Timeout))}
 def process_paper(self,paper,download):
  ident=paper['versioned_id'];target=self.D/'papers'/ident;self.active=ident;t=time.perf_counter()
  record={'id':ident,'started_at_utc':now(),'metadata':paper,'source_only':True,'driver':'parallel_v3'}
  old=self.db.execute('select status from papers where id=?',(ident,)).fetchone()
  if not old:self.db.execute('insert into papers values(?,?,?)',(ident,'attempt_started',native.enc(record)));self.db.commit()
  try:
   if 'error' in download:raise ValueError(download['error'])
   meta=target/'provenance.json'
   if meta.exists():record['metadata']=json.loads(meta.read_text())
   source=target/'source';marker=target/'extraction.json'
   if not marker.exists():
    tick=time.perf_counter();extracted=native.safe_extract(Path(download['archive']),source,max_total=512*1024**2,max_files=20000)
    self.metric('archive_decompression_and_safe_parse',time.perf_counter()-tick);native.once(marker,extracted)
   if not json.loads(marker.read_text()).get('extracted'):
    record['status']='typed_skip_no_extractable_source';return
   pdfs=sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower()=='.pdf');record['pdf_paths_discovered']=len(pdfs)
   futures=[]
   for path in pdfs:
    f=cf.Future();self.pdf_queue.put((path,paper,source,f));futures.append(f)
   for f in futures:f.result()
   record['status']='source_completed'
  except Exception as e:record.update(status='typed_skip_source_attempt',reason=type(e).__name__+':'+str(e)[:1200])
  finally:
   record.setdefault('status','typed_skip_source_attempt');record['finished_at_utc']=now()
   native.atomic(target/'record.json',record)
   self.db.execute('update papers set status=?,record=? where id=?',(record['status'],native.enc(record),ident));self.db.commit()
   with self.mu:
    if old:self.paper_counts[old[0]]-=1
    self.paper_counts[record['status']]+=1
   self.metric('paper_parse_and_native_processing_inclusive',time.perf_counter()-t)
   self.emit('paper_finished',paper=ident,status=record['status'],seconds=time.perf_counter()-t)
   self.active=None;self.save()
 def process_batch(self,papers):
  terminal={r[0] for r in self.db.execute("select id from papers where status!='attempt_started'")}
  selected=[p for p in papers if p['versioned_id'] not in terminal and p.get('arxiv_id',p['versioned_id'].split('v')[0]) not in self.inherited_ids]
  failed=0;pool=cf.ThreadPoolExecutor(max_workers=4);pending={};index=0
  try:
   for j,p in enumerate(selected):
    while index<len(selected) and index<j+8:
     pending[index]=pool.submit(self.download,selected[index]);index+=1
    result=pending.pop(j).result();self.process_paper(p,result)
    failed=failed+1 if result.get('network_failure') else 0
    if failed>=3:raise RuntimeError('transport_circuit_breaker_three_consecutive_network_failures')
  finally:pool.shutdown(wait=True,cancel_futures=True)
 def publish_manifest(self):
  with self.publish_lock:
   with connect(self.D/'once.sqlite') as db:rows=db.execute("select record from pdfs where status='qualified_native_xml_png_pair' order by id").fetchall()
   p=self.D/'manifest.jsonl.tmp';p.write_text(''.join(r[0]+'\n' for r in rows));os.replace(p,self.D/'manifest.jsonl')
 def save(self,finished=False):
  with self.mu:
   elapsed=time.perf_counter()-self.started
   stages={k:{**v,'samples_per_second':v['count']/v['seconds'] if v['seconds'] else None} for k,v in self.stats.items()}
   imports=stages.get('official_PDF_import',{}).get('count',0)
   alerts=[]
   if imports>=100 and not self.pdf_counts.get('qualified_native_xml_png_pair',0):
    alerts.append({'kind':'low_native_XML_recovery_rate','note':'Official importer supports embedded drawio XML; producer histogram retained for source-selection diagnosis. No model review invoked.'})
   x={'at_utc':now(),'profile':self.profile,'active_paper':self.active,'elapsed_wall_seconds':elapsed,
      'route':'arxiv -> VPS -> HKUST3','Mac_in_data_path':False,'download_threads':4,'native_import_workers':4,
      'new_source_network_bytes':self.net_bytes,'wall_source_MiB_s':self.net_bytes/1024**2/elapsed,
      'stages':stages,'timing_note':'Stage timings are cumulative across workers and inclusive where marked; do not sum overlapping stages as wall time.',
      'pdf_states':dict(self.pdf_counts),'official_calls_total_including_history':self.official_calls,
      'paper_states':{k:v for k,v in self.paper_counts.items() if v},
      'PDF_creator_or_producer_histogram':dict(self.creators),'alerts':alerts,'finished':finished,'external_model_calls':0}
   native.atomic(CONTROL/(self.profile+'.performance.json'),x)
 def close(self,finished=False):
  for _ in self.workers:self.pdf_queue.put(None)
  for w in self.workers:w.join()
  self.publish_manifest();self.save(finished=finished);self.db.close();self.events.close();self.lock.close()

def run():
 CONTROL.mkdir(exist_ok=True);outer=(CONTROL/'program.lock').open('a');fcntl.flock(outer,fcntl.LOCK_EX|fcntl.LOCK_NB)
 # Honor the original frozen200 input identity; no processed PDF hash is reset.
 D=P/'new_bulk_200_v1';freeze=json.loads((D/'freeze.json').read_text());raw=(D/'papers.jsonl').read_bytes();assert sha(raw)==freeze['papers_sha256']
 state=State(D,'initial_200');finished=False
 try:
  state.process_batch([json.loads(l) for l in raw.decode().splitlines()]);finished=True
 finally:state.close(finished=finished)
 D=P/'recent_ai_source_expansion_v2';state=State(D,'recent_AI');finished=False
 try:
  cfg=json.loads((D/'freeze.json').read_text());cursorfile=D/'cursor.parallel_v3.json'
  cursor=json.loads(cursorfile.read_text()) if cursorfile.exists() else {'units':inventory.months(datetime.date.fromisoformat(cfg['until_date_UTC'])),'position':0,'pages_frozen':0}
  while any(u['state']=='pending' for u in cursor['units']):
   i=cursor['position']%len(cursor['units']);cursor['position']=(i+1)%len(cursor['units']);unit=cursor['units'][i]
   if unit['state']!='pending':continue
   folder=D/'discovery'/unit['key']/str(unit['start']);folder.mkdir(parents=True,exist_ok=True);pagefile=folder/'page.parallel_v3.json'
   try:
    if pagefile.exists():page=json.loads(pagefile.read_text());body=(folder/'response.atom').read_bytes();assert sha(body)==page['response_sha256']
    else:
     query='(cat:cs.CV OR cat:cs.LG OR cat:cs.AI OR cat:cs.CL) AND submittedDate:['+unit['from']+' TO '+unit['to']+']'
     url='https://export.arxiv.org/api/query?'+urllib.parse.urlencode({'search_query':query,'start':unit['start'],'max_results':200,'sortBy':'submittedDate','sortOrder':'descending'})
     with state.request(url,api=True) as response:body=response.content
     assert len(body)<=16*1024**2
     total,papers=inventory.parse_feed(body,unit);(folder/'response.atom').write_bytes(body)
     page={'at_utc':now(),'url':url,'response_sha256':sha(body),'total_results':total,'entries':len(papers)};native.once(pagefile,page)
    total,papers=inventory.parse_feed(body,unit)
    if total>20000:cursor['units'].extend(inventory.split_days(unit));unit['state']='partitioned'
    else:
     state.process_batch(papers);unit['start']+=len(papers)
     if not papers or unit['start']>=total:unit['state']='done'
    cursor['pages_frozen']+=1
   except RuntimeError:raise
   except Exception as e:
    unit['failures']+=1;unit['last_error']=type(e).__name__+':'+str(e)[:1000]
    if unit['failures']>=3:unit['state']='typed_failure'
    state.emit('metadata_partition_failure',partition=unit['key'],reason=unit['last_error'])
   native.atomic(cursorfile,cursor);state.save()
  finished=True
 finally:state.close(finished=finished)

if __name__=='__main__':run()
