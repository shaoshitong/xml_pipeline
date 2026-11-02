import json,sqlite3,io,hashlib
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert_v5 import build
from svg_source_coverage_v2 import audit
from native_move_audit import audit as move_audit
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite');id,raw=D.execute('select id,output_record from jobs where id like "003be89c%"').fetchone();out=json.loads(raw);src=R/(out.get('source_render_svg') or out['original_source_code']);code=src.read_text();data=(R/out['original_reference']).read_bytes();w,h=Image.open(io.BytesIO(data)).size
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page(viewport={'width':w,'height':h});page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+code);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',[w,h]);page.evaluate('document.fonts.ready');dom=page.evaluate((W/'scripts/svg_dom.js').read_text());xml,stats=build(dom,w,h);coverage=audit(dom,xml,stats);b.close()
assert len(stats['native_graphviz_arrowheads'])>0,stats;assert coverage['ok'],coverage
movement=move_audit(xml);assert len(movement['moves'])==2*movement['edge_count'];assert all(abs(m['delta']['x']-17)<.05 and abs(m['delta']['y']-11)<.05 for m in movement['moves']);assert all(m['arrow']=='open' for m in movement['moves'] if m['side']=='target')
render=native.native_job(xml,w,h,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];png=render.pop('png');work=W/'vee_native_pilot'/id;work.mkdir(parents=True,exist_ok=True);(work/'diagram.drawio').write_text(xml);(work/'image.png').write_bytes(png);report={'id':id,'time':now(),'source_svg':str(src.relative_to(R)),'source_coverage':coverage,'arrow_conversions':stats['native_graphviz_arrowheads'],'movement':movement,'stats':stats,'reference_ssim':metric(data,png),'current_harness_reference_ssim':out['metrics']['original_reference_ssim_512'],'render':render['native_render'],'accepted':False};(work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'id':id,'reference_ssim':report['reference_ssim'],'current_harness_reference_ssim':report['current_harness_reference_ssim'],'arrows':stats['counts']['native_arrowheads'],'real_terminal_moves':len(movement['moves']),'coverage':coverage,'accepted':False}))
