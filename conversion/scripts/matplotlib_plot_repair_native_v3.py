from pathlib import Path
import concurrent.futures,json,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1';sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from matplotlib_plot_engine_v3 import convert,CHROME
from matplotlib_plot_quality_v3 import validate
from playwright.sync_api import sync_playwright
cases=[D/'controls/capture_v4_actual_bbox']+sorted((D/'repair_development_v2/cases').iterdir())
def one(case):
 begin=time.monotonic()
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);nr=convert(case,b);b.close()
 out={'id':case.name,'source_execution_reused':True,'native_status':nr['status'],'error':nr.get('error'),'native_cells':nr.get('native_cells'),'images':nr.get('source_raster_image_objects'),'axes':nr.get('source_axes'),'IR_native_seconds':time.monotonic()-begin}
 if nr['status']=='editable_native_development_candidate':
  t=time.monotonic();q=validate(case);out.update(ok=q['ok'],profiles=q['profiles'],QA_seconds=time.monotonic()-t,metric={k:{j:q[k].get(j) for j in ['ok','failures','ssim_1024','foreground_tile_p10_ssim']} for k in ['source_SVG_native_gate','fresh_Agg_native_gate','fresh_SVG_Agg_gate']},assets=q['independent_image_clip_assets'],edit=q['actual_edit_probe'],complete=q['complete_recorded_source_export_and_RNG_contract'])
 (case/'native_v3/repair_result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True);return out
if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as ex:out=list(ex.map(one,cases))
 (D/'repair_development_v2/native_v3_summary.json').write_text(json.dumps(out,indent=2)+'\n')
