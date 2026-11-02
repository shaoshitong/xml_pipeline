"""Original TikZ compiler with executed named and honest source-coordinate paths.

No model/canonical-DB/queue writes. Every source paint and Unicode text object
is retained. Named terminals bind to source nodes; numeric terminals retain
explicit mxGeometry endpoints. Fixed full-page projection uses PNG header only.
"""
from __future__ import annotations
import collections,copy,hashlib,io,json,math,sys,uuid,xml.etree.ElementTree as ET
from pathlib import Path
from compiler_language_capture_v1 import screenshot
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='compiler_tikz_free_paths_v1';FIELD=VERSION
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
DEPENDENCIES=('compiler_language_capture_v1.py','compiler_tikz_free_paths_v1.py','tikz_execution_binding_v3.py','tikz_execution_binding.py','tikz_execution_graph.py','tikz_execution_graph_hooks.tex','tikz_literal_graph.py','tikz_literal_connectivity.py','tikz_connectivity.py','tectonic_compile.py','sandbox_runner.py','pdf_to_native.py','pdf_fonts.py','svg_dom_pdf_v2.js','svg_convert_v2.py','svg_convert_v3.py','tikz_execution_marker_paint_fit.py','tikz_execution_binding_v2.py','tikz_execution_marker_quality.py','auto_quality_common_v4.py','strict_canvas_gate.py','compiler_languages_source_layout_v1.py')
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda v:(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def save(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():require(p.read_bytes()==b,'immutable_payload_changed')
 else:p.write_bytes(b)
def entry(p):return {'file':str(Path(p).relative_to(R)),'sha256':sha(Path(p).read_bytes())}
def checked(e):
 p=(R/e['file']).resolve(strict=True);require(p.is_relative_to(R/'clean'),'payload_outside_clean');require(not p.is_symlink(),'symlink_payload');b=p.read_bytes();require(sha(b)==e['sha256'],'payload_hash_changed');return b

def configuration(data_root=R):
 require(Path(data_root).resolve()==R,'registered_HKUST_root_required')
 from tectonic_compile import RUNTIME
 pins={str(W/'scripts'/n):sha((W/'scripts'/n).read_bytes()) for n in DEPENDENCIES}
 for n in ('tikz.code.tex','pgfmoduleshapes.code.tex','pgfcorearrows.code.tex'):
  p=next((RUNTIME/'cache/bundles/data').glob('*/'+n));pins[str(p)]=sha(p.read_bytes())
 for p in [RUNTIME/'tectonic',Path(CHROME),W/'rendering_paintbounds_strict/remote_render.py',R/'evaluation/assets/viewer-static.min.js',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']:
  pins[str(p)]=sha(p.read_bytes())
 return {'policy':VERSION+':'+sha(raw(pins))[:20],'pins':pins,'source_requires_native_info':False,'units':{'tikz':'executed_named_nodes_and_explicit_free_paths_v1'},'model_calls':0}

def inputs(record,job=None):
 from compiler_languages_source_layout_v1 import _inputs
 return _inputs(record,job)

def static_support(record):
 try:
  source,code,ref=inputs(record);require(source['format']=='tikz','requires_tikz');require(len(code)<=250000,'source_resource_bound')
  from PIL import Image
  w,h=Image.open(io.BytesIO(ref)).size;require(max(w,h)<=8192 and w*h<=64000000,'source_canvas_resource_bound')
  return {'supported':True,'unit':'executed_named_nodes_and_explicit_free_paths_v1','scope':'Static resource eligibility only; actual source execution/coverage/fidelity remain mandatory.'}
 except Exception as e:return {'supported':False,'reasons':[str(e)]}

def capture_source(code,reference,work):
 from tikz_execution_graph import compile_execution_graph,parse_events
 from tikz_execution_binding_v3 import graph_from_events
 from pdf_to_native import source_svg
 from PIL import Image
 from playwright.sync_api import sync_playwright
 work=Path(work);work.mkdir(parents=True,exist_ok=False)
 sidecar=compile_execution_graph(code,work/'execution')
 require(set(sidecar['runs'])=={'baseline','instrumented'} and all(x['returncode']==0 for x in sidecar['runs'].values()),'original_source_compile_failed')
 require(sidecar.get('source_bytes_unchanged') is True and sidecar.get('instrumentation_pdf_pixel_equivalence') and all(x['pixel_identical'] for x in sidecar['instrumentation_pdf_pixel_equivalence']),'source_instrumentation_changed_PDF_pixels')
 events=parse_events((work/'execution/instrumented/source.iic').read_text());graph=graph_from_events(events)
 require(graph['ok'],'typed_source_trace_unsupported:'+json.dumps(graph['failures'])[:2000])
 # Legacy numeric-path rejection is retained as evidence; typed source analysis
 # must independently account the complete same trace before emission.
 sidecar={**sidecar,'legacy_graph':sidecar['graph'],'graph':graph,'ok':True}
 sys.path.append(str(W/'runtime/python_packages'));import pymupdf
 with pymupdf.open(work/'execution/baseline/source.pdf') as doc:
  require(len(doc)==1 and doc[0].rotation==0,'requires_single_unrotated_source_page')
  svg,fonts,pdfstats=source_svg(doc,doc[0],work)
  require(not pdfstats['issues'],'PDF_source_feature_unsupported:'+json.dumps(pdfstats['issues'])[:1000])
 width,height=Image.open(io.BytesIO(reference)).size;blocked=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=context.new_page()
   page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+svg)
   from compiler_languages_source_layout_v1 import PROJECT_JS
   frame=page.evaluate(PROJECT_JS,[width,height]);page.evaluate('document.fonts.ready');png=screenshot(page);projected=page.locator('svg').evaluate('s=>s.outerHTML').encode();dom=page.evaluate((W/'scripts/svg_dom_pdf_v2.js').read_text());matrix=page.evaluate('()=>{const m=document.querySelector("svg").getScreenCTM();return [m.a,m.b,m.c,m.d,m.e,m.f]}')
   require(screenshot(page)==png,'source_extraction_changed_pixels');require(not blocked,'source_external_resources');require(not dom.get('issues'),'source_DOM_feature_unsupported:'+json.dumps(dom['issues'])[:1200])
  finally:browser.close()
 save(work/'source.svg',projected);save(work/'source.png',png);save(work/'source_dom.json',raw(dom));save(work/'typed_execution.json',raw(sidecar));return {'svg':svg.encode(),'projected_svg':projected,'png':png,'fonts':fonts,'pdfstats':pdfstats,'dom':dom,'matrix':matrix,'sidecar':sidecar,'events':events,'frame':frame,'pdf':(work/'execution/baseline/source.pdf').read_bytes()}

def emit(capture,width,height):
 from svg_convert_v2 import build
 from pdf_to_native import attach_fonts
 from tikz_execution_binding_v3 import bind_execution
 xml,stats=build(capture['dom'],width,height);base=attach_fonts(xml,capture['fonts'])
 xml,binding=bind_execution(base,capture['dom'],capture['sidecar'],capture['events'],capture['matrix'])
 require(binding['complete'],'source_binding_incomplete:'+json.dumps(binding['issues'])[:2000])
 xml,fit=fit_markers(xml,capture['dom'],binding)
 return xml,base,{'converter':stats,'binding':binding,'marker_fit':fit}

def fit_markers(xml,dom,binding):
 """Source-vector contour calibration; never uses reference raster pixels."""
 from tikz_execution_marker_paint_fit import PAINT_FIT,local_path
 from tikz_execution_binding_v2 import _source_geometry,TYPES
 from svg_convert_v2 import num
 from svg_convert_v3 import unpack,pack
 from playwright.sync_api import sync_playwright
 root=ET.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};objects={o['id']:o for o in dom['objects']};reports=[]
 markers=binding['binding']['native_arrowheads']
 if not markers:return xml,{'policy':'source_vector_contour_native_marker_fit_no_reference_pixels_v1','markers':[]}
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>')
   for marker in markers:
    obj=objects[marker['source_object']];geo=_source_geometry(obj,objects[marker['edge']],marker['side']);d,closed=local_path(obj,geo);style=obj['style'];outline=geo['outline_stroke'] if style['stroke']!='none' else 0.;native_outline=0. if marker['native_marker_stroke']=='transparent' else geo['stroke']
    fitted=page.evaluate(PAINT_FIT,{'path':d,'closed':closed,'length':geo['length'],'width':geo['width'],'stroke':geo['stroke'],'outline':outline,'nativeOutline':native_outline,'join':style['linejoin'],'cap':style['linecap'],'fillAlpha':style['fillOpacity']*style['opacity'],'strokeAlpha':style['strokeOpacity']*style['opacity'],'types':list(TYPES)})
    chosen=fitted['ranked'][0];cell=cells[marker['edge']];st=unpack(cell.get('style'));stroke=float(st['strokeWidth']);point=geo['tip']+geo['u']*(stroke*1.118+chosen['along']);side='source' if marker['side']=='start' else 'target';terminal=cell.get(side);prefix='exit' if side=='source' else 'entry';st.update({marker['side']+'Arrow':chosen['kind'],marker['side']+'Size':num(chosen['size'])})
    if terminal:
     bb=objects[terminal]['bbox'];st.update({prefix+'X':num((point[0]-bb['x'])/bb['w']),prefix+'Y':num((point[1]-bb['y'])/bb['h']),prefix+'Perimeter':'0'})
    else:
     ep=cell.find("mxGeometry/mxPoint[@as='"+side+"Point']");require(ep is not None,'free_marker_endpoint_missing');ep.set('x',num(point[0]));ep.set('y',num(point[1]))
    cell.set('style',pack(st));reports.append({'edge':marker['edge'],'side':side,'source_marker':obj['id'],'chosen':chosen,'source_vector_only':True})
  finally:b.close()
 return ET.tostring(root,encoding='unicode'),{'policy':'source_vector_contour_native_marker_fit_no_reference_pixels_v1','markers':reports}

def source_visual(reference,capture):
 from auto_quality_common_v4 import image_quality
 positions=[]
 for o in capture['dom']['objects']:
  if o['type']=='text' and o.get('text','').strip():
   b=o['bbox'];positions.append({'cell':o['id'],'runs':[{'chars':[{'text':o['text'],'x':b['x'],'y':b['y'],'width':b['w'],'height':b['h']}]}]})
 q=image_quality(reference,capture['png'],{},positions)
 return {'supported':True,'ok':q['ok'],'reason':'source_reference_reproduced' if q['ok'] else 'source_reference_mismatch','visual':q,'fixed_projection':capture['frame']}

def convert(record,job,work):
 out={'ok':False,'qualified':False,'model_calls':0};stage='input';work=Path(work)
 try:
  require(work.resolve().is_relative_to(W/VERSION),'unowned_work');work.mkdir(parents=True,exist_ok=False);source,code,reference=inputs(record,job);require(source['format']=='tikz','requires_tikz');config=configuration();stage='source_execution';c=capture_source(code,reference,work/'source');reproduction=source_visual(reference,c);out['source_reproduction']=reproduction
  from PIL import Image
  width,height=Image.open(io.BytesIO(reference)).size;stage='native_emission';xml,base,stats=emit(c,width,height)
  from native_worker import native
  from strict_canvas_gate import require_declared_page
  rendered=native.native_job(xml,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(rendered['ok'],'native_render_failed:'+str({k:v for k,v in rendered.items() if k!='png'})[:1200]);save(work/'native_render.json',raw({k:v for k,v in rendered.items() if k!='png'}));save(work/'native.png',rendered['png'])
  # A generated complete native candidate can still fail the page/alignment
  # qualification gate; retain it for generic repair instead of hiding codegen.
  try:require_declared_page(rendered['native_render'],width,height);native_canvas_ok=True
  except AssertionError:native_canvas_ok=False
  dest=R/'clean'/VERSION/source['pair_sha256'][:2]/source['pair_sha256']/uuid.uuid4().hex;dest.mkdir(parents=True);files={}
  payloads={'original_source':(code,'tex'),'original_reference':(reference,'png'),'source_pdf':(c['pdf'],'pdf'),'source_svg':(c['projected_svg'],'svg'),'source_png':(c['png'],'png'),'source_dom':(raw(c['dom']),'json'),'source_trace':((work/'source/execution/instrumented/source.iic').read_bytes(),'iic'),'source_execution':(raw(c['sidecar']),'json'),'source_frame':(raw(c['frame']),'json'),'source_stats':(raw(stats),'json'),'baseline_xml':(base.encode(),'drawio'),'candidate_xml':(xml.encode(),'drawio'),'candidate_png':(rendered['png'],'png')}
  for key,(blob,ext) in payloads.items():p=dest/(key+'.'+ext);save(p,blob);files[key]=entry(p)
  font_records=[]
  for f in c['fonts'].values():
   blob=Path(f['file']).read_bytes();require(sha(blob)==f['sha256'],'font_changed');p=dest/(f['family']+'.otf');save(p,blob);font_records.append({'family':f['family'],'file':str(p.relative_to(R)),'sha256':f['sha256'],'original_PDF_font_sha256':f['source_font_sha256']})
  text_ids=[o['id'] for o in c['dom']['objects'] if o['type']=='text' and o.get('text','').strip()];cells=list(ET.fromstring(xml).iter('mxCell'));vertices={x.get('id') for x in cells if x.get('vertex')=='1'};edges=[x for x in cells if x.get('edge')=='1'];proof={'policy':config['policy'],'pins':config['pins'],'files':files,'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'candidate_code_sha256':sha(xml.encode()),'required_text_cell_ids':text_ids,'frame':c['frame'],'source_reference_reproduced':bool(reproduction['ok']),'native_canvas_qualified':native_canvas_ok,'edge_roles':stats['binding']['binding']['bound_edges'],'typed_free_paths':c['sidecar']['graph']['typed_free_paths'],'closed_source_paint':c['sidecar']['graph']['closed_source_paint']}
  candidate={k:source[k] for k in ('source','category')};candidate.update(id=source['pair_sha256'],source_pair_sha256=source['pair_sha256'],source_format='tikz',source_record=source,format='drawio',source_code_sha256=sha(code),source_image_sha256=sha(reference),code_file=files['candidate_xml']['file'],code_sha256=sha(xml.encode()),image_file=files['candidate_png']['file'],image_sha256=sha(rendered['png']),original_source_code=files['original_source']['file'],original_reference=files['original_reference']['file'],source_render_pdf=files['source_pdf']['file'],source_render_pdf_sha256=files['source_pdf']['sha256'],source_render_svg=files['source_svg']['file'],source_render_svg_sha256=files['source_svg']['sha256'],source_render_png=files['source_png']['file'],source_render_png_sha256=files['source_png']['sha256'],native_embedded_fonts=font_records,vertices=len(vertices),edges=len(edges),bound_edges=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),free_edges=sum(not e.get('source') or not e.get('target') for e in edges),conversion_method=VERSION,model=None,model_calls=0,accepted=False,render=rendered['native_render'],quality_state='pending_independent_typed_source_native_font_render_editing_quality',candidate_quality_adapter={'file':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).read_bytes()),'policy':config['policy']},**{FIELD:proof})
  save(dest/'record.json',raw(candidate));out.update(ok=True,record=candidate,record_file=str(dest/'record.json'),reason='native_candidate_pending_independent_full_quality',stats={'nodes':len(c['sidecar']['graph']['nodes']),'edges':len(edges),'free_edges':candidate['free_edges']})
 except Exception as e:out.update(reason=str(e).split(':',1)[0],detail=str(e)[:3000],stage=stage,error_type=type(e).__name__)
 if work.is_dir():save(work/'result.json',raw(out))
 return out

def validate_source(record,xml):
 result={'profile':VERSION,'supported':False,'ok':False,'failures':[],'evidence':{}}
 try:
  p=record[FIELD];config=configuration();require(p['policy']==config['policy'] and p['pins']==config['pins'],'source_implementation_changed');require(sha(xml.encode())==record['code_sha256']==p['candidate_code_sha256'],'candidate_revision_changed')
  for f in p['files'].values():checked(f)
  source,code,reference=inputs(record);require((sha(code),sha(reference))==(p['source_code_sha256'],p['source_image_sha256']),'source_revision_changed')
  fresh=capture_source(code,reference,W/VERSION/'validation'/record['id']/uuid.uuid4().hex);require(fresh['projected_svg']==checked(p['files']['source_svg']),'fresh_original_source_projection_changed');require(fresh['png']==checked(p['files']['source_png']),'fresh_original_source_pixels_changed');require(raw(fresh['dom'])==checked(p['files']['source_dom']),'fresh_source_DOM_changed')
  from PIL import Image
  width,height=Image.open(io.BytesIO(reference)).size;rebuilt,base,stats=emit(fresh,width,height);require(ET.canonicalize(rebuilt)==ET.canonicalize(xml),'fresh_source_geometry_text_marker_or_endpoint_changed');require(sha(base.encode())==p['files']['baseline_xml']['sha256'],'fresh_full_source_baseline_changed')
  for f in record['native_embedded_fonts']:checked({'file':f['file'],'sha256':f['sha256']})
  result.update(supported=True,ok=True,evidence={'complete_source_coverage':True,'required_text_cell_ids':p['required_text_cell_ids'],'candidate_code_sha256':record['code_sha256'],'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'named_and_free_endpoints_distinguished':True,'edge_roles':p['edge_roles'],'typed_free_paths':p['typed_free_paths'],'closed_source_paint':p['closed_source_paint'],'source_reference_reproduced':p['source_reference_reproduced'],'fixed_full_source_frame':p['frame']})
 except Exception as e:result['failures']=[{'reason':str(e).split(':',1)[0],'detail':str(e)[:2000]}]
 return result

def check_source(record,xml,source,data_root,native_info=None):
 require(Path(data_root).resolve()==R,'requires_HKUST_root');require(sha(source.encode())==record['source_code_sha256'],'source_argument_changed');return validate_source(record,xml)

def source_reproduction(record,work):
 try:
  source,code,ref=inputs(record);return source_visual(ref,capture_source(code,ref,work))
 except Exception as e:return {'supported':False,'ok':False,'reason':str(e).split(':',1)[0],'detail':str(e)[:1500]}

EDIT_JS=r'''async xml=>{document.body.innerHTML='<div id="g" style="width:8192px;height:8192px"></div>';const g=new Graph(document.getElementById('g'));new mxCodec(mxUtils.parseXml(xml)).decode(mxUtils.parseXml(xml).getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;const req=(b,m)=>{if(!b)throw Error(m)},near=(a,b)=>Math.abs(a-b)<.05;const encode=()=>mxUtils.getXml(new mxCodec().encode(g.model));const originalXML=encode(),observations=[];const ss=e=>{let s=g.view.getState(e);return {points:s.absolutePoints.map(p=>[p.x,p.y]),paint:s.shape.node.innerHTML}};for(const edge of Object.values(g.model.cells).filter(c=>c.edge)){for(const source of [true,false]){const term=g.model.getTerminal(edge,source),key=source?'sourcePoint':'targetPoint',cell=term||edge;const old=cell.geometry.clone(),z=old.clone(),before=ss(edge);if(term){z.x+=17;z.y+=11}else{req(z[key],'missing source explicit free endpoint');z[key]=new mxPoint(z[key].x+17,z[key].y+11)}g.model.setGeometry(cell,z);g.view.validate();const after=ss(edge),index=source?0:before.points.length-1;req(near(after.points[index][0]-before.points[index][0],17)&&near(after.points[index][1]-before.points[index][1],11),'actual endpoint did not follow its source role');req(after.paint!==before.paint,'native shaft/marker paint did not respond');g.model.setGeometry(cell,old);g.view.validate();req(encode()===originalXML&&JSON.stringify(ss(edge))===JSON.stringify(before),'native endpoint edit did not restore');observations.push({edge:edge.id,side:source?'source':'target',kind:term?'executed_named_terminal':'explicit_source_coordinate_endpoint',actual_endpoint_followed:true,actual_native_paint_changed:true,restored:true})}}g.destroy();return {ok:true,endpoint_moves:observations.length,moves:observations,native_graph_model_restored:true}}'''
def audit_editing(record,xml,source_profile,data_root):
 require(source_profile.get('ok') and source_profile['evidence']['candidate_code_sha256']==sha(xml.encode()),'source_profile_required')
 from playwright.sync_api import sync_playwright
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   page=browser.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(R/'evaluation/assets/viewer-static.min.js'));result=page.evaluate(EDIT_JS,xml)
  finally:browser.close()
 require(result['endpoint_moves']==2*record['edges'],'incomplete_actual_endpoint_interventions');return result
