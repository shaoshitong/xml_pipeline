"""Publish the complete frozen dispatch/validation implementation and receipts."""
from pathlib import Path
import datetime,hashlib,json,shutil,subprocess
W=Path(__file__).resolve().parents[2];repo=W/'work/xml_pipeline';src=W/'work/catalog_refresh';O=W/'outputs'
prefixes=('svg_whitespace_','launch_svg_whitespace_','close_svg_whitespace_','register_svg_whitespace_','derive_svg_whitespace_','svg_source_whitespace_quality_control_')
names=sorted(p.name for p in src.iterdir()if p.suffix=='.py'and p.name.startswith(prefixes)and not(repo/'conversion/scripts'/p.name).exists());assert names
code="from pathlib import Path\nimport hashlib,json\nS=Path('/backup/shaoshitong/img2code_20261029/conversion/scripts')\nresult=[]\nfor name in "+repr(names)+":\n p=S/name;b=p.read_bytes();p.chmod(0o444);result.append(dict(file='conversion/scripts/'+name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=p.stat().st_mtime_ns))\nprint(json.dumps(result))"
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,check=True,timeout=30);remote=json.loads(r.stdout)
for entry,name in zip(remote,names):
    p=src/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'];shutil.copyfile(p,repo/entry['file'])
files=['svg-whitespace-quality-controls-launch-v1.json','svg-whitespace-manual-history-v1.json','svg-whitespace-closed-controls-v1.json','svg-whitespace-validation-chain-launch-v1.json','svg-whitespace-chain-progress1.json','svg-whitespace-chain-progress2.json','svg-whitespace-source-admission-terminal-audit-v1.json','resolved-geometry-mass-value-review3.json','resolved-geometry-mass-decisions3.json','resolved-geometry-mass-publication3.json']
for name in files:shutil.copyfile(O/name,repo/'operations'/name)
progress=json.loads((O/'svg-whitespace-chain-progress2.json').read_text());publication=json.loads((O/'resolved-geometry-mass-publication3.json').read_text());audit=json.loads((O/'svg-whitespace-source-admission-terminal-audit-v1.json').read_text())
for name in ['CURRENT_HANDOFF.json','CURRENT_RELEASE.json']:
    p=repo/'operations'/name;x=json.loads(p.read_text());x.update(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),strict_main_rows=publication['publication']['main']['rows'],authoritative_main=publication['publication']['main'],latest_mass_progress=progress,goal_complete=False)
    x['whitespace_automatic_rollout']=dict(chain=json.loads((O/'svg-whitespace-validation-chain-launch-v1.json').read_text()),latest=progress,full8_controls=json.loads((O/'svg-whitespace-closed-controls-v1.json').read_text()),manual_once_history=json.loads((O/'svg-whitespace-manual-history-v1.json').read_text()),source_admission=audit,whole_batch_foreign_pending_wait=True,gates=dict(minimum_fraction=.2,minimum_new_qualified=5,regressions=0,infrastructure_errors=0),normal_calls_per_original_per_core=1)
    x['next_step']='Follow existing immutable whitespace chain and its child program, not the terminated source-admission owner. Runtime dispatch proof must preserve the manual normal and qualify the existing positive without converting it. Then the chain seals all 3047 source targets (2730 retained plus 317 flat additions), selects globally independent unseen families under atomic reservation, runs B/C, and gates the full applicable v24 batch. Before mass it waits for verified foreign pending conversions to finish so no overlapping originals are silently omitted. Continue v11 and review only new qualified PNGs. No restart solely because a launcher exited.'
    p.write_text(json.dumps(x,indent=2)+'\n')
shutil.copyfile(Path(__file__),repo/'operations'/Path(__file__).name)
for name in ['SOURCE_MANIFEST.json','REMOTE_SOURCE_MANIFEST.json']:
    p=repo/name;m=json.loads(p.read_text());entries={r['file']:r for r in m['files']};entries.update({r['file']:r for r in remote})
    if name=='SOURCE_MANIFEST.json':
        for f in(repo/'operations').iterdir():
            if f.is_file():b=f.read_bytes();entries[str(f.relative_to(repo))]=dict(file=str(f.relative_to(repo)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),mtime_ns=f.stat().st_mtime_ns)
    m.update(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=list(entries.values()));p.write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(new_source_files=len(names),source_files=names,strict_main=publication['publication']['main']['rows'],source_admission=audit['summary']['counts'],goal_complete=False)))
