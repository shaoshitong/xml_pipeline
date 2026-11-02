"""Install only observed missing TeX dependencies in a new immutable overlay."""
from pathlib import Path
import datetime,hashlib,json,os,shutil,sqlite3,subprocess,time
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';OLD=W/'runtime/priority_datikz_overlay_v3';NEW=W/'runtime/priority_datikz_overlay_v4';BASE=W/'runtime/texlive2025_source_v1';PYTHON='/home/shaoshitong/anaconda3/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 started=time.monotonic();source=W/'priority_datikz_compile_preflight_v2/52b0951b3f964cf1ba2d7841fec7557a';assert(source/'summary.json').exists()
 with sqlite3.connect((source/'status.sqlite').as_uri()+'?mode=ro',uri=True)as db:results=[json.loads(x[0])for x in db.execute('select result from samples where result is not null')]
 packages=['trimspaces','helvet'];evidence={p:[r['id']for r in results if ('phvr7t'if p=='helvet'else p)in r.get('reason','')]for p in packages};assert all(evidence.values()),evidence
 assert NEW.exists() and not(NEW/'receipt.json').exists(),'only_unreleased_failed_overlay_may_be_completed'
 assert 'package helvet not present in repository' in(NEW/'install.log').read_text()
 assert json.loads((NEW/'state.json').read_text())['stage']=='installing_observed_dependencies'
 old_manifest=json.loads((OLD/'manifest.json').read_bytes());assert sha(OLD/'manifest.json')==json.loads((OLD/'receipt.json').read_bytes())['manifest_sha256']
 pins={str(p):sha(p)for p in [OLD/'manifest.json',OLD/'receipt.json',BASE/'runtime_manifest.json',BASE/'receipt.json']}
 for row in old_manifest['files']:assert sha(OLD/row['file'])==row['sha256']
 assert(NEW/'texmf').is_dir()
 for name in ['texmf-config','texmf-var','tmp']:(NEW/name).mkdir(exist_ok=True)
 state=dict(stage='installing_observed_dependencies',packages=packages,evidence=evidence,old_pins=pins);(NEW/'state.json').write_text(json.dumps(state,indent=2))
 binary=BASE/'texlive/bin/x86_64-linux';argv=[str(binary/'tlmgr'),'--usermode','--usertree',str(NEW/'texmf'),'--repository',old_manifest['repository'],'install','helvetic']
 env=dict(os.environ,PATH=str(binary)+':/usr/bin:/bin',TEXMFHOME=str(NEW/'texmf'),TEXMFCONFIG=str(NEW/'texmf-config'),TEXMFVAR=str(NEW/'texmf-var'),TMPDIR=str(NEW/'tmp'))
 with(NEW/'install_recovery.log').open('wb')as log:proc=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
 assert proc.returncode==0,'official_dependency_install_failed_read_install_log'
 found={}
 for name in ['trimspaces.sty','phvr7t.tfm']:
  p=subprocess.run([str(binary/'kpsewhich'),name],env=env,text=True,capture_output=True,timeout=15);assert p.returncode==0 and p.stdout.strip(),name;q=Path(p.stdout.strip()).resolve();assert q.is_relative_to(NEW);found[name]=dict(file=str(q.relative_to(NEW)),sha256=sha(q))
 assert all(sha(Path(p))==digest for p,digest in pins.items())
 assert all(sha(OLD/row['file'])==row['sha256']for row in old_manifest['files'])
 files=[dict(file=str(p.relative_to(NEW)),sha256=sha(p),bytes=p.stat().st_size)for p in sorted((NEW/'texmf').rglob('*'))if p.is_file()]
 manifest=dict(repository=old_manifest['repository'],inherits_exact_v3_overlay_manifest=pins[str(OLD/'manifest.json')],observed_dependencies=['trimspaces','helvetic'],evidence=evidence,files=files,old_runtime_metadata_unchanged=pins)
 (NEW/'manifest.json').write_text(json.dumps(manifest,indent=2));receipt=dict(stage='complete',at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),root=str(NEW),TEXMFHOME=str(NEW/'texmf'),manifest_sha256=sha(NEW/'manifest.json'),bytes=sum(r['bytes']for r in files),seconds=time.monotonic()-started,old_runtimes_modified=False,command=argv,verified_observed_files=found,source_code_rewriting=False)
 (NEW/'receipt.json').write_text(json.dumps(receipt,indent=2));(NEW/'state.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
