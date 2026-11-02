"""Finite actual native edits and browser-coordinate semantic controls."""
from pathlib import Path
import sys,json,uuid,hashlib
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
ROOT=W/'tikz_node_paint_normal_development_v2/67924c6fa8f74a1bb3893d9af058df0d'
OUTPUT=W/'tikz_node_paint_editing_precision_actual_controls_v1'/uuid.uuid4().hex

def run():
 import tikz_node_paint_editing_v4 as editing
 from playwright.sync_api import sync_playwright
 from compiler_tikz_node_paint_viewport_v2 import CHROME,raw,sha
 OUTPUT.mkdir(parents=True,exist_ok=False);rows=[]
 for identifier in ('8689389d1f64000151962180f407dadaaef208bb7dfcf18b5746f14d9826cd17','0593a28ecc6e324f9bd19cdd673619ddf61a96328c03b396f26ec8dfc3f5e693'):
  old=json.loads((ROOT/identifier/'summary.json').read_bytes());record=json.loads(Path(old['candidate_file']).read_bytes());before=Path(old['candidate_file']).read_bytes();qa_summary=json.loads((ROOT/identifier/'QA4_existing_candidate_summary.json').read_bytes());qa=json.loads(Path(qa_summary['quality_report']).read_bytes());profile=qa['checks']['source'];xml=(R/record['code_file']).read_text();report=editing.audit(xml,record=record,source_profile=profile)
  assert report['ok']and Path(old['candidate_file']).read_bytes()==before
  (OUTPUT/(identifier+'.json')).write_bytes(raw(report));rows.append(dict(id=identifier,vertex_count=report['vertex_count'],edge_count=report['edge_count'],ok=report['ok'],model_and_all_live_states_restored=report['model_and_all_live_states_restored'],report=str(OUTPUT/(identifier+'.json')),report_sha256=sha((OUTPUT/(identifier+'.json')).read_bytes())))
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
  try:
   page=browser.new_page(viewport={'width':4096,'height':512});page.set_content('<style>html,body{margin:0}</style><svg width="4096" height="512"><rect id="paint" x="2062.86" y="91.78" width="137.79" height="39.37" fill="red"/></svg>');page.add_script_tag(path=str(editing.PRECISION))
   controls=page.evaluate('''()=>{const r=document.getElementById('paint'),box=()=>{const b=r.getBoundingClientRect();return{x:b.x,y:b.y,width:b.width,height:b.height}},before=box(),offset={x:-13,y:19},out=[];r.setAttribute('x',String(2062.86-13));r.setAttribute('y',String(91.78+19));const after=box();out.push({name:'actual_binary32_translation',before,after,offset,expected:true,proof:tikzEditingPaintPrecisionV1.prove(before,after,offset)});r.setAttribute('width',String(137.79+.002));out.push({name:'actual_point002_extent_negative',before,after:box(),offset,expected:false,proof:tikzEditingPaintPrecisionV1.prove(before,box(),offset)});r.setAttribute('width','137.79');r.setAttribute('x',String(2062.86-13+.25*100/72));out.push({name:'actual_quarter_bp_shift_negative',before,after:box(),offset,expected:false,proof:tikzEditingPaintPrecisionV1.prove(before,box(),offset)});return out;}''')
   assert all(c['proof']['ok']is c['expected']for c in controls)
  finally:browser.close()
 summary=dict(schema='tikz_node_paint_editing_precision_actual_controls_v1',producer=dict(file=str(Path(__file__)),sha256=sha(Path(__file__).read_bytes())),native_existing_candidate_edits=rows,actual_browser_controls=controls,normal_frontend_calls=0,model_calls=0,goal_complete=False)
 (OUTPUT/'proof.json').write_bytes(raw(summary));print(json.dumps(dict(file=str(OUTPUT/'proof.json'),sha256=sha((OUTPUT/'proof.json').read_bytes()))),flush=True)

if __name__=='__main__':run()
