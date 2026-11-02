"""Explicit full-source clean-bundle adapter for independent deterministic RO QA."""
import base64,hashlib,io,json,math,sys,uuid,xml.etree.ElementTree as E
from pathlib import Path
import tikz_closed_paint_candidate_v1 as bundle

R=bundle.ROOT;W=R/'conversion'
for p in (W/'scripts',W/'prototype',W/'runtime/python_packages'):
 if str(p) not in sys.path:sys.path.append(str(p))
NAME='tikz_closed_basic_original_PDF_fixed_projection_clean_source_v1'
sha=bundle.sha;canonical=bundle.canonical;require=bundle.require
LOADED_SHA256=sha(Path(__file__).read_bytes())

def configuration(data_root):
 import tikz_source_only_failure_v1 as source
 import tikz_closed_paint_projection_v1 as projection
 require(Path(data_root).resolve()==R,'formal candidate profile requires actual registered HKUST root');require(sha(Path(__file__).read_bytes())==LOADED_SHA256,'adapter changed after import');source_config=source.configuration(R);projection.pins(source_config);pins=dict(source_config['pins'])
 for name in ('tikz_closed_paint_quality_adapter_v1.py','tikz_closed_paint_candidate_v1.py','tikz_closed_paint_projection_v1.py','tikz_closed_paint_bridge_v1.py','tikz_closed_paint_bridge_v1.js','svg_convert_v5.py','svg_convert_v6.py'):
  p=W/'scripts'/name;pins[str(p)]=sha(p.read_bytes())
 environment=source.environment_files(R)
 policy=NAME+':'+sha(canonical(pins))[:20];return {'policy':policy,'pins':pins,'environment':environment,'source_configuration':source_config,'source_requires_native_info':False,'data_root':str(R)}

def registration_record(record,reference,xml,data_root):
 from PIL import Image
 import tikz_closed_paint_projection_v1 as projection
 import pymupdf
 manifest=bundle.load_manifest(data_root,record,xml);require(sha(reference)==record['source_image_sha256'],'registered original reference differs');svg=bundle.checked(data_root,manifest['files']['original_PDF_derived_svg']).decode();projected,frame=projection.project_svg(svg,list(Image.open(io.BytesIO(reference)).size));require(projected.encode()==bundle.checked(data_root,manifest['files']['projected_svg']) and canonical(frame)==canonical(manifest['projection']),'not the sole complete source viewBox xMidYMid meet projection');require(canonical(record['declared_source_projection'])==canonical(frame),'candidate projection metadata differs');model=E.fromstring(xml).find('.//mxGraphModel');require([float(model.get(k)) for k in ('pageWidth','pageHeight')]==frame['reference_viewport'],'candidate canvas not identical to original reference header')
 return {**record,'_verified_tikz_closed_paint_projection':frame},{'version':1,'method':NAME,'original_reference_sha256':record['source_image_sha256'],'source_pdf_sha256':record['source_render_pdf_sha256'],'source_manifest_sha256':record[bundle.FIELD]['sha256'],'full_source_projection':frame,'provider_DPI_recovered':False,'no_pixel_fit':True,'source_objects_cropped':False}

def _font_bytes(data_root,roster):
 return {f['family']:{**f,'file':str(bundle.clean_path(data_root,f['file'])),'uri':'data:font/otf;base64,'+base64.b64encode(bundle.checked(data_root,f)).decode()} for f in roster}

def check_source(record,xml,source,data_root,native_info=None):
 result={'profile':NAME,'supported':False,'ok':False,'failures':[],'evidence':{}}
 work=None
 try:
  import tikz_source_only_failure_v1 as guard
  import tikz_closed_paint_bridge_v1 as bridge
  import tikz_closed_paint_projection_v1 as projection
  from tikz_execution_graph import parse_events,graph_from_events
  from tikz_execution_source_profile import WRAPPERS
  from pdf_to_native import source_svg,pathdata,rgb
  import pymupdf
  from PIL import Image
  config=configuration(data_root);manifest=bundle.load_manifest(data_root,record,xml);require(manifest['runtime_policy']==config['policy'] and record['candidate_quality_adapter']['policy']==config['policy'],'candidate source program catalogue changed');files=manifest['files'];code=bundle.checked(data_root,files['original_source']);reference=bundle.checked(data_root,files['original_reference']);require(code.decode()==source and sha(code)==record['source_code_sha256'] and sha(reference)==record['source_image_sha256'],'authoritative original bytes differ');require(manifest['source_record']==record['source_record'],'complete original source metadata differs');require(guard.source_context_guard(source)['ok'],'source environment/assets not within proved static subset');receipt=json.loads(bundle.checked(data_root,files['source_execution_receipt']));require(receipt['version']=='original_cached_PGF_source_compile_receipt_v1' and receipt['source_sha256']==sha(code) and receipt['source_bytes_unchanged'] is True,'original execution/source binding differs');require(set(receipt['runs'])=={'baseline','instrumented'} and all(x['returncode']==0 for x in receipt['runs'].values()),'source compile failure is never accepted as semantic proof')
  for name in bundle.CORE_NAMES:
   path=str(W/'scripts'/name);require(receipt['core_implementation'][path]==sha(Path(path).read_bytes()),'recorded source execution core changed: '+name)
  for mode in ('baseline','instrumented'):
   wrapper=bundle.checked(data_root,files[mode+'_wrapper']);require(wrapper==WRAPPERS[mode] and receipt['runs'][mode]['wrapper_sha256']==sha(wrapper),'source compilation wrapper differs')
  hook=bundle.checked(data_root,files['instrumented_hook']);require(sha(hook)==receipt['hook_sha256']==sha((W/'scripts/tikz_execution_graph_hooks.tex').read_bytes()),'source trace hook differs');old_env=json.loads(bundle.checked(data_root,files['source_environment']));require(old_env and all(p in config['environment'] and config['environment'][p]==v for p,v in old_env.items()),'original complete source execution software/assets changed or missing');events=parse_events(bundle.checked(data_root,files['source_trace']).decode());graph=graph_from_events(events);require(graph==receipt['graph'],'full original source trace replay differs');work=W/'prototype/tikz_closed_paint_clean_source_v1'/record['id']/uuid.uuid4().hex;work.mkdir(parents=True,exist_ok=False)
  baseline=bundle.checked(data_root,files['baseline_pdf']);instrumented=bundle.checked(data_root,files['instrumented_pdf']);page_equivalence=[]
  with pymupdf.open(stream=baseline,filetype='pdf') as doc,pymupdf.open(stream=instrumented,filetype='pdf') as hooked:
   require(len(doc)==len(hooked)==1,'source pages not a complete single picture');page=doc[0];require(page.rotation==0 and page.rect==page.mediabox==page.cropbox and not page.get_images(),'source clipping/rotation/raster assets need another explicit profile');a=page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);b=hooked[0].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);require(a.irect==b.irect and a.samples==b.samples,'instrumented source PDF changed original paint');page_equivalence.append({'page':0,'pixels_identical':True,'size':[a.width,a.height],'pixel_sha256':sha(a.samples)})
   drawings=[]
   for i,d in enumerate(page.get_drawings(extended=True)):
    require(d['type'] not in ('clip','group'),'unmapped source compositing');drawings.append({'id':i,'seqno':d['seqno'],'parts':bridge.path_ops(pathdata(d)),'fill':rgb(d.get('fill')),'stroke':rgb(d.get('color')),'stroke_width':d.get('width') or 0})
   roles=bridge.source_roles(events,drawings);require(all(x['role']=='source_explicit_closed_basic_paint' for x in roles['objects']),'open/axis/relation sources are outside this closed-only admission');svg,fonts,stats=source_svg(doc,page,work/'source');require(not stats['issues'],'unknown source PDF/SVG semantics');require(svg.encode()==bundle.checked(data_root,files['original_PDF_derived_svg']),'source SVG is not actual original-PDF extraction');traces=__import__('pdf_fonts').build_fonts(doc,page,work/'font_recheck')[1];physical=bridge.font_proof(doc,page,fonts,traces)
  roster=json.loads(bundle.checked(data_root,files['source_font_roster']));require(roster==record['native_embedded_fonts'],'source/native font roster differs');by_family={f['family']:f for f in fonts.values()};require(set(by_family)=={f['family'] for f in roster},'original embedded source font inventory differs')
  for f in roster:
   require(bundle.checked(data_root,f)==Path(by_family[f['family']]['file']).read_bytes() and f['source_font_sha256']==by_family[f['family']]['source_font_sha256'],'current portable font is not original-PDF contour/Unicode/advance reconstruction')
  projected,frame=projection.project_svg(svg,list(Image.open(io.BytesIO(reference)).size));require(projected.encode()==bundle.checked(data_root,files['projected_svg']) and canonical(frame)==bundle.checked(data_root,files['projection_contract']) and canonical(frame)==canonical(record['declared_source_projection']),'fixed complete source projection differs');dom=projection._fresh_DOM_without_writes(projected,frame['reference_viewport']);identity={k:record[k] for k in ('id','source_pair_sha256','source_format','source_code_sha256','source_image_sha256')};coverage=projection.check_source_profile(record,xml,dom=dom,roles=roles,frame=frame,physical_fonts=physical,source_identity=identity);require(coverage['supported'] and coverage['ok'],'complete original source/projection/native coverage failed: '+json.dumps(coverage['failures'])[:2000]);text_ids=[o['id'] for o in dom['objects'] if o['type']=='text'];expected_families={o['id']:o['fontFamily'].split(',')[0].strip('"\'') for o in dom['objects'] if o['type']=='text'}
  if native_info is not None:
   usage=[(row['cell'],f) for row in native_info.get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0)>0];require(usage and all(f.get('isCustomFont') is True and f.get('familyName')==expected_families.get(cell) and f.get('postScriptName')==expected_families.get(cell) for cell,f in usage),'actual native physical face is not the original source CFF font');require(sum(f['glyphCount'] for _,f in usage)==sum(f['used_clusters'] for f in physical['fonts']),'actual native glyph inventory differs from complete original PDF clusters')
  result=coverage;result['profile']=NAME;result['evidence'].update(complete_source_coverage=True,required_text_cell_ids=text_ids,clean_source_manifest=record[bundle.FIELD],actual_source_trace_replayed=True,baseline_instrumented_original_PDF_equivalence=page_equivalence,complete_source_PGF_and_PDF_paint=roles,original_source_environment_subset_unchanged=True,required_software_dependencies={p:v['sha256'] for p,v in old_env.items()},current_program_policy=config['policy'],candidate_code_sha256=record['code_sha256'],no_source_format_relabel=True,debug_work=str(work),actual_physical_fonts_checked=native_info is not None)
  (work/'full_source_DOM.json').write_bytes(canonical(dom));(work/'source_profile.json').write_bytes(canonical(result))
 except Exception as exc:result={'profile':NAME,'supported':False,'ok':False,'failures':[{'reason':'unproved_complete_clean_TikZ_source','error':repr(exc)}],'evidence':{'complete_source_coverage':False,'required_text_cell_ids':[]}}
 return result

def close_worker_runtime():
 import svg_source_scene_dom_v1 as scene
 scene.close_worker_runtime()

def audit_editing(record,xml,source_profile,data_root):
 import tikz_closed_paint_bridge_v1 as bridge
 require(source_profile.get('supported') is True and source_profile.get('ok') is True and source_profile.get('evidence',{}).get('complete_source_coverage') is True,'editing requires complete original source/projection proof');require(source_profile['evidence']['candidate_code_sha256']==record['code_sha256']==sha(xml.encode()),'editing candidate revision differs');require(not any(c.get('edge')=='1' for c in E.fromstring(xml).iter('mxCell')),'closed-only route cannot waive any connector');manifest=bundle.load_manifest(data_root,record,xml);roster=json.loads(bundle.checked(data_root,manifest['files']['source_font_roster']));fonts=_font_bytes(data_root,roster);work=W/'prototype/tikz_closed_paint_clean_editing_v1'/record['id']/uuid.uuid4().hex;work.mkdir(parents=True,exist_ok=False)
 try:result=bridge.audit_native(xml,fonts,[],work)
 finally:close_worker_runtime()
 require(result['ok'] and result['actual_native_intervention']['object_count']==sum(c.get('vertex')=='1' for c in E.fromstring(xml).iter('mxCell')),'incomplete native object intervention');bundle.load_manifest(data_root,record,xml);(work/'editing.json').write_bytes(canonical(result));return {**result,'profile':NAME+'_actual_all_object_editing','source_manifest_sha256':record[bundle.FIELD]['sha256'],'candidate_code_sha256':record['code_sha256'],'evidence_file':str(work/'editing.json')}
