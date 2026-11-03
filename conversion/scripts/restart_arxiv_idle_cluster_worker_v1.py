"""Restart owned worker only at a verified no-paper/no-PDF-conversion boundary.

Freeze the exact process group before reading its local WAL database so no new
conversion can race the check. A busy worker is immediately continued unchanged.
All pending downloads and upload outboxes remain on the same data disk.
"""
from pathlib import Path
import argparse,json,os,signal,sqlite3,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();root=a.root
receipt=json.loads((root/'launch.json').read_text());pid=receipt['pid']
def birth(pid):
    try:
        r=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return r[19] if r[0]!='Z' else None
    except FileNotFoundError:return None
if birth(pid)!=receipt['birth_ticks']:
    subprocess.run([sys.executable,str(root/'conversion/scripts/launch_arxiv_cluster_worker_v1.py'),'--root',str(root)],check=True);sys.exit()
assert os.getpgid(pid)==pid and b'arxiv_cluster_worker_v1.py' in Path('/proc',str(pid),'cmdline').read_bytes()
os.killpg(pid,signal.SIGSTOP)
try:
    db=root/'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/once.sqlite'
    with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=5) as c:
        papers=c.execute("select count(*) from papers where status='attempt_started'").fetchone()[0]
        pdfs=c.execute("select count(*) from pdfs where status='attempt_started'").fetchone()[0]
    if papers or pdfs:
        print(json.dumps(dict(node=receipt['node'],busy_preserved=True,active_papers=papers,active_PDF_imports=pdfs)));sys.exit(3)
    # No active native conversion or paper processing can be interrupted here.
    os.killpg(pid,signal.SIGTERM)
finally:os.killpg(pid,signal.SIGCONT)
for _ in range(50):
    if birth(pid)!=receipt['birth_ticks']:break
    time.sleep(.1)
assert birth(pid)!=receipt['birth_ticks'],'owned_idle_worker_not_terminal'
(root/'last_idle_handover.json').write_text(json.dumps(dict(old=receipt,active_papers=0,active_PDF_imports=0,partials_and_uploads_preserved=True)))
subprocess.run([sys.executable,str(root/'conversion/scripts/launch_arxiv_cluster_worker_v1.py'),'--root',str(root)],check=True)
