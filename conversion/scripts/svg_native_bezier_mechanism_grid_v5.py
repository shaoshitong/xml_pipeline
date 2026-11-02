from pathlib import Path
import sys,json,xml.etree.ElementTree as E,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from svg_native_bezier_ir_v1 import compile_path
from playwright.sync_api import sync_playwright
from portable_native_fonts import ready_page
script=r'''a=>{document.body.innerHTML='<div id="p" style="width:256px;height:256px;position:absolute;top:0;left:0"></div>';const graph=new Graph(document.getElementById('p')),doc=mxUtils.parseXml(a.xml);new mxCodec(doc).decode(doc.documentElement,graph.model);graph.refresh();graph.view.validate();const cell=graph.model.cells.curve,state=graph.view.getState(cell);const before=state.shape.node.outerHTML,points=state.absolutePoints.map(p=>[p.x,p.y]),curved=Graph.getEdgeCurvePoints(state);const initialBounds=state.shape.bounds,initialStyle=state.style;const clone=cell.geometry.clone();clone.targetPoint.x+=13;const clonePointCount=clone.points?.length;graph.model.setGeometry(cell,clone);graph.refresh();graph.view.validate();const changed=graph.view.getState(cell);const result={before,after:changed.shape.node.outerHTML,style:initialStyle,bounds:initialBounds,pointCount:points.length,first:points.slice(0,4),last:points.slice(-4),curvedPointCount:curved?.length,clonePointCount,afterPointCount:changed.absolutePoints.length};graph.destroy();return result;}'''
rows=[]
with sync_playwright()as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 try:
  page=ready_page(browser)
  for final_y in (80,100):
   for curved in (0,1):
    for span in (2,2000):
     ir=compile_path('M20 80 C20 20 140 20 140 '+str(final_y),maximum_span=span);points=ir['points'];root=E.Element('mxGraphModel');r=E.SubElement(root,'root');E.SubElement(r,'mxCell',id='0');E.SubElement(r,'mxCell',id='1',parent='0');cell=E.SubElement(r,'mxCell',id='curve',edge='1',parent='1',style='edgeStyle=none;shape=connector;bezier=1;curved='+str(curved)+';rounded=0;jumpStyle=none;startArrow=none;endArrow=none;strokeColor=#123456;strokeWidth=1;');g=E.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'});E.SubElement(g,'mxPoint',x=str(points[0][0]),y=str(points[0][1]),attrib={'as':'sourcePoint'});E.SubElement(g,'mxPoint',x=str(points[-1][0]),y=str(points[-1][1]),attrib={'as':'targetPoint'});b=E.SubElement(g,'Array',attrib={'as':'points'});
     for point in points[1:-1]:E.SubElement(b,'mxPoint',x=str(point[0]),y=str(point[1]))
     actual=page.evaluate(script,dict(xml=E.tostring(root,encoding='unicode')));rows.append(dict(final_y=final_y,curved=curved,span=span,actual=actual))
 finally:browser.close()
work=W/'svg_native_bezier_mechanism_grid_v4'/uuid.uuid4().hex;work.mkdir(parents=True);(work/'proof.json').write_text(json.dumps(rows,indent=2));print(json.dumps(dict(path=str(work/'proof.json'),rows=rows)))
