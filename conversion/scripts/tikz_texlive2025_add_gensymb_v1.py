"""Add the one observed missing package before freezing the private runtime."""
from pathlib import Path
import hashlib,json,os,subprocess,time
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'conversion/runtime/texlive2025_source_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
 assert not (R/'release/compiler_iterations/controls/tikz_pdftex2025_v2_controls_20261101_v1/proof.json').exists(),'runtime_already_released_do_not_mutate'
 assert not (D/'gensymb_dependency_receipt.json').exists(),'dependency_already_installed_do_not_repeat'
 receipt=json.loads((D/'receipt.json').read_bytes());assert receipt['stage']=='complete'
 evidence=R/'conversion/compiler_tikz_poppler_source_v2/development/known_structural_139bdeeb72194fbbb62daa0ba0b06330/report.json'
 rows=json.loads(evidence.read_bytes())['records'];assert any(x['id']=='00266a4387b64e2fa257525731ab9e5df1a768df3cdb5b8b5a0c4702602a8983' and "gensymb.sty" in x.get('detail','') for x in rows)
 (D/'receipt.initial.json').write_bytes((D/'receipt.json').read_bytes());(D/'runtime_manifest.initial.json').write_bytes((D/'runtime_manifest.json').read_bytes())
 binary=D/'texlive/bin/x86_64-linux';argv=[str(binary/'tlmgr'),'--repository',receipt['repository'],'install','gensymb'];env={**os.environ,'PATH':str(binary)+':'+os.environ['PATH'],'TEXMFCONFIG':str(D/'texmf-config'),'TEXMFVAR':str(D/'texmf-var'),'TEXMFHOME':str(D/'texmf-home'),'TMPDIR':str(D/'tmp')}
 with (D/'gensymb_install.log').open('xb') as log:proc=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 assert proc.returncode==0,'observed_missing_dependency_install_failed'
 old=json.loads((D/'runtime_manifest.json').read_bytes());entries=[]
 for p in sorted((D/'texlive').rglob('*')):
  if p.is_file():entries.append({'file':str(p.relative_to(D)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
 old.update(files=entries,file_count=len(entries),bytes=sum(x['bytes'] for x in entries),packages=sorted(set(old['packages']+['gensymb'])))
 (D/'runtime_manifest.json').write_text(json.dumps(old,sort_keys=True,indent=2)+'\n')
 receipt.update(runtime_manifest_sha256=sha((D/'runtime_manifest.json').read_bytes()),installed_files=len(entries),installed_bytes=sum(x['bytes'] for x in entries),observed_dependency_additions=['gensymb'],initial_receipt_sha256=sha((D/'receipt.initial.json').read_bytes()),missing_dependency_evidence_sha256=sha(evidence.read_bytes()))
 (D/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');(D/'state.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 result={'runtime':str(D),'added':'gensymb','evidence':str(evidence),'runtime_manifest_sha256':receipt['runtime_manifest_sha256'],'old_runtimes_modified':False};(D/'gensymb_dependency_receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
