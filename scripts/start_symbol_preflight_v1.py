from pathlib import Path
import subprocess,json
runner='''from pathlib import Path
import sys,json,sqlite3,time,traceback,os
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
import compiler_svg_scene_frontend_v13 as f
identifier='6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb';start=time.monotonic();out=dict(id=identifier,normal_calls=0)
try:
 with sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True)as db:
  db.row_factory=sqlite3.Row;job=dict(db.execute('select*from jobs where id=?',(identifier,)).fetchone())
 prepared=f.prepare_source(job)
 dom=prepared['capture']['dom'];facts=dom.get('sourceSymbolViewportFacts',[])
 out.update(ok=prepared['ok'],source_work=str(prepared['work']),objects=len(dom['objects']),issues=dom.get('issues'),symbol_instances=len(facts),symbol_proved=sum(x.get('proof',{}).get('ok')is True for x in facts),contexts=dom['sceneMetadata']['useContexts'])
except Exception as e:out.update(ok=False,error=str(e),traceback=traceback.format_exc())
out['elapsed_seconds']=time.monotonic()-start
Path(sys.argv[1]).write_text(json.dumps(out,indent=2));print(json.dumps(out))
'''
code='''from pathlib import Path
import subprocess,json,uuid,os
R=Path('/backup/shaoshitong/img2code_20261029');work=R/'conversion/symbol_runtime_preflight_v1'/uuid.uuid4().hex;work.mkdir(parents=True)
script=work/'run.py';script.write_text(RUNNER)
log=(work/'output.log').open('wb');env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(script),str(work/'summary.json')],stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
receipt=dict(pid=p.pid,work=str(work),summary=str(work/'summary.json'));print(json.dumps(receipt))
'''.replace('RUNNER',repr(runner))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=20)
print(r.stdout);print(r.stderr)
if r.returncode==0:Path('outputs/symbol-runtime-preflight-launch-20261102.json').write_text(r.stdout)
raise SystemExit(r.returncode)
