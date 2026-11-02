import hashlib,io,json,math
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from svg_batch import metric
selected=[r for r in json.loads((W/'text_fidelity_selection.json').read_text()) if r['format']=='mermaid'];work=W/'mermaid_layout_probe';work.mkdir(exist_ok=True);results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html><body></body></html>');page.add_script_tag(path=str(W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js'))
 for r in selected:
  code=(R/r['source_code']).read_text();reference=(R/r['reference']).read_bytes();folder=work/r['id'];folder.mkdir(exist_ok=True);entries=[]
  for name,labels,font in [('default_html',True,None),('default_svg',False,None),('arial_html',True,'Arial'),('arial_svg',False,'Arial')]:
   config={'startOnLoad':False,'securityLevel':'strict','maxTextSize':2000000,'flowchart':{'htmlLabels':labels}}
   if font:config['themeVariables']={'fontFamily':font}
   try:
    rendered=page.evaluate('''async ({code,config,id})=>{document.body.innerHTML='';mermaid.initialize(config);return (await mermaid.render(id,code)).svg;}''',{'code':code,'config':config,'id':'test_'+name});page.evaluate('s=>{document.body.innerHTML="<style>html,body{margin:0;background:white}</style>"+s}',rendered);size=page.evaluate('()=>{let s=document.querySelector("svg"),v=s.viewBox.baseVal;s.style.maxWidth="none";s.style.width=Math.ceil(v.width)+"px";s.style.height=Math.ceil(v.height)+"px";return {width:Math.ceil(v.width),height:Math.ceil(v.height)}}');page.set_viewport_size(size);page.evaluate('document.fonts.ready');page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');png=page.screenshot();(folder/(name+'.svg')).write_text(rendered);(folder/(name+'.png')).write_bytes(png);details=page.evaluate('()=>({nodes:[...document.querySelectorAll("g.node")].slice(0,3).map(e=>e.outerHTML),edges:[...document.querySelectorAll("path.flowchart-link")].slice(0,2).map(e=>e.outerHTML),labels:[...document.querySelectorAll("g.edgeLabel")].slice(0,2).map(e=>e.outerHTML)})');(folder/(name+'_dom.json')).write_text(json.dumps(details,indent=2));entry={'variant':name,'ssim':metric(reference,png),'size':size}
   except Exception as e:entry={'variant':name,'error':str(e)[:1200]}
   entries.append(entry);print(json.dumps({'id':r['id'],**entry}),flush=True)
  results.append({'id':r['id'],'previous_native_ssim':r['score'],'variants':entries})
 b.close()
(W/'mermaid_layout_probe/report.json').write_text(json.dumps({'time':now(),'results':results},indent=2))
