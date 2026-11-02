from pathlib import Path
import collections,datetime,hashlib,json,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029')
A=R/'conversion/source_semantic_admission_audit_v1/e430695f8e8042d3bf1b4426ca99b423'
C=R/'conversion/semantic_admission_validation_launch_v1/633bef4096854e8d81b03d04112e620e'
def read(p):
 try:return json.loads(p.read_bytes())
 except FileNotFoundError:return None
def live(receipt):
 if not receipt:return None
 pid=receipt['pid'];expected=str(receipt.get('birth_ticks',receipt.get('start_ticks')))
 try:
  parts=Path('/proc',str(pid),'stat').read_text().rsplit(') ',1)[1].split();return dict(pid=pid,same_birth=parts[19]==expected,live=parts[19]==expected and parts[0]!='Z',state=parts[0])
 except FileNotFoundError:return dict(pid=pid,live=False,missing=True)
out=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),audit=dict(live=live(read(A/'launch.json')),summary=read(A/'summary.json')),chain=dict(live=live(read(C/'launch.json')),state=read(C/'state.json')),goal_complete=False)
with sqlite3.connect((A/'status.sqlite').as_uri()+'?mode=ro',uri=True)as d:
 rows=[json.loads(row[0])for row in d.execute('select result from sources where result is not null')];out['audit']['measured_completed']=len(rows);out['audit']['admission_reasons']=dict(collections.Counter(row.get('reason','unknown').split(':',1)[0]for row in rows));out['audit']['observer_seconds_mean']=round(sum(row.get('elapsed_seconds',0)for row in rows)/max(1,len(rows)),3);out['audit']['candidate_emissions']=sum(row.get('candidate_emissions',0)for row in rows)
program=read(C/'program_launch.json')
if program:
 out['program']=dict(live=live(program),handle=program,state=read(Path(program['program_dir'])/'state.json'))
 for phase in('B','C'):
  p=R/'release/compiler_iterations/runs'/('svg_complex_semantic_admission_unseen_20261102_v8_'+phase)/'status.sqlite'
  if p.exists():
   with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)as d:out['program'][phase]=dict(d.execute('select status,count(*)from samples group by status'))
runtime=R/'release/compiler_iterations/controls/svg_edge_use_runtime_controls_20261102_v1/proof.json'
if runtime.exists():out['runtime_proof']=dict(file=str(runtime.relative_to(R)),sha256=hashlib.sha256(runtime.read_bytes()).hexdigest())
old=R/'release/compiler_iterations/programs/svg_complex_symbol_viewport_unseen100_20261102_v7';out['previous_round']=dict(state=read(old/'state.json'),post_failure_closure=read(old/'post_failure_closure.json'))
pointer=read(R/'clean/complexity_curation_20261102T054553Z_v1/current.json');main=pointer['views']['paired_priority_complex'];blob=(R/main['file']).read_bytes();assert hashlib.sha256(blob).hexdigest()==main['sha256'];rows=[json.loads(x)for x in blob.splitlines()if x];assert len(rows)==main['rows'];out['strict_main']=dict(rows=len(rows),sha256=main['sha256'],new_667_pair_present=any(r['id']=='66710413a814b9d85d1efbf1a163c6cfc4a7bcbb3e26541c71d18914b6a08a84'for r in rows));out['catalogue']=read(R/'clean/research_pairs_catalog/current.json')
print(json.dumps(out))
