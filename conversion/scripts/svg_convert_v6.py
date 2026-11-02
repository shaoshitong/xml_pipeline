"""Native editable text rotation measured from actual SVG text ranges."""
import xml.etree.ElementTree as E
from svg_convert_v5 import build as build_previous
from svg_convert_v3 import unpack,pack
from svg_convert_v2 import num

def build(dom,width,height):
 xml,stats=build_previous(dom,width,height);root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};converted=[]
 for obj in dom['objects']:
  if obj['type']!='text' or not obj.get('rotationHandled'):continue
  cell=cells[obj['id']];style=unpack(cell.get('style',''));style['rotation']=num(obj['nativeRotation']);cell.set('style',pack(style));converted.append({'source_object':obj['id'],'text':obj['text'],'rotation':obj['nativeRotation'],'unrotated_box':obj['bbox'],'original_rotated_box':obj['originalBoundingBox']})
 stats['native_rotated_text']=converted;stats['converter_version']='svg_native_v6_editable_text_rotation';return E.tostring(root,encoding='unicode'),stats
