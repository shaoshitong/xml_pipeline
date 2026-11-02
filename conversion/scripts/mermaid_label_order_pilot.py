"""Derive native edge ordering constraints without changing geometry or bindings."""
import json,sqlite3,copy,io,xml.etree.ElementTree as E
from PIL import Image
import numpy as np
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now,sha
from portable_native_fonts import ready_page
from mermaid_native_v2 import check_backgrounds,MOVE_SCRIPT
from native_move_audit import SCRIPT as ENDPOINT_MOVES
from svg_batch import metric
from strict_canvas_gate import require_declared_page

ORDER_SCRIPT=r'''async ({xml,bindings})=>{
document.body.innerHTML='<div id="g"></div>';const g=new Graph(document.getElementById('g')),doc=mxUtils.parseXml(xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();
const pane=g.view.drawPane, inv=pane.getScreenCTM().inverse();
const boxes=bindings.map(x=>{const s=g.view.getState(g.model.cells[x.background]);return {...x,x:s.x,y:s.y,w:s.width,h:s.height}});
const edges=Object.values(g.model.cells).filter(c=>c.edge),constraints=[];
for(const e of edges){const s=g.view.getState(e),paths=[...s.shape.node.querySelectorAll('path')];
 for(const box of boxes){if(box.edge===e.id)continue;let hit=false;
  for(const path of paths){const css=getComputedStyle(path);if(css.stroke==='none' && css.fill==='none')continue;
   const matrix=inv.multiply(path.getScreenCTM()),length=path.getTotalLength(),pad=parseFloat(css.strokeWidth||0)/2;
   for(let t=0;t<=Math.ceil(length*2);t++){const q=path.getPointAtLength(Math.min(length,t/2)).matrixTransform(matrix);
    if(q.x>box.x-pad && q.x<box.x+box.w+pad && q.y>box.y-pad && q.y<box.y+box.h+pad){hit=true;break;}}
   if(hit)break;
  }
  if(hit)constraints.push({before:e.id,after:box.edge,background:box.background});
 }
}
const order=edges.map(e=>e.id),pending=new Set(order),sorted=[];
while(pending.size){const next=order.find(id=>pending.has(id)&&!constraints.some(c=>c.after===id&&pending.has(c.before)));if(!next)break;sorted.push(next);pending.delete(next);}
g.destroy();return {boxes,constraints,original_order:order,ordered:sorted,cyclic:[...pending]};}'''

def main():
 ID='02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce';db=sqlite3.connect(W/'jobs.sqlite',timeout=60);raw=db.execute('select output_record from jobs where id=?',(ID,)).fetchone()[0];r=json.loads(raw);xml=(R/r['code_file']).read_text();bindings=r['svg_conversion']['native_html_label_backgrounds'];B=W/'mermaid_label_order_pilot'/ID;B.mkdir(parents=True,exist_ok=True)
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser);order=page.evaluate(ORDER_SCRIPT,{'xml':xml,'bindings':bindings});(B/'order.json').write_text(json.dumps(order,indent=2));assert not order['cyclic'],order
  root=E.fromstring(xml);container=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in root.iter('mxCell')};old=list(container);replacement=iter([cells[id] for id in order['ordered']]);container[:]=[next(replacement) if c.get('edge')=='1' else c for c in old];candidate=E.tostring(root,encoding='unicode');check_backgrounds(candidate,bindings)
  # Only edge order changed: all cell attributes, values, geometry and parent/terminal IDs are byte-identical.
  assert {c.get('id'):E.tostring(c) for c in E.fromstring(xml).iter('mxCell')}=={c.get('id'):E.tostring(c) for c in root.iter('mxCell')}
  moves=page.evaluate(ENDPOINT_MOVES,candidate);backgroundmoves=page.evaluate(MOVE_SCRIPT,{'xml':candidate,'bindings':bindings});browser.close()
 for m in moves['moves']:assert abs(m['delta']['x']-17)<.01 and abs(m['delta']['y']-11)<.01
 for m in backgroundmoves:assert all(abs(m['background_delta'][k]-m['label_delta'][k])<.01 for k in ['x','y'])
 w,h=Image.open(R/r['original_reference']).size
 def render(s):
  out=native.native_job(s,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert out['ok'];require_declared_page(out['native_render'],w,h);return out
 result=render(candidate);(B/'candidate.drawio').write_text(candidate);(B/'candidate.png').write_bytes(result['png']);(B/'native_render.json').write_text(json.dumps(result['native_render'],indent=2))
 for c in root.iter('mxCell'):
  if c.get('value'):c.set('value','')
 diagnostic=render(E.tostring(root,encoding='unicode'));pixels=np.asarray(Image.open(io.BytesIO(diagnostic['png'])).convert('RGB'));checks=[]
 for box in order['boxes']:
  x,y,bw,bh=[box[k] for k in ['x','y','w','h']];crop=pixels[int(np.ceil(y))+2:int(np.floor(y+bh))-2,int(np.ceil(x))+2:int(np.floor(x+bw))-2];assert crop.size;bad=int(((np.max(crop,axis=2)-np.min(crop,axis=2))>20).sum());checks.append({'background':box['background'],'colored_connector_pixels_inside':bad})
 out={'at':now(),'id':ID,'input_code_sha256':r['code_sha256'],'candidate_sha256':sha(candidate.encode()),'constraints':order,'actual_pixel_checks':checks,'endpoint_moves':moves,'background_moves':backgroundmoves,'before_ssim':r['metrics']['original_reference_ssim_512'],'after_ssim':metric((R/r['original_reference']).read_bytes(),result['png']),'all_cells_unchanged':True,'published':False,'accepted':False,'occlusion_fixed':all(x['colored_connector_pixels_inside']==0 for x in checks)};(B/'report.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
if __name__=='__main__':main()
