"""Exact engine UID scene ownership/links plus editable source paint, no layout."""
import urllib.parse,xml.etree.ElementTree as E
from plantuml_native_minimax_v1 import build as legacy
from svg_convert_v3 import unpack,pack
from svg_convert_v2 import num

def build(dom,width,height,metadata):
 # The frozen primitive/marker lowering receives true flat source frames first;
 # semantic containment is applied only after source-coordinate arrow lowering.
 flat={**metadata,'parents':[],'issues':[]};xml,stats=legacy(dom,width,height,flat);tree=E.fromstring(xml);root=tree.find('.//mxGraphModel/root');cells={c.get('id'):c for c in root.iter('mxCell')};groups={g['uid']:g for g in metadata['groups']};ir=dom['engine_ir'];links={l['uid']:l for l in ir['links']}
 for uid,g in groups.items():
  cid='node_'+uid;c=cells.get(cid)
  if c is None:
   c=E.SubElement(root,'mxCell',{'id':cid,'parent':'1','vertex':'1','value':'','style':'group=1;connectable=1;fillColor=none;strokeColor=none;'});b=g['bbox'];E.SubElement(c,'mxGeometry',{'x':num(b['x']),'y':num(b['y']),'width':num(b['w']),'height':num(b['h']),'as':'geometry'});cells[cid]=c
  st=unpack(c.get('style',''));st['compilerEngineUid']=uid;c.set('style',pack(st))
 # Each group uses the engine's actual parent UID. A nonpainted logical group
 # has an explicitly declared editor frame, never a fabricated visible outline.
 for uid,g in groups.items():
  if g.get('parent'):
   c=cells['node_'+uid];geo=c.find('mxGeometry');parent=groups[g['parent']]['bbox'];geo.set('x',num(g['bbox']['x']-parent['x']));geo.set('y',num(g['bbox']['y']-parent['y']));c.set('parent','node_'+g['parent'])
 visible={}
 for obj in dom['objects']:
  if obj.get('edge') and obj['tag']=='path' and obj['style']['fill']=='none':
   uid=obj['edge']['id'];assert uid in links;visible[uid]=cells[obj['id']]
 for link in metadata['links']:
  uid=link['uid'];c=visible.get(uid)
  if c is None:
   if link['visible']:raise ValueError('visible_engine_link_not_lowered')
   c=E.SubElement(root,'mxCell',{'id':'engine_layout_'+uid,'parent':'1','edge':'1','value':'','source':'node_'+link['entity1_uid'],'target':'node_'+link['entity2_uid'],'style':'edgeStyle=none;rounded=0;opacity=0;strokeColor=none;fillColor=none;startArrow=none;endArrow=none;exitX=0.5;exitY=0.5;entryX=0.5;entryY=0.5;exitPerimeter=0;entryPerimeter=0;'});E.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'})
  if link.get('visible') and link.get('owner_entity'):
   owner=link['owner_entity'];c.set('parent','node_'+owner);origin=groups[owner]['bbox']
   for point in c.find('mxGeometry').iter('mxPoint'):
    if point.get('as')!='offset':
     point.set('x',num(float(point.get('x',0))-origin['x']));point.set('y',num(float(point.get('y',0))-origin['y']))
  st=unpack(c.get('style',''));st.update(compilerLinkUid=uid,compilerEnginePort1=urllib.parse.quote(link.get('port1') or '',safe=''),compilerEnginePort2=urllib.parse.quote(link.get('port2') or '',safe=''),compilerEngineLabel=urllib.parse.quote(link.get('label') or '',safe=''));c.set('style',pack(st))
 stats.update(converter_version='plantuml_engine_UID_owned_editable_scene_v1',engine_entities=len(ir['entities']),engine_groups=len(ir['groups']),engine_links=len(ir['links']),invisible_layout_links=sum(not l['visible'] for l in metadata['links']),semantic_ownership_source='actual_official_engine_UID_parent_link_port_decor',inferred_endpoint_or_parent_count=0)
 return E.tostring(tree,encoding='unicode'),stats
