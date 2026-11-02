import json,sqlite3
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now

D=sqlite3.connect(W/'jobs.sqlite',timeout=60);results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for id in ['0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641','02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce','047acd3596838a3e998ae96081f3d778bdec3210a6eb1e0ced7e4aafbe81733f']:
  r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);files=r['native_source_geometry_repair']['files'];ast=json.loads((R/files['source_ast.json']['file']).read_text());svg=(R/r['source_render_svg']).read_text();w,h=Image.open(R/r['original_reference']).size;page=b.new_page(viewport={'width':w,'height':h});page.route('**/*',lambda route:route.abort());html='<style>html,body{margin:0;background:white;overflow:hidden}</style>'+svg;page.set_content(html);page.evaluate('document.fonts.ready');before=page.screenshot();ids=page.locator('g.node').evaluate_all('(es)=>es.map(e=>e.id)');page.evaluate((W/'scripts/mermaid_dom_adapter_v2.js').read_text(),ast);assert before==page.screenshot();assert ids==page.locator('g.node').evaluate_all('(es)=>es.map(e=>e.id)');dom=page.evaluate((W/'scripts/svg_dom_mermaid_v3.js').read_text());assert before==page.screenshot(),'Object extractor changed pixels';assert not dom['issues']
  out={'id':id,'metadata_annotation_pixels_identical':True,'object_extraction_pixels_identical':True,'node_ids_unchanged':True}
  if id.startswith('047'):
   page.set_content(html);page.evaluate('document.fonts.ready');page.evaluate((W/'scripts/mermaid_dom_adapter_v1.js').read_text(),ast);assert page.screenshot()!=before;out['legacy_css_collision_reproduced']=True
  results.append(out);page.close()
 b.close()
out={'at':now(),'results':results,'ok':True,'database_unchanged':True};(W/'mermaid_adapter_nonvisual_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
