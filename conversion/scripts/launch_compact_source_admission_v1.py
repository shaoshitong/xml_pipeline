"""Freeze the already-screened additive source scope and launch source-only admission."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 import compiler_svg_general_guard_v18 as core
 screen=R/'clean/priority_svg_compact_source_screen_v1/ba1792e0b02f44dab9b2b613ea562876'
 selected=screen/'selected.jsonl';assert sha(selected.read_bytes())=='d193619a51a1caa563e3999f16b7ba89d7d6788251ee67e7bed0787132fef1ed'
 wanted={r['id']:r for r in map(json.loads,selected.read_text().splitlines())};assert len(wanted)==365
 receipt=screen/'source_admission_launch_v1.json';assert not receipt.exists(),'Existing launch must be observed, never duplicated'
 original=R/'release/compiler_iterations/source_pools/svg_actual_shadow_unseen100_20261102_v4/supported_population.jsonl'
 rows=[]
 for r in map(json.loads,original.read_text().splitlines()):
  if r['id']not in wanted:continue
  w=wanted[r['id']];assert(r['source']['code_sha256'],r['source']['image_sha256'])==(w['source_code_sha256'],w['source_image_sha256']);r['compiler_unit']=core.UNIT;rows.append(r)
 assert len(rows)==len(wanted)
 pool=screen/'resolved_geometry_source_pool_v1';pool.mkdir(exist_ok=False);p=pool/'supported_population.jsonl';p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in rows));p.chmod(0o444)
 script=S/'source_resolved_geometry_admission_v1.py';script.chmod(0o444)
 root=R/'conversion/source_resolved_geometry_admission_v1'/uuid.uuid4().hex
 created=subprocess.run([sys.executable,str(script),'create','--work',str(root),'--source-pool',str(pool)],capture_output=True,text=True,check=True)
 log=(root/'run.log').open('wb');process=subprocess.Popen([sys.executable,str(script),'run','--work',str(root),'--workers','12','--timeout','120'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
 birth=Path('/proc',str(process.pid),'stat').read_text().rsplit(') ',1)[1].split()[19]
 result=dict(root=str(root),pid=process.pid,birth_ticks=birth,targets=len(rows),workers=12,input_sha256=sha(p.read_bytes()),normal_calls=0,QA_calls=0,model_calls=0,goal_complete=False)
 receipt.write_text(json.dumps(result,indent=2));receipt.chmod(0o444);print(json.dumps(result))
if __name__=='__main__':main()
