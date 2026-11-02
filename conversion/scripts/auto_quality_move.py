"""Actual upstream editing proof for endpoints and complete label groups."""
from playwright.sync_api import sync_playwright
from native_worker import R,native
SCRIPT=r'''async xml=>{
document.body.innerHTML='<div id="g" style="width:8192px;height:8192px;position:relative"></div>';
const g=new Graph(document.getElementById('g')),doc=mxUtils.parseXml(xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],g.model);
g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();
const descendants=c=>(c.children||[]).flatMap(x=>[x,...descendants(x)]),moves=[];
for(const edge of Object.values(g.model.cells).filter(c=>c.edge)){
 for(const source of [true,false]){
  const target=g.model.getTerminal(edge,source),state=g.view.getState(edge),endpoint=state.absolutePoints[source?0:state.absolutePoints.length-1].clone();
  const children=descendants(target).map(c=>({id:c.id,x:g.view.getState(c)?.x,y:g.view.getState(c)?.y}));
  const labels=(edge.children||[]).map(c=>({id:c.id,members:[c,...descendants(c)].map(x=>({id:x.id,x:g.view.getState(x)?.x,y:g.view.getState(x)?.y}))}));
  const original=target.geometry.clone(),moved=original.clone();moved.x+=17;moved.y+=11;
  g.model.beginUpdate();g.model.setGeometry(target,moved);g.model.endUpdate();g.view.validate();
  const points=g.view.getState(edge).absolutePoints,after=points[source?0:points.length-1];
  const delta=b=>({id:b.id,x:g.view.getState(g.model.cells[b.id])?.x-b.x,y:g.view.getState(g.model.cells[b.id])?.y-b.y});
  moves.push({edge:edge.id,terminal:target.id,side:source?'source':'target',delta:{x:after.x-endpoint.x,y:after.y-endpoint.y},child_deltas:children.map(delta),label_member_deltas:labels.map(l=>({label:l.id,members:l.members.map(delta)}))});
  g.model.beginUpdate();g.model.setGeometry(target,original);g.model.endUpdate();g.view.validate();
 }
}
g.destroy();return {moves,edge_count:moves.length/2};}'''

def audit(xml):
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
  try:
   page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'));return page.evaluate(SCRIPT,xml)
  finally:browser.close()
