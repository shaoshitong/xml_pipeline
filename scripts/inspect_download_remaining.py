#!/usr/bin/env python3
"""Read-only five-run download inventory/manifest accounting; metadata stdout only.
No raw/media traversal, body reads, downloads, hashes, or process operations.
Remaining bytes include unverified partial files at their full inventory size.
"""
import argparse,collections,datetime,json,re,tempfile
from pathlib import Path
RUNS=('priority','bulk','rap','extra','omni_i2c')
GOOD={'complete','already_complete'}


def load(path,default,issues):
 try:return json.loads(path.read_text())
 except (OSError,ValueError) as exc:issues.append({'path':str(path),'error_type':type(exc).__name__});return default

def logical(record,repo=None):return (record.get('repo_id') or repo,record.get('path'))
def immutable(record,repo=None,revision=None):return (*logical(record,repo),record.get('revision') or revision)
def size(record):
 value=record.get('expected_size',record.get('size',0))
 return value if isinstance(value,int) and value>=0 else 0

def error_type(record):
 value=str(record.get('error') or record.get('reason') or 'unknown')
 return re.split(r'[:(\s]',value,1)[0][:80] or 'unknown'

def key_info(key):return {'repo_id':key[0],'path':key[1],'revision':key[2]}

def summarize(root,runs,top_files=3,duplicate_examples=20):
 issues=[];planned={};locations=collections.defaultdict(list);per_run={};complete=set();manifest_occurrences=collections.defaultdict(list);manifest_unplanned=[];failure_records=[];discovery_failures=[];inventory_conflicts=[];logical_keys=collections.defaultdict(set);completion_candidates=collections.defaultdict(list);run_task_maps={}
 for name in runs:
  folder=root if name=='priority' else root/'runs'/name
  inventory=load(folder/'download_inventory.json',[],issues);manifest=load(folder/'download_manifest.json',{},issues);failures=load(folder/'download_failures.json',[],issues)
  if not isinstance(inventory,list) or not isinstance(manifest,dict) or not isinstance(failures,list):issues.append({'run':name,'error_type':'unexpected_metadata_schema'});continue
  run_tasks={};entry_count=0;entry_bytes=0;inv_duplicates=collections.Counter();logical_revisions=collections.defaultdict(set)
  for repo in inventory:
   for task in repo.get('files',[]):
    entry_count+=1;entry_bytes+=size(task);key=immutable(task,repo.get('repo_id'),repo.get('revision'))
    if not key[0] or not key[1]:issues.append({'run':name,'error_type':'inventory_key_missing'});continue
    inv_duplicates[key]+=1;locations[key].append(name);logical_keys[key[:2]].add(key[2]);logical_revisions[key[:2]].add(key[2])
    record={**task,'repo_id':key[0],'path':key[1],'revision':key[2],'expected_size':size(task)}
    if key in planned and (planned[key]['expected_size']!=record['expected_size'] or (planned[key].get('lfs_sha256') and record.get('lfs_sha256') and planned[key]['lfs_sha256']!=record['lfs_sha256'])):
     inventory_conflicts.append({**key_info(key),'runs':sorted(set(locations[key])),'expected_sizes':[planned[key]['expected_size'],record['expected_size']],'lfs_hash_conflict':planned[key].get('lfs_sha256')!=record.get('lfs_sha256')})
     # Use the larger size for an explicit upper-bound accounting under conflict.
     record['expected_size']=max(planned[key]['expected_size'],record['expected_size'])
    if key in planned and not record.get('lfs_sha256') and planned[key].get('lfs_sha256'):record['lfs_sha256']=planned[key]['lfs_sha256']
    planned[key]=record;run_tasks[key]=record
  run_good=set();run_manifest_keys=collections.Counter();invalid_complete=[]
  def resolve(record):
   key=immutable(record)
   if key[2] is None and len(logical_revisions.get(key[:2],()))==1:key=(*key[:2],next(iter(logical_revisions[key[:2]])))
   return key
  for record in manifest.get('files',[]):
   key=resolve(record);run_manifest_keys[key]+=1;manifest_occurrences[key].append({'run':name,'status':record.get('status')})
   if key not in run_tasks:
    if len(manifest_unplanned)<duplicate_examples:manifest_unplanned.append({'run':name,**key_info(key),'status':record.get('status')})
    continue
   if record.get('status') in GOOD:
    completion_candidates[key].append({'run':name,'record':record})
    expected=run_tasks[key]
    valid=size(record)==expected['expected_size'] and (not expected.get('lfs_sha256') or record.get('sha256')==expected['lfs_sha256'])
    if valid:run_good.add(key);complete.add(key)
    else:invalid_complete.append({**key_info(key),'recorded_bytes':size(record),'inventory_bytes':expected['expected_size'],'hash_matches':not expected.get('lfs_sha256') or record.get('sha256')==expected['lfs_sha256']})
   elif record.get('status')=='failed':failure_records.append({'run':name,'origin':'manifest','key':key,'error_type':error_type(record)})
  for record in failures:
   if record.get('stage')=='discovery' or not record.get('path'):
    discovery_failures.append({'run':name,'repo_id':record.get('repo_id'),'stage':record.get('stage'),'error_type':error_type(record)});continue
   failure_records.append({'run':name,'origin':'failure_list','key':resolve(record),'error_type':error_type(record)})
  run_task_maps[name]=run_tasks
  remaining=set(run_tasks)-run_good
  per_run[name]={'inventory_folder':str(folder),'manifest_updated_at':manifest.get('updated_at'),'manifest_finished':manifest.get('finished',False),'inventory_entry_count':entry_count,'inventory_entry_bytes':entry_bytes,'unique_planned_files':len(run_tasks),'planned_bytes':sum(x['expected_size'] for x in run_tasks.values()),'recorded_complete_files':len(run_good),'recorded_complete_bytes':sum(run_tasks[x]['expected_size'] for x in run_good),'remaining_files':len(remaining),'remaining_bytes':sum(run_tasks[x]['expected_size'] for x in remaining),'duplicate_inventory_key_count':sum(x>1 for x in inv_duplicates.values()),'duplicate_manifest_key_count':sum(x>1 for x in run_manifest_keys.values()),'invalid_complete_records':invalid_complete[:duplicate_examples]}
 conflicted_keys={(x['repo_id'],x['path'],x['revision']) for x in inventory_conflicts}
 complete.clear();global_run_good=collections.defaultdict(set);invalid_global_completion=[]
 for key,evidence in completion_candidates.items():
  if key not in planned:continue
  expected=planned[key]
  for entry in evidence:
   record=entry['record'];valid=key not in conflicted_keys and size(record)==expected['expected_size'] and (not expected.get('lfs_sha256') or record.get('sha256')==expected['lfs_sha256'])
   if valid:complete.add(key);global_run_good[entry['run']].add(key)
   elif len(invalid_global_completion)<duplicate_examples:invalid_global_completion.append({'run':entry['run'],**key_info(key),'recorded_bytes':size(record),'inventory_bytes':expected['expected_size'],'known_lfs_hash_matches':not expected.get('lfs_sha256') or record.get('sha256')==expected['lfs_sha256'],'inventory_conflicted':key in conflicted_keys})
 for name,run_tasks in run_task_maps.items():
  good=global_run_good[name];remaining_keys=set(run_tasks)-good
  per_run[name].update({'recorded_complete_files':len(good),'recorded_complete_bytes':sum(run_tasks[key]['expected_size'] for key in good),'remaining_files':len(remaining_keys),'remaining_bytes':sum(run_tasks[key]['expected_size'] for key in remaining_keys)})
 failures_by_key={}
 for record in failure_records:
  key=record['key'];entry=failures_by_key.setdefault(key,{**key_info(key),'runs':set(),'origins':set(),'error_types':set(),'recorded_complete_elsewhere_or_later':key in complete,'planned_key':key in planned})
  entry['runs'].add(record['run']);entry['origins'].add(record['origin']);entry['error_types'].add(record['error_type'])
 for entry in failures_by_key.values():
  for field in ('runs','origins','error_types'):entry[field]=sorted(entry[field])
 repos=[]
 for repo in sorted({key[0] for key in planned}):
  keys={key for key in planned if key[0]==repo};good=keys&complete;remaining=keys-good
  largest=sorted(remaining,key=lambda key:planned[key]['expected_size'],reverse=True)[:top_files]
  repo_failures=[entry for key,entry in failures_by_key.items() if key[0]==repo]
  repos.append({'repo_id':repo,'runs':sorted({name for key in keys for name in locations[key]}),'revisions':sorted({key[2] for key in keys if key[2] is not None}),'planned_files':len(keys),'planned_bytes':sum(planned[key]['expected_size'] for key in keys),'complete_files':len(good),'complete_bytes':sum(planned[key]['expected_size'] for key in good),'remaining_files':len(remaining),'remaining_bytes':sum(planned[key]['expected_size'] for key in remaining),'failed_paths':repo_failures,'largest_remaining_files':[{**key_info(key),'expected_size':planned[key]['expected_size']} for key in largest]})
 repos.sort(key=lambda row:(-row['remaining_bytes'],-row['remaining_files'],row['repo_id']))
 duplicates=[{**key_info(key),'inventory_occurrences':len(names),'runs':sorted(set(names))} for key,names in locations.items() if len(names)>1]
 manifest_duplicates=[{**key_info(key),'manifest_occurrences':len(records),'runs':sorted({x['run'] for x in records}),'statuses':sorted({str(x['status']) for x in records})} for key,records in manifest_occurrences.items() if len(records)>1]
 revision_conflicts=[{'repo_id':key[0],'path':key[1],'revisions':sorted(str(x) for x in values)} for key,values in logical_keys.items() if len(values)>1]
 remaining=set(planned)-complete
 totals={'unique_immutable_planned_keys':len(planned),'unique_logical_repo_path_keys':len(logical_keys),'unique_manifest_immutable_keys':len(manifest_occurrences),'duplicate_manifest_immutable_keys':len(manifest_duplicates),'cross_run_duplicate_manifest_keys':sum(len(x['runs'])>1 for x in manifest_duplicates),'recorded_complete_immutable_keys':len(complete&set(planned)),'remaining_immutable_keys':len(remaining),'planned_bytes':sum(x['expected_size'] for x in planned.values()),'recorded_complete_bytes':sum(planned[key]['expected_size'] for key in complete if key in planned),'remaining_bytes':sum(planned[key]['expected_size'] for key in remaining),'global_inventory_entries':sum(row['inventory_entry_count'] for row in per_run.values()),'duplicate_immutable_inventory_keys':len(duplicates),'duplicate_inventory_extra_occurrences':sum(x['inventory_occurrences']-1 for x in duplicates),'cross_run_duplicate_immutable_keys':sum(len(x['runs'])>1 for x in duplicates),'logical_keys_with_multiple_revisions':len(revision_conflicts),'inventory_size_or_hash_conflicts':len(inventory_conflicts),'unique_failure_keys':len(failures_by_key),'unresolved_failed_planned_keys':sum(key in planned and key not in complete for key in failures_by_key)}
 return {'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'read_only_metadata_probe':True,'runs':per_run,'totals':totals,'repositories':repos,'duplicate_inventory_key_examples':duplicates[:duplicate_examples],'duplicate_manifest_key_examples':manifest_duplicates[:duplicate_examples],'revision_conflict_examples':revision_conflicts[:duplicate_examples],'inventory_conflict_examples':inventory_conflicts[:duplicate_examples],'invalid_global_completion_examples':invalid_global_completion,'unplanned_manifest_key_examples':manifest_unplanned,'discovery_failures':discovery_failures,'metadata_read_issues':issues,'accounting_notes':['Primary global key is (repo_id,path,revision), with (repo_id,path) revision collisions reported separately. Duplicated run entries are counted once globally.','A known consistent LFS SHA is preserved across duplicate inventories, even when another run omits it; all completion evidence is rechecked against the final global inventory.',
 'Complete means a matching current manifest completion status, expected size and available LFS digest; no source media file was read or rehashed.','Inventory size/hash conflicts conservatively remove the affected key from global complete accounting until reconciled.',
 'Remaining bytes count every not-yet-recorded-complete file at full inventory size, including already-saved partial bytes. They are an upper bound on future network transfer.','A restarted resume-inventory run may temporarily republish only newly reverified completion records. These figures describe the five current metadata snapshots, not a raw-disk existence scan.','Inventory, manifest and failure files are atomically replaced separately while jobs run; small cross-file snapshot races and resolved stale failure entries are reported explicitly.']}


def self_test():
 with tempfile.TemporaryDirectory(prefix='download-metadata-fixture-') as directory:
  root=Path(directory)
  def write(run,inventory,files,failures=()):
   folder=root if run=='priority' else root/'runs'/run;folder.mkdir(parents=True,exist_ok=True);(folder/'download_inventory.json').write_text(json.dumps(inventory));(folder/'download_manifest.json').write_text(json.dumps({'finished':False,'files':files}));(folder/'download_failures.json').write_text(json.dumps(list(failures)))
  first={'repo_id':'owner/repo','revision':'commit1','path':'a.parquet','expected_size':10,'lfs_sha256':'a'*64};second={**first,'path':'b.parquet','expected_size':20,'lfs_sha256':None}
  write('priority',[{'repo_id':'owner/repo','revision':'commit1','files':[first]}],[{**first,'status':'complete','sha256':'a'*64}])
  write('bulk',[{'repo_id':'owner/repo','revision':'commit1','files':[first,second,second]}],[{**first,'status':'already_complete','sha256':'a'*64},{**second,'status':'failed','error':'ReadTimeout: detail'}],[{**second,'status':'failed','error':'ReadTimeout: detail'}])
  result=summarize(root,('priority','bulk'))
  assert result['totals']['unique_immutable_planned_keys']==2 and result['totals']['planned_bytes']==30
  assert result['totals']['recorded_complete_bytes']==10 and result['totals']['remaining_bytes']==20
  assert result['totals']['cross_run_duplicate_immutable_keys']==1 and result['totals']['duplicate_inventory_extra_occurrences']==2
  assert result['repositories'][0]['failed_paths'][0]['path']=='b.parquet' and len(result['repositories'][0]['failed_paths'])==1
  assert not result['metadata_read_issues']
  # An omitted digest in another run cannot erase known SHA evidence, in either run order.
  write('priority',[{'repo_id':'owner/repo','revision':'commit1','files':[first]}],[])
  unknown={**first,'lfs_sha256':None};write('bulk',[{'repo_id':'owner/repo','revision':'commit1','files':[unknown]}],[{**unknown,'status':'complete','sha256':'b'*64}])
  for order in [('priority','bulk'),('bulk','priority')]:
   probe=summarize(root,order);assert probe['totals']['recorded_complete_immutable_keys']==0 and probe['totals']['remaining_bytes']==10;assert probe['invalid_global_completion_examples']
 print('{"self_test":"passed","checks":["deduplicated global repo/path/revision accounting","within/cross-run duplicate keys","complete versus remaining sizes","failure-list and manifest failure union","known LFS proof survives unknown duplicate inventory in either run order"]}')

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path);parser.add_argument('--runs',nargs='+',default=list(RUNS));parser.add_argument('--top-files',type=int,default=3);parser.add_argument('--duplicate-examples',type=int,default=20);parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
 if args.self_test:self_test()
 elif args.root:print(json.dumps(summarize(args.root.resolve(),args.runs,args.top_files,args.duplicate_examples),ensure_ascii=False),flush=True)
 else:parser.error('--root required')
