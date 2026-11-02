"""Bounded Chromium viewport capture; no DOM or render-policy changes."""
import base64,io

def screenshot(page):
 try:return page.screenshot(type='png',timeout=45000)
 except Exception as error:
  if 'Unable to capture screenshot' not in str(error):raise
  session=page.context.new_cdp_session(page)
  try:
   answer=session.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False});blob=base64.b64decode(answer['data'],validate=True)
   from PIL import Image
   if list(Image.open(io.BytesIO(blob)).size)!=[page.viewport_size['width'],page.viewport_size['height']]:raise ValueError('infrastructure_source_capture_canvas_changed')
   return blob
  except Exception as fallback:raise ValueError('infrastructure_source_capture_failed:'+str(fallback)[:1200]) from fallback
  finally:session.detach()
