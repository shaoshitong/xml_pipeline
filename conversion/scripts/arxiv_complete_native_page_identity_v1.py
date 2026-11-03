"""Independent exact native page identity, including paint order and model attrs."""
import functools,hashlib,json,xml.etree.ElementTree as E
from arxiv_author_native_assets_v1 import models,LIMIT

def sha(b):return hashlib.sha256(b).hexdigest()
@functools.lru_cache(maxsize=4)
def parent_xml(blob):
 if len(blob)>LIMIT or b'<!DOCTYPE' in blob.upper() or b'<!ENTITY' in blob.upper():raise ValueError('parent_XML_bound_or_DTD')
 return E.fromstring(blob)
def tree(n):
 return [n.tag,sorted(n.attrib.items()),n.text if (n.text or '').strip() else None,[tree(c) for c in n]]
def verify(full,side,index,page_id,page_name):
 if not isinstance(index,int) or isinstance(index,bool):raise ValueError('page_index_not_integer')
 parent=parent_xml(full)
 if parent.tag=='mxGraphModel':
  if index!=0:raise ValueError('page_index_out_of_range')
  original=parent;actual_id=actual_name=None
 elif parent.tag=='mxfile':
  diagrams=parent.findall('diagram')
  if not 0<=index<len(diagrams):raise ValueError('page_index_out_of_range')
  diagram=diagrams[index];actual_id=diagram.get('id');actual_name=diagram.get('name');inline=diagram.find('mxGraphModel')
  if inline is not None:original=inline
  else:
   # Reuse the independently pinned native decoder on this complete diagram,
   # not every compressed page in the parent container.
   one=b'<mxfile>'+E.tostring(diagram,encoding='utf-8')+b'</mxfile>'
   _,decoded=models(one)
   if len(decoded)!=1:raise ValueError('not_one_selected_native_model')
   original=decoded[0]
 else:raise ValueError('parent_not_native_document')
 if (actual_id,actual_name)!=(page_id,page_name):raise ValueError('selected_page_id_or_name_changed')
 if len(side)>LIMIT or b'<!DOCTYPE' in side.upper() or b'<!ENTITY' in side.upper():raise ValueError('sidecar_XML_bound_or_DTD')
 selected=E.fromstring(side)
 if selected.tag!='mxGraphModel':raise ValueError('sidecar_not_complete_native_model')
 a=tree(original);b=tree(selected)
 if a!=b:raise ValueError('selected_page_model_cells_styles_geometry_labels_or_order_changed')
 cells=list(original.iter('mxCell'))
 return dict(policy='complete_native_page_exact_model_identity_v1',full_embedded_XML_sha256=sha(full),selected_page_XML_sha256=sha(side),selected_page_index=index,selected_page_id=actual_id,selected_page_name=actual_name,model_tree_SHA256=sha(json.dumps(a,ensure_ascii=True).encode()),cell_count=len(cells),vertices=sum(c.get('vertex')=='1' for c in cells),edges=sum(c.get('edge')=='1' for c in cells),all_original_cells_edges_groups_styles_geometry_labels_and_order_preserved=True,source_modified=False)
