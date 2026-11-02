"""Retain source HTML label backgrounds and bind them to the same native edge as text."""
import copy,xml.etree.ElementTree as E
from mermaid_native_v1 import build as previous
from svg_convert_v3 import unpack
from svg_convert_v2 import color,num

def build(dom,w,h,metadata):
 xml,stats,processed=previous(dom,w,h,metadata);root=E.fromstring(xml);container=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in root.iter('mxCell')};bindings=[]
 for o in processed['objects']:
  owner=o.get('sourceHtmlBackgroundOwner')
  if not owner:continue
  bg=cells[o['id']];expected=color(o['style']['fill']);assert unpack(bg.get('style'))['fillColor']==expected
  labels=[x for x in processed['objects'] if x['type']=='text' and x['sourceId']==owner];assert labels,'CSS background without native text owner'
  text=labels[0];label=cells[text['id']]
  if o.get('edge'):
   edge=cells[label.get('parent')];assert edge.get('edge')=='1'
   g=copy.deepcopy(label.find('mxGeometry'));assert g.get('relative')=='1';offset=g.find("mxPoint[@as='offset']");assert offset is not None
   offset.set('x',num(float(offset.get('x',0))+o['bbox']['x']-text['bbox']['x']));offset.set('y',num(float(offset.get('y',0))+o['bbox']['y']-text['bbox']['y']));g.set('width',num(o['bbox']['w']));g.set('height',num(o['bbox']['h']));bg.remove(bg.find('mxGeometry'));bg.append(g);bg.set('parent',edge.get('id'));container.remove(bg);container.insert(list(container).index(label),bg)
   bindings.append({'background':bg.get('id'),'label':label.get('id'),'edge':edge.get('id'),'source_css_color':expected,'source_bbox':o['bbox']})
  else:assert bg.get('parent')==label.get('parent'),'Background and node label separated'
 stats['native_html_label_backgrounds']=bindings;stats['converter_version']='mermaid10_source_geometry_html_backgrounds_v2'
 return E.tostring(root,encoding='unicode'),stats,processed

def check_backgrounds(xml,bindings):
 cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
 for x in bindings:
  b,t,e=[cells.get(x[k]) for k in ['background','label','edge']];assert b is not None and t is not None and e is not None
  assert e.get('edge')=='1' and b.get('parent')==t.get('parent')==x['edge']
  style=unpack(b.get('style'));assert style['fillColor']==x['source_css_color'] and float(style.get('opacity',100))==100 and float(style.get('fillOpacity',100))==100
  assert b.find('mxGeometry').get('relative')=='1'
 return {'ok':True,'source_backgrounds':len(bindings),'native_edge_owned_backgrounds':len(bindings)}

MOVE_SCRIPT=r'''async ({xml,bindings})=>{document.body.innerHTML='<div id="g"></div>';const g=new Graph(document.getElementById('g'));new mxCodec(mxUtils.parseXml(xml)).decode(mxUtils.parseXml(xml).getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();const rows=[];for(const x of bindings){for(const source of [true,false]){const e=g.model.cells[x.edge],node=g.model.getTerminal(e,source),original=node.geometry.clone(),pos=id=>{const s=g.view.getState(g.model.cells[id]);return {x:s.x,y:s.y}},b0=pos(x.background),t0=pos(x.label),next=original.clone();next.x+=17;next.y+=11;g.model.setGeometry(node,next);g.view.validate();const b1=pos(x.background),t1=pos(x.label);rows.push({background:x.background,label:x.label,edge:x.edge,side:source?'source':'target',background_delta:{x:b1.x-b0.x,y:b1.y-b0.y},label_delta:{x:t1.x-t0.x,y:t1.y-t0.y}});g.model.setGeometry(node,original);g.view.validate();}}g.destroy();return rows;}'''
