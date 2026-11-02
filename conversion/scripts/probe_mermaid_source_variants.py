import json,io,sqlite3
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);id='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641';r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);code=(R/r['original_source_code']).read_text();ref=(R/r['original_reference']).read_bytes();w,h=Image.open(io.BytesIO(ref)).size;B=W/'mermaid_variant_source_probe'/id;B.mkdir(parents=True,exist_ok=True);rows=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for version,html_labels in [(v,l) for v in ['10.9.1','11.0.2','11.4.1','11.17.2'] for l in [True,False]]:
  font=None
  name=version+('_html' if html_labels else '_svg');ctx=b.new_context(viewport={'width':800,'height':600},service_workers='block');page=ctx.new_page();blocked=[];page.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page.set_content('<html><body></body></html>');page.add_script_tag(path=str(W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js' if version=='11.17.2' else W/'runtime/mermaid_versions'/version/'mermaid.min.js'));svg=page.evaluate('''async ({code,font,html_labels})=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,themeVariables:font?{fontFamily:font}:{},flowchart:{htmlLabels:html_labels}});return (await mermaid.render('diagram',code)).svg;}''',{'code':code,'font':font,'html_labels':html_labels});page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.set_viewport_size({'width':w,'height':h});page.evaluate('({w,h})=>{let s=document.querySelector("svg");s.style.maxWidth="none";s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("preserveAspectRatio","none")}',{'w':w,'h':h});page.evaluate('document.fonts.ready');png=page.screenshot();assert not blocked;(B/(name+'.svg')).write_text(svg);(B/(name+'.png')).write_bytes(png);labels=page.evaluate('()=>[...document.querySelectorAll(".nodeLabel")].map((e,i)=>{e.setAttribute("data-probe-id",i);const s=getComputedStyle(e);return {selector:`[data-probe-id="${i}"]`,text:e.textContent,font:s.fontFamily,weight:s.fontWeight,size:s.fontSize,bounds:e.getBoundingClientRect().toJSON()}})');cdp=ctx.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');root=cdp.send('DOM.getDocument',{'depth':-1})['root']['nodeId']
  for label in labels:
   node=cdp.send('DOM.querySelector',{'nodeId':root,'selector':label['selector']})['nodeId'];label['actual_fonts']=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
  rows.append({'version':version,'html_labels':html_labels,'font':font,'ssim':metric(ref,png),'labels':labels});ctx.close()
 b.close()
result={'at':now(),'id':id,'results':rows};(B/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
