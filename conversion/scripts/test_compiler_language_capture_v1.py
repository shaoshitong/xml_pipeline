import base64,io,unittest
from PIL import Image
from compiler_language_capture_v1 import screenshot
class Session:
 def __init__(self,blob):self.blob=blob;self.detached=False;self.args=None
 def send(self,name,args):self.args=(name,args);return {'data':base64.b64encode(self.blob).decode()}
 def detach(self):self.detached=True
class Page:
 def __init__(self,error,size=(3,4),actual=(3,4)):
  b=io.BytesIO();Image.new('RGB',actual).save(b,format='PNG');self.blob=b.getvalue();self.error=error;self.viewport_size=dict(zip(['width','height'],size));self.session=Session(self.blob);self.context=self
 def screenshot(self,**kw):
  if self.error:raise ValueError(self.error)
  return self.blob
 def new_cdp_session(self,p):return self.session
class CaptureTests(unittest.TestCase):
 def test_normal_capture_unchanged(self):
  p=Page(None);self.assertEqual(screenshot(p),p.blob);self.assertIsNone(p.session.args)
 def test_exact_compositor_failure_bounded_fallback(self):
  p=Page('Page.captureScreenshot: Unable to capture screenshot');self.assertEqual(screenshot(p),p.blob);self.assertEqual(p.session.args,('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False}));self.assertTrue(p.session.detached)
 def test_timeout_not_hidden(self):
  p=Page('Timeout45000ms');
  with self.assertRaisesRegex(ValueError,'Timeout'):screenshot(p)
  self.assertIsNone(p.session.args)
 def test_canvas_change_is_infrastructure_failure(self):
  p=Page('Unable to capture screenshot',actual=(4,4))
  with self.assertRaisesRegex(ValueError,'infrastructure_source_capture_failed'):screenshot(p)
  self.assertTrue(p.session.detached)
if __name__=='__main__':unittest.main()
