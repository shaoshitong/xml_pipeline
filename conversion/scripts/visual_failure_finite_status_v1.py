import argparse,datetime,hashlib,json,os,pathlib,re,sys
R=pathlib.Path('/backup/shaoshitong/img2code_20261029');B=R/'conversion/prototype/visual_failure_certificate_v1'
parser=argparse.ArgumentParser(description='Read-only finite visual collector status; never starts a worker or writer.');parser.add_argument('--run-id',default='ef0f5d5590304eaba639d22203838158');args=parser.parse_args();rid=args.run_id;assert re.fullmatch('[0-9a-f]{32}',rid);run=B/'finite_runs'/rid
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def proc(pid):
 try:
  t=pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split();cmd=pathlib.Path('/proc',str(pid),'cmdline').read_bytes().decode(errors='replace').split('\0');return {'pid':pid,'start_ticks':int(t[19]),'ppid':int(t[1]),'state':t[0],'command':cmd}
 except OSError:return None
out={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_id':rid,'run':str(run),'read_only':True,'writer_called':False,'api_calls':0}
ownerpath=run/'owner.json';p=run/'progress.json'
if not ownerpath.exists() or not p.exists():
 launch=json.loads((B/'finite_launch_receipts'/(rid+'.json')).read_bytes());actual=proc(launch['pid']);mpath=run/'manifest.json';mraw=mpath.read_bytes() if mpath.exists() else b'';manifest=json.loads(mraw) if mraw else {}
 out.update(state='initializing',owner_exists=ownerpath.exists(),progress_exists=p.exists(),case_state_records=len(list((run/'cases').glob('*/state.json'))),actual_owner=actual,owner_birth_matches=bool(actual and actual['start_ticks']==launch['start_ticks']),manifest_count=len(manifest.get('items',[])),manifest_sha256=sha(mraw) if mraw else None);print(json.dumps(out));sys.exit(0)
owner=json.loads(ownerpath.read_bytes());progress=json.loads(p.read_bytes());mraw=(run/'manifest.json').read_bytes();manifest=json.loads(mraw);assert sha(mraw)==owner['manifest']['sha256'] and manifest['count']==1730
states=[];missing=[]
for item in manifest['items']:
 q=run/'cases'/item['id']/'state.json'
 if q.is_file():s=json.loads(q.read_bytes());assert s['id']==item['id'] and s['attempts_this_run']<=1;states.append(s)
 else:missing.append(item['id'])
counts={}
for s in states:counts[s['state']]=counts.get(s['state'],0)+1
actualowner=proc(owner['owner']['pid']);workers=[]
for pid,record in progress['workers'].items():
 current=proc(int(pid));workers.append({'declared':record['worker'],'actual':current,'same_birth':bool(current and current['start_ticks']==record['worker']['start_ticks']),'child_of_owner':bool(current and current['ppid']==owner['owner']['pid'])})
finished=[s for s in states if s['state'] not in ('queued','scheduled','running')];effective=[s for s in finished if s.get('effective_proposal')];cleanup_errors=[];live_owned=[]
for s in finished:
 ex=s.get('outer_execution')
 if ex and (not ex.get('cleanup_complete') or s.get('matching_live_owned_births')):cleanup_errors.append(s['id'])
 if ex:
  for q in ex.get('tracked_processes',[]):
   c=proc(q['pid'])
   if c and c['start_ticks']==q['start_ticks']:live_owned.append({'id':s['id'],'process':c})
out.update(owner=owner['owner'],actual_owner=actualowner,owner_birth_matches=bool(actualowner and actualowner['start_ticks']==owner['owner']['start_ticks']),manifest_sha256=sha(mraw),manifest_count=len(manifest['items']),format_counts=manifest['format_counts'],implementation=manifest['implementation'],coverage_records=len(states),missing_coverage=missing,counts=counts,finished=len(finished),effective_proposals=len(effective),attempted_unique=sum(s['attempts_this_run'] for s in states),max_attempts=max(s['attempts_this_run'] for s in states),workers=workers,worker_count=len(workers),drain_reason=progress['drain_reason'],final=progress['final'],retained=progress['retained'],outer_cleanup_errors=cleanup_errors,matching_live_finished_case_births=live_owned,progress_at=progress['at'])
folder=run/'readonly_status';folder.mkdir(exist_ok=True);path=folder/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'.json');path.write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));print('receipt',str(path),'sha256',sha(path.read_bytes()))
