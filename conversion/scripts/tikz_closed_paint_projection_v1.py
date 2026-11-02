"""One declared full-page SVG meet projection; independent, nonpublishing RO QA.

The projection comes from PDF viewBox and bound reference header alone, never
image differences or guessed DPI. Production QA/profile/records stay untouched.
"""
from __future__ import annotations
import copy,hashlib,io,json,math,sys,xml.etree.ElementTree as E
from pathlib import Path

POLICY='original_tikz_PDF_closed_paint_single_meet_projection_RO_QA_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
canonical=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
for _path in (Path(__file__).resolve().parent.parent/'prototype',Path(__file__).resolve().parent.parent/'runtime/python_packages'):
 if _path.is_dir() and str(_path) not in sys.path:sys.path.append(str(_path))
LOADED_SHA256=sha(Path(__file__).read_bytes())
BRIDGE_SHA256='dcbac80faed854c3636341d7fa2de81f9b4f0f7ccef7ff739f821462fadffbfa'
BRIDGE_JS_SHA256='ebd11e0ae336d523aece1590e5849e7d9f4d63feb73edc2893da6d414c8553cd'

def require(ok,why):
 if not ok:raise ValueError(why)

def meet_frame(viewbox,viewport):
 require(len(viewbox)==4 and len(viewport)==2 and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in list(viewbox)+list(viewport)),'nonfinite/invalid page frame')
 x,y,w,h=viewbox;W,H=viewport;require(w>0 and h>0 and W>0 and H>0 and int(W)==W and int(H)==H,'invalid complete PDF/ref dimensions');s=min(W/w,H/h);dx=(W-w*s)/2-x*s;dy=(H-h*s)/2-y*s
 return {'policy':'complete_viewBox_to_reference_header_xMidYMid_meet','viewBox':list(viewbox),'reference_viewport':list(viewport),'scale':s,'translate':[dx,dy],'matrix':[s,0,0,s,dx,dy],'preserveAspectRatio':'xMidYMid meet','clip_source_objects':False,'pixel_fitting_used':False,'provider_DPI_recovered':False}

def project_svg(svg,viewport):
 E.register_namespace('','http://www.w3.org/2000/svg');root=E.fromstring(svg);require(root.tag.endswith('svg'),'missing original PDF SVG root');viewbox=[float(x) for x in root.get('viewBox','').split()];frame=meet_frame(viewbox,viewport);root.set('width',str(viewport[0]));root.set('height',str(viewport[1]));root.set('preserveAspectRatio','xMidYMid meet')
 return E.tostring(root,encoding='unicode'),frame

def check_dom_frame(dom,frame):
 errors=[];s=frame['scale'];expected=frame['matrix']
 for obj in dom['objects']:
  m=obj['matrix'];error=max(abs(a-b) for a,b in zip(m,expected))
  # Fresh source text extractor can bake its rotation/scaled-font metric origin;
  # all original PDF text here is horizontal and source text has no transforms.
  if obj['type']=='shape' and error>.003:errors.append({'id':obj['id'],'reason':'derived_source_shape_frame_differs','matrix':m,'expected':expected})
  box=obj['bbox'];W,H=frame['reference_viewport']
  if min(box['x'],box['y'])<-.03 or box['x']+box['w']>W+.03 or box['y']+box['h']>H+.03:errors.append({'id':obj['id'],'reason':'projected_source_object_outside_full_viewport','bbox':box})
 return {'ok':not errors,'errors':errors,'object_count':len(dom['objects']),'source_object_crop_performed':False,'formula':frame}

def pins(config):
 import tikz_source_only_failure_v1 as source
 source.pins_ok(config);here=Path(__file__).parent
 require(sha(Path(__file__).read_bytes())==LOADED_SHA256,'projection module changed after import');require(sha((here/'tikz_closed_paint_bridge_v1.py').read_bytes())==BRIDGE_SHA256,'unreviewed bridge module');require(sha((here/'tikz_closed_paint_bridge_v1.js').read_bytes())==BRIDGE_JS_SHA256,'unreviewed native intervention script')


def check_source_profile(record,xml,*,dom,roles,frame,physical_fonts,source_identity):
 """Pure source/object/font/frame proof for this separately verified provenance."""
 import tikz_closed_paint_bridge_v1 as bridge
 from auto_quality_source_vector_v2 import _paint_coverage,_graphviz_coverage
 from auto_quality_svg_closed_scene_v1 import _native_integrity
 result={'profile':POLICY,'supported':False,'ok':False,'failures':[],'evidence':{}}
 try:
  require(record['source_format']=='tikz' and record['id']==record['source_pair_sha256']==source_identity['id'],'source identity/format differs');require(record['code_sha256']==sha(xml.encode()),'candidate code hash differs');require(record['source_code_sha256']==source_identity['source_code_sha256'] and record['source_image_sha256']==source_identity['source_image_sha256'],'original source hashes differ');require(roles['ok'] and roles['all_source_and_PDF_paint_accounted'],'incomplete original PGF/PDF paint role proof');require(all(x['role']=='source_explicit_closed_basic_paint' for x in roles['objects']),'numeric arrows require the separate failed marker profile');require(physical_fonts['ok'],'physical source PDF font proof incomplete');require(not dom.get('issues'),'derived source DOM has unhandled features');require(not dom.get('nodes') and all(not o.get('edge') and not o.get('markerOwner') for o in dom['objects']),'closed source gate cannot waive graph relationships')
  source_ids={o.get('sourceId'):o for o in dom['objects']};basic=[]
  for role in roles['objects']:
   obj=source_ids['pdfpath'+str(role['pdf_objects'][0])];basic.append({'id':obj['id'],**bridge.closed_basic(obj,role['source'])})
  shapes=[o for o in dom['objects'] if o['type']=='shape'];require(len(shapes)==len(basic),'unknown source paint role in derived SVG');require(all(o['type'] in ('shape','text') for o in dom['objects']),'unexpanded/raster source asset')
  coverage=_paint_coverage(dom,xml);inventory=_graphviz_coverage(dom,xml,{});integrity=_native_integrity(dom,xml);bounds=check_dom_frame(dom,frame);require(all(abs(coverage['source_layout_translation'][k])<=.03 for k in ('dx','dy')),'candidate moved relative to declared projection');cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};families={x['family'] for x in physical_fonts['fonts']};text_faces=[]
  for obj in dom['objects']:
   if obj['type']!='text':continue
   st=dict(x.split('=',1) for x in cells[obj['id']].get('style','').split(';') if '=' in x);family=obj['fontFamily'].split(',')[0].strip('"\'');require(st.get('fontFamily')==family and family in families,'native source font family is not the proved original PDF font');text_faces.append({'id':obj['id'],'family':family,'text':obj['text']})
  errors=coverage['errors']+inventory['errors']+integrity['errors']+bounds['errors'];result.update(supported=True,ok=not errors,failures=errors);result['evidence']={'source_identity':source_identity,'declared_projection':frame,'complete_derived_source_object_and_text_inventory':inventory,'exact_original_PDF_path_native_paint_mapping':coverage,'native_visibility_transform_and_paint_order':integrity,'full_original_source_frame':bounds,'closed_PGF_roles':basic,'physical_source_fonts':physical_fonts,'actual_expected_native_text_faces':text_faces,'source_code_unchanged':True,'native_graph_edges_invented':False,'fresh_DOM_sha256':sha(canonical(dom)),'candidate_code_sha256':sha(xml.encode()),'source_format_relabelled':False,'provider_DPI_claim':False}
 except Exception as exc:result['failures'].append({'reason':'unproved_closed_paint_projection_source_profile','error':repr(exc)})
 return result

def prepare(db,identifier,bridge_report,config,work):
 import tikz_source_only_failure_v1 as source
 import tikz_closed_paint_bridge_v1 as bridge
 import svg_failure_closure_v1 as shared
 from tikz_execution_graph import parse_events,graph_from_events
 from pdf_to_native import source_svg,pathdata,rgb
 import pymupdf
 from PIL import Image
 root=Path(config['root']);work=Path(work).resolve();require(work.is_relative_to(root/'conversion/prototype/tikz_closed_paint_projection_v1'),'private projection prototype only');work.mkdir(parents=True,exist_ok=False);report={'id':identifier,'policy':POLICY,'accepted':False,'published':False,'models_called':0,'failures':[],'checks':{},'production_QA_modified':False,'projection_candidates_evaluated':1};files={}
 def save(name,value):
  p=work/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value if isinstance(value,bytes) else canonical(value));files[str(p)]=sha(p.read_bytes());return p
 try:
  require(not db.in_transaction,'RO autocommit connection required');pins(config);before=shared.snapshot(db,identifier);r=json.loads(Path(bridge_report).read_text());require(r['id']==identifier and r.get('bridge_source_role_supported') is True and r.get('source_code_sha256') and not any(x['role']!='source_explicit_closed_basic_paint' for x in r['source_role_proof']['objects']),'not a complete source-closed-paint case');body={k:v for k,v in r.items() if k!='report_sha256'};require(sha(bridge.canonical(body))==r['report_sha256'],'bridge report damaged');require(r.get('module_sha256')==BRIDGE_SHA256,'bridge proof module differs')
  for p,h in r['files'].items():require(sha(Path(p).read_bytes())==h,'original bridge artifact changed')
  src_report=json.loads(Path(r['source_only_evidence']).read_text());require(src_report['pins']==config['pins'],'source engine/route policy differs');require(sha(source.canonical({k:v for k,v in src_report.items() if k!='certificate_sha256'}))==src_report['certificate_sha256'],'source compile certificate damaged')
  for p,h in src_report['files'].items():require(sha(Path(p).read_bytes())==h,'original source/compile/runtime evidence changed')
  srcdir=Path(src_report['evidence_directory']);environment=json.loads((srcdir/'environment.json').read_text());require(source.environment_files(root)==environment['files'],'actual frozen source environment changed');original_record,manifest=db.execute('select input_record,input_manifest from jobs where id=?',(identifier,)).fetchone();original_record=json.loads(original_record);manifest=json.loads(manifest);require(db.execute('select status from processing_outcomes_v2 where id=?',(identifier,)).fetchone()[0]=='pending','not pending authoritative scope');require((original_record['code_sha256'],original_record['image_sha256'])==(r['source_code_sha256'],r['source_image_sha256'])==(manifest['code_sha256'],manifest['image_sha256']),'source revision changed')
  original=(root/manifest['source_code']).read_bytes();reference=(root/manifest['reference_image']).read_bytes();require((sha(original),sha(reference))==(r['source_code_sha256'],r['source_image_sha256']),'actual source/reference changed');require(source.source_context_guard(original.decode())['ok'],'original source context not closed');image=Image.open(io.BytesIO(reference));viewport=list(image.size);require(image.info=={},'new density metadata requires an explicit non-guessing review; this route does not use it');private=work/'resource_gate_private_root';clean=private/'clean';clean.mkdir(parents=True);(clean/'original_source.tex').write_bytes(original);(clean/'original_reference.png').write_bytes(reference)
  execution=srcdir/'execution';sidecar=json.loads((execution/'execution_graph.json').read_text());require(set(sidecar['runs'])=={'baseline','instrumented'} and all(x['returncode']==0 for x in sidecar['runs'].values()) and all(x['pixel_identical'] for x in sidecar['instrumentation_pdf_pixel_equivalence']),'source compilation equivalence incomplete');events=parse_events((execution/'instrumented/source.iic').read_text());require(graph_from_events(events)==sidecar['graph'],'fresh PGF trace replay differs');pdf=execution/'baseline/source.pdf';require(sha(pdf.read_bytes())==r['source_pdf_sha256'],'original source PDF differs');(clean/'original_source.pdf').write_bytes(pdf.read_bytes())
  with pymupdf.open(pdf) as doc:
   require(len(doc)==1 and doc[0].rotation==0 and doc[0].rect==doc[0].mediabox==doc[0].cropbox,'complete unrotated source PDF page only');page=doc[0];drawings=[]
   for i,d in enumerate(page.get_drawings(extended=True)):
    require(d['type'] not in ('clip','group'),'unknown PDF clip/compositing');drawings.append({'id':i,'seqno':d['seqno'],'parts':bridge.path_ops(pathdata(d)),'fill':rgb(d.get('fill')),'stroke':rgb(d.get('color')),'stroke_width':d.get('width') or 0})
   roles=bridge.source_roles(events,drawings);require(bridge.canonical(roles)==bridge.canonical(r['source_role_proof']),'source roles do not freshly replay');svg,fonts,stats=source_svg(doc,page,clean);require(not stats['issues'],'original PDF SVG converter has unknown semantics');require(sha(svg.encode())==r['source_derived_svg_sha256'],'fresh original PDF SVG differs');traces=__import__('pdf_fonts').build_fonts(doc,page,work/'font_recheck')[1];fontproof=bridge.font_proof(doc,page,fonts,traces)
  (clean/'original_PDF_derived.svg').write_text(svg);projected,frame=project_svg(svg,viewport);save('projection_contract.json',frame);(clean/'projected_source.svg').write_text(projected);dom=bridge.capture_svg(projected,work,*viewport);save('fresh_projection_source_DOM.json',dom);xml,candidate=bridge.native_candidate(dom,*viewport,fonts,roles);require(not candidate['axes'],'closed circle route must not process arrows');(clean/'candidate.drawio').write_text(xml)
  record={'id':identifier,'source_pair_sha256':identifier,'source_format':'tikz','source_code_sha256':r['source_code_sha256'],'source_image_sha256':r['source_image_sha256'],'code_file':'clean/candidate.drawio','code_sha256':sha(xml.encode()),'original_source_code':'clean/original_source.tex','original_reference':'clean/original_reference.png','source_render_pdf':'clean/original_source.pdf','source_render_pdf_sha256':sha(pdf.read_bytes()),'source_render_svg':'clean/projected_source.svg','source_render_svg_sha256':sha(projected.encode()),'native_embedded_fonts':[{'family':f['family'],'file':str(Path(f['file']).relative_to(private)),'sha256':f['sha256'],'original_PDF_font_sha256':f['source_font_sha256']} for f in fonts.values()],'declared_tikz_source_projection':frame,'private_resource_check_root':str(private),'quality_state':'research_only_not_accepted'}
  source_identity={k:record[k] for k in ('id','source_pair_sha256','source_format','source_code_sha256','source_image_sha256')};coverage=check_source_profile(record,xml,dom=dom,roles=roles,frame=frame,physical_fonts=fontproof,source_identity=source_identity);report['checks']['source']=coverage;save('independent_source_profile.json',coverage)
  from auto_quality_common_v4 import structure_checks,resource_checks,require_rendered_text,image_quality
  from auto_quality_batch_v4b import RENDERER
  from clip_canvas_render_v4b import render
  from strict_canvas_gate import require_declared_page
  report['checks']['structure']=structure_checks(xml);report['checks']['resources']=resource_checks(private,record,xml,reference);rendered=render(xml,*viewport,180,RENDERER,8192,root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(rendered.get('ok'),'actual strict native renderer failed: '+str({k:v for k,v in rendered.items() if k!='png'})[:2000]);png=rendered['png'];info=rendered['native_render'];save('strict_native.png',png);save('strict_native_render.json',info);require_declared_page(info,*viewport);require(info.get('runtime_cache_manifest_sha256')==sha((root/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json').read_bytes()),'actual renderer runtime manifest differs');from tikz_execution_binding_v2 import VIEWER_SHA256;require(info.get('viewer_bundle_sha256')==VIEWER_SHA256,'actual renderer viewer differs from editing proof');record.update(image_file='clean/image.native.png',image_sha256=sha(png));(clean/'image.native.png').write_bytes(png);report['checks']['strict_canvas']={'ok':True,'canvas':viewport,'outside_page_pixel_audit':info['outside_page_pixel_audit'],'renderer_sha256':sha(Path(RENDERER).read_bytes())};report['checks']['actual_rendered_text']=require_rendered_text(xml,info)
  usage=[f for row in info.get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0)>0];families={f['family'] for f in fonts.values()};font_ok=bool(usage) and all(f.get('isCustomFont') and f.get('familyName') in families for f in usage);report['checks']['actual_physical_fonts']={'ok':font_ok,'glyphs':sum(f['glyphCount'] for f in usage),'all_custom_and_original_PDF_font_families':font_ok,'usage':info.get('actual_platform_font_usage',[]),'source_physical_font_proof':fontproof}
  visual=image_quality(reference,png,record,info.get('actual_text_positions'));report['checks']['authoritative_original_image_global_foreground_and_every_native_text_line']=visual;editing=bridge.audit_native(xml,fonts,[],work);save('actual_native_editing.json',editing);report['checks']['actual_native_editing']={'ok':editing['ok'],'objects':editing['actual_native_intervention']['object_count'],'all_restored':editing['actual_native_intervention']['model_and_all_actual_live_paint_restored'],'evidence':'actual_native_editing.json'}
  report['checks']['resources_after_render']=resource_checks(private,record,xml,reference);passed=coverage['supported'] and coverage['ok'] and font_ok and visual['ok'] and editing['ok'];report.update(read_only_new_profile_full_QA_passed=passed,reason='all_independent_read_only_gates_passed_not_canonical' if passed else 'one_or_more_original_source_native_or_full_image_gates_failed_retain_pending',source_record=record,projection=frame,bridge_evidence=str(bridge_report),bridge_evidence_sha256=sha(Path(bridge_report).read_bytes()),source_identity=source_identity,snapshot=before,external_files={**r['files'],**src_report['files'],str(bridge_report):sha(Path(bridge_report).read_bytes()),str(r['source_only_evidence']):sha(Path(r['source_only_evidence']).read_bytes())},QA_policy=config['policy'],pins=config['pins'],environment_manifest_sha256=environment['manifest_sha256']);save('private_candidate_record.json',record)
  require(shared.snapshot(db,identifier)==before,'source/job/outcome/owner changed during projection QA');pins(config);require(source.environment_files(root)==environment['files'],'actual source environment changed after QA')
  for p,h in report['external_files'].items():require(sha(Path(p).read_bytes())==h,'original source/proof changed after native QA')
 except Exception as exc:report.update(read_only_new_profile_full_QA_passed=False,reason='unproved_projection_remains_pending');report['failures'].append(repr(exc))
 for p in work.rglob('*'):
  if p.is_file():require(not p.is_symlink(),'private artifact symlink');files[str(p)]=sha(p.read_bytes())
 report.update(files=files,work=str(work),module_sha256=LOADED_SHA256);report['report_sha256']=sha(canonical(report));(work/'report.json').write_bytes(canonical(report));return report

def _fresh_DOM_without_writes(svg,viewport):
 import svg_source_scene_dom_v1 as scene
 browser=scene._browser();context=browser.new_context(viewport={'width':viewport[0],'height':viewport[1]},java_script_enabled=False,service_workers='block');blocked=[]
 try:
  context.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page=context.new_page();page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg);page.evaluate('document.fonts.ready');dom=page.evaluate(scene.EXTRACTOR.read_text())
 finally:context.close()
 require(not blocked,'source projection depends on external resources');scene.enrich_scene(dom);return dom

def revalidate(db,report,config,check_files=True):
 """RO hook: full CAS, source trace/font/frame replay, fresh DOM, unchanged QA.

No output, source, queue, cache, file or model writes. Callers must keep the
returned report private; this API has no qualification/publication authority.
"""
 try:
  require(report.get('policy')==POLICY and report.get('read_only_new_profile_full_QA_passed') is True,'not a successful independent research QA report');require(report.get('accepted') is False and report.get('published') is False,'production acceptance is not authorized');require(sha(canonical({k:v for k,v in report.items() if k!='report_sha256'}))==report['report_sha256'],'projection report damaged');pins(config);require(report['module_sha256']==LOADED_SHA256 and report['pins']==config['pins'] and report['QA_policy']==config['policy'],'implementation/QA catalogue changed')
  import svg_failure_closure_v1 as shared
  import tikz_source_only_failure_v1 as source
  import tikz_closed_paint_bridge_v1 as bridge
  from tikz_execution_graph import parse_events,graph_from_events
  from pdf_to_native import pathdata,rgb
  from pdf_fonts import clusters
  import pymupdf
  from PIL import Image
  require(shared.snapshot(db,report['id'])==report['snapshot'],'authoritative source/job/outcome/owner snapshot changed')
  if check_files:
   for p,h in {**report['files'],**report['external_files']}.items():require(sha(Path(p).read_bytes())==h,'source/candidate/evidence file changed: '+p)
  record=report['source_record'];private=Path(record['private_resource_check_root']);require(private.resolve()==(Path(report['work'])/'resource_gate_private_root').resolve(),'private resource proof root redirected')
  for k in ('code_file','image_file','original_source_code','original_reference','source_render_pdf','source_render_svg'):
   p=(private/record[k]).resolve();require(p.is_relative_to((private/'clean').resolve()) and report['files'].get(str(p))==sha(p.read_bytes()),'opened private payload not hash-bound under the private clean root')
  xml=(private/record['code_file']).read_text();original=(private/record['original_source_code']).read_bytes();reference=(private/record['original_reference']).read_bytes();require((sha(original),sha(reference))==(record['source_code_sha256'],record['source_image_sha256']),'private source identity changed');input_record,manifest=db.execute('select input_record,input_manifest from jobs where id=?',(report['id'],)).fetchone();input_record=json.loads(input_record);manifest=json.loads(manifest);require((input_record['code_sha256'],input_record['image_sha256'])==(record['source_code_sha256'],record['source_image_sha256'])==(manifest['code_sha256'],manifest['image_sha256']),'current authoritative source hashes differ');require(source.source_context_guard(original.decode())['ok'],'original source context not proved')
  root=Path(config['root']);require(sha((root/manifest['source_code']).read_bytes())==record['source_code_sha256'] and sha((root/manifest['reference_image']).read_bytes())==record['source_image_sha256'],'actual authoritative files changed');base=json.loads(Path(report['bridge_evidence']).read_text());src=json.loads(Path(base['source_only_evidence']).read_text());require(base.get('module_sha256')==BRIDGE_SHA256 and sha(bridge.canonical({k:v for k,v in base.items() if k!='report_sha256'}))==base['report_sha256'],'baseline bridge provenance damaged');require(src['pins']==config['pins'] and sha(source.canonical({k:v for k,v in src.items() if k!='certificate_sha256'}))==src['certificate_sha256'],'original source execution provenance damaged');srcdir=Path(src['evidence_directory']);require(sha((private/record['source_render_pdf']).read_bytes())==record['source_render_pdf_sha256']==base['source_pdf_sha256']==sha((srcdir/'execution/baseline/source.pdf').read_bytes()),'original source PDF provenance differs');env=json.loads((srcdir/'environment.json').read_text());require(source.environment_files(root)==env['files'],'frozen source runtime/assets changed');sidecar=json.loads((srcdir/'execution/execution_graph.json').read_text());events=parse_events((srcdir/'execution/instrumented/source.iic').read_text());require(graph_from_events(events)==sidecar['graph'],'full original PGF trace replay changed')
  font_rows=record['native_embedded_fonts'];fonts={}
  with pymupdf.open(private/record['source_render_pdf']) as doc:
   require(len(doc)==1,'source PDF page count changed');page=doc[0];drawings=[]
   for i,d in enumerate(page.get_drawings(extended=True)):
    require(d['type'] not in ('clip','group'),'unknown PDF compositor');drawings.append({'id':i,'seqno':d['seqno'],'parts':bridge.path_ops(pathdata(d)),'fill':rgb(d.get('fill')),'stroke':rgb(d.get('color')),'stroke_width':d.get('width') or 0})
   roles=bridge.source_roles(events,drawings)
   import re
   for f in page.get_fonts(full=True):
    name,ext,typ,data=doc.extract_font(f[0]);key=re.sub(r'^[A-Z]{6}\+','',name).removesuffix('-Identity-H');rows=[x for x in font_rows if x['original_PDF_font_sha256']==sha(data)];require(len(rows)==1,'physical source font file ambiguous');row=rows[0];fonts[key]={'family':row['family'],'file':str(private/row['file']),'source_font_sha256':sha(data)}
   traces=page.get_texttrace()
   for t in traces:t['clusters']=clusters(t)
   physical=bridge.font_proof(doc,page,fonts,traces)
  original_svg=(private/'clean/original_PDF_derived.svg').read_text();require(sha(original_svg.encode())==base['source_derived_svg_sha256'],'original source SVG provenance differs');projected,frame=project_svg(original_svg,list(Image.open(io.BytesIO(reference)).size));require(projected==(private/record['source_render_svg']).read_text() and canonical(frame)==canonical(report['projection']),'the sole fixed full-page projection changed');dom=_fresh_DOM_without_writes(projected,frame['reference_viewport']);coverage=check_source_profile(record,xml,dom=dom,roles=roles,frame=frame,physical_fonts=physical,source_identity=report['source_identity']);require(coverage['supported'] and coverage['ok'],'fresh complete source profile no longer passes')
  from auto_quality_common_v4 import structure_checks,resource_checks,require_rendered_text,image_quality
  from strict_canvas_gate import require_declared_page
  structure_checks(xml);resource_checks(private,record,xml,reference);info=json.loads((Path(report['work'])/'strict_native_render.json').read_text());png=(private/record['image_file']).read_bytes();require(sha(png)==record['image_sha256'],'actual full native PNG changed');require_declared_page(info,*frame['reference_viewport']);require_rendered_text(xml,info);usage=[f for row in info.get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0)>0];families={f['family'] for f in font_rows};require(usage and all(f.get('isCustomFont') and f.get('familyName') in families for f in usage),'actual physical custom source fonts no longer pass');visual=image_quality(reference,png,record,info.get('actual_text_positions'));require(visual['ok'],'original-image full global/local gates no longer pass');require(shared.snapshot(db,report['id'])==report['snapshot'],'source state changed during RO revalidation');pins(config)
  return {'current':True,'id':report['id'],'fresh_full_source_DOM_replayed':True,'source_physical_fonts_replayed':True,'full_original_image_global_local_gates_recomputed':True,'published':False,'accepted':False}
 except Exception as exc:return {'current':False,'id':report.get('id'),'reason':repr(exc),'published':False,'accepted':False}
