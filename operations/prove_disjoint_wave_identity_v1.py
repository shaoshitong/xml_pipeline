"""Verify the saved approved-generation identity and disjoint dispatch inputs."""
from pathlib import Path
import argparse,json,subprocess
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
code='''from pathlib import Path
import json,hashlib,datetime,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029');B=R/'release/compiler_iterations';name='svg_source_whitespace_disjoint_20261103_v2_mass';root=B/'disjoint_batches'/name;p=B/'programs/svg_complex_source_whitespace_cached_unseen_20261103_v12'
def read(x):return json.loads(x.read_text())
def rows(x):return[json.loads(y)for y in x.read_text().splitlines()]
def asset(x):return dict(file=str(x.relative_to(R)),sha256=hashlib.sha256(x.read_bytes()).hexdigest(),bytes=x.stat().st_size)
f=read(root/'freeze.json');parent=read(p/'implementation.json');assert f['pins']==parent['pins'];assert f['implementation_identity']==parent['implementation_identity'];assert f['implementation_identity_sha256']==parent['implementation_identity_sha256'];assert Path(f['release_gate']['file']).resolve()==(p/'release_gate.json').resolve();assert f['release_gate']['sha256']==asset(p/'release_gate.json')['sha256']
ids={r['id']for r in rows(root/'input.jsonl')};old={r['id']for r in rows(B/'disjoint_batches/svg_source_whitespace_disjoint_20261103_v1_mass/input.jsonl')};seen={r['id']for r in rows(root/'source_core_history_before.jsonl')};active=set(read(root/'live_overlap_snapshot.json')['active']);selected={r['id']for r in rows(p/'selected.jsonl')};assert len(ids)==285;assert not(ids&old or ids&seen or ids&active or ids&selected)
a=R/'conversion/scripts/launch_svg_whitespace_disjoint_mass_v1.py';b=R/'conversion/scripts/launch_svg_whitespace_disjoint_mass_v2.py';assert b.read_bytes().replace(name.encode(),b'svg_source_whitespace_disjoint_20261103_v1_mass')==a.read_bytes()
with sqlite3.connect((B/'runs'/name/'status.sqlite').as_uri()+'?mode=ro',uri=True)as d:counts=dict(d.execute('select status,count(*)from samples group by status'));attempts=dict(d.execute('select attempts,count(*)from samples group by attempts'))
observation=read(p/'foreign_pending_observation.json');assert name in json.dumps(observation['verified_live_owners'])
print(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),run=name,targets=len(ids),exact_parent_implementation_and_pins_preserved=True,approved_release_gate=f['release_gate'],freeze=asset(root/'freeze.json'),producer=asset(b),producer_differs_only_by_unique_batch_name=True,overlap_with_first_disjoint_batch=0,overlap_with_same_core_prior_events=0,overlap_with_launch_time_live_pending=0,overlap_with_current_validation=0,parent_observes_live_second_disjoint_batch=True,current_counts=counts,current_attempts=attempts,new_validation_calls=0,normal_conversions_are_only_existing_approved_mass_dispatch=True,goal_complete=False)))
'''
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=30);assert r.returncode==0,r.stderr
v=json.loads(r.stdout);a.output.write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
