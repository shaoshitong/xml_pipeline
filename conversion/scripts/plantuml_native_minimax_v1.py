"""PlantUML source-SVG geometry and engine terminal identities to native drawio."""
import math,re,xml.etree.ElementTree as E
import svg_convert_v3 as core
from svg_convert_v3 import distance,unpack,pack
from svg_convert_v2 import num

from plantuml_marker_minimax_v1 import classic

def build(dom,width,height,metadata):
 from plantuml_svg_builder_v4 import build as private_build
 xml,stats=private_build(dom,width,height)
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};groups={g['uid']:g for g in metadata['groups']}
 # The actual SVG source supplies these canvas stroke settings. Native canvas
 # defaults to miterlimit=10, whereas SVG defaults to 4.
 for obj in dom['objects']:
  if obj['type']!='shape' or obj['id'] not in cells:continue
  paint=obj.get('original_computed_paint')
  if paint is None:raise ValueError('fresh_original_computed_paint_missing')
  style=unpack(cells[obj['id']].get('style',''));style.update(linecap=paint['linecap'],linejoin=paint['linejoin'],miterlimit=num(paint['miterlimit']));cells[obj['id']].set('style',pack(style))

 # Reparent native entity groups without changing their absolute source positions.
 for rel in metadata['parents']:
  cell=cells['node_'+rel['child']];g=cell.find('mxGeometry');parent=groups[rel['parent']]['bbox'];g.set('x',num(float(g.get('x'))-parent['x']));g.set('y',num(float(g.get('y'))-parent['y']));cell.set('parent','node_'+rel['parent'])
 stats['plantuml_source_metadata']=metadata;stats['issues']+=metadata['issues'];stats['issues'].append({'reason':'plantuml_engine_geometry_requires_original_visual_validation'})
 if metadata['parents']:stats['issues'].append({'reason':'plantuml_nested_membership_requires_source_review','count':len(metadata['parents'])})
 if any(x.get('contour_approximation') for x in stats['native_graphviz_arrowheads']):stats['issues'].append({'reason':'native_plantuml_classic_contour_approximation_requires_visual_review'})
 if len(metadata['links'])!=metadata['expectedLinkCount']:stats['issues'].append({'reason':'plantuml_unresolved_link_metadata_count'})
 stats['converter_version']='plantuml_actual_four_vertex_classic_minimax_native_v4';return E.tostring(root,encoding='unicode'),stats
