from pathlib import Path
import concurrent.futures,json,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/matplotlib_plot_pipeline_20261102_v1';sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from matplotlib_plot_engine_v5 import convert,CHROME
from matplotlib_plot_quality_v5 import validate
from playwright.sync_api import sync_playwright
cases=[D/'colorbar_development_v3/cases/dbc14b29eda0cafe5a5de5f5070fe60010e07df11a162d10c196f6e3c91a1fd2',D/'cases/72973d4c5e745314d5f7eacacb5857460619a99658f6782922946a8f6b3a4fc0',D/'cases/c51b288fc53501f59d25c3176f189849a3ffd3668db4eae5e0e8c2d3e626611f']
def one(case):
 t=time.monotonic()
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);r=convert(case,b);b.close()
 out={'id':case.name,'source_execution_reused_no_repeat':True,'native_status':r['status'],'error':r.get('error'),'IR_seconds':time.monotonic()-t,'text_geometry_translations':r.get('live_text_geometry_corrected_objects'),'native_objects':r.get('native_cells'),'source_data_vertices':r['source_data_vertices']}
 if r['status']=='editable_native_development_candidate':
  t=time.monotonic();q=validate(case);out.update(ok=q['ok'],profiles=q['profiles'],QA_seconds=time.monotonic()-t,coverage=q['independent_source_coverage'],assets=q['source_image_assets_complete'],edit=q['actual_edit_probe'],gates={k:{j:q[k].get(j) for j in ['ok','failures','ssim_1024','foreground_tile_p10_ssim']} for k in ['source_SVG_native_gate','fresh_Agg_native_gate','fresh_SVG_Agg_gate']})
 (case/'native_v5/repair_result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True);return out
if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as ex:results=list(ex.map(one,cases))
 (D/'text_geometry_repair_v1_summary.json').write_text(json.dumps(results,indent=2)+'\n')
