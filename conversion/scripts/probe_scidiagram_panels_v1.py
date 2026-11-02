"""Original routed panel bytes versus inline resolution, then source preflight."""
from pathlib import Path
import json,hashlib,sys,time,traceback,uuid,sqlite3,copy
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def main():
 from playwright.sync_api import sync_playwright
 from scidiagram_panel_assets_v1 import inventory,resolve
 import compiler_scidiagram_source_frontend_v1 as f
 identifier='0186e98ef75dda6a66308b68b0fc72be864a3e197416d82fae0134eba19d3d10';work=R/'conversion/scidiagram_panel_probe_v1'/uuid.uuid4().hex;work.mkdir(parents=True);start=time.monotonic();result=dict(id=identifier,work=str(work),normal_calls=0,QA_calls=0,accepted=False)
 try:
  with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True)as d:d.row_factory=sqlite3.Row;job=dict(d.execute('select*from jobs where id=?',(identifier,)).fetchone())
  ctx=inventory(dict(id=identifier),job);code=(R/ctx['manifest']['source_code']).read_bytes();size=[ctx['manifest']['width'],ctx['manifest']['height']];normalized,proof=resolve(code,ctx);result['asset_proof']=proof;f.source_admission(ctx['source'],code,size)
  with sync_playwright()as p:
   browser=p.chromium.launch(executable_path=f.CHROME,args=['--disable-dev-shm-usage','--disable-gpu']);context=browser.new_context(viewport=dict(width=size[0],height=size[1]),device_scale_factor=1,java_script_enabled=False,service_workers='block');requests=[];blocked=[]
   def route(request):
    url=request.request.url;prefix='https://original-panels.invalid/'
    if url.startswith(prefix)and url[len(prefix):]in ctx['aliases']:
     a=ctx['aliases'][url[len(prefix):]];requests.append(dict(alias=url[len(prefix):],sha256=a['sha256']));request.fulfill(status=200,content_type=a['mime'],body=a['blob'])
    else:blocked.append(url);request.abort()
   context.route('**/*',route);page=context.new_page()
   def capture(payload,base):
    page.set_content('<base href="'+base+'"><style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+payload.decode('utf-8-sig'));page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',size);page.evaluate('()=>document.fonts.ready');return page.screenshot(type='png')
   before=capture(code,'https://original-panels.invalid/');after=capture(normalized,'about:blank');assert before==after,'source_panel_inlining_changed_actual_browser_pixels';assert not blocked,blocked;assert{r['alias']for r in requests}=={r['source_href']for r in proof['resolved_images']};context.close();browser.close()
  result.update(original_routed_and_inline_source_pixels_exact=True,actual_original_asset_requests=requests,network_requests=0)
  import xml.etree.ElementTree as E
  negative=[]
  for name,uri in [('unlisted_relative','not-declared.png'),('network_URL','https://not-allowed.invalid/image.png'),('filesystem_path','/etc/passwd')]:
   tree=E.fromstring(code);element=next(e for e in tree.iter()if e.tag.split('}')[-1]=='image');key=next(k for k in element.attrib if k.split('}')[-1]=='href');element.set(key,uri)
   try:resolve(E.tostring(tree),ctx)
   except ValueError as e:negative.append(dict(name=name,rejected=True,reason=str(e)))
   else:raise AssertionError('unproved_resource_accepted:'+name)
  result['actual_resource_negative_controls']=negative
  seed=dict(id=identifier,source_code_sha256=ctx['source']['code_sha256'],source_image_sha256=ctx['source']['image_sha256']);prepared=f.prepare_source(seed,job);result.update(source_preflight_ok=prepared['ok'],source_work=str(prepared['work']),source_reference=prepared['sourceproof']['source_reference'],objects=len(prepared['capture']['dom']['objects']),source_original_code_sha256=prepared['sourceproof']['source_code_sha256'])
 except Exception as e:result.update(error=str(e),traceback=traceback.format_exc())
 result['elapsed_seconds']=time.monotonic()-start;(work/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
