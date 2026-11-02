"""mxGeometry scalar fields are named by `as`; waypoint arrays stay ordered.

This only normalizes the order of unique explicitly named mxGeometry children.
Duplicates and unnamed children are rejected rather than guessed. All names,
coordinates, attrs, point-array order, labels, styles, IDs and cell order remain.
"""
import copy,decimal,json,hashlib,xml.etree.ElementTree as ET
POLICY='complete_native_cells_unique_geometry_as_fields_with_ordered_waypoints_v1'
def raw(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def tree(node,geometry=False):
 geometry=geometry or node.tag in ('mxGeometry','mxPoint','mxRectangle');attrs={}
 for key,value in node.attrib.items():
  if geometry and key in ('x','y','width','height','relative'):
   d=decimal.Decimal(value)
   if not d.is_finite():raise ValueError('nonfinite_native_geometry')
   value='0'if d==0 else format(d.normalize(),'f')
  attrs[key]=value
 children=list(node)
 if node.tag=='mxGeometry'and children:
  roles=[c.get('as')for c in children]
  if not all(roles)or len(set(roles))!=len(roles):raise ValueError('ambiguous_geometry_as_fields')
  children=sorted(children,key=lambda child:child.get('as'))
 return[node.tag,sorted(attrs.items()),node.text if(node.text or'').strip()else None,node.tail if(node.tail or'').strip()else None,[tree(c,geometry)for c in children]]
def cells(xml):
 root=ET.fromstring(xml);models=list(root.iter('mxGraphModel'))
 if len(models)!=1:raise ValueError('exactly_one_complete_native_model')
 roots=[c for c in models[0]if c.tag=='root']
 if len(roots)!=1:raise ValueError('complete_native_cell_root_missing')
 return tree(roots[0])
def compare(source,current):
 a,b=cells(source),cells(current)
 return {'policy':POLICY,'ok':a==b,'source_complete_cells_sha256':sha(raw(a)),'current_complete_cells_sha256':sha(raw(b)),'all_cell_IDs_labels_markup_styles_parents_terminals_coordinates_and_waypoint_order_preserved':a==b,'only_unique_named_mxGeometry_child_field_order_normalized':True,'model_editor_viewport_and_export_attrs_not_part_of_cell_inventory':True}
