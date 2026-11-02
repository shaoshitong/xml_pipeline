import collections,hashlib,io,json,sqlite3,sys,time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from svg_convert_v6 import build
from svg_source_coverage_v2 import audit
from svg_batch import metric
from pdf_to_native_v2 import source_svg,attach_fonts
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
D=sqlite3.connect(W/'jobs.sqlite');selected=[];seen=set()
for id,fmt,src,raw in D.execute('select id,format,source,output_record from jobs where state in ("rendered","needs_quality_repair") and ((format="svg" and json_extract(output_record,"$.svg_conversion.issues") like "%text_transform%") or (format="tikz" and json_extract(output_record,"$.pdf_conversion.issues") like "%rotated_pdf_text%")) order by id'):
 if (fmt,src) in seen:continue
 out=json.loads(raw)
 if fmt=='tikz' and not out.get('source_render_pdf'):continue
 seen.add((fmt,src));selected.append((id,fmt,src,out))
 if len(selected)>=8:break
work=W/'rotation_real_pilot';work.mkdir(exist_ok=True);report={'started_at_utc':now(),'selected':[{'id':a,'format':b,'source':c} for a,b,c,d in selected],'results':[]};(work/'selection.json').write_text(json.dumps(report['selected'],indent=2));
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 for id,fmt,src,out in selected:
  start=time.monotonic();folder=work/id;folder.mkdir(exist_ok=True);ctx=None;doc=None;result={'id':id,'format':fmt,'source':src}
  try:
   data=(R/out['original_reference']).read_bytes();assert hashlib.sha256(data).hexdigest()==out['source_image_sha256'];w,h=Image.open(io.BytesIO(data)).size;fonts={};pdfstats={}
   if fmt=='tikz':doc=pymupdf.open(R/out['source_render_pdf']);assert len(doc)==1;svg,fonts,pdfstats=source_svg(doc,doc[0],folder)
   else:svg=(R/(out.get('source_render_svg') or out['original_source_code'])).read_text()
   (folder/'source.svg').write_text(svg);ctx=browser.new_context(viewport={'width':w,'height':h},java_script_enabled=False);page=ctx.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<style>html,body{margin:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',[w,h]);page.evaluate('document.fonts.ready');source_png=page.screenshot();dom=page.evaluate((W/'scripts'/('svg_dom_pdf_v2.js' if fmt=='tikz' else 'svg_dom_v6.js')).read_text());xml,stats=build(dom,w,h)
   if fonts:xml=attach_fonts(xml,fonts)
   coverage=audit(dom,xml,stats);assert coverage['ok'],coverage;assert len(stats['native_rotated_text'])>0,'no native rotations';render=native.native_job(xml,w,h,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'];png=render.pop('png');(folder/'diagram.drawio').write_text(xml);(folder/'image.png').write_bytes(png);(folder/'source.png').write_bytes(source_png);result.update(ok=True,rotated_runs=len(stats['native_rotated_text']),coverage=coverage,source_native_ssim=metric(source_png,png),original_native_ssim=metric(data,png),previous_original_ssim=out['metrics']['original_reference_ssim_512'],source_original_ssim=metric(source_png,data),pdf_issues=pdfstats.get('issues',[]),svg_issues=stats['issues'],accepted=False);(folder/'stats.json').write_text(json.dumps({'stats':stats,'pdf':pdfstats,'render':render['native_render']},default=list,indent=2))
  except Exception as e:result.update(ok=False,error=type(e).__name__+': '+str(e)[:1500])
  finally:
   if ctx:ctx.close()
   if doc:doc.close()
  result['seconds']=time.monotonic()-start;report['results'].append(result);(work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=list)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['pdf_issues','svg_issues','coverage']},ensure_ascii=False),flush=True)
 browser.close()
report['finished_at_utc']=now();(work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=list)+'\n')
