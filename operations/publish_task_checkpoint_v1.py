"""Persist current source-bound delivery, runtime and audit receipts in Git."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess
W=Path(__file__).resolve().parents[2];repo=W/'work/xml_pipeline';O=W/'outputs';ops=repo/'operations'
p=argparse.ArgumentParser();p.add_argument('--source',action='append',default=[]);p.add_argument('--receipt',action='append',default=[])
for name in ['delivery','publication','runtime','scope','payload']:p.add_argument('--'+name,required=True)
p.add_argument('--next-step',required=True);a=p.parse_args()
names=a.source;remote=[]
if names:
 assert all(Path(n).name==n and n.endswith('.py')for n in names)
 code="from pathlib import Path\nimport json,hashlib\nS=Path('/backup/shaoshitong/img2code_20261029/conversion/scripts')\nresult=[]\nfor name in "+repr(names)+":\n p=S/name;b=p.read_bytes();p.chmod(0o444);result.append(dict(file='conversion/scripts/'+name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=p.stat().st_mtime_ns))\nprint(json.dumps(result))"
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,check=True,timeout=30);remote=json.loads(r.stdout)
 for entry,name in zip(remote,names):
  source=W/'work/catalog_refresh'/name;assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['sha256'];target=repo/entry['file']
  if target.exists():assert target.read_bytes()==source.read_bytes()
  else:shutil.copyfile(source,target)
refs={k:getattr(a,k)for k in ['delivery','publication','runtime','scope','payload']};values={k:json.loads((O/v).read_text())for k,v in refs.items()}
delivery=values['delivery'];publication=values['publication']['publication'];runtime=values['runtime'];scope=values['scope'];payload=values['payload']
assert publication['main']['rows']==delivery['curation_memberships']['complex_paper_diagrams_and_posters']
assert payload['source_pairs']==delivery['pairs']and payload['counts']==dict(payload_valid=delivery['unique_code_RGBA_pairs'])
files=set(a.receipt)|set(refs.values())|{'CURATED_RESEARCH_DELIVERY.md'}
for name in files:
 assert Path(name).name==name and(O/name).stat().st_size>0;target=ops/name
 if target.exists()and name!='CURATED_RESEARCH_DELIVERY.md':assert target.read_bytes()==(O/name).read_bytes(),name
 else:shutil.copyfile(O/name,target)
for name in ['snapshot_current_batch_runtime_v2.py',Path(__file__).name]:shutil.copyfile(W/'work/takeover'/name,ops/name)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
for name in ['CURRENT_HANDOFF.json','CURRENT_RELEASE.json']:
 target=ops/name;x=json.loads(target.read_text());x.update(at_utc=now,strict_main_rows=publication['main']['rows'],authoritative_main=publication['main'],curated_delivery=delivery,latest_actual_PNG_publication=values['publication'],latest_runtime_progress=runtime,seven_source_delivery_audit=scope,curated_payload_audit=payload,review_registry=runtime['review_registry'],pending_reviews=runtime['review_registry'].get('await_actual_PNG_review',0),goal_complete=False,next_step=a.next_step)
 if scope.get('all_approved_disjoint_masses'):x['all_approved_disjoint_masses']=scope['all_approved_disjoint_masses']
 target.write_text(json.dumps(x,indent=2)+'\n')
for name in ['SOURCE_MANIFEST.json','REMOTE_SOURCE_MANIFEST.json']:
 target=repo/name;m=json.loads(target.read_text());entries={r['file']:r for r in m['files']};entries.update({r['file']:r for r in remote})
 if name=='SOURCE_MANIFEST.json':
  for f in ops.rglob('*'):
   if f.is_file():b=f.read_bytes();entries[str(f.relative_to(repo))]=dict(file=str(f.relative_to(repo)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=f.stat().st_mtime_ns)
 m.update(at_utc=now,files=list(entries.values()));target.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(source_files_verified=len(remote),strict_main=publication['main']['rows'],curated_delivery=delivery['unique_code_RGBA_pairs'],all_curated_payloads_audited=True,goal_complete=False)))
