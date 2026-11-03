from pathlib import Path
import datetime,json,subprocess,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/embedded_XML_image_inventory_v2';D.mkdir(exist_ok=True)
def birth(pid):
 try:
  x=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return x[19] if x[0]!='Z' else None
 except FileNotFoundError:return None
p=D/'launch.json'
if p.exists():
 r=json.loads(p.read_text())
 if birth(r['pid'])==r['birth_ticks']:print(json.dumps(dict(already_running=True,**r)));raise SystemExit()
 if (D/'inventory.json').exists() and json.loads((D/'inventory.json').read_text()).get('scan_complete'):print(json.dumps(dict(already_complete=True)));raise SystemExit()
with (D/'program.log').open('ab') as f:child=subprocess.Popen([sys.executable,'-u',str(R/'conversion/scripts/inventory_arxiv_embedded_XML_images_v2.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
r=dict(pid=child.pid,birth_ticks=birth(child.pid),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());p.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
