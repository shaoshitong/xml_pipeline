"""Read-only TikZ->original PDF->SVG source-role bridge research.

No format relabelling, QA bypass, canonical publication or graph-node invention.
Closed source paths use the original PDF/SVG path, not a silently appended Z.
Coordinate arrows are honest free edges; marker fidelity is a separate hard gate.
"""
from __future__ import annotations
import base64,copy,hashlib,html,io,json,math,re,sys,urllib.parse,xml.etree.ElementTree as E
from pathlib import Path

POLICY='tikz_original_pdf_closed_paint_and_free_axis_bridge_prototype_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
HERE=Path(__file__).resolve().parent
MODULE_SHA256=sha(Path(__file__).read_bytes())

def require(ok,why):
 if not ok:raise ValueError(why)
def normalized_ops(value):
 """Discard move-only subpaths; expand a closing segment without changing paint."""
 parts=[];current=[];start=None;point=None
 def finish():
  nonlocal current
  if any(o in ('lineTo','curveTo') for o,p in current):parts.append(current)
  current=[]
 for op,points in value:
  points=[list(map(float,p)) for p in points]
  if op=='moveTo':finish();current=[(op,points)];start=point=points[0]
  elif op in ('lineTo','curveTo'):current.append((op,points));point=points[-1]
  elif op=='closePath':
   if point is not None and start is not None and math.dist(point,start)>1e-7:current.append(('lineTo',[start]))
   finish();start=point=None
  elif op=='endPath':finish();start=point=None
  else:raise ValueError('unhandled contour operation '+op)
 finish();return parts

def softpath(text):
 pattern=re.compile(r'\\pgfsyssoftpath@([A-Za-z]+)token\s*\{([-+0-9.]+)pt\}\s*\{([-+0-9.]+)pt\}')
 matches=list(pattern.finditer(text));require(not pattern.sub('',text).strip(),'unknown PGF softpath syntax')
 ops=[];controls=[];closed=0
 for m in matches:
  op=m[1];p=[float(m[2]),float(m[3])]
  if op=='moveto':ops.append(('moveTo',[p]))
  elif op=='lineto':ops.append(('lineTo',[p]))
  elif op in ('curvetosupporta','curvetosupportb'):controls.append(p)
  elif op=='curveto':require(len(controls)==2,'incomplete cubic controls');ops.append(('curveTo',controls+[p]));controls=[]
  elif op=='closepath':ops.append(('closePath',[]));closed+=1
  else:raise ValueError('unsupported PGF path token '+op)
 require(not controls,'unterminated cubic controls')
 return {'parts':normalized_ops(ops),'explicit_closed_count':closed}

def path_ops(d):
 from fontTools.svgLib.path import parse_path
 from fontTools.pens.recordingPen import RecordingPen
 p=RecordingPen();parse_path(d,p);return normalized_ops(p.value)
def points(ops):return [p for part in ops for op,values in part for p in values]
def transform_ops(parts,offset):return [[(op,[[p[0]*72/72.27+offset[0],-p[1]*72/72.27+offset[1]] for p in ps]) for op,ps in part] for part in parts]
def op_distance(a,b):
 if len(a)!=len(b):return float('inf')
 worst=0
 for pa,pb in zip(a,b):
  if len(pa)!=len(pb):return float('inf')
  for (oa,aa),(ob,bb) in zip(pa,pb):
   if oa!=ob or len(aa)!=len(bb):return float('inf')
   worst=max(worst,max((math.dist(x,y) for x,y in zip(aa,bb)),default=0))
 return worst

def source_roles(events,drawings):
 """Unique, complete source-PGF/PDF paint bijection; ambiguity fails closed."""
 require(not any(e['kind']=='unsupportedpaint' for e in events),'source has unowned direct PGF paint')
 require(not any(e['kind']=='ref' for e in events),'named graph/reference source belongs to PGF graph route')
 require(not any(e['kind']=='node' and e['fields'][4] for e in events),'named nodes belong to existing graph route')
 paths=[]
 for e in events:
  if e['kind']!='finish' or not e['fields'][5].strip():continue
  f=e['fields'];sp=softpath(f[5]);require(len(sp['parts'])==1,'multiple source subpaths need an explicit composition proof')
  paths.append({'picture':f[0],'path':f[1],'arrows_tex':f[2],'start_arrow':f[3]=='1','end_arrow':f[4]=='1',**sp})
 closed=[p for p in paths if p['explicit_closed_count']==1 and not p['start_arrow'] and not p['end_arrow']]
 require(closed,'no closed source shape to anchor the PDF coordinate frame')
 offsets=[]
 for p in closed:
  a=points(p['parts'])[0]
  for d in drawings:
   b=points(d['parts'])[0];off=[b[0]-a[0]*72/72.27,b[1]+a[1]*72/72.27]
   if op_distance(transform_ops(p['parts'],off),d['parts'])<=.03:offsets.append(off)
 require(offsets,'PGF closed paint does not match the actual original PDF')
 viable=[]
 for off in offsets:
  mapped=[];used=set();ok=True
  for p in closed:
   options=[d for d in drawings if op_distance(transform_ops(p['parts'],off),d['parts'])<=.03]
   if len(options)!=1 or options[0]['id'] in used:ok=False;break
   d=options[0];mapped.append({'source':p,'pdf_objects':[d['id']],'role':'source_explicit_closed_basic_paint','maximum_control_point_error_bp':op_distance(transform_ops(p['parts'],off),d['parts'])});used.add(d['id'])
  if ok and not any(math.dist(off,x[0])<.01 for x in viable):viable.append((off,mapped,used))
 require(len(viable)==1,'source-PDF global translation or closed-paint ownership ambiguous');off,mapped,used=viable[0]
 for p in paths:
  if p in closed:continue
  require(p['arrows_tex']=='-stealth' and not p['start_arrow'] and p['end_arrow'] and not p['explicit_closed_count'],'unhandled source paint/arrow role')
  ops=transform_ops(p['parts'],off);require(len(ops[0])==2 and [o for o,_ in ops[0]]==['moveTo','lineTo'],'axis source is not one explicit straight numeric segment')
  start,end=points(ops);delta=[end[i]-start[i] for i in (0,1)];length=math.hypot(*delta);require(length>10,'arrow source too short for a proved axis');u=[v/length for v in delta];shaft=[]
  for d in drawings:
   if d['id'] in used or d['fill']!='none' or d['stroke']=='none' or len(d['parts'])!=1 or [o for o,_ in d['parts'][0]]!=['moveTo','lineTo']:continue
   a,b=points(d['parts']);short=sum((end[i]-b[i])*u[i] for i in (0,1));normal=abs((b[0]-start[0])*u[1]-(b[1]-start[1])*u[0])
   if math.dist(a,start)<=.03 and normal<=.03 and .1<short<min(20,length*.1):shaft.append(d)
  require(len(shaft)==1,'source straight shaft has no unique PDF owner');shaft=shaft[0];heads=[]
  for d in drawings:
   if d['id'] in used or d['id']==shaft['id'] or d['stroke']!='none' or d['fill']!=shaft['stroke'] or len(d['parts'])!=1:continue
   ops=d['parts'][0]
   if len(ops)!=4 or [o for o,_ in ops]!=['moveTo','lineTo','lineTo','lineTo']:continue
   poly=points(d['parts']);tip=max(poly,key=lambda q:sum(q[i]*u[i] for i in (0,1)));local=[[(q[0]-tip[0])*u[0]+(q[1]-tip[1])*u[1],-(q[0]-tip[0])*u[1]+(q[1]-tip[1])*u[0]] for q in poly];left=min(local,key=lambda q:q[1]);right=max(local,key=lambda q:q[1]);back=min(q[0] for q in local);interior=[q for q in local if abs(q[1])<=.03 and q[0]<-.03]
   # Only a symmetric concave stealth head, same shaft colour and actual tip.
   if math.dist(tip,end)<=.03 and abs(left[0]-right[0])<=.03 and abs(left[1]+right[1])<=.03 and back<-.1 and len(interior)==1 and back<interior[0][0]<-.03:heads.append((d,poly,tip,local))
  require(len(heads)==1,'axis arrow head owner/side/stealth shape ambiguous');head,poly,tip,local=heads[0];used.update([shaft['id'],head['id']]);mapped.append({'source':p,'pdf_objects':[shaft['id'],head['id']],'role':'explicit_numeric_coordinate_axis_free_edge','source_start_bp':start,'source_tip_bp':end,'unit':u,'source_head_polygon_bp':poly,'source_shaft_end_bp':points(shaft['parts'])[-1],'source_head_length_bp':-min(q[0] for q in local),'source_head_width_bp':max(q[1] for q in local)-min(q[1] for q in local),'source_colour':shaft['stroke'],'source_stroke_width_bp':shaft['stroke_width'],'graph_terminals_invented':False})
 axes=[m for m in mapped if m['role']=='explicit_numeric_coordinate_axis_free_edge']
 if axes:
  require(len(axes)==2 and math.dist(axes[0]['source_start_bp'],axes[1]['source_start_bp'])<=.03 and abs(sum(a*b for a,b in zip(axes[0]['unit'],axes[1]['unit'])))<=1e-6,'numeric arrow role is not a uniquely proved shared-origin orthogonal coordinate-axis pair')
 require(used=={d['id'] for d in drawings},'unmapped PDF paint objects remain')
 return {'ok':True,'global_PGF_pt_to_PDF_bp_frame':{'scale':72/72.27,'flip_y':True,'translation':off},'objects':mapped,'all_source_and_PDF_paint_accounted':True,'axis_graph_terminal_claim':False}

def closed_basic(obj,pgf):
 """Source PGF explicitly closes; candidate retains the exact original SVG d."""
 import svg_source_scene_dom_v1 as scene
 import auto_quality_svg_closed_scene_v1 as closed
 require(pgf['explicit_closed_count']==1 and not pgf['start_arrow'] and not pgf['end_arrow'],'not proved source closed paint')
 x=copy.deepcopy(obj);x['d']+=' Z';x.pop('sceneGeometry',None);scene.enrich_scene({'objects':[x],'issues':[]});role=closed._basic_closed_geometry(x);require(role,'closed source is not within the frozen basic-shape family')
 return {'role':role,'source_explicitly_closed_by_PGF':True,'original_SVG_path_unchanged':True,'native_path_must_equal_original_PDF_path':True,'physical_Z_insertion':False}

def font_proof(doc,page,fonts,traces):
 from fontTools.cffLib import CFFFontSet
 from fontTools.ttLib import TTFont
 from fontTools.pens.recordingPen import RecordingPen
 result=[];sources={}
 for row in page.get_fonts(full=True):
  name,ext,typ,data=doc.extract_font(row[0]);sources[re.sub(r'^[A-Z]{6}\+','',name).removesuffix('-Identity-H')]=data
 for name,f in fonts.items():
  data=sources[name];require(sha(data)==f['source_font_sha256'],'original PDF font differs');old=CFFFontSet();old.decompile(io.BytesIO(data),None);ot=old.topDictIndex[0];new=TTFont(f['file']);nt=new['CFF '].cff.topDictIndex[0];require(ot.charset==nt.charset and list(ot.FontMatrix)==list(nt.FontMatrix),'font glyph roster/matrix changed');cmap=new.getBestCmap();used=[]
  for t in traces:
   if t['font']!=name:continue
   for c in t['clusters']:
    glyph=('cid'+str(c['gid']).zfill(5)) if hasattr(ot,'ROS') and c['gid'] else ot.charset[c['gid']] if not hasattr(ot,'ROS') else '.notdef';require(cmap.get(ord(c['text']))==glyph,'source Unicode->glyph mapping changed');a=RecordingPen();b=RecordingPen();ot.CharStrings[glyph].draw(a);nt.CharStrings[glyph].draw(b);require(a.value==b.value,'actual source glyph contour changed');require(abs(ot.CharStrings[glyph].width-new['hmtx'][glyph][0])<=1e-8,'glyph advance changed');used.append((ord(c['text']),glyph))
  result.append({'family':f['family'],'source_font_sha256':sha(data),'native_font_sha256':sha(Path(f['file']).read_bytes()),'used_clusters':len(used),'glyph_contours_Unicode_mapping_and_advances_exact':True})
 return {'ok':True,'fonts':result}

def capture_svg(svg,work,width,height):
 import svg_source_scene_dom_v1 as scene
 browser=scene._browser();ctx=browser.new_context(viewport={'width':math.ceil(width),'height':math.ceil(height)},java_script_enabled=False,service_workers='block');blocked=[]
 try:
  ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));p=ctx.new_page();p.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg);p.evaluate('document.fonts.ready');dom=p.evaluate(scene.EXTRACTOR.read_text());p.screenshot(path=str(Path(work)/'derived_source_svg.png'))
 finally:ctx.close()
 require(not blocked,'derived source depends on external network');scene.enrich_scene(dom);dom['bridge_capture']={'source_is_derived_SVG_not_authoritative_format_relabel':True,'svg_sha256':sha(svg.encode()),'extractor_sha256':sha(scene.EXTRACTOR.read_bytes()),'width':width,'height':height,'offline':True};return dom

def native_candidate(dom,width,height,fonts,roles):
 from svg_convert_v6 import build
 from svg_convert_v3 import unpack,pack
 from svg_convert_v2 import num
 from pdf_to_native import attach_fonts
 xml,stats=build(dom,width,height);root=E.fromstring(xml);container=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in container};by_source={o.get('sourceId'):o for o in dom['objects']};axes=[]
 for role in roles['objects']:
  if role['role']!='explicit_numeric_coordinate_axis_free_edge':continue
  shaft,head=[by_source['pdfpath'+str(i)] for i in role['pdf_objects']];require(dom['objects'].index(head)==dom['objects'].index(shaft)+1,'shaft/head source paint is interleaved and cannot be atomically merged');c=cells[shaft['id']];g=c.find('mxGeometry');c.remove(g);c.attrib.pop('vertex',None);c.set('edge','1');st=unpack(c.get('style'));st.update(strokeWidth=num(role['source_stroke_width_bp']),strokeColor=role['source_colour'],shape='connector',fillColor='none',endArrow='classic',startArrow='none',endFill='1',endSize=num(max(.1,role['source_head_length_bp']-role['source_stroke_width_bp'])),edgeStyle='none',rounded='0',curved='0');c.set('style',pack(st));g=E.SubElement(c,'mxGeometry',{'relative':'1','as':'geometry'});E.SubElement(g,'mxPoint',dict(x=num(role['source_start_bp'][0]),y=num(role['source_start_bp'][1]),**{'as':'sourcePoint'}));u=role['unit'];sw=role['source_stroke_width_bp'];ep=[role['source_tip_bp'][i]+u[i]*sw*1.118 for i in (0,1)];E.SubElement(g,'mxPoint',dict(x=num(ep[0]),y=num(ep[1]),**{'as':'targetPoint'}));container.remove(cells[head['id']]);axes.append({**role,'cell_id':shaft['id'],'removed_source_marker_cell':head['id'],'native_marker_type':'classic','native_marker_size':float(st['endSize']),'native_target_point':ep})
 return attach_fonts(E.tostring(root,encoding='unicode'),fonts),{'converter':stats,'axes':axes,'honest_free_edges_without_graph_terminals':True}

def polygon_distance(a,b):
 def dist(p,x,y):
  d=[y[i]-x[i] for i in (0,1)];s=sum(v*v for v in d);t=max(0,min(1,sum((p[i]-x[i])*d[i] for i in (0,1))/s)) if s else 0;return math.dist(p,[x[i]+t*d[i] for i in (0,1)])
 def directed(x,y):
  return max(min(dist(p,a,b) for a,b in zip(y,y[1:]+y[:1])) for p in [q for a,b in zip(x,x[1:]+x[:1]) for q in [[a[i]+(b[i]-a[i])*t/32 for i in (0,1)] for t in range(33)]])
 return max(directed(a,b),directed(b,a))

def audit_native(xml,fonts,axes,work):
 from native_worker import native
 import svg_source_scene_dom_v1 as scene
 from tikz_execution_binding_v2 import VIEWER_SHA256,native_marker_polygon
 cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};require({c.get('id') for c in cells.values() if c.get('edge')=='1'}=={a['cell_id'] for a in axes},'unproved additional native edge')
 for a in axes:
  cell=cells[a['cell_id']];require(not cell.get('source') and not cell.get('target'),'coordinate axis invents graph terminals');geom=cell.find('mxGeometry');st=dict(v.split('=',1) for v in cell.get('style','').split(';') if '=' in v)
  for side,expected in [('source',a['source_start_bp']),('target',a['native_target_point'])]:
   point=geom.find("mxPoint[@as='"+side+"Point']");require(point is not None and all(abs(float(point.get(k))-v)<=1e-6 for k,v in zip(('x','y'),expected)),'native free endpoint/source provenance differs')
  require(st.get('endArrow')==a['native_marker_type'] and abs(float(st.get('endSize',0))-a['native_marker_size'])<=1e-6 and st.get('strokeColor')==a['source_colour'] and abs(float(st.get('strokeWidth',0))-a['source_stroke_width_bp'])<=1e-6,'native axis marker or paint/source provenance differs')
 root=Path('/backup/shaoshitong/img2code_20261029');viewer=native.renderer_path(root).parent/'assets/viewer-static.min.js';require(sha(viewer.read_bytes())==VIEWER_SHA256,'unreviewed native viewer');script=HERE/'tikz_closed_paint_bridge_v1.js';script_blob=script.read_bytes();p=scene._browser().new_page(viewport={'width':math.ceil(float(E.fromstring(xml).find('.//mxGraphModel').get('pageWidth'))),'height':math.ceil(float(E.fromstring(xml).find('.//mxGraphModel').get('pageHeight')))})
 try:
  p.route('**/*',lambda r:r.abort());p.set_content('<style>html,body{margin:0;padding:0;background:white}</style>');p.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');p.add_script_tag(path=str(viewer));raw=p.evaluate(script_blob.decode(),{'xml':xml,'fonts':[{'family':f['family'],'uri':f['uri']} for f in fonts.values()]});p.screenshot(path=str(Path(work)/'candidate_native.png'))
 finally:p.close()
 require(script.read_bytes()==script_blob and sha(viewer.read_bytes())==VIEWER_SHA256,'native script/runtime changed during proof')
 marker=[]
 for axis in axes:
  expected,_=native_marker_polygon(axis['native_marker_type'],axis['native_marker_size'],axis['source_stroke_width_bp'],axis['native_target_point'],axis['unit']);distance=polygon_distance(axis['source_head_polygon_bp'],expected);marker.append({'cell_id':axis['cell_id'],'maximum_source_native_head_boundary_error_bp':distance,'strict_maximum_bp':.03,'source_native_marker_exact_within_numeric_tolerance':distance<=.03,'source_role':'coordinate_axis_not_graph_edge'})
 return {'ok':raw.get('ok') is True and all(x['source_native_marker_exact_within_numeric_tolerance'] for x in marker),'actual_native_intervention':raw,'source_native_markers':marker,'viewer_sha256':VIEWER_SHA256,'script_sha256':sha(script_blob),'acceptance':False}

def prepare(db,identifier,evidence,config,work):
 import tikz_source_only_failure_v1 as source
 import svg_failure_closure_v1 as shared
 from tikz_execution_graph import parse_events,graph_from_events
 from pdf_to_native import source_svg,pathdata,rgb
 import pymupdf
 work=Path(work).resolve();root=Path(config['root']);require(work.is_relative_to(root/'conversion/prototype/tikz_closed_paint_bridge_v1'),'private bridge work only');work.mkdir(parents=True,exist_ok=False);report={'policy':POLICY,'id':identifier,'published':False,'accepted':False,'models_called':0,'proposal':False};files={}
 def save(name,value):
  path=work/name;path.write_bytes(value if isinstance(value,bytes) else canonical(value));files[str(path)]=sha(path.read_bytes())
 try:
  require(not db.in_transaction,'RO autocommit required');source.pins_ok(config);require(sha(Path(__file__).read_bytes())==MODULE_SHA256,'bridge module changed after import');before=shared.snapshot(db,identifier);r=json.loads(Path(evidence).read_text());require(r['id']==identifier and r['policy']==config['policy'] and r['pins']==config['pins'],'source-only evidence catalogue differs');require(sha(source.canonical({k:v for k,v in r.items() if k!='certificate_sha256'}))==r['certificate_sha256'],'source-only certificate differs')
  for p,h in r['files'].items():require(sha(Path(p).read_bytes())==h,'original source/runtime/evidence changed')
  folder=Path(r['evidence_directory']);env=json.loads((folder/'environment.json').read_text());require(source.environment_files(root)==env['files'],'original environment changed');record=json.loads(db.execute('select input_record from jobs where id=?',(identifier,)).fetchone()[0]);require((record['code_sha256'],record['image_sha256'])==(r['source_code_sha256'],r['source_image_sha256']),'source revision changed');require(db.execute('select status from processing_outcomes_v2 where id=?',(identifier,)).fetchone()[0]=='pending','no longer pending')
  sidecar=json.loads((folder/'execution/execution_graph.json').read_text());require(set(sidecar['runs'])=={'baseline','instrumented'} and all(x['returncode']==0 for x in sidecar['runs'].values()) and all(x['pixel_identical'] for x in sidecar['instrumentation_pdf_pixel_equivalence']),'no successful pixel-equivalent original source execution');require(source.source_context_guard((folder/'original_source.tex').read_text())['ok'],'unproved source execution context');events=parse_events((folder/'execution/instrumented/source.iic').read_text());require(graph_from_events(events)==sidecar['graph'],'PGF event replay changed');pdf=folder/'execution/baseline/source.pdf'
  with pymupdf.open(pdf) as doc:
   require(len(doc)==1,'multiframe source not supported');page=doc[0];require(not page.get_images(),'raster assets require independent extraction');drawings=[]
   for i,d in enumerate(page.get_drawings(extended=True)):
    require(d['type'] not in ('clip','group'),'clip/group PDF semantics not proved');drawings.append({'id':i,'seqno':d['seqno'],'parts':path_ops(pathdata(d)),'fill':rgb(d.get('fill')),'stroke':rgb(d.get('color')),'stroke_width':d.get('width') or 0})
   roles=source_roles(events,drawings);save('source_PGF_to_original_PDF_roles.json',roles);svg,fonts,stats=source_svg(doc,page,work/'source');page.get_pixmap(matrix=pymupdf.Matrix(1,1),alpha=False).save(str(work/'original_baseline_pdf.png'));require(not stats['issues'],'PDF converter reported unresolved semantics');fproof=font_proof(doc,page,fonts,__import__('pdf_fonts').build_fonts(doc,page,work/'font_recheck')[1]);save('physical_font_proof.json',fproof);save('source_derived.svg',svg.encode());dom=capture_svg(svg,work,page.rect.width,page.rect.height);require(not dom.get('issues'),'derived source capture reported unhandled semantics');save('fresh_derived_source_DOM.json',dom)
   by_source={o.get('sourceId'):o for o in dom['objects']};basic=[]
   for role in roles['objects']:
    if role['role']=='source_explicit_closed_basic_paint':basic.append({'source_path':role['source']['path'],'native_object':by_source['pdfpath'+str(role['pdf_objects'][0])]['id'],'proof':closed_basic(by_source['pdfpath'+str(role['pdf_objects'][0])],role['source'])})
   save('closed_basic_roles.json',basic);xml,candidate=native_candidate(dom,page.rect.width,page.rect.height,fonts,roles);save('candidate.drawio',xml.encode());save('candidate_object_mapping.json',candidate)
  axes=candidate['axes'];axis_pdf_ids={i for a in axes for i in a['pdf_objects']};paint_dom=copy.deepcopy(dom);paint_dom['objects']=[o for o in dom['objects'] if o.get('sourceId') not in {'pdfpath'+str(i) for i in axis_pdf_ids}]
  from auto_quality_source_vector_v2 import _paint_coverage,_graphviz_coverage
  from auto_quality_svg_closed_scene_v1 import _native_integrity
  coverage=_paint_coverage(paint_dom,xml);require(all(abs(coverage['source_layout_translation'][k])<=.03 for k in ('dx','dy')),'unregistered source PDF canvas translation');require({o['id'] for o in dom['objects']}-{a['removed_source_marker_cell'] for a in axes}=={c.get('id') for c in E.fromstring(xml).iter('mxCell') if c.get('vertex')=='1' or c.get('edge')=='1'},'extra/missing source-native editable object');paint_root=E.fromstring(xml);paint_cells=paint_root.find('.//mxGraphModel/root')
  for cell in list(paint_cells):
   if cell.get('id') in {a['cell_id'] for a in axes}:paint_cells.remove(cell)
  paint_xml=E.tostring(paint_root,encoding='unicode');inventory=_graphviz_coverage(paint_dom,paint_xml,{});integrity=_native_integrity(paint_dom,paint_xml);integrity['scope']='exact closed/text subset; all removed axes separately checked as actual source-bound free edges, complete full inventory checked before subset';save('closed_and_text_exact_native_mapping.json',{'paint':coverage,'integrity':integrity,'complete_source_text_and_object_inventory':inventory});audit=audit_native(xml,fonts,axes,work);save('native_intervention.json',audit)
  from auto_quality_common import image_quality
  from PIL import Image
  diagnostics={}
  for name,path in [('original_PDF_vs_derived_SVG','original_baseline_pdf.png'),('derived_SVG_vs_native','derived_source_svg.png')]:
   try:diagnostics[name]=image_quality((work/path).read_bytes(),(work/('derived_source_svg.png' if name=='original_PDF_vs_derived_SVG' else 'candidate_native.png')).read_bytes(),{})
   except Exception as exc:diagnostics[name]={'ok':False,'error':repr(exc)}
  original=(root/json.loads(db.execute('select input_manifest from jobs where id=?',(identifier,)).fetchone()[0])['reference_image']).read_bytes();require(sha(original)==r['source_image_sha256'],'authoritative source reference changed')
  diagnostics['authoritative_original_reference_size']=list(Image.open(io.BytesIO(original)).size);diagnostics['prototype_native_size']=list(Image.open(work/'candidate_native.png').size);diagnostics['authoritative_original_image_acceptance']='not asserted; full registered original-image QA remains mandatory'
  save('image_diagnostics_not_acceptance.json',diagnostics)
  require(shared.snapshot(db,identifier)==before,'source/job/outcome/owner snapshot changed during proof');source.pins_ok(config);require(sha(Path(__file__).read_bytes())==MODULE_SHA256,'bridge module changed during proof');require(source.environment_files(root)==env['files'],'environment changed after bridge proof')
  report.update(source_role_proof=roles,closed_objects=basic,source_derived_svg_sha256=sha(svg.encode()),source_pdf_sha256=sha(pdf.read_bytes()),source_code_sha256=r['source_code_sha256'],source_image_sha256=r['source_image_sha256'],source_only_evidence=str(evidence),environment_manifest_sha256=env['manifest_sha256'],physical_fonts=fproof,source_paint_mapping=coverage,native_integrity=integrity,source_text_and_object_inventory=inventory,native_editing=audit,bridge_source_role_supported=True,bridge_complete=False,reason='research_prototype_requires_registered_source_profile_and_original_image_full_QA',native_object_count=len(E.fromstring(xml).findall('.//mxCell'))-2,snapshot=before,actual_QA4b_source_profile_modified=False,image_diagnostics=diagnostics,module_sha256=MODULE_SHA256)
  if axes and not audit['ok']:report['reason']='axis_source_owner_proved_but_builtin_native_marker_fidelity_not_proved_retain_pending'
 except Exception as exc:report.update(bridge_source_role_supported=False,bridge_complete=False,reason='unproved_bridge_remains_pending',error=repr(exc))
 for path in work.rglob('*'):
  if path.is_file():require(not path.is_symlink(),'private bridge artifact symlink');files[str(path)]=sha(path.read_bytes())
 report['files']=files;report['work']=str(work);report['report_sha256']=sha(canonical(report));(work/'report.json').write_bytes(canonical(report));return report
