import json,sqlite3
from playwright.sync_api import sync_playwright
from native_worker import R,W
from portable_native_fonts import ready_page
ID='02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce';d=sqlite3.connect(W/'jobs.sqlite');r=json.loads(d.execute('select output_record from jobs where id=?',(ID,)).fetchone()[0]);xml=(R/r['code_file']).read_text()
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(b);out=page.evaluate('''async xml=>{document.body.innerHTML='<div id="g"></div>';const g=new Graph(document.getElementById('g')),doc=mxUtils.parseXml(xml);new mxCodec(doc).decode(doc.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();const e=Object.values(g.model.cells).find(c=>c.edge);return {markerFunction:mxMarker.markers.block.toString(),edge:e.id,style:g.getCellStyle(e),nativeSvg:g.view.getState(e).shape.node.innerHTML};}''',xml);b.close()
out['source_marker']=r['svg_conversion']['native_graphviz_arrowheads'][0];(W/'mermaid_marker_size_investigation.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
