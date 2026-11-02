"""Instance-to-source-paint proof for visible symmetric circles/ellipses.

Repeated empty labels are not matched by text or by the final global spelling.
The fixed physical TeXpt/PDFbp/SVG scale is verified against one unique global
translation and a complete injective geometry mapping. This prototype never
changes XML, discards objects, accepts a job, or binds numeric terminals.
"""
import hashlib,json,math,xml.etree.ElementTree as E
import numpy as np
from tikz_execution_binding import TEX_PT_TO_PDF_BP,_pt,_mapped,_softpath_points,_path_matches_execution,_verify_source_paint
from tikz_literal_connectivity import polyline,norm
from tikz_execution_binding_v2 import sampled_path
from svg_convert_v2 import stencil
from svg_convert_v3 import unpack


def ellipse_geometry(obj):
 if obj.get('type')!='shape':return None
 b=obj['bbox'];rx=b['w']/2;ry=b['h']/2
 if min(rx,ry)<1:return None
 style=obj['style']
 if style['fill']=='none' and (style['stroke']=='none' or not style['strokeWidth']):return None
 try:points=sampled_path(obj,step=.2)
 except (ValueError,KeyError):return None
 if len(points)<12 or np.linalg.norm(points[0]-points[-1])>.01:return None
 center=np.array([b['x']+rx,b['y']+ry]);relative=(points-center)/np.array([rx,ry]);radial=np.sum(relative*relative,axis=1);error=float(np.max(np.abs(radial-1)))
 if error>.005:return None
 return {'object':obj['id'],'center':center.tolist(),'radii':[rx,ry],'maximum_normalized_squared_radial_error':error}


def map_circle_instances(dom,graph,root_matrix):
 out={'supported':True,'ok':False,'failures':[],'evidence':{}}
 try:
  if not graph.get('identity_ok'):raise ValueError('Actual execution instance/anchor ownership proof failed')
  if graph.get('pictures')!=1:raise ValueError('Instance mapping currently requires one source picture')
  a,b,c,d,_,_=root_matrix
  if abs(b)>1e-8 or abs(c)>1e-8 or min(a,d)<=0:raise ValueError('Actual source SVG root is not positive axis aligned')
  sx=a*TEX_PT_TO_PDF_BP;sy=-d*TEX_PT_TO_PDF_BP;nodes=[n for n in graph['nodes'] if n['shape'] in ('circle','ellipse')];candidates=[(o,g) for o in dom['objects'] if (g:=ellipse_geometry(o)) is not None]
  if len(nodes)<3:raise ValueError('At least three visible symmetric node instances are needed for fixed-scale translation proof')
  if len(candidates)<len(nodes):raise ValueError('Not every source circle/ellipse instance has a visible shape candidate')
  centers={n['instance_id']:[sx*_pt(n['center_pt'][0]),sy*_pt(n['center_pt'][1])] for n in nodes};solutions=[]
  for center in centers.values():
   for _,candidate in candidates:
    tx,ty=np.array(candidate['center'])-np.array(center);matched={};errors=[];used=set()
    for node in nodes:
     expected=np.array(centers[node['instance_id']])+np.array([tx,ty]);hits=[(obj,g,float(np.linalg.norm(expected-np.array(g['center'])))) for obj,g in candidates if np.linalg.norm(expected-np.array(g['center']))<=.05]
     if len(hits)!=1 or hits[0][0]['id'] in used:break
     obj,geometry,error=hits[0];used.add(obj['id']);matched[node['instance_id']]={'source_name':node['source_name'],'name_generation':node['name_generation'],'definition_sequence':node['definition_sequence'],'serial':node['serial'],'source_object_id':obj['id'],'source_object_paint_order':dom['objects'].index(obj),'center_error_px':error,'source_shape_geometry':geometry};errors.append(error)
    if len(matched)==len(nodes):
     signature=tuple((id,row['source_object_id']) for id,row in matched.items())
     if any(s['assignment_signature']==signature for s in solutions):continue
     offsets=np.array([np.array(row['source_shape_geometry']['center'])-np.array(centers[id]) for id,row in matched.items()]);tx,ty=np.median(offsets,axis=0);errors=[]
     for id,row in matched.items():row['center_error_px']=float(np.linalg.norm(np.array(centers[id])+np.array([tx,ty])-np.array(row['source_shape_geometry']['center'])));errors.append(row['center_error_px'])
     if max(errors)<=.05:solutions.append({'matrix':[sx,0,0,sy,float(tx),float(ty)],'instances':matched,'max_center_error_px':max(errors),'assignment_signature':signature})
  if len(solutions)!=1:raise ValueError('Source instance positions do not define one complete unique injective fixed-scale source-paint mapping: '+str(len(solutions)))
  mapping=solutions[0];xs=[p[0] for p in centers.values()];ys=[p[1] for p in centers.values()]
  if max(xs)-min(xs)<5 or max(ys)-min(ys)<5:raise ValueError('Instance positions do not span two axes enough to verify the physical-unit mapping')
  mapped=set(mapping['instances']);out['evidence']={'coordinate_mapping':mapping,'fixed_tex_pt_to_pdf_bp':TEX_PT_TO_PDF_BP,'actual_svg_root_screen_ctm':root_matrix,'mapped_symmetric_instances':len(nodes),'all_matched_source_object_ids_unique':True,'source_spelling_not_used_as_identity':True,'unmapped_named_instances':[{'instance_id':n['instance_id'],'source_name':n['source_name'],'shape':n['shape']} for n in graph['nodes'] if n['instance_id'] not in mapped],'full_execution_graph_ok':graph['ok'],'scope':'Visible symmetric instance mapping only. Every other source object is retained; no unmapped node or numeric terminal is inferred.'};out['ok']=True
 except (ValueError,KeyError) as exc:out['failures'].append({'reason':'instance_source_paint_mapping_unsupported','error':str(exc)})
 return out


def verify_unchanged_native_inventory(xml,dom):
 if dom.get('issues'):raise ValueError('Source DOM has unsupported visible features')
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};objects=dom['objects']
 if {c.get('id') for c in cells.values() if c.get('vertex')=='1'}!={o['id'] for o in objects}:raise ValueError('Original native/source paint object inventory differs')
 _verify_source_paint(xml,dom)
 for obj in objects:
  cell=cells[obj['id']]
  if obj['type']=='shape':
   shape,bounds=stencil(obj);geometry=cell.find('mxGeometry')
   if unpack(cell.get('style')).get('shape')!=shape or any(abs(float(geometry.get(k,'0'))-v)>1e-4 for k,v in zip(('x','y','width','height'),bounds)):raise ValueError('Original source/native shape geometry changed: '+obj['id'])
  if obj['type']=='text' and norm(cell.get('value',''))!=norm(obj['text']):raise ValueError('Original source/native text changed: '+obj['id'])
 return {'ok':True,'all_source_paint_objects_retained':len(objects),'text_fragments_retained':sum(o['type']=='text' for o in objects),'xml_modified':False,'xml_sha256':hashlib.sha256(xml.encode()).hexdigest()}


def prove_named_circle_edge_paint(dom,graph,events,mapping):
 """Identify actual source shafts for mapped instance pairs; no XML edits."""
 matrix=mapping['evidence']['coordinate_mapping'];instances=matrix['instances'];finishes={tuple(e['fields'][:2]):e['fields'][-1] for e in events if e['kind']=='finish'};paths=[]
 for obj in dom['objects']:
  if obj['type']=='shape' and obj['style']['fill']=='none' and obj['style']['stroke']!='none':
   try:points=polyline(obj)
   except ValueError:continue
   if len(points)==2 and math.dist(*points)>.1:paths.append((obj,points))
 proof=[];unsupported=[];used=set();by_path={}
 for edge in graph['edges']:by_path[(edge['picture'],edge['path'])]=by_path.get((edge['picture'],edge['path']),0)+1
 for edge in graph['edges']:
  key=(edge['picture'],edge['path'])
  if edge['source'] not in instances or edge['target'] not in instances:continue
  try:
   if by_path[key]!=1:raise ValueError('Multiple executed segments share one painted path')
   expected=[_mapped(p,matrix) for p in _softpath_points(finishes[key])];matches=[(obj,points) for obj,points in paths if _path_matches_execution(points,expected,edge)]
   if len(matches)!=1 or matches[0][0]['id'] in used:raise ValueError('Actual named shaft is not one uniquely matched source object')
   obj,points=matches[0];used.add(obj['id']);proof.append({'picture':key[0],'path':key[1],'source_instance':edge['source'],'target_instance':edge['target'],'source_native_object':instances[edge['source']]['source_object_id'],'target_native_object':instances[edge['target']]['source_object_id'],'shaft_source_object':obj['id'],'source_spelling':instances[edge['source']]['source_name'],'target_spelling':instances[edge['target']]['source_name'],'source_generation':instances[edge['source']]['name_generation'],'target_generation':instances[edge['target']]['name_generation'],'actual_softpath_points':expected,'actual_source_shaft_points':points,'start_arrow':edge['start_arrow'],'end_arrow':edge['end_arrow']})
  except ValueError as exc:unsupported.append({'picture':key[0],'path':key[1],'reason':str(exc)})
 return {'matched_named_instance_edges':proof,'unsupported_mapped_pair_edges':unsupported,'source_object_inventory_unchanged':True,'numeric_or_unmapped_terminals_bound':0,'published':False}
