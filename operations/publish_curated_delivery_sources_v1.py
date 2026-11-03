"""Back up all source-selection/delivery code and small auditable receipts."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
W=Path(__file__).resolve().parents[2];repo=W/'work/xml_pipeline';src=W/'work/catalog_refresh';O=W/'outputs';ops=repo/'operations'
names=['curate_complex_arxiv_native_sources_v1.py','curate_complex_arxiv_native_sources_v2.py','publish_complex_arxiv_native_curation_v1.py','review_fixed_svg_whitespace_pairs_v1.py','publish_curated_research_delivery_v1.py','audit_seven_source_delivery_v4.py']
assert all(not(repo/'conversion/scripts'/name).exists()for name in names)
code="from pathlib import Path\nimport hashlib,json\nS=Path('/backup/shaoshitong/img2code_20261029/conversion/scripts')\nresult=[]\nfor name in "+repr(names)+":\n p=S/name;b=p.read_bytes();p.chmod(0o444);result.append(dict(file='conversion/scripts/'+name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=p.stat().st_mtime_ns))\nprint(json.dumps(result))"
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,check=True,timeout=30);remote=json.loads(r.stdout)
for entry,name in zip(remote,names):
    p=src/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'];shutil.copyfile(p,repo/entry['file'])
files=['complex-arxiv-native-source-curation-v1.json','complex-arxiv-native-source-curation-v2.json','arxiv-complex-graph-spot-selection-v1.json','arxiv-composite-spot-selection-v2.json','complex-arxiv-native-curation-publication-v1.json','svg-whitespace-C-value-review1.json','svg-whitespace-C-decisions1.json','svg-whitespace-C-publication1.json','curated-complex-research-delivery-v1.json','seven-source-delivery-audit-v4.json','CURATED_RESEARCH_DELIVERY.md']
for name in files:shutil.copyfile(O/name,ops/name)
delivery=json.loads((O/'curated-complex-research-delivery-v1.json').read_text());audit=json.loads((O/'seven-source-delivery-audit-v4.json').read_text());publication=json.loads((O/'svg-whitespace-C-publication1.json').read_text());arxiv=json.loads((O/'complex-arxiv-native-curation-publication-v1.json').read_text())
for name in ['CURRENT_HANDOFF.json','CURRENT_RELEASE.json']:
    p=ops/name;x=json.loads(p.read_text());x.update(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),strict_main_rows=1012,authoritative_main=publication['publication']['main'],curated_delivery=delivery,complex_arxiv_curated=arxiv,seven_source_delivery_audit=audit,active_programs=audit['programs'],goal_complete=False)
    x['whitespace_automatic_rollout'].update(gate_passed=True,unseen_samples=43,qualified=17,full_qualified_rate=17/43,latest=audit['programs']['svg_complex_source_whitespace_cached_unseen_20261103_v12'])
    x['next_step']='Continue existing birth-verified v11 mass and v12 validated foreign-pending wait; no new source-core normal or validation reruns. v12 passed 17/43 and automatically starts the full applicable batch after v11 releases overlapping pending originals. Current strict main1012; graded curated delivery1366=1012 main+92 complex charts+262 arXiv (99 native frameworks,163 labeled source composites;90 original-PDF visual,172 source-replay-only). One arXiv visual anomaly held; original qualifiers and all nonselected originals retained. Review newly qualified PNG increments, refresh graded delivery and seven-source audit, and perform final requirement audit after batch completion. Do not treat the current usable snapshot or validated gate as completion of the full goal.'
    p.write_text(json.dumps(x,indent=2)+'\n')
shutil.copyfile(Path(__file__),ops/Path(__file__).name)
for name in ['SOURCE_MANIFEST.json','REMOTE_SOURCE_MANIFEST.json']:
    p=repo/name;m=json.loads(p.read_text());entries={r['file']:r for r in m['files']};entries.update({r['file']:r for r in remote})
    if name=='SOURCE_MANIFEST.json':
        for f in ops.rglob('*'):
            if f.is_file():b=f.read_bytes();entries[str(f.relative_to(repo))]=dict(file=str(f.relative_to(repo)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=f.stat().st_mtime_ns)
    m.update(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=list(entries.values()));p.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(new_source_files=names,strict_main=1012,graded_delivery=1366,arxiv_curated=262,whitespace_gate='17/43 passed',goal_complete=False)))
