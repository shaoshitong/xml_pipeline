"""Finite private TeXLive2025 installation from the fixed historic final repo.

Only this new runtime subtree is written. Existing runtimes, PATH, datasets,
canonical jobs, registries and running converter implementations are untouched.
"""
from pathlib import Path
import hashlib,json,os,re,subprocess,tarfile,time,urllib.request
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'conversion/runtime/texlive2025_source_v1'
REPOSITORY='https://ftp.math.utah.edu/pub/tex/historic/systems/texlive/2025/tlnet-final'
PACKAGES=['standalone','pgfplots','cm-super','preview','lm','amsfonts','amsmath','xcolor']
sha=lambda b:hashlib.sha256(b).hexdigest()

def write(name,value):
 p=D/name;p.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')

def fetch(name):
 p=D/'downloads'/name
 with urllib.request.urlopen(REPOSITORY+'/'+name,timeout=120) as response:p.write_bytes(response.read())
 return p

def main():
 if D.exists():
  assert not (D/'receipt.json').exists(),'runtime_already_installed_do_not_mutate'
  failure=json.loads((D/'failure.json').read_bytes())
  assert failure['reason']=='texlive_scheme_install_failed_see_install_log','unrecognized_partial_install_requires_explicit_diagnosis'
  (D/'failure.json').rename(D/'first_install_failure.json')
  (D/'install.log').rename(D/'first_install.log')
 else:D.mkdir(parents=True,exist_ok=False)
 (D/'downloads').mkdir(exist_ok=True);(D/'tmp').mkdir(exist_ok=True)
 started=time.time();write('state.json',{'stage':'downloading','finite':True,'model_calls':0})
 archive=fetch('install-tl-unx.tar.gz');checksums=fetch('install-tl-unx.tar.gz.sha512')
 expected=re.search(r'\b[0-9a-fA-F]{128}\b',checksums.read_text()).group().lower()
 assert hashlib.sha512(archive.read_bytes()).hexdigest()==expected,'official_installer_sha512_mismatch'
 with tarfile.open(archive) as tar:tar.extractall(D/'installer',filter='data')
 installer=next((D/'installer').glob('*/install-tl'))
 profile='\n'.join(['selected_scheme scheme-basic','binary_x86_64-linux 1',
  'TEXDIR '+str(D/'texlive'),'TEXMFCONFIG '+str(D/'texmf-config'),'TEXMFVAR '+str(D/'texmf-var'),
  'TEXMFSYSVAR '+str(D/'texlive/texmf-var'),'TEXMFSYSCONFIG '+str(D/'texlive/texmf-config'),
  'TEXMFHOME '+str(D/'texmf-home'),'TEXMFLOCAL '+str(D/'texmf-local'),
  'instopt_adjustpath 0','instopt_letter 0','instopt_portable 1',
  'tlpdbopt_install_docfiles 0','tlpdbopt_install_srcfiles 0','tlpdbopt_autobackup 0'])+'\n'
 (D/'profile.txt').write_text(profile)
 env={**os.environ,'TMPDIR':str(D/'tmp'),'TEXMFCONFIG':str(D/'texmf-config'),'TEXMFVAR':str(D/'texmf-var'),'TEXMFHOME':str(D/'texmf-home')}
 argv=['perl',str(installer),'--no-gui','--no-interaction','--repository',REPOSITORY,'--profile',str(D/'profile.txt')]
 write('state.json',{'stage':'installing_scheme_basic','pid':os.getpid(),'started':started,'argv':argv,'finite':True})
 print(json.dumps({'stage':'installing_scheme_basic','runtime':str(D),'repository':REPOSITORY}),flush=True)
 with (D/'install.log').open('wb') as log:proc=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=2400)
 assert proc.returncode==0,'texlive_scheme_install_failed_see_install_log'
 binary=D/'texlive/bin/x86_64-linux';env={**env,'PATH':str(binary)+':'+os.environ['PATH']}
 argv=[str(binary/'tlmgr'),'--repository',REPOSITORY,'install',*PACKAGES]
 write('state.json',{'stage':'installing_required_packages','pid':os.getpid(),'argv':argv,'finite':True})
 print(json.dumps({'stage':'installing_required_packages','packages':PACKAGES}),flush=True)
 with (D/'packages.log').open('wb') as log:proc=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=2400)
 assert proc.returncode==0,'texlive_dependency_install_failed_see_packages_log'
 version=subprocess.check_output([str(binary/'pdflatex'),'--version'],text=True,env=env)
 assert 'TeX Live 2025' in version,'installed_engine_not_texlive2025'
 entries=[]
 for p in sorted((D/'texlive').rglob('*')):
  if p.is_file():entries.append({'file':str(p.relative_to(D)),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
 write('runtime_manifest.json',{'files':entries,'file_count':len(entries),'bytes':sum(x['bytes'] for x in entries),'repository':REPOSITORY,'packages':PACKAGES,'pdflatex_version':version})
 result={'stage':'complete','runtime':str(D),'repository':REPOSITORY,'installer_sha512':expected,'runtime_manifest_sha256':sha((D/'runtime_manifest.json').read_bytes()),'pdflatex_version':version,'installed_files':len(entries),'installed_bytes':sum(x['bytes'] for x in entries),'seconds':time.time()-started,'finite':True,'model_calls':0}
 write('receipt.json',result);write('state.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':
 try:main()
 except Exception as error:
  if D.exists():write('failure.json',{'error_type':type(error).__name__,'reason':str(error),'finite':True})
  raise
