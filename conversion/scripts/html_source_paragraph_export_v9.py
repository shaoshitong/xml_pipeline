"""Original HTML screenshot viewport; no target bounds or paint fitting."""
import io,json,hashlib,xml.etree.ElementTree as E
from PIL import Image
MODE='original_HTML_source_viewport_complete_native_inspection_v9'
KEY='sourceHTMLViewportV9'
def attach(xml,viewport):
 root=E.fromstring(xml);model=root.find('.//mxGraphModel');width,height=map(int,viewport);assert[int(float(model.get(k)))for k in('pageWidth','pageHeight')]==[width+64,height+64];model.set(KEY,json.dumps([32,32,width,height],separators=(',',':')));model.set('sourceHTMLExportPolicy',MODE);return E.tostring(root,encoding='unicode')
def strip(xml):
 root=E.fromstring(xml);model=root.find('.//mxGraphModel');model.attrib.pop(KEY,None);model.attrib.pop('sourceHTMLExportPolicy',None);return E.tostring(root,encoding='unicode')
def pixels(blob):
 with Image.open(io.BytesIO(blob))as image:return image.convert('RGBA').tobytes()
def compare(inspection,export,viewport):
 width,height=map(int,viewport)
 with Image.open(io.BytesIO(inspection))as image:
  assert image.size==(width+64,height+64);expected=image.crop((32,32,width+32,height+32)).convert('RGBA').tobytes()
 with Image.open(io.BytesIO(export))as image:assert image.size==(width,height);assert image.convert('RGBA').tobytes()==expected,'HTML_source_viewport_export_not_exact_full_native_crop'
 return True
