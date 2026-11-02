"""Provider-before-edit SVG with original manifest-bound panel resolution."""
from pathlib import Path
_BASE=Path(__file__).with_name('compiler_svg_scene_frontend_v15.py')
exec(compile(_BASE.read_text(),str(_BASE),'exec'),globals())
import contextvars
from scidiagram_panel_assets_v1 import inventory as panel_inventory,resolve as resolve_panels
_BASE_PREPARE=prepare_source;_BASE_RENDER=_render_source;_BASE_CAPTURE=_capture;_BASE_WRITE=_write;_BASE_CONFIGURATION=configuration
VERSION='compiler_scidiagram_source_frontend_v1'
UNIT='provider_before_edit_scientific_SVG_hashed_panels_source_layout_v1'
DEPENDENCIES=(VERSION+'.py','compiler_svg_scene_frontend_v15.py','scidiagram_panel_assets_v1.py',*DEPENDENCIES[1:])
_PANEL_CONTEXT=contextvars.ContextVar('original_scidiagram_panels',default=None)

def source_admission(source,code,size):
 require(source.get('source')=='yashengsun--SciDiagramRevision'and source.get('format')=='svg'and source.get('category')=='scientific_diagram','source_requires_original_SciDiagramRevision_scientific_SVG')
 require(source.get('gold_code_provenance')=='dataset_input_svg_before_edit'and source.get('image_provenance')=='dataset_provided_before_edit_render','source_requires_provider_before_edit_provenance')
 require(source['code_sha256']==sha(code),'source_original_SVG_hash_changed')
 require(list(size)==[source['image_info']['width'],source['image_info']['height']],'source_original_image_size_changed')
 require(max(size)<=8192 and size[0]*size[1]<=64000000 and len(code)<=2000000,'source_resource_bound')
 require(b'<!ENTITY'not in code.upper()and not re.search(br'<!DOCTYPE[^>]*\[',code,re.I),'source_xml_entity_unsupported')
 root=ET.fromstring(code);allowed={'svg','g','a','title','desc','metadata','defs','marker','symbol','use','style','path','polygon','polyline','rect','circle','ellipse','line','text','tspan','image'};ids=set();markers=0;images=0
 for element in root.iter():
  tag=element.tag.split('}')[-1];require(tag in allowed,'unsupported_svg_element:'+tag)
  if tag=='style':
   css=''.join(element.itertext());require('@import'not in css.lower(),'source_external_stylesheet_unsupported')
   for url in re.findall(r'url\((.*?)\)',css,re.I|re.S):require(url.strip().strip("\"'").startswith('#'),'source_external_CSS_resource_unsupported')
  if tag=='marker':markers+=1
  if tag=='image':images+=1
  identifier=element.get('id')
  if identifier:require(identifier not in ids,'duplicate_source_xml_id');ids.add(identifier)
  for key,value in element.attrib.items():
   local=key.split('}')[-1];require(not local.lower().startswith('on'),'source_event_handler_unsupported');require(local not in('filter','clip-path','mask','marker-mid'),'source_effect_requires_another_frontend')
   if local=='href'and tag!='image':require(value.startswith('#')or tag=='a'and re.match(r'^(?:https?://|mailto:)',value),'source_external_resource_unsupported')
   if 'url('in value.lower():require(not re.search(r'url\(\s*[\"\']?(?!#)[^\s\"\')]',value,re.I),'source_external_paint_resource_unsupported')
 require(markers,'general_svg_scene_requires_explicit_source_markers');require(images,'source_requires_original_panel_assets')
 return dict(unit=UNIT,reference_canvas=list(size),source_explicit_marker_definitions=markers,source_original_panel_images=images,source_provenance='provider_before_edit_SVG_and_PNG',fresh_Cairo_and_browser_and_original_reference_gates_required=True,source_layout_preserved=True,relayout=False)

def configuration(data_root=R):
 result=_BASE_CONFIGURATION(data_root);result.update(source_renderer='provider_before_edit_SVG_with_original_panels_fresh_Cairo_browser_and_original_PNG_crosschecks',provider_original_render_engine_not_assumed=True);return result

def _resolved(code):
 context=_PANEL_CONTEXT.get();require(context is not None,'source_panel_resolution_context_missing');return resolve_panels(code,context)
def _render_source(code,size,work):return _BASE_RENDER(_resolved(code)[0],size,work)
def _capture(code,size,work,cairo_fonts=None):return _BASE_CAPTURE(_resolved(code)[0],size,work,cairo_fonts)
def _write(path,blob):
 if Path(path).name=='sourceproof.json':
  value=json.loads(blob);context=_PANEL_CONTEXT.get();code=(R/context['manifest']['source_code']).read_bytes();_,proof=resolve_panels(code,context);value['original_panel_resolution']=proof;value['source_renderer']='fresh_CairoSVG_from_unchanged_provider_SVG_with_exact_original_panel_bytes';blob=raw(value)
 return _BASE_WRITE(path,blob)
def prepare_source(record,job=None,work=None):
 context=panel_inventory(record,job);token=_PANEL_CONTEXT.set(context)
 try:
  result=_BASE_PREPARE(record,job,work);result['sourceproof']=json.loads((result['work']/'sourceproof.json').read_bytes());return result
 finally:_PANEL_CONTEXT.reset(token)
