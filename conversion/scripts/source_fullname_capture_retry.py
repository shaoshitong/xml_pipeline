"""Bounded retries for the observed Chromium screenshot transport failure only."""
import json
from playwright.sync_api import Error
from native_worker import now
from svg_fullname_fonts import capture_source as capture_once

def capture_source(browser,record,directory,width,height):
 errors=[]
 for attempt in range(1,4):
  try:
   result=capture_once(browser,record,directory,width,height)
  except Error as e:
   if 'Page.screenshot: Protocol error (Page.captureScreenshot): Unable to capture screenshot' not in str(e):raise
   errors.append({'at':now(),'attempt':attempt,'error':str(e)})
   directory.mkdir(parents=True,exist_ok=True)
   (directory/'source_capture_retries.json').write_text(json.dumps({'errors':errors,'succeeded':False},indent=2))
   if attempt==3:raise
  else:
   if errors:(directory/'source_capture_retries.json').write_text(json.dumps({'errors':errors,'succeeded':True,'successful_attempt':attempt},indent=2))
   return result
