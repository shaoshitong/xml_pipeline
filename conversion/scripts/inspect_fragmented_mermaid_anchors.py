import json,sqlite3,io,base64,collections
from PIL import Image,ImageDraw
from playwright.sync_api import sync_playwright
from native_worker import R,W
from mermaid_reference_fit_v4 import rgb,components,NODE_SCRIPT,STYLE_SCRIPT,BUNDLE
ids=['043b313be6a7a027462c0d86aab0c8e91eb0b4eea30c34757b53fc95401837ed','0b4d8f904638e102675cf373b09496594eab6c9bfd948e01a460c56fb405a785','0b8e6086486b77fdc223c81e902f2927af8f9a3be730f9f2133c68479b637fdb'];D=sqlite3.connect(W/'jobs.sqlite',timeout=60);rows=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for id in ids:
  r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);ref=(R/r['original_reference']).read_bytes();h,w=rgb(ref).shape[:2];page=b.new_page(viewport={'width':w,'height':h});page.route('**/*',lambda route:route.abort());page.set_content('<html></html>');page.add_script_tag(path=str(BUNDLE));svg=page.evaluate("async code=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',flowchart:{htmlLabels:true}});return (await mermaid.render('diagram',code)).svg}",(R/r['original_source_code']).read_text());page.set_content('<style>html,body{margin:0;background:white;overflow:hidden}</style>'+svg);page.evaluate(STYLE_SCRIPT,[w,h,0,0]);page.evaluate('document.fonts.ready');source=page.screenshot();nodes=page.evaluate(NODE_SCRIPT);group=collections.defaultdict(list)
  for n in nodes:group[tuple(n['color'])].append(n)
  B=W/'fragmented_anchor_probe'/id;B.mkdir(parents=True,exist_ok=True);(B/'source.png').write_bytes(source);(B/'source.svg').write_text(svg);out={'id':id,'nodes':nodes,'groups':[],'reference':r['original_reference']}
  for color,ns in group.items():
   area=max(32,min((n['x1']-n['x0'])*(n['y1']-n['y0']) for n in ns)*.05);out['groups'].append({'color':color,'source_components':components(rgb(source),color,area),'reference_components':components(rgb(ref),color,area)})
  (B/'anchors.json').write_text(json.dumps(out,indent=2));rows.append(out);page.close()
 b.close()
(W/'fragmented_anchor_probe.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows))
