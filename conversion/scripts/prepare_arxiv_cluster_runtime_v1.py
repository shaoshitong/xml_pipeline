"""Create a remote-only reproducible runtime bundle from existing pinned assets."""
from pathlib import Path
import hashlib, json, os, shutil, sqlite3, subprocess, tarfile
import playwright, pyee, greenlet, typing_extensions
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'cluster_direct_v1'
D.mkdir(exist_ok=True)
stage=D/'runtime_build';stage.mkdir(exist_ok=True)
paths=[('conversion/scripts',R/'conversion/scripts'),('evaluation/assets/drawio-runtime-v32.6.1/draw.war',R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war'),('clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer',P/'drawio_builtin_import_v1/official_importer'),('runtime/chrome',Path('/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64'))]
for m in [playwright,pyee,greenlet]:paths.append(('runtime/packages/'+m.__name__,Path(m.__file__).parent))
paths.append(('runtime/packages/typing_extensions.py',Path(typing_extensions.__file__)))
for name in ['fitz','pymupdf']:
    paths.append(('runtime/packages/'+name,R/'evaluation/assets/pdf_inventory_python_v1'/name))
with sqlite3.connect((P/'new_bulk_200_v1/once.sqlite').as_uri()+'?mode=ro',uri=True) as c:
    inherited=[r[0] for r in c.execute('select id from papers')]
(stage/'inherited_paper_ids.json').write_text(json.dumps(inherited))
paths.append(('runtime/inherited_paper_ids.json',stage/'inherited_paper_ids.json'))
fontfiles=sorted(set(subprocess.check_output(['fc-list','--format','%{file}\n'],text=True).splitlines()))
for i,name in enumerate(fontfiles):
    p=Path(name)
    if p.is_file():paths.append(('runtime/fonts/'+str(i)+'_'+p.name,p))
manifest={}
archive=D/'runtime.tar.gz'
with tarfile.open(archive.with_suffix('.partial'),'w:gz') as t:
    for dest,source in paths:
        def audit(info):
            if info.isfile():
                rel=Path(info.name)
                if rel.suffix in ['.pyc'] or '__pycache__' in rel.parts:return None
            return info
        t.add(source,arcname=dest,filter=audit)
os.replace(archive.with_suffix('.partial'),archive)
h=hashlib.sha256()
with archive.open('rb') as f:
    for b in iter(lambda:f.read(1024**2),b''):h.update(b)
receipt=dict(bytes=archive.stat().st_size,sha256=h.hexdigest(),canonical_runtime_and_importer_unchanged=True,font_files=len(fontfiles),VPS_used=False,Mac_bulk_transfer=False)
(D/'runtime_manifest.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
