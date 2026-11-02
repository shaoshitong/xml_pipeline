"""Render preserved SVG bytes offline at the same reference viewport as source conversion."""
import hashlib
from native_worker import R

def snapshot(browser,record,width,height):
 key='source_render_svg' if record['source_format']=='python' else 'original_source_code';digest='source_render_svg_sha256' if key=='source_render_svg' else 'source_code_sha256';path=R/record[key];assert path.resolve().is_relative_to(R/'clean');svg=path.read_bytes();assert hashlib.sha256(svg).hexdigest()==record[digest];blocked=[];context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');page=context.new_page();context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()))
 try:
  page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode());page.evaluate('([w,h])=>{const s=document.querySelector("svg");if(!s.viewBox.baseVal.width)s.setAttribute("viewBox",`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');png=page.screenshot();assert not blocked,blocked;return png
 finally:context.close()

def auxiliary_hashes(record):
 hashes={}
 for key,digest in [('original_source_data','source_data_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_dot',None)]:
  if record.get(key):
   path=R/record[key];assert path.resolve().is_relative_to(R/'clean');h=hashlib.sha256(path.read_bytes()).hexdigest()
   if digest:assert h==record[digest]
   hashes[key]={'file':record[key],'sha256':h}
 for a in record.get('source_assets',[]):
  if a['source']=='embedded_original_html_asset':continue
  path=R/a['source'];assert path.resolve().is_relative_to(R/'clean');h=hashlib.sha256(path.read_bytes()).hexdigest();assert h==a['source_sha256'];hashes[a['source']]={'file':a['source'],'sha256':h}
 return hashes
