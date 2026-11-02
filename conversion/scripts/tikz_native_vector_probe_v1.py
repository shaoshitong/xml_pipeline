"""Actual per-cell native SVG geometry vs the same seen original-PDF scene."""
from pathlib import Path
import json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from playwright.sync_api import sync_playwright
from compiler_tikz_poppler_source_v2 import CHROME
INPUT=W/'compiler_tikz_poppler_source_v2/development/00af61a2de3044e998f0e117d30d1f04/report.json'

def main():
 target=W/'compiler_tikz_poppler_source_v2/development'/('actual_native_vector_'+uuid.uuid4().hex);target.mkdir(parents=True,exist_ok=False);out=[]
 for row in json.loads(INPUT.read_bytes())['records']:
  record=json.loads(Path(row['record_file']).read_bytes());proof=record['compiler_tikz_poppler_source_v2'];dom=json.loads((R/proof['files']['source_dom']['file']).read_bytes());padding=json.loads((R/proof['files']['native_padding_proof']['file']).read_bytes());dx,dy=padding['geometry']['translation'];xml=(R/record['code_file']).read_text()
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text']);page=browser.new_page(viewport={'width':1024,'height':2048});page.route('**/*',lambda route:route.abort())
   try:
    page.set_content('<style>html,body{margin:0;padding:0}</style><div id="g" style="position:relative;width:8192px;height:8192px"></div>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(R/'evaluation/assets/viewer-static.min.js'))
    native=page.evaluate('''xml=>{const g=new Graph(document.getElementById('g'));new mxCodec(mxUtils.parseXml(xml)).decode(mxUtils.parseXml(xml).getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();const out=[];for(const c of Object.values(g.model.cells)){const s=g.view.getState(c);if(!s?.shape?.node||!c.vertex)continue;const paths=[...s.shape.node.querySelectorAll('path,rect,ellipse,polygon')].map(e=>{const b=e.getBoundingClientRect(),cs=getComputedStyle(e),m=e.getScreenCTM();return {box:{x:b.x,y:b.y,w:b.width,h:b.height},transform:m?[m.a,m.b,m.c,m.d,m.e,m.f]:null,fill:cs.fill,stroke:cs.stroke,strokeWidth:cs.strokeWidth};});out.push({cell:c.id,offset:s.shape.getSvgScreenOffset?.(),bounds:{x:s.x,y:s.y,w:s.width,h:s.height},paths});}g.destroy();return out;}''',xml)
   finally:browser.close()
  byid={x['cell']:x for x in native};diff=[]
  for obj in dom['objects']:
   if obj['type']!='shape' or obj['id'] not in byid:continue
   n=byid[obj['id']]
   if not n['paths']:continue
   b=n['paths'][0]['box'];a=obj['bbox'];diff.append({'cell':obj['id'],'native_svg_offset':n['offset'],'dx':b['x']-dx-a['x'],'dy':b['y']-dy-a['y'],'dw':b['w']-a['w'],'dh':b['h']-a['h'],'native_paths':n['paths']})
  (target/(row['id']+'.json')).write_text(json.dumps({'source_native_vectors':diff,'native_all':native},ensure_ascii=False,indent=2)+'\n');item={'id':row['id'],'vectors':len(diff),'first_geometry_deltas':[{k:v for k,v in x.items() if k!='native_paths'} for x in diff[:8]]};out.append(item);print(json.dumps(item),flush=True)
 (target/'report.json').write_text(json.dumps({'records':out,'unseen_consumed':0,'model_calls':0},indent=2)+'\n');print(json.dumps({'report':str(target/'report.json')}),flush=True)

if __name__=='__main__':main()
