"""Read-only measured batch progress, birth identity and recent QA timings."""
from pathlib import Path
import argparse,json,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
code='''from pathlib import Path
import datetime,json,sqlite3,statistics,os
R=Path('/backup/shaoshitong/img2code_20261029');base=R/'release/compiler_iterations'
def read(p):return json.loads(p.read_text())if p.exists()else None
def owner(p):
 o=read(p)
 if not o:return None
 f=Path('/proc',str(o['pid']),'stat')
 if not f.exists():return dict(pid=o['pid'],live=False)
 fields=f.read_text().rsplit(') ',1)[1].split();birth=o.get('start_ticks',o.get('birth',o.get('birth_ticks')))
 return dict(pid=o['pid'],birth=fields[19],live=fields[0]!='Z'and(birth is None or int(fields[19])==int(birth)))
out=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),batches={},cpu_count=os.cpu_count(),load_average=os.getloadavg(),new_normal_calls=0,new_QA_calls=0)
for name in ['svg_complex_resolved_geometry_cached_unseen_20261102_v11_mass','svg_source_whitespace_disjoint_20261103_v1_mass','svg_source_whitespace_disjoint_20261103_v2_mass','svg_complex_source_whitespace_cached_unseen_20261103_v12_mass']:
 q=base/'runs'/name
 if not(q/'status.sqlite').exists():out['batches'][name]=dict(created=False);continue
 with sqlite3.connect((q/'status.sqlite').as_uri()+'?mode=ro',uri=True,timeout=5)as d:
  counts=dict(d.execute('select status,count(*)from samples group by status'));results=[json.loads(r[0])for r in d.execute('select result from samples where result is not null order by finished_at')]
 times=[]
 for result in results[-20:]:
  ref=result.get('quality_report')
  if ref:
   report=read(R/ref)
   if report and isinstance(report.get('seconds'),(float,int)):times.append(report['seconds'])
 out['batches'][name]=dict(counts=counts,total=sum(counts.values()),terminal=sum(counts.get(k,0)for k in ['qualified','abandoned']),infrastructure_errors=sum(r.get('infrastructure_failure')is True for r in results),controller=owner(q/'owner.json'),recent_quality_seconds=dict(samples=len(times),mean=statistics.mean(times),median=statistics.median(times),max=max(times))if times else None,infrastructure_stop=read(q/'infrastructure_stop.json'))
p=base/'programs/svg_complex_source_whitespace_cached_unseen_20261103_v12';foreign=read(p/'foreign_pending_observation.json')
out['parent']=dict(state=read(p/'state.json'),owner=owner(p/'owner.json'),foreign_pending_count=len(foreign.get('pending_ids',[]))if foreign else None,failure=read(p/'failure.json'))
with sqlite3.connect((R/'clean/complexity_curation_20261102T054553Z_v1/value_review_registry_v1/status.sqlite').as_uri()+'?mode=ro',uri=True)as d:out['review_registry']=dict(d.execute('select status,count(*)from reviews group by status'))
print(json.dumps(out))
'''
started=time.monotonic();r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=30)
assert r.returncode==0,r.stderr
result=json.loads(r.stdout);result['local_exec_wall_seconds']=round(time.monotonic()-started,3)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
