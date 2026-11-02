"""Fresh official engine semantics + full native paint; no producer proof."""
import base64,collections,html,math,urllib.parse,zlib,xml.etree.ElementTree as E
from auto_quality_source_vector_v2 import _style,_world_box,_plain,_paint_coverage,_graphviz_coverage
from svg_convert_v2 import stencil
from native_svg_screen_offset_v1 import observe,transform

def _world_box(cell, cells, seen=None):
    seen = set(seen or ())
    key = cell.get('id')
    assert key not in seen, 'native parent cycle'
    seen.add(key)
    geo = cell.find('mxGeometry')
    assert geo is not None, 'missing native geometry: ' + str(key)
    x, y, width, height = [float(geo.get(k, 0)) for k in ('x', 'y', 'width', 'height')]
    parent = cells.get(cell.get('parent'))
    if parent is not None and parent.get('edge') == '1':
        assert geo.get('relative') == '1', 'edge child uses unsupported absolute label geometry'
        points = _edge_points(parent, cells, seen)
        segments = [math.dist(a, b) for a, b in zip(points, points[1:])]
        along = max(0, min(1, (x+1)/2))*sum(segments)
        point = points[-1]
        for a, b, length in zip(points, points[1:], segments):
            if along <= length and length:
                fraction = along/length
                # mxGraph's relative y is perpendicular distance along the edge.
                point = (a[0]+fraction*(b[0]-a[0])+y*(b[1]-a[1])/length,
                         a[1]+fraction*(b[1]-a[1])-y*(b[0]-a[0])/length)
                break
            along -= length
        offset = geo.find("mxPoint[@as='offset']")
        return (point[0] + (float(offset.get('x', 0)) if offset is not None else 0),
                point[1] + (float(offset.get('y', 0)) if offset is not None else 0), width, height)
    if parent is not None and parent.get('vertex') == '1':
        assert geo.get('relative') != '1', 'relative vertex requires a separate source geometry profile'
        px, py, _, _ = _world_box(parent, cells, seen)
        x += px; y += py
    return x, y, width, height


def _edge_points(edge, cells, seen=None):
    style = _style(edge)
    points = []
    for key, prefix in [('source', 'exit'), ('target', 'entry')]:
        terminal = cells.get(edge.get(key))
        assert terminal is not None, 'missing bound terminal'
        x, y, width, height = _world_box(terminal, cells, seen)
        assert prefix+'X' in style and prefix+'Y' in style, 'source geometry requires explicit fixed connection constraints'
        points.append((x+float(style[prefix+'X'])*width, y+float(style[prefix+'Y'])*height))
    geo = edge.find('mxGeometry')
    assert geo is not None, 'missing native edge geometry'
    parent=cells.get(edge.get('parent'));origin=_world_box(parent,cells,seen)[:2] if parent is not None and parent.get('vertex')=='1' else (0.,0.)
    bends = [(float(p.get('x'))+origin[0], float(p.get('y'))+origin[1]) for p in geo.findall("Array[@as='points']/mxPoint")]
    return [points[0], *bends, points[1]]


def require(ok,reason):
 if not ok:raise ValueError(reason)
def decoded(shape):
 if not shape.startswith('stencil('):return shape
 return E.canonicalize(urllib.parse.unquote(zlib.decompress(base64.b64decode(shape[8:-1]),-15).decode()))

def match(dom,metadata,xml):
 frame=observe(xml);xml=transform(xml,frame['offsets'],1);tree=E.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')};require(len(cells)==len(list(tree.iter('mxCell'))),'duplicate_candidate_cell_id');ir=dom['engine_ir'];source_entities={g['uid']:g for g in metadata['groups']};entities={};native_links={};mapping={};normal_shapes={};font_pairs=[];hidden=[]
 for cid,c in cells.items():
  st=_style(c)
  if 'compilerEngineUid' in st:
   uid=st['compilerEngineUid'];require(uid in source_entities and uid not in entities,'missing_extra_or_duplicate_actual_engine_UID');require(c.get('vertex')=='1' and st.get('group')=='1' and not c.get('value') and st.get('fillColor')=='none' and st.get('strokeColor')=='none' and st.get('shadow','0')=='0','engine_entity_group_has_unproved_paint');entities[uid]=cid;mapping[cid]='node_'+uid
  if 'compilerLinkUid' in st:
   uid=st['compilerLinkUid'];require(uid not in native_links and c.get('edge')=='1','duplicate_or_nonedge_engine_link_UID');native_links[uid]=cid
 require(set(entities)==set(source_entities),'complete_actual_engine_entity_inventory_changed');require(set(native_links)=={l['uid'] for l in ir['links']},'complete_actual_engine_link_inventory_changed')
 def owner(cid,include_self=False):
  seen=set();cur=cid if include_self else cells[cid].get('parent')
  while cur in cells and cur not in seen:
   seen.add(cur);st=_style(cells[cur])
   if 'compilerEngineUid' in st:return ('entity',st['compilerEngineUid'])
   if 'compilerLinkUid' in st:return ('link',st['compilerLinkUid'])
   cur=cells[cur].get('parent')
  return None
 for uid,cid in entities.items():
  g=source_entities[uid];expected=('entity',g['parent']) if g.get('parent') else None;require(owner(cid)==expected,'actual_engine_parent_UID_changed:'+uid);b=_world_box(cells[cid],cells);require(all(abs(a-g['bbox'][k])<=.03 for a,k in zip(b,('x','y','w','h'))),'actual_engine_entity_editor_frame_changed:'+uid)
 visible_paths={}
 for o in dom['objects']:
  if o.get('edge') and o['tag']=='path' and o['style']['fill']=='none':
   uid=o['edge']['id'];require(uid not in visible_paths,'multiple_shaft_paths_for_engine_link');visible_paths[uid]=o
 source_links={l['uid']:l for l in metadata['links']};edge_map={};source_marker_sides=collections.defaultdict(set)
 for o in dom['objects']:
  if o.get('edge') and o['tag']=='polygon':
   path=visible_paths.get(o['edge']['id']);require(path is not None,'source_marker_has_no_engine_shaft');center=[o['bbox']['x']+o['bbox']['w']/2,o['bbox']['y']+o['bbox']['h']/2];dist=[math.dist(center,path['sampledPoints'][i]) for i in (0,-1)];require(abs(dist[0]-dist[1])>=1,'source_marker_side_ambiguous');side='start' if dist[0]<dist[1] else 'end';require(side not in source_marker_sides[o['edge']['id']],'multiple_source_marker_components_on_one_terminal_pending');source_marker_sides[o['edge']['id']].add(side)
 for uid,cid in native_links.items():
  link=source_links[uid];cell=cells[cid];st=_style(cell);require(cell.get('source')==entities[link['entity1_uid']] and cell.get('target')==entities[link['entity2_uid']],'actual_engine_link_terminal_UID_changed:'+uid)
  for i in (1,2):require(urllib.parse.unquote(st.get('compilerEnginePort'+str(i),''))==(link.get('port'+str(i)) or ''),'actual_engine_named_port_changed')
  require(urllib.parse.unquote(st.get('compilerEngineLabel',''))==(link.get('label') or ''),'actual_engine_link_declared_label_changed')
  present={s for s in ('start','end') if st.get(s+'Arrow','none') not in ('none','')};require(present==source_marker_sides[uid],'source_native_marker_terminal_inventory_changed:'+uid)
  if link['visible']:
   require(owner(cid)==(('entity',link['owner_entity']) if link.get('owner_entity') else None),'actual_source_engine_link_container_changed')
   obj=visible_paths.get(uid);require(obj is not None,'actual_engine_visible_shaft_missing');edge_map[obj['id']]=cid;mapping[cid]=obj['id']
  else:
   require(st.get('opacity')=='0' and st.get('strokeColor')=='none' and st.get('fillColor')=='none' and not cell.get('value') and all(e.tag=='mxGeometry' for e in cell) and not any(e.get('parent')==cid for e in cells.values()),'hidden_engine_layout_link_fabricates_paint_or_label');hidden.append(cid);mapping[cid]='engine_layout_'+uid
 for obj in dom['objects']:
  if obj['id'] in edge_map or (obj['type']=='shape' and obj.get('edge') and obj['tag']=='polygon'):continue
  wanted_shape,wanted_box=stencil(obj) if obj['type']=='shape' else (None,tuple(obj['bbox'][k] for k in ('x','y','w','h')));choices=[];wanted_owner=('entity',obj['node']) if obj.get('node') else ('link',obj['edge']['id']) if obj.get('edge') else None
  for cid,c in cells.items():
   if cid in mapping or c.get('vertex')!='1' or _style(c).get('group')=='1' or owner(cid)!=wanted_owner:continue
   st=_style(c)
   try:b=_world_box(c,cells)
   except Exception:continue
   if any(abs(a-bb)>(2 if obj['type']=='text' else .03) for a,bb in zip(b,wanted_box)):continue
   if obj['type']=='text':
    if _plain(c.get('value',''))!=obj['text'] or st.get('shape')!='text':continue
   elif obj['type']=='shape':
    equivalent=decoded(st.get('shape','rectangle'))==decoded(wanted_shape)
    if not equivalent and obj['tag']=='rect' and not obj['attrs'].get('rx') and not obj['attrs'].get('ry'):equivalent=st.get('shape','rectangle') in ('rectangle','') and st.get('rounded','0')=='0' and st.get('rotation','0')=='0'
    if not equivalent:continue
   else:raise ValueError('source_asset_type_not_yet_lowered')
   choices.append(cid)
  require(len(choices)==1,'source_primitive_or_text_owner_geometry_missing_ambiguous:'+obj['id']);cid=choices[0];mapping[cid]=obj['id']
  if wanted_shape:normal_shapes[cid]=wanted_shape
  if obj['type']=='text':font_pairs.append((obj,cid))
 require(not [cid for cid,c in cells.items() if (c.get('vertex')=='1' or c.get('edge')=='1') and cid not in mapping],'extra_native_paint_or_semantic_object')
 # Audit a renamed copy, with only the proven nonpainted layout relations
 # omitted from the visible-paint inventory. Their real semantics/editing are
 # independently checked above and by the actual group/terminal move probe.
 for c in cells.values():
  if c.get('edge')=='1':
   parent=cells.get(c.get('parent'));origin=_world_box(parent,cells)[:2] if parent is not None and parent.get('vertex')=='1' else (0.,0.)
   for point in c.findall("mxGeometry/Array[@as='points']/mxPoint"):
    point.set('x',str(float(point.get('x'))+origin[0]));point.set('y',str(float(point.get('y'))+origin[1]))
   # Frozen paint helper inspects edge geometry before using its routed points.
   # Flatten only the audit copy after converting bends to world coordinates;
   # semantic native containment was independently verified above.
   c.set('parent','1')
 for cid in hidden:tree.find('.//mxGraphModel/root').remove(cells[cid])
 for c in tree.iter('mxCell'):
  cid=c.get('id');c.set('id',mapping.get(cid,cid))
  for key in ('source','target','parent'):
   if c.get(key) in mapping:c.set(key,mapping[c.get(key)])
  if cid in normal_shapes:
   st=_style(c);st['shape']=normal_shapes[cid];c.set('style',';'.join(k+'='+v for k,v in st.items())+';')
 from plantuml_engine_shadow_source_v1 import native_style,POLICY as shadow_policy
 effect_rows=[];source_by_id={o['id']:o for o in dom['objects']}
 for cid,c in cells.items():
  source_id=mapping.get(cid);obj=source_by_id.get(source_id,{})
  native_style(_style(c),obj.get('source_shadow'))
  if obj.get('source_shadow'):effect_rows.append({'source_object':source_id,'native_cell':cid,'source_shadow':obj['source_shadow'],'all_source_operator_parameters_and_primary_ownership_exact':True})
 normalized=E.tostring(tree,encoding='unicode');stats={'native_graphviz_arrowheads':[{'source_arrow_object':o['id']} for o in dom['objects'] if o['type']=='shape' and o.get('edge') and o['tag']=='polygon']};graph=_graphviz_coverage(dom,normalized,stats);paint=_paint_coverage(dom,normalized);require(abs(paint['source_layout_translation']['dx'])<=.03 and abs(paint['source_layout_translation']['dy'])<=.03,'candidate_source_origin_moved');errors=graph['errors']+paint['errors']
 return {'ok':not errors,'errors':errors,'graph':graph,'paint':paint,'candidate_to_source_mapping':mapping,'font_pairs':font_pairs,'edge_map':edge_map,'normalized_xml':normalized,'cells':cells,'engine_entities':entities,'engine_links':native_links,'source_effects':{'policy':shadow_policy,'rows':effect_rows,'not_pixel_exact_alias':True},'source_engine_semantics':{'diagram_class':ir['diagram_class'],'entities':len(ir['entities']),'groups':len(ir['groups']),'links':len(ir['links']),'invisible_layout_relations':len(hidden),'true_UID_parents_ports_and_decorators':True,'geometry_used_to_infer_connections_or_parents':False}}
