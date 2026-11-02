"""Element-wise SVG -> native editable drawio shapes/text; honest pending flags."""
import base64,html,json,math,re,urllib.parse,xml.etree.ElementTree as E,zlib
from fontTools.svgLib.path import parse_path
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen

def num(x):return format(float(x),'.6f').rstrip('0').rstrip('.') or '0'
def path_for(o):
 a=o['attrs'];t=o['tag']
 if t=='path':return o['d'] or ''
 if t=='line':return f'M{a["x1"]},{a["y1"]} L{a["x2"]},{a["y2"]}'
 if t in ('polygon','polyline'):return 'M'+(o['pointsAttr'] or '')+(' Z' if t=='polygon' else '')
 if t in ('circle','ellipse'):
  x,y=a['cx'],a['cy'];rx=a['r'] if t=='circle' else a['rx'];ry=a['r'] if t=='circle' else a['ry']
  return f'M{x-rx},{y} A{rx},{ry} 0 1,0 {x+rx},{y} A{rx},{ry} 0 1,0 {x-rx},{y} Z'
 if t=='rect':
  x,y,w,h=a['x'],a['y'],a['width'],a['height'];rx=min(a['rx'] or a['ry'],w/2);ry=min(a['ry'] or a['rx'],h/2)
  if not rx or not ry:return f'M{x},{y} h{w} v{h} h{-w} Z'
  return f'M{x+rx},{y} H{x+w-rx} A{rx},{ry} 0 0,1 {x+w},{y+ry} V{y+h-ry} A{rx},{ry} 0 0,1 {x+w-rx},{y+h} H{x+rx} A{rx},{ry} 0 0,1 {x},{y+h-ry} V{y+ry} A{rx},{ry} 0 0,1 {x+rx},{y} Z'
 raise ValueError(t)
def color(s):
 if s=='none':return s
 m=re.match(r'rgba?\(([^)]+)\)',s)
 if m:return '#'+''.join(f'{round(float(v)):02x}' for v in re.findall(r'[\d.]+',m[1])[:3])
 if s.startswith('url('):return 'none'
 return s

def style(o):
 s=o['style'];a,b,c,d,_,_=o['matrix'];scale=math.sqrt(abs(a*d-b*c));out={'fillColor':color(s['fill']),'strokeColor':color(s['stroke']),'strokeWidth':num(s['strokeWidth']*scale),'fillOpacity':num(s['fillOpacity']*100),'strokeOpacity':num(s['strokeOpacity']*100),'opacity':num(s['opacity']*100),'html':'1','shadow':'0'}
 g=o.get('gradient')
 if g and g['units']=='objectBoundingBox' and not g['transform'] and len(g['stops'])==2 and g['stops'][0]['offset']==0 and g['stops'][1]['offset']==1:
  x1,y1,x2,y2=[float(g[k].strip('%'))/(100 if '%' in g[k] else 1) for k in ['x1','y1','x2','y2']]
  if x1==x2 or y1==y2:
   direction=('south' if y2>y1 else 'north') if x1==x2 else ('east' if x2>x1 else 'west');out.update(fillColor=color(g['stops'][0]['color']),gradientColor=color(g['stops'][1]['color']),gradientDirection=direction,gradientFillAlpha=num(g['stops'][0]['opacity']*100),gradientAlpha=num(g['stops'][1]['opacity']*100));o['gradientHandled']=True
 if s['dash']!='none':out.update(dashed='1',fixDash='1',dashPattern=' '.join(num(float(x)*scale) for x in re.findall(r'[\d.]+',s['dash'])))
 return out

def stencil(o):
 rec=RecordingPen();parse_path(path_for(o),TransformPen(rec,tuple(o['matrix'])));bounds=BoundsPen(None);rec.replay(bounds)
 if not bounds.bounds:raise ValueError('empty_path')
 x,y,x2,y2=bounds.bounds;w=max(x2-x,.01);h=max(y2-y,.01);shape=E.Element('shape',{'name':'svg_element','w':num(w),'h':num(h),'aspect':'variable','strokewidth':'inherit'});fg=E.SubElement(shape,'foreground');s=o['style']
 E.SubElement(fg,'linecap',{'cap':'flat' if s['linecap']=='butt' else s['linecap']});E.SubElement(fg,'linejoin',{'join':s['linejoin']});p=E.SubElement(fg,'path')
 for op,points in rec.value:
  pts=[(xx-x,yy-y) for xx,yy in points]
  if op=='moveTo':E.SubElement(p,'move',dict(x=num(pts[0][0]),y=num(pts[0][1])))
  elif op=='lineTo':E.SubElement(p,'line',dict(x=num(pts[0][0]),y=num(pts[0][1])))
  elif op in ('curveTo','qCurveTo'):
   expected=3 if op=='curveTo' else 2
   if len(pts)!=expected:raise ValueError('unsupported_multi_control_path')
   E.SubElement(p,'curve' if op=='curveTo' else 'quad',{k+str(i):num(v) for i,pt in enumerate(pts,1) for k,v in zip(('x','y'),pt)})
  elif op=='closePath':E.SubElement(p,'close')
  elif op!='endPath':raise ValueError('unknown_path_op '+op)
 fill=s['fill']!='none' and (not s['fill'].startswith('url(') or o.get('gradientHandled'));stroke=s['stroke']!='none' and s['strokeWidth']>0
 E.SubElement(fg,'fillstroke' if fill and stroke else 'fill' if fill else 'stroke')
 payload=urllib.parse.quote(E.tostring(shape,encoding='unicode'),safe="~()*!.'-").encode();compress=zlib.compressobj(wbits=-15);encoded=base64.b64encode(compress.compress(payload)+compress.flush()).decode()
 return 'stencil('+encoded+')',(x,y,w,h)

def build(dom,width,height):
 root=E.Element('mxfile',{'host':'app.diagrams.net','type':'device'});diagram=E.SubElement(root,'diagram',{'id':'page-1','name':'SVG objects'});model=E.SubElement(diagram,'mxGraphModel',{'page':'1','pageWidth':str(width),'pageHeight':str(height),'pageScale':'1'});cells=E.SubElement(model,'root');E.SubElement(cells,'mxCell',{'id':'0'});E.SubElement(cells,'mxCell',{'id':'1','parent':'0'});issues=list(dom['issues']);counts={'text':0,'vector_shapes':0,'bound_edges':0,'node_groups':0};node_by_title={};node_bbox={};links=[]
 def cell(id,style,value='',bbox=None,parent='1',edge=None):
  attrs={'id':id,'parent':parent,'value':value,'style':';'.join(k+'='+str(v) for k,v in style.items())+';'};attrs.update({'edge':'1',**edge} if edge else {'vertex':'1'});c=E.SubElement(cells,'mxCell',attrs)
  if bbox:E.SubElement(c,'mxGeometry',{'x':num(bbox[0]),'y':num(bbox[1]),'width':num(bbox[2]),'height':num(bbox[3]),'as':'geometry'})
  return c
 for id,n in dom['nodes'].items():
  b=n['bbox'];bbox=(b['x'],b['y'],b['w'],b['h']);cell('node_'+id,{'group':'1','connectable':'1','fillColor':'none','strokeColor':'none'},bbox=bbox);node_by_title[n['title']]='node_'+id;node_bbox['node_'+id]=bbox;counts['node_groups']+=1
 candidates=[]
 for obj in dom['objects']:
  if obj['type']=='shape' and not obj.get('markerOwner') and not obj.get('edge') and obj['tag'] in ('rect','circle','ellipse','polygon','path') and obj['style']['fill']!='none':
   b=obj['bbox']
   if min(b['w'],b['h'])>=8 and b['w']*b['h']<width*height*.65:candidates.append(obj)
 def endpoint(point,exclude=None):
  scored=[]
  for obj in candidates:
   if obj['id']==exclude:continue
   b=obj['bbox'];x,y,w,h=b['x'],b['y'],b['w'],b['h'];px,py=point;dx=max(x-px,0,px-x-w);dy=max(y-py,0,py-y-h);dist=math.hypot(dx,dy) if dx or dy else min(px-x,x+w-px,py-y,y+h-py)
   if dist<=12:scored.append((dist,w*h,obj))
  scored.sort(key=lambda a:(a[0],a[1]));return scored[0][2] if scored and (len(scored)==1 or scored[1][0]-scored[0][0]>=2.5) else None
 for o in dom['objects']:
  parent='node_'+o['node'] if o.get('node') else '1';origin=node_bbox[parent][:2] if parent!='1' else (0,0)
  if o['type']=='image':
   b=o['bbox'];uri=o['href'].replace(';base64,',',');cell(o['id'],{'shape':'image','image':uri,'imageAspect':'0','opacity':num(o['style']['opacity']*100)},bbox=(b['x']-origin[0],b['y']-origin[1],b['w'],b['h']),parent=parent);counts['source_raster_assets']=counts.get('source_raster_assets',0)+1;continue
  if o['type']=='text':
   b=o['bbox'];st={'shape':'text','html':'1','align':'left','verticalAlign':'middle','spacing':'0','whiteSpace':'nowrap','overflow':'visible','strokeColor':'none','fillColor':'none','fontFamily':o['fontFamily'].split(',')[0].strip('"\''),'fontSize':num(o['fontSize']),'fontColor':color(o['color']),'fontStyle':int(o['bold'])+2*int(o['italic'])+4*int(o['underline']),'opacity':num(o['opacity']*100)}
   cell(o['id'],st,html.escape(o['text']),bbox=(b['x']-origin[0],b['y']-origin[1],b['w'],b['h']),parent=parent);counts['text']+=1;continue
  try:
   st=style(o);edge=o.get('edge');title=edge and edge.get('title');parts=re.split(r'->|--',title or '')
   if edge and o['tag']=='path' and len(parts)==2 and all(p in node_by_title for p in parts) and o.get('sampledPoints') and o['style']['fill']=='none':
    src,tgt=[node_by_title[p] for p in parts];pts=o['sampledPoints'];sx,sy,sw,sh=node_bbox[src];tx,ty,tw,th=node_bbox[tgt];st.update(fillColor='none',endArrow='none',startArrow='none',edgeStyle='none',rounded='0',exitX=num((pts[0][0]-sx)/max(sw,.01)),exitY=num((pts[0][1]-sy)/max(sh,.01)),entryX=num((pts[-1][0]-tx)/max(tw,.01)),entryY=num((pts[-1][1]-ty)/max(th,.01)),exitPerimeter='0',entryPerimeter='0')
    c=cell(o['id'],st,edge={'source':src,'target':tgt});g=E.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'});arr=E.SubElement(g,'Array',{'as':'points'})
    for px,py in pts[1:-1]:E.SubElement(arr,'mxPoint',{'x':num(px),'y':num(py)})
    counts['bound_edges']+=1;links.append({'cell':o['id'],'source':parts[0],'target':parts[1],'edge_group':edge['id'],'curve_sampling_max_step_px':2});continue
   if not edge and o.get('sampledPoints') and (o.get('markerStart','none')!='none' or o.get('markerEnd','none')!='none'):
    pts=o['sampledPoints'];src=endpoint(pts[0],o['id']);tgt=endpoint(pts[-1],o['id']);st.update(fillColor='none',endArrow='none',startArrow='none',edgeStyle='none',rounded='0');attrs={}
    for endpoint_obj,point,prefix,key in [(src,pts[0],'exit','source'),(tgt,pts[-1],'entry','target')]:
     if endpoint_obj:
      b=endpoint_obj['bbox'];attrs[key]=endpoint_obj['id'];st.update({prefix+'X':num((point[0]-b['x'])/max(b['w'],.01)),prefix+'Y':num((point[1]-b['y'])/max(b['h'],.01)),prefix+'Perimeter':'0'})
    c=cell(o['id'],st,edge=attrs or {'svgUnbound':'1'});g=E.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'});arr=E.SubElement(g,'Array',{'as':'points'})
    for px,py in pts[1:-1]:E.SubElement(arr,'mxPoint',{'x':num(px),'y':num(py)})
    if not src:E.SubElement(g,'mxPoint',{'x':num(pts[0][0]),'y':num(pts[0][1]),'as':'sourcePoint'})
    if not tgt:E.SubElement(g,'mxPoint',{'x':num(pts[-1][0]),'y':num(pts[-1][1]),'as':'targetPoint'})
    counts['inferred_connector_edges']=counts.get('inferred_connector_edges',0)+1
    if src and tgt and src['id']!=tgt['id']:counts['bound_edges']+=1
    issues.append({'id':o['id'],'reason':'geometric_connector_binding_requires_semantic_review','source':src['id'] if src else None,'target':tgt['id'] if tgt else None});continue
   sh,b=stencil(o);st['shape']=sh;cell(o['id'],st,bbox=(b[0]-origin[0],b[1]-origin[1],b[2],b[3]),parent=parent);counts['vector_shapes']+=1
  except Exception as e:issues.append({'id':o['id'],'reason':'conversion_error','error':str(e)})
 if any(o.get('markerOwner') for o in dom['objects']):issues.append({'reason':'expanded_marker_vectors_require_connector_grouping_review'})
 if any(o.get('edge') and o['tag']=='polygon' for o in dom['objects']):issues.append({'reason':'edge_arrowheads_separate_vector_objects_require_editing_review'})
 handled={o.get('sourceId') for o in dom['objects'] if o.get('gradientHandled') and o.get('sourceId')}
 # Anonymous SVG ids are common; never suppress ambiguous paint-server warnings.
 issues=[i for i in issues if not (i.get('reason')=='fill_paint_server' and i.get('id') in handled)]
 return E.tostring(root,encoding='unicode'),{'counts':counts,'issues':issues,'source_objects':len(dom['objects']),'graphviz_links':links,'quality_state':'pending_source_and_visual_validation'}
