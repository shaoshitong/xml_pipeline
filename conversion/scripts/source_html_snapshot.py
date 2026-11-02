import hashlib,mimetypes,urllib.parse
from native_worker import R,W

def snapshot(browser,record,width,height):
 code=(R/record['original_source_code']).read_text();assert hashlib.sha256(code.encode()).hexdigest()==record['source_code_sha256'];assets=(R/record['original_asset_root']).resolve();assert assets.is_relative_to(R/'clean');blocked=[];context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');page=context.new_page()
 def route(req):
  url=urllib.parse.urlparse(req.request.url)
  if url.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
  rel=urllib.parse.unquote(url.path.lstrip('/'))
  if rel=='index.html':req.fulfill(body=code,content_type='text/html');return
  path=(assets/rel).resolve()
  if not path.is_relative_to(assets) or not path.is_file():blocked.append(rel);req.abort();return
  req.fulfill(body=path.read_bytes(),content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
 context.route('**/*',route)
 try:
  page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready');dom=page.evaluate((W/'scripts/html_dom_clip.js').read_text());png=page.screenshot();assert not blocked,blocked;return png,dom
 finally:context.close()
