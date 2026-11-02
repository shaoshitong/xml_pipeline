from pathlib import Path
import ast,concurrent.futures,json,re,shutil,sqlite3,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1';O=D/'colorbar_development_v3';O.mkdir(exist_ok=True);sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from matplotlib_plot_inputs_v1 import payload,sha
from sandbox_runner import run,PYTHON
from matplotlib_plot_engine_v4 import convert,CHROME
from matplotlib_plot_quality_v4 import validate
from playwright.sync_api import sync_playwright
seed='HKUST-Matplotlib-colorbar-component-dev-v3-public-seed-20261102';rows=[json.loads(l) for l in (D/'inputs.jsonl').read_text().splitlines()];db=sqlite3.connect(D/'once.sqlite');done={r[0] for r in db.execute('select id from cases')};db.close();done|={p.name for p in (D/'repair_development_v2/cases').iterdir()};selected=[]
for source in ['CSU-JPG--Chart2Code','ChartMimic--ChartMimic']:
 pool=sorted([r for r in rows if r['source']==source and r['static_audit']['safe_selfcontained_source'] and r['id'] not in done and not r.get('development_excluded') and r['static_audit']['call_counts'].get('colorbar',0)>0],key=lambda r:sha((seed+r['id']).encode()))
 for r in pool:
  code=payload(r['payloads']['code']);strings=[n.value for n in ast.walk(ast.parse(code)) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
  if any(re.search('[\u3400-\u9fff]',s) for s in strings):continue
  selected.append(r);break
assert len(selected)==2;(O/'selected.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in selected))
def one(row):
 t=time.monotonic();case=O/'cases'/row['id'];case.mkdir(parents=True,exist_ok=False);code=payload(row['payloads']['code']);image=payload(row['payloads']['image']);(case/'source.py').write_bytes(code);(case/'original_reference.png').write_bytes(image);(case/'input_audit.json').write_text(json.dumps(dict(row['static_audit'],id=row['id'],source=row['source'],source_image_sha256=row['payloads']['image']['expected_sha256'],payloads=row['payloads'])));shutil.copyfile(R/'conversion/scripts/matplotlib_plot_capture_v5.py',case/'capture.py');(case/'source_execution_started.json').write_text(json.dumps({'capture_sha256':sha((case/'capture.py').read_bytes()),'source_code_sha256':sha(code),'no_repeat':True}));r=run(case,[PYTHON,'-I','/work/capture.py'],timeout=150);(case/'stdout.log').write_text(r.stdout);(case/'stderr.log').write_text(r.stderr);e=json.loads((case/'execution.json').read_text());out={'id':row['id'],'source':row['source'],'source_capture_ok':e['ok'],'capture_seconds':time.monotonic()-t,'new_model_calls':0}
 if e['ok'] and len(e['captures'])==1:
  t=time.monotonic()
  with sync_playwright() as p:
   b=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);nr=convert(case,b);b.close()
  out.update(IR_seconds=time.monotonic()-t,native_status=nr['status'],error=nr.get('error'),native_objects=nr.get('native_cells'),source_axes=nr['source_axes'],source_data_vertices=nr['source_data_vertices'],colorbar_components=nr.get('backend_rasterized_colorbar_components'))
  if nr['status']=='editable_native_development_candidate':
   t=time.monotonic();q=validate(case);out.update(QA_seconds=time.monotonic()-t,ok=q['ok'],profiles=q['profiles'],assets=q['source_image_assets_complete'],full_arrays=q['source_array_shape_and_count_audit'],edit=q['actual_edit_probe'],gates={k:{j:q[k].get(j) for j in ['ok','failures','ssim_1024','foreground_tile_p10_ssim']} for k in ['source_SVG_native_gate','fresh_Agg_native_gate','fresh_SVG_Agg_gate']})
 (case/'colorbar_result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True);return out
if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:results=list(ex.map(one,selected))
 (O/'summary.json').write_text(json.dumps({'seed':seed,'fixed_real_development_rows':2,'CJK_requires_separate_font_closure_domain':True,'results':results},indent=2)+'\n')
