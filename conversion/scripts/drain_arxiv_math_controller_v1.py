from pathlib import Path
import json,os,signal,time
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/math_source_replay_v1'
def birth(pid):
 try:
  r=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return r[19] if r[0]!='Z' else None
 except FileNotFoundError:return None
receipt=json.loads((D/'launch.json').read_text());pid=receipt['pid']
if birth(pid)!=receipt['birth_ticks']:
 print(json.dumps(dict(already_terminal=True)));raise SystemExit()
assert b'arxiv_math_source_repair_v1.py' in Path('/proc',str(pid),'cmdline').read_bytes()
os.kill(pid,signal.SIGSTOP)
children=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:args=(p/'cmdline').read_bytes().split(b'\0')
 except (FileNotFoundError,PermissionError):continue
 if b'--case' in args and str(R/'conversion/scripts/arxiv_math_source_repair_v1.py').encode() in args:
  children.append((int(p.name),birth(int(p.name))))
os.kill(pid,signal.SIGTERM);os.kill(pid,signal.SIGCONT)
while any(birth(p)==b for p,b in children):time.sleep(2)
print(json.dumps(dict(controller_drained=True,children_finished=len(children),source_replays_repeated=0)))
