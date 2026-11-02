import io,json,math
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from svg_batch import metric
selected=[r for r in json.loads((W/'text_fidelity_selection.json').read_text()) if r['format']=='mermaid'];work=W/'mermaid_version_probe';work.mkdir(exist_ok=True);results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for version in ['10.9.1','11.0.2','11.4.1','11.17.2']:
  bundle=W/'runtime/mermaid_versions'/version/'mermaid.min.js' if version!='11.17.2' else W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js'
  if not bundle.exists():print('MISSING',version,flush=True);continue
  context=b.new_context(viewport={'width':800,'height':600});page=context.new_page();page.set_default_timeout(30000);page.route('**/*',lambda r:r.abort());page.set_content('<html><body></body></html>');page.add_script_tag(path=str(bundle))
  for r in selected:
   code=(R/r['source_code']).read_text();ref=(R/r['reference']).read_bytes();folder=work/r['id'];folder.mkdir(exist_ok=True)
   for labels in [True,False]:
    name=version+('_html' if labels else '_svg');entry={'id':r['id'],'variant':name,'original_size':Image.open(io.BytesIO(ref)).size}
    try:
     page.set_viewport_size({'width':800,'height':600});svg=page.evaluate('''async ({code,labels})=>{document.body.innerHTML='';mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:labels}});return (await mermaid.render('probe',code)).svg;}''',{'code':code,'labels':labels});page.evaluate('s=>document.body.innerHTML="<style>html,body{margin:0;background:white}</style>"+s',svg);size=page.evaluate('()=>{let s=document.querySelector("svg"),v=s.viewBox.baseVal;s.style.maxWidth="none";s.style.width=Math.ceil(v.width)+"px";s.style.height=Math.ceil(v.height)+"px";return {width:Math.ceil(v.width),height:Math.ceil(v.height)}}');page.set_viewport_size(size);page.evaluate('document.fonts.ready');png=page.screenshot();(folder/(name+'.svg')).write_text(svg);(folder/(name+'.png')).write_bytes(png);entry.update(size=size,ssim=metric(ref,png));entry['first_labels']=page.evaluate('()=>[...document.querySelectorAll("g.node")].slice(0,2).map(x=>({id:x.id,box:x.getBoundingClientRect().toJSON(),font:getComputedStyle(x.querySelector(".nodeLabel,text")||x).fontFamily}))')
    except Exception as e:entry['error']=repr(e)
    results.append(entry);print(json.dumps(entry),flush=True)
  context.close()
 b.close()
(work/'report.json').write_text(json.dumps({'at':now(),'results':results},indent=2))
