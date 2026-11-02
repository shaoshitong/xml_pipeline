"""Native edge paint-order repair preserving every cell and terminal binding."""
import json,io,xml.etree.ElementTree as E
import numpy as np
from PIL import Image,ImageColor
from native_worker import R,W,native
from portable_native_fonts import ready_page
from strict_canvas_gate import require_declared_page
from mermaid_native_v2 import check_backgrounds
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

def reorder(xml, order):
 assert not order['cyclic'], 'Cross-edge label occlusion constraints form a cycle'
 root=E.fromstring(xml);container=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in root.iter('mxCell')}
 edges=[c for c in container if c.get('edge')=='1'];assert len(edges)==len(order['ordered']) and set(order['ordered'])=={c.get('id') for c in edges}
 assert len({c.get('parent') for c in edges})<=1,'Mixed parent edges require a separate paint-order proof'
 replacement=iter([cells[id] for id in order['ordered']]);container[:]=[next(replacement) if c.get('edge')=='1' else c for c in list(container)]
 candidate=E.tostring(root,encoding='unicode')
 assert {c.get('id'):E.tostring(c) for c in E.fromstring(xml).iter('mxCell')}=={c.get('id'):E.tostring(c) for c in root.iter('mxCell')}
 return candidate

def inspect_order(browser,xml,bindings):
 page=ready_page(browser)
 try:return page.evaluate(ORDER_SCRIPT,{'xml':xml,'bindings':bindings})
 finally:page.close()

def repair(browser,xml,bindings):
 check_backgrounds(xml,bindings);order=inspect_order(browser,xml,bindings);return reorder(xml,order),order

def pixel_audit(xml,boxes,w,h):
 if not boxes:return {'ok':True,'backgrounds':0,'checks':[],'bad_pixels':0}
 root=E.fromstring(xml)
 for cell in root.iter('mxCell'):
  if cell.get('value'):cell.set('value','')
 result=native.native_job(E.tostring(root,encoding='unicode'),w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert result['ok'];require_declared_page(result['native_render'],w,h)
 pixels=np.asarray(Image.open(io.BytesIO(result['png'])).convert('RGB')).astype(int);checks=[]
 for box in boxes:
  x,y,bw,bh=[box[k] for k in ['x','y','w','h']];crop=pixels[int(np.ceil(y))+2:int(np.floor(y+bh))-2,int(np.ceil(x))+2:int(np.floor(x+bw))-2];assert crop.size,'Background too small for independent interior pixel check'
  expected=np.array(ImageColor.getrgb(box['source_css_color']));bad=int((np.max(np.abs(crop-expected),axis=2)>2).sum());checks.append({'background':box['background'],'non_background_pixels':bad,'tested_pixels':crop.shape[0]*crop.shape[1]})
 bad=sum(c['non_background_pixels'] for c in checks)
 return {'ok':bad==0,'backgrounds':len(boxes),'bad_pixels':bad,'checks':checks,'diagnostic':'Actual drawio render with text hidden; opaque label interiors must match source CSS fill, including intersections with other connectors.'}
