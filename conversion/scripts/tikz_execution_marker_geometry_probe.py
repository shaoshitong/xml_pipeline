"""Read actual pinned native marker SVGs; no corpus mutations or media transfer."""
import json
from playwright.sync_api import sync_playwright
from native_worker import R,W
report=json.loads((W/'tikz_execution_binding_v2_pilot.json').read_text());work=R/report['work'];base=json.loads((W/'tikz_execution_binding_pilot.json').read_text());dom=json.loads((R/base['work']/'source_dom.json').read_text());objects={o['id']:o for o in dom['objects']};proof=base['binding']['binding'];xml=(work/'rank0.drawio').read_text()
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 try:
  page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;padding:0}</style>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(R/'evaluation/assets/viewer-static.min.js'))
  native=page.evaluate(r'''xml=>{document.body.innerHTML='<div id="g" style="width:8192px;height:8192px;position:relative"></div>';const g=new Graph(document.getElementById('g')),doc=mxUtils.parseXml(xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();const out=Object.values(g.model.cells).filter(c=>c.edge).map(c=>{let s=g.view.getState(c);return {id:c.id,points:s.absolutePoints,style:s.style,svg:s.shape.node.outerHTML,paths:[...s.shape.node.querySelectorAll('path')].map(p=>{let m=p.getCTM();return {d:p.getAttribute('d'),matrix:[m.a,m.b,m.c,m.d,m.e,m.f],fill:p.getAttribute('fill'),stroke:p.getAttribute('stroke'),strokeWidth:p.getAttribute('stroke-width'),linejoin:p.getAttribute('stroke-linejoin')}})}});g.destroy();return out}''',xml)
 finally:browser.close()
out={'native':native,'source':[{'marker':objects[m['source_object']],'shaft':objects[m['edge']]} for m in proof['native_arrowheads']]};(work/'actual_svg_geometry.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'native_first':native[0],'source_first':out['source'][0]}))
