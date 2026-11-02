from pathlib import Path
import concurrent.futures,hashlib,json,shutil,sqlite3,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1';O=D/'repair_development_v2';O.mkdir(exist_ok=True);sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from matplotlib_plot_inputs_v1 import payload,sha
from sandbox_runner import run,PYTHON
from matplotlib_plot_engine_v2 import convert,CHROME
from matplotlib_plot_quality_v2 import validate
from playwright.sync_api import sync_playwright
seed='HKUST-Matplotlib-actual-bbox-repair-development-v2-public-seed-20261102'
rows=[json.loads(l) for l in (D/'inputs.jsonl').read_text().splitlines()];db=sqlite3.connect(D/'once.sqlite');done={r[0] for r in db.execute('select id from cases')};db.close()
selected=[]
for source,stratum in [('ChartMimic--ChartMimic','multi_axes'),('ChartMimic--ChartMimic','mixed_bar_line')]:
 pool=[r for r in rows if r['source']==source and r['stratum']==stratum and r['id'] not in done and r['static_audit']['safe_selfcontained_source'] and not r.get('development_excluded')]
 selected.append(min(pool,key=lambda r:sha((seed+r['id']).encode())))
selection=O/'selected.jsonl'
if not selection.exists():selection.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in selected))
else:selected=[json.loads(l) for l in selection.read_text().splitlines()]
def one(row):
 started=time.monotonic();case=O/'cases'/row['id'];case.mkdir(parents=True,exist_ok=False);code=payload(row['payloads']['code']);image=payload(row['payloads']['image']);(case/'source.py').write_bytes(code);(case/'original_reference.png').write_bytes(image);(case/'input_audit.json').write_text(json.dumps(dict(row['static_audit'],id=row['id'],source=row['source'],source_image_sha256=row['payloads']['image']['expected_sha256'],payloads=row['payloads'])));shutil.copyfile(R/'conversion/scripts/matplotlib_plot_capture_v4.py',case/'capture.py');(case/'source_execution_started.json').write_text(json.dumps({'capture_sha256':sha((case/'capture.py').read_bytes()),'source_code_sha256':sha(code),'no_repeat':True}));t=time.monotonic();runresult=run(case,[PYTHON,'-I','/work/capture.py'],timeout=150);captureseconds=time.monotonic()-t;(case/'stdout.log').write_text(runresult.stdout);(case/'stderr.log').write_text(runresult.stderr);execution=json.loads((case/'execution.json').read_text());out={'id':row['id'],'source':row['source'],'stratum':row['stratum'],'source_capture_ok':execution['ok'],'model_calls':0,'source_code_unchanged':sha((case/'source.py').read_bytes())==sha(code),'capture_seconds':captureseconds}
 if execution['ok'] and len(execution['captures'])==1:
  t=time.monotonic()
  with sync_playwright() as p:
   b=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);nr=convert(case,b);b.close()
  out.update(native_seconds=time.monotonic()-t,native_status=nr['status'],native_error=nr.get('error'),source_export_registration=nr.get('source_export_registration'),source_axes=nr['source_axes'],source_data_vertices=nr['source_data_vertices'],native_cells=nr.get('native_cells'),text_cells=nr.get('editable_text_cells'))
  if nr['status']=='editable_native_development_candidate':
   t=time.monotonic();q=validate(case);out.update(QA_seconds=time.monotonic()-t,qualified=q['ok'],profiles=q['profiles'],source_SVG_native_gate=q['source_SVG_native_gate'],source_Agg_native_gate=q['fresh_Agg_native_gate'],source_export_gate=q['fresh_SVG_Agg_gate'],complete_contract=q['complete_recorded_source_export_and_RNG_contract'],edit_probe=q['actual_edit_probe'])
 out['seconds']=time.monotonic()-started;(case/'repair_result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True);return out
if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:result=list(ex.map(one,selected))
 (O/'summary.json').write_text(json.dumps({'seed':seed,'fixed_development_cases':2,'results':result,'no_new_model':True,'original_16_baseline_unchanged':True},indent=2)+'\n')
