"""Original TikZ compiler using physical pdfLaTeX2025/Poppler100dpi source paint.

No model/canonical-DB/queue writes. Every source paint and Unicode text object
is retained. Named terminals bind to source nodes; numeric terminals retain
explicit mxGeometry endpoints. Source PDF units and actual native SVG offsets
determine lowering; complete native paint is retained in an explicit external export viewport.
"""
from __future__ import annotations
import collections,copy,hashlib,io,json,math,sys,uuid,xml.etree.ElementTree as ET
from pathlib import Path
from compiler_language_capture_v1 import screenshot
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='priority_datikz_source_viewport_v1';FIELD='compiler_tikz_source_viewport_v1'
UNITS={'tikz':'pdfLaTeX2025_Poppler100dpi_fixed_inspection_native_v1'}
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
DEPENDENCIES=('compiler_language_capture_v1.py','priority_datikz_source_viewport_v1.py','priority_datikz_source_replay_quality_v2.py','tikz_execution_binding_v3.py','tikz_execution_binding.py','tikz_execution_graph.py','tikz_execution_graph_hooks.tex','tikz_literal_graph.py','tikz_literal_connectivity.py','tikz_connectivity.py','tectonic_compile.py','sandbox_runner.py','pdf_to_native.py','pdf_fonts.py','svg_dom_pdf_v2.js','svg_convert_v2.py','svg_convert_v3.py','tikz_execution_marker_paint_fit.py','tikz_execution_binding_v2.py','tikz_execution_marker_quality.py','auto_quality_common_v4.py','strict_canvas_gate.py','compiler_languages_source_layout_v1.py')
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
 from priority_datikz_tex_execution_v1 import runtime_configuration
 runtime=runtime_configuration();names=DEPENDENCIES+('priority_datikz_tex_execution_v1.py','pdf_fonts_pdftex_v1.py','pdf_to_native_pdftex_v1.py','tikz_pdf_glyph_layout_v1.py','compiler_scene_text_v2.py','tikz_native_export_frame_v1.py','native_page_padding.py','native_padding_proof.py','tikz_export_frame_editing_v1.py','tikz_export_frame_editing_v1.js','native_svg_screen_offset_v2.py','portable_native_fonts.py','auto_quality_source_vector_v2.py')
 pins={str(W/'scripts'/n):sha((W/'scripts'/n).read_bytes()) for n in names};pins.update(runtime['pins'])
 from pdf_fonts_pdftex_v1 import TX_ROOT
 for p in (TX_ROOT/'tx',TX_ROOT/'receipt.json'):pins[str(p)]=sha(p.read_bytes())
 for p in (Path(CHROME),W/'rendering_tikz_pdf100_v1/remote_render.py',W/'rendering_tikz_pdf100_padding_v1/remote_render.py',W/'rendering_tikz_export_view_v2/remote_render.py',W/'rendering_tikz_export_view_v2/assets/viewer-static.min.js',W/'rendering_tikz_pdf100_v1/assets/viewer-static.min.js',W/'rendering_tikz_pdf100_padding_v1/assets/viewer-static.min.js',R/'evaluation/assets/viewer-static.min.js',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'):
  pins[str(p)]=sha(p.read_bytes())
 return {'policy':VERSION+':'+sha(raw(pins))[:20],'pins':pins,'source_requires_native_info':False,'source_runtime':runtime,'units':{'tikz':'pdfLaTeX2025_Poppler100dpi_fixed_inspection_native_v1'},'model_calls':0}

def inputs(record,job=None):
 from compiler_languages_source_layout_v1 import _inputs
 return _inputs(record,job)

def static_support(record):
 try:
  source,code,ref=inputs(record);require(source['format']=='tikz','requires_tikz');require(len(code)<=250000,'source_resource_bound')
  require(source['source'] in {'nllg--DaTikZ-V4','nllg--datikz-v3','nllg--datikz'} and source.get('source_image_origin')=='fresh_release_exact_source_private_TeXLive2025_Poppler100dpi','requires_explicit_DaTikZ_current_runtime_source_replay_reference')
  from priority_datikz_tex_execution_v1 import density
  density(ref)
  from PIL import Image
  w,h=Image.open(io.BytesIO(ref)).size;require(max(w,h)<=8192 and w*h<=64000000,'source_canvas_resource_bound')
  return {'supported':True,'unit':'pdfLaTeX2025_Poppler100dpi_fixed_inspection_native_v1','scope':'Static resource eligibility only; actual source execution/coverage/fidelity remain mandatory.'}
 except Exception as e:return {'supported':False,'reasons':[str(e)]}

def capture_source(code,reference,work):
 from priority_datikz_tex_execution_v1 import compile_execution_graph,density
 from tikz_execution_graph import parse_events
 from tikz_execution_binding_v3 import graph_from_events
 from pdf_to_native_pdftex_v1 import source_svg
 from tikz_pdf_glyph_layout_v1 import source_positions
 from priority_datikz_tex_execution_v1 import actual_pdf_text_positions
 from PIL import Image
 from playwright.sync_api import sync_playwright
 from auto_quality_common_v4 import image_quality
 work=Path(work);work.mkdir(parents=True,exist_ok=False);dpi=density(reference)
 sidecar=compile_execution_graph(code,work/'execution',dpi)
 require(set(sidecar['runs'])=={'baseline','instrumented'} and all(x['returncode']==0 for x in sidecar['runs'].values()),'original_source_compile_failed:'+str(sidecar.get('error')))
 require(sidecar.get('source_bytes_unchanged') is True and sidecar.get('instrumentation_pdf_pixel_equivalence') and all(x['pixel_identical'] for x in sidecar['instrumentation_pdf_pixel_equivalence']),'source_instrumentation_changed_actual_PDF_pixels')
 events=parse_events((work/'execution/instrumented/source.iic').read_text());graph=graph_from_events(events)
 require(graph['ok'],'typed_source_trace_unsupported:'+json.dumps(graph['failures'])[:2000])
 sidecar={**sidecar,'legacy_graph':sidecar['graph'],'graph':graph,'ok':True};sys.path.append(str(W/'runtime/python_packages'));import pymupdf
 pdf=work/'execution/baseline/source.pdf';actual_png=(work/'execution/baseline/actual_Poppler100dpi/source.png').read_bytes();width,height=Image.open(io.BytesIO(actual_png)).size
 require(max(width,height)<=8192 and width*height<=64000000,'actual_source_canvas_resource_bound')
 with pymupdf.open(pdf) as doc:
  require(len(doc)==1 and doc[0].rotation==0,'requires_single_unrotated_source_page');page=doc[0]
  svg,fonts,pdfstats=source_svg(doc,page,work);require(not pdfstats['issues'],'PDF_source_feature_unsupported:'+json.dumps(pdfstats['issues'])[:1000])
  drawings=page.get_drawings(extended=True);traces=page.get_texttrace();bboxlog=page.get_bboxlog();display_counts=collections.Counter(x[0] for x in bboxlog)
  # A single PDF text display-list operation may expose several font/style
  # traces. Account the original paint-operation sequence, then every glyph.
  text_operations={t['seqno'] for t in traces if t['type']==0}
  require(text_operations=={n for n,item in enumerate(bboxlog) if item[0]=='fill-text'},'actual_PDF_text_display_list_operation_coverage_differs')
  expected=collections.Counter({'fill-path':sum(x['type'] in ('f','fs') for x in drawings),'stroke-path':sum(x['type'] in ('s','fs') for x in drawings),'fill-text':len(text_operations)})
  expected=+expected;require(display_counts==expected,'actual_PDF_display_list_contains_unaccounted_paint:'+json.dumps({'actual':display_counts,'accounted':expected}))
  pdf_xml=ET.fromstring(svg);paths=[x for x in pdf_xml if x.tag.endswith('path')];texts=[x for x in pdf_xml if x.tag.endswith('text')]
  require(len(paths)==len(drawings) and len(texts)==pdfstats['native_text_runs'],'actual_PDF_display_list_source_scene_bijection_failed')
  page_pt=list(page.rect);text_positions=actual_pdf_text_positions(page,dpi/72)
  for fontname,font in fonts.items():
   actual=collections.Counter(gid for t in traces if t['font']==fontname and t['type']!=3 for unicode,gid,origin,bbox in t['chars'] if gid>=0)
   require(dict(actual)==font['source_glyph_uses'],'actual_PDF_glyph_use_inventory_not_bijective:'+fontname)
  display_proof={'actual_display_list_counts':dict(display_counts),'actual_path_count':len(drawings),'actual_text_trace_count':len(traces),'actual_glyph_count':sum(len(t['chars']) for t in traces if t['type']!=3),'actual_source_scene_text_runs':len(texts),'actual_source_scene_paths':len(paths),'actual_display_list_sha256':sha(raw(bboxlog)),'page_pt':page_pt,'complete_actual_PDF_paint_inventory':True,'actual_source_font_glyph_identity_count':sum(len(f['source_glyph_identities']) for f in fonts.values())}
 # An integer device canvas and an explicit physical-unit group avoid CSS
 # viewport 1/64px quantization and implicit xMidYMid fitting. One fixed scale
 # applies to every original PDF object, with no reference geometry fitting.
 require(svg.startswith('<svg ') and svg.endswith('</svg>'),'actual_PDF_source_SVG_root_changed')
 body=svg[svg.index('>')+1:svg.rfind('</svg>')]
 physical_svg='<svg xmlns="http://www.w3.org/2000/svg" width="'+str(width)+'" height="'+str(height)+'" viewBox="0 0 '+str(width)+' '+str(height)+'"><g data-tikz-physical-pdf-frame="1" transform="scale('+str(dpi/72)+')">'+body+'</g></svg>'
 require([ET.canonicalize(ET.tostring(x,encoding='unicode')) for x in ET.fromstring(svg)]==[ET.canonicalize(ET.tostring(x,encoding='unicode')) for x in ET.fromstring(physical_svg)[0]],'physical_unit_wrapper_changed_original_PDF_objects')
 blocked=[]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text'])
  try:
   context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=context.new_page()
   page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+physical_svg);page.evaluate('document.fonts.ready')
   svg_png=screenshot(page);projected=page.locator('svg').evaluate('s=>s.outerHTML').encode();dom=page.evaluate((W/'scripts/svg_dom_pdf_v2.js').read_text());matrix=page.evaluate('()=>{const m=document.querySelector("g[data-tikz-physical-pdf-frame]").getScreenCTM();return [m.a,m.b,m.c,m.d,m.e,m.f]}')
   require(max(abs(a-b) for a,b in zip(matrix,[dpi/72,0,0,dpi/72,0,0]))<.00001,'source_physical_PDF_unit_projection_changed')
   glyph_positions=source_positions(page,dom);require(screenshot(page)==svg_png,'source_extraction_changed_pixels');require(not blocked,'source_external_resources');require(not dom.get('issues'),'source_DOM_feature_unsupported:'+json.dumps(dom['issues'])[:1200])
  finally:browser.close()
 svg_quality=image_quality(actual_png,svg_png,{},text_positions)
 frame={'policy':'DaTikZ_current_pinned_pdfLaTeX2025_actual_PDF_100dpi_source_replay_units_v1','source_viewBox':page_pt,'reference_viewport':[width,height],'scale':dpi/72,'translation':[0,0],'canvas_from_actual_Poppler':True,'PNG_density_is_profile_clue_only':True,'original_reference_canvas':list(Image.open(io.BytesIO(reference)).size),'crop':False,'parameter_search':False,'individual_object_changes':False}
 save(work/'source.svg',projected);save(work/'source.png',actual_png);save(work/'source_svg_reconstruction.png',svg_png);save(work/'source_dom.json',raw(dom));save(work/'actual_PDF_display_list_proof.json',raw(display_proof));save(work/'actual_PDF_to_source_SVG_quality.json',raw(svg_quality));save(work/'source_glyph_positions.json',raw(glyph_positions));save(work/'typed_execution.json',raw(sidecar))
 return {'svg':svg.encode(),'projected_svg':projected,'png':actual_png,'svg_png':svg_png,'fonts':fonts,'pdfstats':pdfstats,'dom':dom,'matrix':matrix,'sidecar':sidecar,'events':events,'frame':frame,'pdf':pdf.read_bytes(),'canvas':[width,height],'work':str(work),'actual_PDF_display_list_proof':display_proof,'actual_PDF_to_SVG_quality':svg_quality,'source_glyph_positions':glyph_positions}

def emit(capture,width,height):
 from svg_convert_v2 import build
 from pdf_to_native import attach_fonts
 from tikz_execution_binding_v3 import bind_execution
 xml,stats=build(capture['dom'],width,height);base=attach_fonts(xml,capture['fonts'])
 xml,binding=bind_execution(base,capture['dom'],capture['sidecar'],capture['events'],capture['matrix'])
 require(binding['complete'],'source_binding_incomplete:'+json.dumps(binding['issues'])[:2000])
 xml,fit=fit_markers(xml,capture['dom'],binding)
 from native_svg_screen_offset_v2 import observe,transform,verify_translation
 native_frame=observe(xml);changed=transform(xml,native_frame,-1);native_frame['actual_translation_proof']=verify_translation(xml,changed,native_frame,-1);xml=changed
 from native_worker import native
 from tikz_pdf_glyph_layout_v1 import correct
 rendered=native.native_job(xml,width,height,180,W/'rendering_tikz_pdf100_v1/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
 require(rendered.get('ok'),'initial_native_glyph_observation_failed')
 xml,corrections=correct(xml,capture['source_glyph_positions'],rendered['native_render'])
 from tikz_native_export_frame_v1 import produce
 xml,padding,assets=produce(xml,width,height,Path(capture['work'])/'native_page_preservation')
 capture['padding_assets']=assets
 return xml,base,{'converter':stats,'binding':binding,'marker_fit':fit,'glyph_anchor_corrections':corrections,'actual_PDF_display_list':capture['actual_PDF_display_list_proof'],'actual_PDF_to_SVG_quality':capture['actual_PDF_to_SVG_quality'],'native_padding':padding,'native_screen_offset_proof':native_frame}

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
 from PIL import Image
 if Image.open(io.BytesIO(reference)).size!=tuple(capture['canvas']):
  return {'supported':True,'ok':False,'reason':'actual_original_PDF_canvas_differs_from_reference','fixed_projection':capture['frame'],'no_reference_resizing_or_fitting':True}
 positions=[{'cell':k,'runs':[{'chars':row['chars']}]} for k,row in capture['source_glyph_positions'].items()]
 q=image_quality(reference,capture['png'],{},positions)
 return {'supported':True,'ok':q['ok'],'reason':'source_reference_reproduced' if q['ok'] else 'source_reference_mismatch','visual':q,'fixed_projection':capture['frame']}

def convert(record,job,work):
 out={'ok':False,'qualified':False,'model_calls':0};stage='input';work=Path(work)
 try:
  require(work.resolve().is_relative_to(W/VERSION),'unowned_work');work.mkdir(parents=True,exist_ok=False);source,code,reference=inputs(record,job);require(source['format']=='tikz','requires_tikz');config=configuration();stage='source_execution';c=capture_source(code,reference,work/'source');reproduction=source_visual(reference,c);out['source_reproduction']=reproduction
  from PIL import Image
  width,height=c['canvas'];stage='native_emission';xml,base,stats=emit(c,width,height);from tikz_native_export_frame_v1 import dimensions; width,height=dimensions(xml)
  from native_worker import native
  from strict_canvas_gate import require_declared_page
  rendered=native.native_job(xml,width,height,180,W/'rendering_tikz_export_view_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(rendered['ok'],'native_render_failed:'+str({k:v for k,v in rendered.items() if k!='png'})[:1200]);save(work/'native_render.json',raw({k:v for k,v in rendered.items() if k!='png'}));save(work/'native.png',rendered['png'])
  # A generated complete native candidate can still fail the page/alignment
  # qualification gate; retain it for generic repair instead of hiding codegen.
  try:require(rendered['native_render']['strict_outside_export_pixels']==rendered['native_render']['strict_outside_inspection_pixels']==0,'paint_outside_export');native_canvas_ok=True
  except AssertionError:native_canvas_ok=False
  dest=R/'clean'/VERSION/source['pair_sha256'][:2]/source['pair_sha256']/uuid.uuid4().hex;dest.mkdir(parents=True);files={}
  payloads={'original_source':(code,'tex'),'original_reference':(reference,'png'),'source_pdf':(c['pdf'],'pdf'),'source_svg':(c['projected_svg'],'svg'),'source_png':(c['png'],'png'),'source_dom':(raw(c['dom']),'json'),'source_trace':((work/'source/execution/instrumented/source.iic').read_bytes(),'iic'),'source_execution':(raw(c['sidecar']),'json'),'source_frame':(raw(c['frame']),'json'),'source_stats':(raw(stats),'json'),'source_glyph_positions':(raw(c['source_glyph_positions']),'json'),'actual_PDF_display_list_proof':(raw(c['actual_PDF_display_list_proof']),'json'),'actual_PDF_to_SVG_quality':(raw(c['actual_PDF_to_SVG_quality']),'json'),'baseline_xml':(base.encode(),'drawio'),'candidate_xml':(xml.encode(),'drawio'),'candidate_png':(rendered['png'],'png')}
  payloads.update(c['padding_assets'])
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
  fresh=capture_source(code,reference,W/VERSION/'validation'/record['id']/uuid.uuid4().hex);require(fresh['projected_svg']==checked(p['files']['source_svg']),'fresh_original_source_projection_changed');require(fresh['png']==checked(p['files']['source_png']),'fresh_original_source_pixels_changed');require(raw(fresh['dom'])==checked(p['files']['source_dom']),'fresh_source_DOM_changed');require(raw(fresh['source_glyph_positions'])==checked(p['files']['source_glyph_positions']),'fresh_actual_PDF_glyph_positions_changed');require(raw(fresh['actual_PDF_display_list_proof'])==checked(p['files']['actual_PDF_display_list_proof']),'fresh_actual_PDF_paint_inventory_changed');require(fresh['actual_PDF_to_SVG_quality']['ok'],'actual_original_PDF_to_source_SVG_raster_anomaly');require(source_visual(reference,fresh)['ok'],'actual_original_PDF_reference_not_reproduced')
  from PIL import Image
  width,height=fresh['canvas'];rebuilt,base,stats=emit(fresh,width,height);require(ET.canonicalize(rebuilt)==ET.canonicalize(xml),'fresh_source_geometry_text_marker_or_endpoint_changed');require(sha(base.encode())==p['files']['baseline_xml']['sha256'],'fresh_full_source_baseline_changed')
  for f in record['native_embedded_fonts']:checked({'file':f['file'],'sha256':f['sha256']})
  result.update(supported=True,ok=True,evidence={'complete_source_coverage':True,'required_text_cell_ids':p['required_text_cell_ids'],'candidate_code_sha256':record['code_sha256'],'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'named_and_free_endpoints_distinguished':True,'edge_roles':p['edge_roles'],'typed_free_paths':p['typed_free_paths'],'closed_source_paint':p['closed_source_paint'],'source_reference_reproduced':p['source_reference_reproduced'],'fixed_full_source_frame':p['frame'],'actual_original_PDF_paint_inventory':fresh['actual_PDF_display_list_proof'],'native_padding':stats['native_padding']})
 except Exception as e:result['failures']=[{'reason':str(e).split(':',1)[0],'detail':str(e)[:2000]}]
 return result

def check_source(record,xml,source,data_root,native_info=None):
 require(Path(data_root).resolve()==R,'requires_HKUST_root');require(sha(source.encode())==record['source_code_sha256'],'source_argument_changed');
 result=validate_source(record,xml)
 if result['ok'] and native_info is not None:
  try:
   from tikz_pdf_glyph_layout_v1 import validate
   expected=json.loads(checked(record[FIELD]['files']['source_glyph_positions']));plan=result['evidence']['native_padding']['plan']
   for row in expected.values():
    for char in row['chars']:char['x']+=plan['dx'];char['y']+=plan['dy']
   result['evidence']['actual_native_PDF_source_glyphs']=validate(expected,native_info)
  except Exception as error:result.update(ok=False,failures=[{'reason':'actual_native_PDF_source_glyphs_failed','detail':str(error)}])
 return result

def source_reproduction(record,work):
 try:
  source,code,ref=inputs(record);return source_visual(ref,capture_source(code,ref,work))
 except Exception as e:return {'supported':False,'ok':False,'reason':str(e).split(':',1)[0],'detail':str(e)[:1500]}

EDIT_JS=r'''async xml=>{document.body.innerHTML='<div id="g" style="width:8192px;height:8192px"></div>';const g=new Graph(document.getElementById('g'));new mxCodec(mxUtils.parseXml(xml)).decode(mxUtils.parseXml(xml).getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;const req=(b,m)=>{if(!b)throw Error(m)},near=(a,b)=>Math.abs(a-b)<.05;const encode=()=>mxUtils.getXml(new mxCodec().encode(g.model));const originalXML=encode(),observations=[];const ss=e=>{let s=g.view.getState(e);return {points:s.absolutePoints.map(p=>[p.x,p.y]),paint:s.shape.node.innerHTML}};for(const edge of Object.values(g.model.cells).filter(c=>c.edge)){for(const source of [true,false]){const term=g.model.getTerminal(edge,source),key=source?'sourcePoint':'targetPoint',cell=term||edge;const old=cell.geometry.clone(),z=old.clone(),before=ss(edge);if(term){z.x+=17;z.y+=11}else{req(z[key],'missing source explicit free endpoint');z[key]=new mxPoint(z[key].x+17,z[key].y+11)}g.model.setGeometry(cell,z);g.view.validate();const after=ss(edge),index=source?0:before.points.length-1;req(near(after.points[index][0]-before.points[index][0],17)&&near(after.points[index][1]-before.points[index][1],11),'actual endpoint did not follow its source role');req(after.paint!==before.paint,'native shaft/marker paint did not respond');g.model.setGeometry(cell,old);g.view.validate();req(encode()===originalXML&&JSON.stringify(ss(edge))===JSON.stringify(before),'native endpoint edit did not restore');observations.push({edge:edge.id,side:source?'source':'target',kind:term?'executed_named_terminal':'explicit_source_coordinate_endpoint',actual_endpoint_followed:true,actual_native_paint_changed:true,restored:true})}}g.destroy();return {ok:true,endpoint_moves:observations.length,moves:observations,native_graph_model_restored:true}}'''
def audit_editing(record,xml,source_profile,data_root):
 from tikz_export_frame_editing_v1 import audit
 return audit(xml,record=record,source_profile=source_profile)


def registration_record(record,reference,xml,data_root):
 from tikz_native_export_frame_v1 import registration
 return registration(record,reference,xml,data_root)
