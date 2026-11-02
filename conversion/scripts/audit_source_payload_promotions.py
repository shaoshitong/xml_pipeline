import json,sqlite3,hashlib
from pathlib import Path
from native_worker import R,W,now
from harness_source_provenance import validate_frozen
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);owner=json.loads((W/'source_payload_promotion_owner.json').read_text());proc=Path('/proc')/str(owner['pid'])/'cmdline';cmd=proc.read_bytes().replace(b'\0',b' ').decode() if proc.exists() else ''
rows=D.execute('select id,record from source_payload_promotions where state="promoted"').fetchall();checked=0;errors=[];files=0;total=0
for id,raw in rows:
 p=json.loads(raw)
 for key,x in p['changes'].items():
  q=R/x['to'];a=R/x['from'];files+=1;total+=x['bytes']
  if not q.resolve().is_relative_to(R/'clean') or q.is_symlink() or hashlib.sha256(q.read_bytes()).hexdigest()!=x['sha256']:errors.append({'id':id,'key':key,'reason':'promoted source failed hash/path check'})
  if a.exists() and (a.stat().st_ino!=q.stat().st_ino or a.stat().st_dev!=q.stat().st_dev):errors.append({'id':id,'key':key,'reason':'source hard link changed'})
 checked+=1
id='4de2105b6f4dc4c18cb5ab5c9f06df4f2f73ae8732e805ac58fef9d1bedf71f1';q=D.execute('select state,worker_pid,session_dir,error from harness_queue_v3 where id=?',(id,)).fetchone();fresh={'state':q[0],'pid':q[1],'session_dir':q[2],'error':q[3]};p=R/q[2]/'source_provenance/proof.json'
if p.exists():
 proof=json.loads(p.read_text());r=validate_frozen(proof);fresh['real_retry_source_provenance_valid']=True;fresh['original_reference']=r['original_reference'];fresh['original_source_code']=r['original_source_code']
result={'at':now(),'operation':'staged original-source payload promotion; no XML/PNG edits or automatic acceptance','owner':{**owner,'actual_command':cmd,'live':bool(cmd and 'promote_source_payloads.py' in cmd)},'snapshot_records_checked':checked,'promoted_files_checked':files,'logical_bytes_linked_without_copy':total,'errors':errors,'states':dict(D.execute('select state,count(*) from source_payload_promotions group by state')),'first_failed_harness_retry':fresh,'remaining_inventory_requires_separate_fresh_scan':True,'ok':not errors}
(W/'source_payload_promotion_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
