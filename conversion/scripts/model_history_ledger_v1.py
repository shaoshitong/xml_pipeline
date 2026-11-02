"""Read-only history import into an independent model-call ledger; no API client.

Raw histories, jobs and queues are never modified. SDK export/persistent/archive
mirrors deduplicate by session+event/message identities. Usage aggregates are
checksums, not additional calls. Missing/failed sends reserve budget; proven
blocked.local requests do not. lookup_sample_budget is a fail-closed gateway API.
"""
import argparse,collections,datetime,hashlib,io,json,os,re,sqlite3,subprocess,tarfile,time,uuid
from pathlib import Path

ROOT=Path(os.environ.get('IMG2CODE_ROOT','/backup/shaoshitong/img2code_20261029')).resolve()
DEFAULT_DB=str(ROOT/'conversion/model_history_ledger_v1.sqlite')
POLICY='actual_response_identity_retry_and_conservative_unknown_history_v1'
MAX_CALLS=2
TOKEN_FIELDS=('input_uncached','cache_read','cache_write','output_including_reasoning')
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def safe_error(value):
 text=str(value or '')[:2200];text=re.sub(r'(?i)(bearer\s+|authorization[\s:=]+)\S+',r'\1[REDACTED]',text);return re.sub(r'\bsk-[A-Za-z0-9_-]{8,}','[REDACTED]',text)


def normalize_usage(raw,flavor='auto'):
 """Never add reasoning a second time or subtract cache from DSH/Anthropic input."""
 out={'input_uncached':None,'cache_read':None,'cache_write':None,'output_including_reasoning':None,'reasoning_tokens':None,'reported_total':None,'semantics':'unknown','issues':[],'raw_usage':raw}
 if not isinstance(raw,dict):out['issues'].append('usage_missing');return out
 def number(key,default=None):
  value=raw.get(key,default)
  if value is None:return None
  if isinstance(value,bool) or not isinstance(value,(int,float)) or value<0 or int(value)!=value:out['issues'].append('invalid_usage_'+key);return None
  return int(value)
 if 'inputTokens' in raw or 'outputTokens' in raw:
  out.update(input_uncached=number('inputTokens'),cache_read=number('cacheReadTokens',0),cache_write=number('cacheWriteTokens',0),output_including_reasoning=number('outputTokens'),reported_total=number('totalTokens'),semantics='installed_dsh_messages_input_excludes_cache_output_includes_thinking')
 elif 'prompt_tokens' in raw or 'completion_tokens' in raw:
  prompt=number('prompt_tokens');hit=number('prompt_cache_hit_tokens');miss=number('prompt_cache_miss_tokens');details=raw.get('prompt_tokens_details') or {}
  if hit is None and isinstance(details,dict) and isinstance(details.get('cached_tokens'),int):hit=details['cached_tokens']
  if hit is None:hit=0 if prompt is not None and miss==prompt else None
  if miss is None and prompt is not None and hit is not None:miss=prompt-hit
  out.update(input_uncached=miss,cache_read=hit,cache_write=number('cache_write_tokens',0),output_including_reasoning=number('completion_tokens'),reported_total=number('total_tokens'),semantics='deepseek_openai_prompt_total_with_explicit_cache_hit_miss')
  if prompt is not None and miss is not None and hit is not None and miss+hit!=prompt:out['issues'].append('prompt_hit_miss_sum_mismatch')
  completion=raw.get('completion_tokens_details') or {}
  if isinstance(completion,dict) and isinstance(completion.get('reasoning_tokens'),int):out['reasoning_tokens']=completion['reasoning_tokens']
 elif 'input_tokens' in raw or 'output_tokens' in raw:
  out.update(input_uncached=number('input_tokens'),cache_read=number('cache_read_input_tokens',0),cache_write=number('cache_creation_input_tokens',0),output_including_reasoning=number('output_tokens'),reported_total=number('total_tokens'),semantics='anthropic_messages_input_excludes_cache_output_includes_thinking')
  if isinstance(raw.get('reasoning_tokens'),int):out['reasoning_tokens']=raw['reasoning_tokens']
 else:out['issues'].append('usage_schema_unknown')
 values=[out[k] for k in TOKEN_FIELDS];out['known_token_sum']=sum(v for v in values if v is not None);out['split_complete']=all(v is not None for v in values)
 if out['split_complete'] and out['reported_total'] is not None and out['known_token_sum']!=out['reported_total']:out['issues'].append('reported_total_not_equal_to_separate_components')
 out['positive_usage']=out['known_token_sum']>0 or bool(out['reported_total'] and out['reported_total']>0)
 out['usage_unknown']=not out['split_complete'] or bool(out['issues']);return out


def milliseconds(value):
 if isinstance(value,(int,float)):return int(value if value>10**11 else value*1000)
 if isinstance(value,str):
  try:return int(datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1000)
  except ValueError:return None
 return None


def project_event(frame,assumed_session=None):
 if not isinstance(frame,dict):return None
 if frame.get('type')=='session':return {'session_header':frame.get('id')}
 params=frame.get('params',{});event=params.get('event') if isinstance(params,dict) else None
 if not isinstance(event,dict):event=frame
 kind=event.get('type')
 if not kind or kind=='session':return None
 data=event.get('data') if isinstance(event.get('data'),dict) else {};message=data.get('message') if isinstance(data.get('message'),dict) else {};source=message.get('source') if isinstance(message.get('source'),dict) else {}
 result={'session_id':params.get('sessionId') or assumed_session,'type':kind,'seq':event.get('seq'),'time':milliseconds(event.get('time')),'turn':data.get('turn'),'step':data.get('step'),'message_id':message.get('id'),'provider':data.get('provider') or source.get('provider'),'model':data.get('model') or source.get('model')}
 if kind=='assistant/message':
  result['usage_raw']=data.get('usage');result['stream_usages']=[]
  for record in data.get('stream',[]):
   chunk=record.get('chunk',{}) if isinstance(record,dict) else {}
   if chunk.get('type')=='usage' and isinstance(chunk.get('usage'),dict):result['stream_usages'].append(chunk['usage'])
   for key in ('responseId','response_id','requestId','request_id','gateway_request_key'):
    if isinstance(chunk.get(key),str):result[key]=chunk[key]
  for key in ('responseId','response_id','requestId','request_id','gateway_request_key'):
   if isinstance(data.get(key),str):result[key]=data[key]
 elif kind in ('llm/retry','llm/retry-started'):
  result.update(retry=data.get('retry'),retry_id=data.get('retryId'))
 for field in ('failure','reason','error'):
  item=data.get(field)
  if isinstance(item,dict):
   result[field+'_code']=item.get('code') or item.get('kind')
   if isinstance(item.get('error'),dict):result[field+'_nested_code']=item['error'].get('code')
 return result


class Collector:
 def __init__(self):self.events={};self.artifacts=[];self.call_meta=[];self.prompts=[];self.blocked=[];self.group_identity={};self.problems=[];self.event_type_counts=collections.Counter()
 def register_identity(self,group,identity):
  old=self.group_identity.get(group)
  if old and old!=identity:self.problems.append({'reason':'group_identity_conflict','group':group})
  self.group_identity[group]=identity
 def add_events(self,lines,artifact,group,identity,session_hint=None,call_group=None):
  self.register_identity(group,identity);session=session_hint;parse_errors=0;count=0
  for line in lines:
   count+=1
   try:frame=json.loads(line)
   except (ValueError,UnicodeError):parse_errors+=1;continue
   meta=project_event(frame,session)
   if not meta:continue
   if meta.get('session_header'):session=meta['session_header'];continue
   if not meta.get('session_id'):meta['session_id']=session or 'unresolved_session:'+sha((artifact+'|'+group).encode())
   key=json.dumps([meta['session_id'],meta['seq'],meta['type']],separators=(',',':')) if meta['seq'] is not None else sha(json.dumps(meta,sort_keys=True).encode());self.event_type_counts[meta['type']]+=1
   if key in self.events:
    old=self.events[key];old['artifacts'].add(artifact);old['groups'].add(group)
    if call_group:old['call_groups'].add(call_group)
    if old['meta']!=meta:old['conflicts'].append(meta)
   else:self.events[key]={'meta':meta,'artifacts':{artifact},'groups':{group},'call_groups':{call_group} if call_group else set(),'conflicts':[]}
  if parse_errors:self.problems.append({'reason':'event_parse_errors','artifact':artifact,'group':group,'count':parse_errors})
  return count,parse_errors
 def add_meta(self,path,data,group,identity):
  self.register_identity(group,identity)
  if isinstance(data,dict) and isinstance(data.get('usage'),dict):self.call_meta.append({'artifact':path,'call_group':str(Path(path.split('::')[0]).parent),'group':group,'message_id':data.get('message_id'),'session_id':data.get('session_id'),'usage_raw':data['usage'],'aggregate':Path(path.split('::')[0]).name!='call.json' and not re.fullmatch(r'(pass|round)\d+',Path(path.split('::')[0]).parent.name)})
 def serialize(self):
  return {'events':[{'key':k,'meta':v['meta'],'artifacts':sorted(v['artifacts']),'groups':sorted(v['groups']),'call_groups':sorted(v['call_groups']),'conflicts':v['conflicts']} for k,v in self.events.items()],'artifacts':self.artifacts,'call_meta':self.call_meta,'prompts':self.prompts,'blocked':self.blocked,'group_identity':self.group_identity,'problems':self.problems,'event_type_counts':dict(self.event_type_counts)}
 def merge(self,data):
  for group,identity in data.get('group_identity',{}).items():self.register_identity(group,identity)
  for row in data.get('events',[]):
   key=row['key'];value={'meta':row['meta'],'artifacts':set(row['artifacts']),'groups':set(row['groups']),'call_groups':set(row['call_groups']),'conflicts':row['conflicts']}
   if key in self.events:
    old=self.events[key]
    for field in ('artifacts','groups','call_groups'):old[field]|=value[field]
    if old['meta']!=value['meta']:old['conflicts'].append(value['meta'])
   else:self.events[key]=value
  for name in ('artifacts','call_meta','prompts','blocked','problems'):getattr(self,name).extend(data.get(name,[]))
  self.event_type_counts.update(data.get('event_type_counts',{}))


def identity_for_ids(ids,kind='original_id',detail=None):return {'original_ids':sorted(set(ids)),'kind':kind,'ambiguous':len(set(ids))!=1,'detail':detail}


class IdentityResolver:
 def __init__(self,root,jobs=None):
  self.root=Path(root).resolve();self.jobs=jobs or {};self.images=collections.defaultdict(list);self.codes=collections.defaultdict(list);self.aliases={};self.case_folders={}
  for id,row in self.jobs.items():
   if row.get('source_image_sha256'):self.images[row['source_image_sha256']].append(id)
   if row.get('source_code_sha256'):self.codes[row['source_code_sha256']].append(id)
  evaluation=self.root/'evaluation'
  if evaluation.exists():
   for p in sorted(evaluation.glob('**/case.json')):
    data=json.loads(p.read_bytes());alias=data.get('id')
    if not alias:continue
    image=data.get('reference_sha256');matches=self.images.get(image,[]);method='source_image_sha256'
    gold=evaluation/'dataset_gold_validation'/alias/'input_manifest.json'
    if not matches and gold.exists():
     manifest=json.loads(gold.read_bytes());source=next((f['sha256'] for f in manifest.get('files',[]) if f.get('role')=='source'),None);matches=self.codes.get(source,[]);method='unique_gold_source_code_sha256'
    if matches:identity=identity_for_ids(matches,method,{'alias':alias,'reference_sha256':image})
    else:
     key='external:'+sha(json.dumps([data.get('source'),data.get('source_image_id'),data.get('source_file'),image,alias],sort_keys=True).encode());identity=identity_for_ids([key],'external_dataset_case',{'alias':alias,'source':data.get('source'),'source_file':data.get('source_file'),'reference_sha256':image})
    self.case_folders[str(p.parent.resolve())]=identity;self.aliases[alias]=identity
 def __call__(self,path):
  text=str(path).split('::')[0];p=Path(text).resolve();parts=p.parts
  for part in parts:
   found=re.search(r'(?:^|_)([a-f0-9]{64})(?:_|$)',part)
   if found:return str(self.root/'conversion/harness_sessions'/part),identity_for_ids([found[1]],'session_original_id')
  candidates=[(folder,identity) for folder,identity in self.case_folders.items() if p.is_relative_to(folder)]
  if candidates:return max(candidates,key=lambda x:len(x[0]))
  for alias,identity in self.aliases.items():
   if alias in parts:return str(p.parent),identity
  if any(re.match(r'(visibility_probe|runtime_probe|probe_[a-f0-9]|fulltool_mount_probe)',part) for part in parts):return str(p.parent),{'original_ids':[],'kind':'non_dataset_control_probe','ambiguous':False,'detail':None}
  group=str(p.parent);return group,{'original_ids':['unresolved:'+sha(group.encode())],'kind':'unresolved_history_identity','ambiguous':True,'detail':None}


def _zstd_lines(stream):
 try:
  import zstandard
  return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(stream,read_across_frames=True),encoding='utf-8')
 except ImportError:
  # Local historical metadata only; do not install packages or copy media.
  if not getattr(stream,'name',None):raise
  result=subprocess.run(['zstd','-dc',str(stream.name)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True);return io.StringIO(result.stdout.decode())


def is_sdk_session_member(member):
 # macOS tar archives may contain ._session.v4.jsonl.zstd AppleDouble metadata.
 # Only the exact SDK session basename is an event stream.
 return member.isfile() and Path(member.name).name=='session.v4.jsonl.zstd' and '/sessions/' in member.name


def scan_paths(collector,roots,resolver,progress=True):
 ignored={'private','node_modules','profiles','storages','assets','fonts','__pycache__','.git','reference','source_assets','source_provenance','baseline','runtime','env'};files=[]
 for root in roots:
  root=Path(root)
  if not root.exists():continue
  if root.is_file():files.append(root);continue
  for base,dirs,names in os.walk(root,followlinks=False):
   dirs[:]=[d for d in dirs if d not in ignored]
   for name in names:
    p=Path(base)/name
    if p.is_symlink():continue
    if name in ('events.jsonl','all_events.jsonl','call.json','summary.json','session.v4.jsonl.zstd','sdk_model_drain_v1.jsonl','prompt.txt') or name.endswith('.tar.gz') and 'sdk' in name.lower():files.append(p)
 for index,p in enumerate(sorted(set(files))):
  group,identity=resolver(p);before=p.stat();artifact=str(p);kind='other';errors=[]
  try:
   if p.name=='prompt.txt':
    kind='prompt_presence_only';collector.prompts.append({'artifact':artifact,'call_group':str(p.parent),'group':group,'mtime':int(before.st_mtime*1000)})
   elif p.name=='sdk_model_drain_v1.jsonl':
    kind='proven_local_block_receipts'
    for line in p.open():
     r=json.loads(line)
     if r.get('upstream_send_performed') is False and r.get('charged') is False and r.get('kind') in ('blocked_prompt','blocked_fetch'):collector.blocked.append({'group':group,'artifact':artifact,'kind':r['kind'],'session_id':r.get('session_id'),'time':milliseconds(r.get('at'))})
   elif p.name.endswith('.jsonl'):
    kind='sdk_event_export';collector.add_events(p.open(),artifact,group,identity,call_group=str(p.parent))
   elif p.name.endswith('.zstd'):
    kind='sdk_persistent_events'
    with p.open('rb') as raw:
     with _zstd_lines(raw) as stream:collector.add_events(stream,artifact,group,identity,session_hint=p.parent.name)
   elif p.name.endswith('.tar.gz'):
    kind='sdk_session_archive'
    with tarfile.open(p,'r:gz') as archive:
     for member in archive:
      if is_sdk_session_member(member):
       stream=archive.extractfile(member)
       with _zstd_lines(stream) as lines:collector.add_events(lines,artifact+'::'+member.name,group,identity,session_hint=Path(member.name).parent.name)
   else:
    kind='sdk_call_aggregate_metadata';data=json.loads(p.read_bytes());collector.add_meta(artifact,data,group,identity)
  except Exception as exc:errors.append(type(exc).__name__+': '+safe_error(exc));collector.problems.append({'reason':'artifact_read_failed','artifact':artifact,'group':group,'error':errors[-1]})
  after=p.stat();stable=(before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns);digest=None
  if p.name!='prompt.txt':
   h=hashlib.sha256()
   with p.open('rb') as stream:
    for blob in iter(lambda:stream.read(1024*1024),b''):h.update(blob)
   digest=h.hexdigest()
  collector.artifacts.append({'artifact':artifact,'sha256':digest,'kind':kind,'group':group,'size':after.st_size,'mtime_ns':after.st_mtime_ns,'stable':stable,'errors':errors});collector.register_identity(group,identity)
  if progress and (index+1)%200==0:print(json.dumps({'stage':'history_metadata_scanning','artifacts':index+1,'discovered':len(files),'unique_events':len(collector.events),'problems':len(collector.problems)}),flush=True)


def reconcile(collector):
 sessions=collections.defaultdict(list)
 for observation in collector.events.values():sessions[observation['meta']['session_id']].append(observation)
 responses={};requests={};user_ids={};group_responses=collections.defaultdict(set);blocked_sessions={r['session_id'] for r in collector.blocked if r.get('session_id') and r['kind']=='blocked_prompt'};retry_scheduled=0;retry_started=0
 for session,observations in sessions.items():
  observations.sort(key=lambda r:((r['meta']['seq'] if r['meta']['seq'] is not None else 10**18),r['meta']['time'] or 0));turn=0;step=0;attempts=collections.defaultdict(int);provider=None;model=None
  def get_request(t,s,attempt,obs):
   key=json.dumps([session,t,s,attempt],separators=(',',':'));row=requests.setdefault(key,{'request_key':key,'session_id':session,'turn':t,'step':s,'attempt':attempt,'groups':set(),'artifacts':set(),'evidence_types':set(),'response_keys':set(),'first_time':None,'status':'unresolved','reason':'request_started_without_confirmed_usage','gateway_request_key':None})
   row['groups']|=obs['groups'];row['artifacts']|=obs['artifacts'];row['evidence_types'].add(obs['meta']['type']);tm=obs['meta']['time']
   if tm is not None:row['first_time']=tm if row['first_time'] is None else min(row['first_time'],tm)
   return row
  for observation in observations:
   meta=observation['meta'];kind=meta['type'];turn=meta['turn'] if meta['turn'] is not None else turn;step=meta['step'] if meta['step'] is not None else step
   if kind=='turn/start':step=0
   provider=meta.get('provider') or provider;model=meta.get('model') or model;pair=(turn,step);index=attempts[pair]
   if kind=='user/message' and meta.get('message_id'):user_ids[meta['message_id']]=(session,turn)
   if kind in ('request/header','request/context'):get_request(turn,step,index,observation)
   if kind=='llm/retry':
    retry_scheduled+=1;get_request(turn,step,index,observation)['reason']='failed_request_before_scheduled_retry_usage_unknown'
   if kind=='llm/retry-started':
    retry_started+=1;attempts[pair]=max(index+1,int(meta.get('retry') or 1));get_request(turn,step,attempts[pair],observation)['reason']='retry_started_without_confirmed_usage'
   if kind=='session/title-llm-request' or kind=='llm/auxiliary-request':
    key='auxiliary:'+session+':'+str(meta['seq']);requests[key]={'request_key':key,'session_id':session,'turn':turn,'step':step,'attempt':None,'groups':set(observation['groups']),'artifacts':set(observation['artifacts']),'evidence_types':{kind},'response_keys':set(),'first_time':meta['time'],'status':'unresolved','reason':'explicit_auxiliary_model_request_without_usage_telemetry','gateway_request_key':None}
   if kind=='assistant/message':
    raw=meta.get('usage_raw')
    if not raw and meta.get('stream_usages'):raw=meta['stream_usages'][-1]
    usage=normalize_usage(raw);message_id=meta.get('message_id');upstream=meta.get('responseId') or meta.get('response_id');key=('upstream:'+str(provider)+':'+upstream) if upstream else 'sdk:'+session+':'+str(message_id or meta.get('seq'));request=get_request(turn,step,attempts[pair],observation);request['response_keys'].add(key);request['status']='covered_by_response';request['gateway_request_key']=meta.get('gateway_request_key')
    row=responses.setdefault(key,{'response_key':key,'session_id':session,'assistant_message_id':message_id,'turn':turn,'step':step,'attempt':attempts[pair],'provider':provider,'model':model,'usage':usage,'groups':set(),'artifacts':set(),'call_groups':set(),'usage_conflict':False,'gateway_request_key':meta.get('gateway_request_key'),'status':'confirmed' if usage.get('positive_usage') else 'unknown_response_usage'})
    row['groups']|=observation['groups'];row['artifacts']|=observation['artifacts'];row['call_groups']|=observation['call_groups']
    if row['usage']!=usage:row['usage_conflict']=True
    if observation['conflicts']:row['usage_conflict']=True
    if meta.get('stream_usages') and any(u!=raw for u in meta['stream_usages']):row['usage_conflict']=True
    for group in observation['groups']:group_responses[group].add(key)
   # A locally blocked failure can never consume an upstream retry reservation.
   if any(meta.get(k)=='blocked.local' for k in ('failure_code','reason_code','error_code','reason_nested_code','error_nested_code')):
    row=get_request(turn,step,attempts[pair],observation);row['status']='blocked_local';row['reason']='explicit_blocked_local_error'
 # Cross-check prompt aggregates and recover aggregate-only successful calls.
 aggregate_checks=[];covered_call_groups=set()
 for call in collector.call_meta:
  matching=[r for r in responses.values() if call['call_group'] in r['call_groups']]
  if not matching and call.get('message_id') in user_ids:
   session,turn=user_ids[call['message_id']];matching=[r for r in responses.values() if r['session_id']==session and r['turn']==turn]
  if not matching and call.get('session_id'):matching=[r for r in responses.values() if r['session_id']==call['session_id']]
  if not matching and call['aggregate']:matching=[responses[key] for key in group_responses.get(call['group'],[])]
  usage=normalize_usage(call['usage_raw']);expected={k:sum((r['usage'].get(k) or 0) for r in matching) for k in TOKEN_FIELDS};agree=all(usage.get(k)==expected[k] for k in TOKEN_FIELDS) if matching and usage.get('split_complete') else None
  aggregate_checks.append({'artifact':call['artifact'],'matching_responses':len(matching),'usage_matches_responses':agree,'normalized_aggregate':usage})
  if matching:
   covered_call_groups.add(call['call_group'])
   for response in matching:response['call_groups'].add(call['call_group'])
   if agree is False:
    key='aggregate_mismatch:'+sha(call['call_group'].encode());requests[key]={'request_key':key,'session_id':call.get('session_id'),'turn':None,'step':None,'attempt':None,'groups':{call['group']},'artifacts':{call['artifact']},'evidence_types':{'call_aggregate_usage_disagrees_with_response_history'},'response_keys':set(),'first_time':None,'status':'unresolved','reason':'aggregate_usage_response_cross_check_mismatch','gateway_request_key':None}
  elif usage.get('positive_usage'):
   # The turn may contain more than one upstream tool/retry request. One observed
   # aggregate is a lower bound, and missing per-response history locks eligibility.
   key='aggregate_only:'+sha((call['group']+'|'+str(call.get('message_id') or call['call_group'])).encode());responses[key]={'response_key':key,'session_id':call.get('session_id'),'assistant_message_id':None,'turn':None,'step':None,'attempt':None,'provider':None,'model':None,'usage':usage,'groups':{call['group']},'artifacts':{call['artifact']},'call_groups':{call['call_group']},'usage_conflict':False,'gateway_request_key':None,'status':'aggregate_only_unknown_call_multiplicity'};covered_call_groups.add(call['call_group'])
 # Every prompt-only historical folder is unresolved unless persisted events
 # cover it or an explicit local blocked-prompt receipt covers that exact label.
 for prompt in collector.prompts:
  group=prompt['group'];label=Path(prompt['call_group']).name;matching=[r for r in responses.values() if prompt['call_group'] in r['call_groups'] or group in r['groups'] and str(r.get('session_id','')).startswith(label+'-')]
  if matching or prompt['call_group'] in covered_call_groups:continue
  related=[q for q in requests.values() if group in q['groups'] and str(q.get('session_id') or '').startswith(label+'-')]
  if related:continue
  blocked=any(r['group']==group and str(r.get('session_id') or '').startswith(label+'-') and r['kind']=='blocked_prompt' for r in collector.blocked)
  key='prompt_unknown:'+sha(prompt['call_group'].encode());requests[key]={'request_key':key,'session_id':None,'turn':None,'step':None,'attempt':None,'groups':{group},'artifacts':{prompt['artifact']},'evidence_types':{'prompt_presence_only'},'response_keys':set(),'first_time':prompt['mtime'],'status':'blocked_local' if blocked else 'unresolved','reason':'explicit_local_blocked_prompt' if blocked else 'prompt_present_but_no_durable_request_or_response','gateway_request_key':None}
 # request/header/context are preparation evidence. A positive response covers
 # that exact attempt; a retry creates another attempt, never another aggregate.
 for request in requests.values():
  if request['response_keys'] and request['status']!='blocked_local':request['status']='covered_by_response'
  if not request['response_keys'] and request.get('session_id') in blocked_sessions:
   blocks=[b for b in collector.blocked if b.get('session_id')==request['session_id'] and b['kind']=='blocked_prompt'];start=request.get('first_time')
   if start is not None and any(b.get('time') is not None and start>=b['time'] for b in blocks):request['status']='blocked_local';request['reason']='explicit_local_prompt_guard_before_request'
 return {'responses':responses,'requests':requests,'aggregate_checks':aggregate_checks,'retry_scheduled':retry_scheduled,'retry_started':retry_started}


def init(db):
 db.executescript('''create table if not exists imports(history_snapshot_id text primary key,created_at text,policy text,inventory_complete integer,summary_json text);
 create table if not exists artifact_versions(artifact text,sha256 text,record_json text,primary key(artifact,sha256));
 create table if not exists event_observations(event_key text primary key,record_json text);
 create table if not exists responses(response_key text primary key,record_json text);
 create table if not exists request_reservations(request_key text primary key,record_json text);
 create table if not exists sample_totals(original_id text primary key,record_json text);
 create table if not exists ledger_state(key text primary key,value text);''');db.commit()


def persist(db_path,collector,reconciled,jobs,inventory_complete=True):
 responses=reconciled['responses'];requests=reconciled['requests'];db=sqlite3.connect(db_path);init(db)
 previous_artifacts=collections.defaultdict(list)
 for artifact,raw in db.execute('select artifact,record_json from artifact_versions'):previous_artifacts[artifact].append(json.loads(raw))
 old_groups=db.execute('select value from ledger_state where key="group_identity"').fetchone()
 if old_groups:
  for group,identity in json.loads(old_groups[0]).items():collector.group_identity.setdefault(group,identity)
 for key,raw in db.execute('select response_key,record_json from responses'):
  if key not in responses:
   row=json.loads(raw)
   for name in ('groups','artifacts','call_groups'):row[name]=set(row.get(name,[]))
   responses[key]=row
 for key,raw in db.execute('select request_key,record_json from request_reservations'):
  if key not in requests:
   row=json.loads(raw)
   for name in ('groups','artifacts','response_keys','evidence_types'):row[name]=set(row.get(name,[]))
   requests[key]=row
 # Recovery can replace a turn aggregate by its newly recovered individual
 # responses. Preserve the historical row as superseded evidence, not cost.
 actual=[r for r in responses.values() if r['status'] in ('confirmed','unknown_response_usage')]
 for response in responses.values():
  if response['status']=='aggregate_only_unknown_call_multiplicity':
   recovered=[r['response_key'] for r in actual if r['call_groups']&response['call_groups']]
   if recovered:response['status']='superseded_aggregate_by_response';response['superseded_by']=recovered
 for request in requests.values():
  if request['status']=='unresolved' and request['request_key'].startswith('prompt_unknown:'):
   folders={str(Path(a.split('::')[0]).parent) for a in request['artifacts']};recovered=[r['response_key'] for r in actual if r['call_groups']&folders]
   if recovered:request['status']='covered_by_response';request['response_keys'].update(recovered)
  if request['status']=='unresolved' and request['request_key'].startswith('artifact_unknown:'):
   # A parser recovery of the exact same bytes can discharge read uncertainty;
   # replacing or losing those bytes cannot. Actual known responses remain.
   current={a['artifact']:a for a in collector.artifacts};bad_groups={p.get('group') for p in collector.problems}
   def same_bytes_recovered(artifact):
    a=current.get(artifact)
    return a and a['stable'] and not a['errors'] and a.get('sha256') and any(old.get('sha256')==a['sha256'] and old.get('errors') for old in previous_artifacts.get(artifact,[]))
   if not (request['groups']&bad_groups) and request['artifacts'] and all(same_bytes_recovered(a) for a in request['artifacts']):request['status']='superseded_artifact_uncertainty_by_complete_read';request['reason']='same_source_bytes_successfully_reparsed_with_complete_event_history'
 # A corrupt/actively changing history is not a zero-call observation. Reserve
 # at least one uncertain request per affected original work group, without
 # multiplying the same uncertainty by its mirrored files.
 uncertain_groups=collections.defaultdict(set)
 for problem in collector.problems:
  if problem.get('group'):uncertain_groups[problem['group']].add(problem.get('artifact','metadata'))
 for artifact in collector.artifacts:
  if not artifact['stable']:uncertain_groups[artifact['group']].add(artifact['artifact'])
 for group,artifacts in uncertain_groups.items():
  if not any(group in r['groups'] and r['status']=='unresolved' for r in requests.values()):
   key='artifact_unknown:'+sha(group.encode());requests[key]={'request_key':key,'session_id':None,'turn':None,'step':None,'attempt':None,'groups':{group},'artifacts':artifacts,'evidence_types':{'missing_corrupt_or_changing_history'},'response_keys':set(),'first_time':None,'status':'unresolved','reason':'history_artifact_could_hide_an_upstream_request','gateway_request_key':None}
 samples=collections.defaultdict(lambda:{'confirmed_calls':0,'unknown_reservations':0,'unknown_usage':False,'coverage_complete_for_id':True,'response_keys':[],'request_keys':[],'covered_gateway_request_keys':[],'tokens':{k:0 for k in TOKEN_FIELDS},'attribution':set()});global_tokens={k:0 for k in TOKEN_FIELDS};unattributed=[]
 def ids_for(groups):
  identities=[collector.group_identity.get(g,{}) for g in groups];ids=set(x for i in identities for x in i.get('original_ids',[]));uncertain=any(i.get('ambiguous') or i.get('kind')=='unresolved_history_identity' for i in identities);return ids,uncertain
 for key,row in responses.items():
  if row['status']=='superseded_aggregate_by_response':continue
  ids,ambiguous=ids_for(row['groups']);row['original_ids']=sorted(ids);row['identity_ambiguous']=ambiguous
  for k in TOKEN_FIELDS:global_tokens[k]+=row['usage'].get(k) or 0
  if not ids:unattributed.append({'response_key':key,'reason':'explicit_non_dataset_control_probe','status':row['status']})
  for id in ids:
   sample=samples[id];sample['response_keys'].append(key);sample['attribution'].update(collector.group_identity[g]['kind'] for g in row['groups'] if g in collector.group_identity)
   if row['status']=='confirmed':sample['confirmed_calls']+=1
   else:sample['unknown_reservations']+=1
   sample['unknown_usage']|=row['usage'].get('usage_unknown',True) or row['usage_conflict'] or row['status']!='confirmed';sample['coverage_complete_for_id']&=not ambiguous and row['status']!='aggregate_only_unknown_call_multiplicity'
   for k in TOKEN_FIELDS:sample['tokens'][k]+=row['usage'].get(k) or 0
   if row.get('gateway_request_key'):sample['covered_gateway_request_keys'].append(row['gateway_request_key'])
 for key,row in requests.items():
  ids,ambiguous=ids_for(row['groups']);row['original_ids']=sorted(ids);row['identity_ambiguous']=ambiguous
  if row['status']!='unresolved':continue
  if not ids:unattributed.append({'request_key':key,'reason':'non_dataset_control_or_unmapped','status':row['status']})
  for id in ids:
   sample=samples[id];sample['unknown_reservations']+=1;sample['unknown_usage']=True;sample['request_keys'].append(key);sample['coverage_complete_for_id']&=not ambiguous
 for problem in collector.problems:
  group=problem.get('group');identity=collector.group_identity.get(group,{})
  for id in identity.get('original_ids',[]):samples[id]['coverage_complete_for_id']=False;samples[id]['unknown_usage']=True
 for artifact in collector.artifacts:
  if not artifact['stable']:
   for id in collector.group_identity.get(artifact['group'],{}).get('original_ids',[]):samples[id]['coverage_complete_for_id']=False;samples[id]['unknown_usage']=True
 # Include every current original sample, so a genuine scanned/no-evidence zero
 # is distinguishable from a missing or unfinished ledger import.
 for id in jobs:samples[id]
 identity_gaps=sorted({group for row in list(responses.values())+[r for r in requests.values() if r['status']=='unresolved'] for group in row['groups'] if collector.group_identity.get(group,{}).get('kind')=='unresolved_history_identity'})
 manifest=sorted((a['artifact'],a.get('sha256'),a['size'],a['stable']) for a in collector.artifacts);snapshot=sha(json.dumps({'policy':POLICY,'artifacts':manifest,'response_keys':sorted(responses),'request_states':sorted((k,r['status']) for k,r in requests.items())},sort_keys=True).encode());blocked_count=sum(r['status']=='blocked_local' for r in requests.values());exhausted=[]
 for id,sample in samples.items():
  job=jobs.get(id,{});sample['original_id']=id;sample['history_snapshot_id']=snapshot;sample['max_calls']=MAX_CALLS;sample['coverage_complete_for_id']&=inventory_complete and not identity_gaps;sample['calls_lower_bound']=sample['confirmed_calls']+sample['unknown_reservations'];sample['conservative_budget_used']=sample['calls_lower_bound'] if sample['coverage_complete_for_id'] else max(MAX_CALLS,sample['calls_lower_bound']);sample['remaining_calls']=max(0,MAX_CALLS-sample['conservative_budget_used']);sample['current_job_state']=job.get('state','not_in_current_jobs');sample['quality_state']=job.get('quality_state');sample['current_failure_reason']=safe_error(job.get('error'));sample['processing_outcome']=job.get('processing_outcome','pending');sample['qualified']=bool(job.get('qualified'));sample['current_code_sha256']=job.get('code_sha256');sample['current_image_sha256']=job.get('image_sha256');sample['same_revision_failed_qa']=job.get('same_revision_failed_qa',[]);sample['attribution']=sorted(sample['attribution']);sample['unknown_usage']|=not sample['coverage_complete_for_id'];sample['eligible_for_new_call']=bool(sample['coverage_complete_for_id'] and not sample['unknown_usage'] and sample['remaining_calls'] and job and not sample['qualified']);sample['denial_reasons']=[]
  if sample['conservative_budget_used']>=MAX_CALLS:sample['denial_reasons'].append('lifetime_original_sample_model_call_limit_reached')
  if sample['unknown_usage']:sample['denial_reasons'].append('unknown_historical_usage_or_call_multiplicity')
  if not sample['coverage_complete_for_id']:sample['denial_reasons'].append('historical_coverage_incomplete_for_original_id')
  if not job:sample['denial_reasons'].append('external_or_no_current_job')
  if sample['qualified']:sample['denial_reasons'].append('already_qualified')
  if sample['calls_lower_bound']>=2 and not sample['qualified']:exhausted.append({'id':id,'confirmed_calls':sample['confirmed_calls'],'unknown_reservations':sample['unknown_reservations'],'quality_state':sample['quality_state'],'job_state':sample['current_job_state'],'processing_outcome':sample['processing_outcome'],'current_code_sha256':sample['current_code_sha256'],'current_image_sha256':sample['current_image_sha256'],'same_revision_failed_qa':sample['same_revision_failed_qa'],'failure_reason':sample['current_failure_reason'],'denial_reasons':sample['denial_reasons']})
 summary={'history_snapshot_id':snapshot,'created_at':now(),'policy':POLICY,'inventory_complete':inventory_complete,'artifact_versions':len(collector.artifacts),'unique_events':len(collector.events),'unique_responses':sum(r['status']!='superseded_aggregate_by_response' for r in responses.values()),'confirmed_response_calls':sum(r['status']=='confirmed' for r in responses.values()),'aggregate_only_unknown_multiplicity':sum(r['status']=='aggregate_only_unknown_call_multiplicity' for r in responses.values()),'unknown_response_usage':sum(r['status']=='unknown_response_usage' for r in responses.values()),'unresolved_request_reservations':sum(r['status']=='unresolved' for r in requests.values()),'proven_blocked_local_requests':blocked_count,'proven_blocked_local_receipts':len(collector.blocked),'retry_scheduled':reconciled['retry_scheduled'],'retry_started':reconciled['retry_started'],'historical_unique_response_tokens':global_tokens,'historical_unique_response_token_sum':sum(global_tokens.values()),'reasoning_accounting':'Output includes reasoning; never add reasoning again. A separate reasoning split is nullable when the provider did not report it.','sample_rows':len(samples),'samples_with_model_evidence':sum(s['conservative_budget_used']>0 for s in samples.values()),'at_least_two_unqualified_samples':len(exhausted),'unattributed_control_observations':unattributed,'aggregate_usage_cross_checks':{'checked':len(reconciled['aggregate_checks']),'mismatches':sum(r['usage_matches_responses'] is False for r in reconciled['aggregate_checks'])},'source_read_problems':collector.problems,'event_type_counts':dict(collector.event_type_counts)}
 summary.update(identity_coverage_complete=not identity_gaps,unresolved_identity_groups=identity_gaps,usage_accounting_complete=not any(s['unknown_usage'] for s in samples.values()),new_model_calls_performed=0,original_histories_jobs_and_outcomes_modified=False)
 db.execute('begin immediate')
 def serial(row):return json.dumps({k:sorted(v) if isinstance(v,set) else v for k,v in row.items()},sort_keys=True)
 for a in collector.artifacts:db.execute('insert or replace into artifact_versions values(?,?,?)',(a['artifact'],a.get('sha256') or 'presence_only',serial(a)))
 for key,row in collector.events.items():db.execute('insert or replace into event_observations values(?,?)',(key,serial(row)))
 for key,row in responses.items():db.execute('insert or replace into responses values(?,?)',(key,serial(row)))
 for key,row in requests.items():db.execute('insert or replace into request_reservations values(?,?)',(key,serial(row)))
 for id,row in samples.items():db.execute('insert or replace into sample_totals values(?,?)',(id,serial(row)))
 db.execute('insert or replace into imports values(?,?,?,?,?)',(snapshot,summary['created_at'],POLICY,int(inventory_complete),json.dumps(summary,sort_keys=True)));db.execute('insert or replace into ledger_state values("latest_snapshot",?)',(snapshot,));db.execute('insert or replace into ledger_state values("group_identity",?)',(json.dumps(collector.group_identity,sort_keys=True),));db.commit();db.close();return summary,exhausted


def lookup_sample_budget(original_id,db_path=DEFAULT_DB,request_keys=None):
 denied={'original_id':original_id,'history_snapshot_id':None,'max_calls':2,'confirmed_calls':None,'unknown_reservations':None,'conservative_budget_used':2,'eligible_for_new_call':False,'remaining_calls':0,'coverage_complete_for_id':False,'unknown_usage':True,'covered_gateway_request_keys':[]}
 try:
  db=sqlite3.connect('file:'+str(Path(db_path).resolve())+'?mode=ro',uri=True);latest=db.execute('select value from ledger_state where key="latest_snapshot"').fetchone();row=db.execute('select record_json from sample_totals where original_id=?',(original_id,)).fetchone();db.close()
  if not latest or not row:return denied
  value=json.loads(row[0])
  if value.get('history_snapshot_id')!=latest[0]:return denied
  if request_keys is not None:value['covered_gateway_request_keys']=sorted(set(value.get('covered_gateway_request_keys',[]))&set(request_keys))
  return value
 except (OSError,sqlite3.Error,ValueError):return denied


def load_jobs(root):
 db=sqlite3.connect('file:'+str(root/'conversion/jobs.sqlite')+'?mode=ro',uri=True);sql='''select id,state,error,json_extract(input_record,'$.image_sha256'),json_extract(input_record,'$.code_sha256'),json_extract(output_record,'$.quality_state'),json_extract(output_record,'$.code_sha256'),json_extract(output_record,'$.image_sha256') from jobs''';rows={id:{'state':state,'error':error,'source_image_sha256':image,'source_code_sha256':code,'quality_state':quality,'code_sha256':current_code,'image_sha256':current_image,'qualified':False,'processing_outcome':'pending','same_revision_failed_qa':[]} for id,state,error,image,code,quality,current_code,current_image in db.execute(sql)}
 exists=lambda table:db.execute('select 1 from sqlite_master where type="table" and name=?',(table,)).fetchone() is not None
 if exists('processing_outcomes_v2'):
  for id,status,reason,raw in db.execute('select id,status,reason,record from processing_outcomes_v2'):
   if id not in rows:continue
   rows[id]['processing_outcome']=status
   if status=='qualified' and raw:
    proof=json.loads(raw);rows[id]['qualified']=proof.get('code_sha256')==rows[id]['code_sha256'] and proof.get('image_sha256')==rows[id]['image_sha256'] and bool(proof.get('automatic_quality_policy'))
 if exists('auto_quality_audits_v1'):
  for id,code,image,policy,state,raw,at in db.execute('''select q.id,q.code_hash,q.image_hash,q.policy,q.state,q.record,q.updated_at from auto_quality_audits_v1 q join jobs j on j.id=q.id where q.code_hash=json_extract(j.output_record,'$.code_sha256') and q.image_hash=json_extract(j.output_record,'$.image_sha256')'''):
   report=json.loads(raw) if raw else {};failures=report.get('failures') or []
   if state in ('repair_required','failed','rejected') or failures:rows[id]['same_revision_failed_qa'].append({'policy':policy,'state':state,'at':at,'code_sha256':code,'image_sha256':image,'failures':[safe_error(x) for x in failures],'current_v3_policy':policy=='source_execution_glyph_lineage_native_render_and_local_fidelity_v3' or policy.startswith('source_execution_glyph_lineage_native_render_and_local_fidelity_v3:')})
 db.close();return rows


def write_reports(root,collector,reconciled,summary,exhausted):
 directory=Path(root)/'conversion/model_history_ledger_v1';directory.mkdir(exist_ok=True)
 for filename,value in [('summary.json',summary),('at_least_two_unqualified.json',exhausted),('budget_exhausted_current_failed_qa.json',[r for r in exhausted if r['same_revision_failed_qa']]),('budget_exhausted_current_v3_failed_qa.json',[r for r in exhausted if any(q['current_v3_policy'] for q in r['same_revision_failed_qa'])]),('budget_exhausted_no_current_qa_pending.json',[r for r in exhausted if not r['same_revision_failed_qa']]),('aggregate_cross_checks.json',reconciled['aggregate_checks']),('identity_map.json',collector.group_identity)]:
  (directory/filename).write_text(json.dumps(value,indent=2)+'\n')


def main(args):
 root=Path(args.root).resolve();jobs=load_jobs(root);resolver=IdentityResolver(root,jobs);collector=Collector();roots=[root/'conversion/harness_sessions',root/'evaluation']
 for base in (root,root/'conversion'):
  roots.extend(p for p in base.iterdir() if p.is_dir() and any(t in p.name.lower() for t in ('manual','deepseek','harness')) and p not in roots and p.name!='harness_sessions')
 print(json.dumps({'stage':'history_import_started','roots':list(map(str,roots)),'jobs':len(jobs),'no_network_or_model_calls':True}),flush=True);scan_paths(collector,roots,resolver)
 if args.local_snapshot:collector.merge(json.loads(Path(args.local_snapshot).read_bytes()))
 directory=root/'conversion/model_history_ledger_v1';directory.mkdir(exist_ok=True)
 # Sanitized metadata only: retain an exact replay input before reconciliation,
 # so parser defects never require reading compressed SDK history again.
 (directory/'scanned_metadata.json').write_text(json.dumps(collector.serialize(),separators=(',',':'))+'\n')
 reconciled=reconcile(collector);summary,exhausted=persist(args.db,collector,reconciled,jobs,inventory_complete=True);write_reports(root,collector,reconciled,summary,exhausted);print(json.dumps({k:v for k,v in summary.items() if k not in ('event_type_counts','source_read_problems','unattributed_control_observations')}),flush=True)


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(ROOT));parser.add_argument('--db',default=DEFAULT_DB);parser.add_argument('--local-snapshot');main(parser.parse_args())
