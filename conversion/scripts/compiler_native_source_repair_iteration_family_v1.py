"""Native template graph families; labels/coordinate numbers are normalized."""
import hashlib
import json
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
from types import SimpleNamespace


def family(code):
 import compiler_types_source_ir_v1 as ir
 import compiler_validation_dot_ir_v2 as typed
 from native_worker import normalize
 normalized,pages,_=normalize(code)
 if pages!=1:raise ValueError('native_family_multi_page_unknown')
 root=ET.fromstring(normalized)
 class Labels(HTMLParser):
  def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
  def handle_starttag(self,tag,attrs):self.parts.append(['start',tag,sorted(attrs)])
  def handle_endtag(self,tag):self.parts.append(['end',tag])
  def handle_startendtag(self,tag,attrs):self.parts.append(['empty',tag,sorted(attrs)])
  def handle_data(self,data):
   if data:self.parts.append(['text','TEXT'if data.strip()else' '])
 for wrapper in root.iter():
  for cell in wrapper.findall('mxCell'):
   if not cell.get('id')and wrapper.get('id'):cell.set('id',wrapper.get('id'))
   if not cell.get('value')and wrapper.get('label'):cell.set('value',wrapper.get('label'))
 for cell in root.iter('mxCell'):
  label=cell.get('value','');parser=Labels();parser.feed(label);parser.close()
  if label:cell.set('value','<source-label data-template="'+hashlib.sha256(json.dumps(parser.parts,sort_keys=True).encode()).hexdigest()+'">TEXT</source-label>')
 for geometry in root.iter('mxGeometry'):
  for name in ('x','y','width','height'):
   if name in geometry.attrib:geometry.set(name,'N')
  for point in geometry.iter('mxPoint'):
   for name in ('x','y'):
    if name in point.attrib:point.set(name,'N')
 _,graph,evidence=ir.native(ET.tostring(root,encoding='unicode'),SimpleNamespace(expanded_xml=ET.fromstring))
 key='native_source_text_node_template_graph_v1:'+typed.invariant(graph)
 return key,{key},dict(method='typed_native_parent_terminal_ports_styles_and_markup_template_v1',source_evidence=evidence,label_content_and_geometry_numbers_normalized=True,style_shape_font_and_markup_semantics_retained=True,hidden_generator_independence_proven=False)
