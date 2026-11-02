import io,json,hashlib
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from mermaid_semantic_audit import PARSE
from mermaid_native_v1 import build
from svg_source_coverage_v2 import audit
from svg_batch import metric
selected=[x for x in json.loads((W/'text_fidelity_selection.json').read_text()) if x['format']=='mermaid'];base=W/'mermaid_native_probe';base.mkdir(exist_ok=True);results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for row in selected:
  work=base/row['id'];work.mkdir(exist_ok=True);ctx=b.new_context(viewport={'width':800,'height':600});page=ctx.new_page();blocked=[];page.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page.set_content('<html><body></body></html>');page.add_script_tag(path=str(W/'runtime/mermaid_versions/10.9.1/mermaid.min.js'));entry={'id':row['id']}
  try:
   code=(R/row['source_code']).read_text();ref=(R/row['reference']).read_bytes();w,h=Image.open(io.BytesIO(ref)).size;svg=page.evaluate('''async ({code,font})=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,themeVariables:font?{fontFamily:font}:{},flowchart:{htmlLabels:true}});return (await mermaid.render('diagram',code)).svg;}''',{'code':code,'font':'Arial' if row['id'].startswith('ab692') else None});ast=page.evaluate(PARSE,code);page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.set_viewport_size({'width':w,'height':h});page.evaluate('''a=>{let s=document.querySelector('svg');s.style.maxWidth='none';s.style.width=a.w+'px';s.style.height=a.h+'px';s.setAttribute('preserveAspectRatio','none');}''',{'w':w,'h':h});page.evaluate('document.fonts.ready');sourcepng=page.screenshot();md=page.evaluate((W/'scripts/mermaid_dom_adapter_v1.js').read_text(),ast);dom=page.evaluate((W/'scripts/svg_dom_mermaid_v1.js').read_text());xml,stats,processed=build(dom,w,h,md);coverage=audit(processed,xml,stats);assert coverage['ok'],json.dumps(coverage['errors']);assert not blocked,blocked;render=native.native_job(xml,w,h,90,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'],str({k:v for k,v in render.items() if k!='png'});(work/'diagram.drawio').write_text(xml);(work/'image.png').write_bytes(render['png']);(work/'source.png').write_bytes(sourcepng);(work/'source.svg').write_text(svg);(work/'dom.json').write_text(json.dumps(processed));(work/'stats.json').write_text(json.dumps(stats,indent=2));(work/'ast.json').write_text(json.dumps(ast,indent=2));entry.update(source_ssim=metric(ref,sourcepng),native_ssim=metric(ref,render['png']),source_native_ssim=metric(sourcepng,render['png']),counts=stats['counts'],issues=stats['issues'],coverage=coverage,render=render['native_render'])
  except Exception as e:entry['error']=repr(e)
  finally:ctx.close()
  results.append(entry);print(json.dumps(entry),flush=True)
 b.close()
(base/'report.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
