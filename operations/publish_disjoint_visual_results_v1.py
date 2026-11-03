"""Persist the new fixed-generation visual review and full-scope audit receipts."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
W=Path(__file__).resolve().parents[2];repo=W/'work/xml_pipeline';O=W/'outputs';ops=repo/'operations'
names=['review_fixed_svg_whitespace_pairs_v2.py','audit_seven_source_delivery_v5.py']
code="from pathlib import Path\nimport json,hashlib\nS=Path('/backup/shaoshitong/img2code_20261029/conversion/scripts')\nresult=[]\nfor name in "+repr(names)+":\n p=S/name;b=p.read_bytes();p.chmod(0o444);result.append(dict(file='conversion/scripts/'+name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=p.stat().st_mtime_ns))\nprint(json.dumps(result))"
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,check=True,timeout=30);remote=json.loads(r.stdout)
for entry,name in zip(remote,names):
 p=W/'work/catalog_refresh'/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'];target=repo/entry['file']
 if target.exists():assert target.read_bytes()==p.read_bytes()
 else:shutil.copyfile(p,target)
files=['resolved-geometry-mass-value-review5.json','resolved-geometry-mass-decisions5.json','resolved-geometry-mass-publication5.json','svg-whitespace-disjoint-value-review1.json','svg-whitespace-disjoint-decisions1.json','svg-whitespace-disjoint-publication1.json','curated-complex-research-delivery-v3.json','seven-source-delivery-audit-v5.json','current-batch-runtime-progress3.json','current-batch-runtime-progress4.json','current-batch-runtime-progress5.json','CURATED_RESEARCH_DELIVERY.md']
for name in files:assert(O/name).stat().st_size>0;shutil.copyfile(O/name,ops/name)
shutil.copyfile(Path(__file__),ops/Path(__file__).name)
def load(name):return json.loads((O/name).read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat();publication=load('svg-whitespace-disjoint-publication1.json');audit=load('seven-source-delivery-audit-v5.json');progress=load('current-batch-runtime-progress5.json');delivery=load('curated-complex-research-delivery-v3.json')
assert publication['publication']['main']['rows']==delivery['curation_memberships']['complex_paper_diagrams_and_posters']==1062
assert delivery['unique_code_RGBA_pairs']==1416 and audit['existing_qualified_rows_screened']==15118
for name in ['CURRENT_HANDOFF.json','CURRENT_RELEASE.json']:
 p=ops/name;x=json.loads(p.read_text());x.update(at_utc=now,strict_main_rows=1062,authoritative_main=publication['publication']['main'],curated_delivery=delivery,latest_actual_PNG_publication=publication,latest_runtime_progress=progress,seven_source_delivery_audit=audit,review_registry=progress['review_registry'],pending_reviews=progress['review_registry'].get('await_actual_PNG_review',0),goal_complete=False)
 x['next_step']='Continue existing birth-verified v11 mass, approved disjoint v24 mass, and unchanged automatic parent v12 catchup. No new experiments or validation reruns. Review only newly qualified actual PNGs after accumulating an increment; 31 actual PNGs inspected this turn, 28 published and three held, source qualifications unchanged. Current 1416 curated pairs comprise 1062 strict diagram/poster,92 chart,262 arXiv pairs with separate reference grades. Final acceptance must wait for whole applicable batch terminal outcomes and refresh all delivery/index/audit counts. v5 audit now records the disjoint batch and the authoritative original 15118-qualified-row structural screening receipt.'
 p.write_text(json.dumps(x,indent=2)+'\n')
for name in ['SOURCE_MANIFEST.json','REMOTE_SOURCE_MANIFEST.json']:
 p=repo/name;m=json.loads(p.read_text());entries={r['file']:r for r in m['files']};entries.update({r['file']:r for r in remote})
 if name=='SOURCE_MANIFEST.json':
  for f in ops.rglob('*'):
   if f.is_file():b=f.read_bytes();entries[str(f.relative_to(repo))]=dict(file=str(f.relative_to(repo)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=f.stat().st_mtime_ns)
 m.update(at_utc=now,files=list(entries.values()));p.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(source_files_verified=len(remote),strict_main=1062,curated_delivery=1416,goal_complete=False)))
