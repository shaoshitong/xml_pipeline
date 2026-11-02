"""Compact read-only status of exact current cache, handoff and fixed queues."""
from pathlib import Path
import datetime,hashlib,json,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029')
CACHE=R/'conversion/source_cached_admission_v1/2d47ad593b4545038329916ff229a8ea'
CHAIN=R/'conversion/background_rotation_validation_launch_v1/80af62c518714f07a16a39c2eb87d3a6'
RUN='svg_complex_background_rotation_cached_unseen_20261102_v9'

def read(p):return json.loads(p.read_bytes())if p.exists()else None
def live(h):
 if not h:return None
 birth=str(h.get('birth_ticks',h.get('start_ticks')))
 try:
  state=Path('/proc',str(h['pid']),'stat').read_text().rsplit(') ',1)[1].split()
  return dict(pid=h['pid'],live=state[19]==birth and state[0]!='Z',same_birth=state[19]==birth,state=state[0])
 except FileNotFoundError:return dict(pid=h['pid'],live=False,missing=True)
def counts(p):
 if not p.exists():return None
 with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)as d:
  return dict(d.execute('select status,count(*)from samples group by status'))
def compact_gate(g):
 if g is None:return None
 return {k:v for k,v in g.items()if k!='implementation_identity'}
def compact_state(s):
 if s is None:return None
 s=dict(s)
 if s.get('gate'):s['gate']=compact_gate(s['gate'])
 if s.get('selection'):
  s['selection']={k:v for k,v in s['selection'].items()if k!='policy'}
 return s
out=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 cache=dict(live=live(read(CACHE/'launch.json')),summary=read(CACHE/'summary.json')),
 chain=dict(live=live(read(CHAIN/'launch.json')),state=compact_state(read(CHAIN/'state.json'))),
 runtime_preflight=counts(R/'release/compiler_iterations/runs/svg_background_rotation_runtime_preflight_20261102_v1/status.sqlite'),
 goal_complete=False)
handle=read(CHAIN/'program_launch.json')
if handle:
 p=Path(handle['program_dir']);gate=p/'release_gate.json';out['program']=dict(handle={k:v for k,v in handle.items()if k!='argv'},live=live(handle),state=compact_state(read(p/'state.json')),gate=compact_gate(read(gate)),gate_asset=dict(file=str(gate.relative_to(R)),sha256=hashlib.sha256(gate.read_bytes()).hexdigest())if gate.exists()else None,summary=compact_state(read(p/'summary.json')),queues={phase:counts(R/'release/compiler_iterations/runs'/(RUN+'_'+phase)/'status.sqlite')for phase in ['B','C','mass']})
if out['chain']['state']and out['chain']['state'].get('stage')=='requires_repair':out['chain']['log_tail']=(CHAIN/'output.log').read_text(errors='replace')[-1800:]
p=read(R/'clean/complexity_curation_20261102T054553Z_v1/current.json');ref=p['views']['paired_priority_complex'];data=(R/ref['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==ref['sha256'];assert len(data.splitlines())==ref['rows'];out['strict_main']=ref
catalog=read(R/'clean/research_pairs_catalog/current.json');out['catalogue']={k:catalog.get(k)for k in ['at_utc','unique_code_PNG_pairs','unique_pairs_by_evidence_view']}
print(json.dumps(out))
