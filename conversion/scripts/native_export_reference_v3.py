"""Actual drawio tight export of an unchanged, complete original native graph.

The published XML retains original geometry. Declared-page paint and exported
viewport paint are independently audited. Viewport size/translation come only
from upstream graph bounds and a common export border, never image-score search.
"""
import hashlib,json,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
OWNER=R/'conversion/native_export_reference_v3'
SCHEMA='original_native_graph_complete_actual_export_viewport_v3'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def configuration():
 scripts=Path(__file__).parent
 paths=[Path(__file__),scripts/'native_export_canvas_v2.py',scripts/'native_html_quality_v2.py',scripts/'native_html_compiler_v2.py',R/'conversion/rendering_native_export_view_v2/remote_render.py',R/'conversion/rendering_paintbounds_strict/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json']
 return {str(p):sha(p.read_bytes()) for p in paths}
def validate_inventory(baseline,exported):
 from native_source_font_profile_v4 import signature
 for key in ('cells','vertices','edges'):
  require(baseline[key]==exported[key],'native_export_graph_inventory_changed:'+key)
 require(signature(baseline['actual_platform_font_usage'])==signature(exported['actual_platform_font_usage']),'native_export_actual_font_glyph_inventory_changed')
 text=lambda info:{row['cell']:[c['text'] for run in row.get('runs',[]) for c in run.get('chars',[])] for row in info['actual_text_positions']}
 require(text(baseline)==text(exported),'native_export_actual_text_inventory_changed')
 a=baseline.get('actual_dom_paint_bounds') or {};b=exported.get('actual_dom_paint_bounds') or {}
 require(not a.get('unsupported') and not b.get('unsupported') and a.get('element_count')==b.get('element_count'),'native_export_native_paint_element_inventory_changed')
 return {'cells':baseline['cells'],'vertices':baseline['vertices'],'edges':baseline['edges'],'actual_source_text_objects':len(text(baseline)),'actual_native_paint_elements':a.get('element_count'),'all_actual_text_and_physical_glyph_counts_preserved':True}
def _render_export(record,xml,reference):
 import xml.etree.ElementTree as E
 from native_export_canvas_v2 import render,render_view,export_plan
 from strict_canvas_gate import require_declared_page
 model=E.fromstring(xml).find('.//mxGraphModel');page=[int(round(float(model.get(k,0)))) for k in ('pageWidth','pageHeight')]
 full=render(xml,page);require_declared_page(full['native_render'],*page)
 dx,dy,size,basebox,refbox,mode=export_plan(reference,full)
 require(mode=='official_graph_bounds_uniform_border','native_export_requires_upstream_bounds_and_uniform_border')
 export=render_view(xml,size,dx,dy);require_declared_page(export['native_render'],*size)
 inventory=validate_inventory(full['native_render'],export['native_render'])
 return full,export,{'translation':[dx,dy],'source_declared_page':page,'export_viewport':size,'view_transform':[1,0,0,1,dx,dy],'device_scale_factor':1,'css_dpi':96,'mode':mode,'source_graph_bounds':full['native_render']['graphBounds'],'complete_paint_inventory':inventory}
def repair(record,job,work):
 from fixed_batch_case_v1 import checked,save,raw
 try:
  require(record.get('source_format')=='drawio' and not record.get('auto_quality_canvas_repair'),'native_export_requires_unregistered_original_native_source')
  xml=checked(record['code_file'],record['code_sha256']).decode();reference=checked(record['original_reference'],record['source_image_sha256']);checked(record['original_source_code'],record['source_code_sha256'])
  pins=configuration();full,export,view=_render_export(record,xml,reference)
  require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()),'native_export_implementation_changed_during_render')
  folder=OWNER/record['id']/uuid.uuid4().hex;dest=R/'clean/native_export_reference_v3'/record['id'][:2]/record['id']/folder.name;folder.mkdir(parents=True);dest.mkdir(parents=True)
  save(folder/'before_record.json',raw(record));save(folder/'original_geometry.drawio',xml.encode());save(folder/'declared_page.png',full['png']);save(folder/'export.png',export['png']);save(folder/'export.native.json',raw(export['native_render']));save(dest/'image.png',export['png'])
  proof={'schema':SCHEMA,'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'unchanged_native_xml_sha256':record['code_sha256'],'input_image_sha256':record['image_sha256'],'export_image_sha256':sha(export['png']),'declared_page_png_sha256':sha(full['png']),'view':view,'pins':pins,'audit':str((folder/'proof.json').relative_to(R)),'accepted':False}
  save(folder/'proof.json',raw(proof));out={**record,'image_file':str((dest/'image.png').relative_to(R)),'image_sha256':proof['export_image_sha256'],'native_export_reference_v3':proof,'render':{**export['native_render'],'export_viewport_contract':view},'quality_state':'pending_complete_original_native_export_quality'}
  save(folder/'candidate_record.json',raw(out));save(dest/'conversion.json',raw(out));return {'ok':True,'record':out,'evidence':proof,'model_calls':0}
 except Exception as exc:return {'ok':False,'reason':'native_export_reference_refused','error_type':type(exc).__name__,'detail':str(exc)}
def validate(record,xml):
 from fixed_batch_case_v1 import checked
 proof=record['native_export_reference_v3'];folder=(R/proof['audit']).resolve(strict=True).parent
 require(proof.get('schema')==SCHEMA and proof.get('accepted') is False,'native_export_invalid_contract_schema')
 require(folder.is_relative_to((OWNER/record['id']).resolve()),'native_export_unowned_contract')
 require(json.loads((folder/'proof.json').read_bytes())==proof,'native_export_frozen_contract_changed')
 previous=json.loads((folder/'before_record.json').read_bytes());current=json.loads((folder/'candidate_record.json').read_bytes())
 for obj in [proof,previous,current]:require(all(obj.get(k)==record.get(k) for k in ('id','source_code_sha256','source_image_sha256')),'native_export_original_source_identity_changed')
 require((folder/'original_geometry.drawio').read_text()==xml and sha(xml.encode())==previous['code_sha256']==current['code_sha256']==record['code_sha256']==proof['unchanged_native_xml_sha256'],'native_export_original_native_geometry_or_font_revision_changed')
 require(current.get('native_export_reference_v3')==proof and current['image_file']==record['image_file'] and current['image_sha256']==record['image_sha256']==proof['export_image_sha256'],'native_export_current_frozen_image_changed')
 require(proof.get('pins')==configuration(),'native_export_implementation_pins_changed')
 reference=checked(record['original_reference'],record['source_image_sha256']);full,export,view=_render_export(record,xml,reference)
 require(view==proof['view'],'native_export_viewport_not_rederived_from_original_graph_bounds')
 require(sha(full['png'])==proof['declared_page_png_sha256'] and sha(export['png'])==record['image_sha256'],'native_export_fresh_page_or_export_pixels_changed')
 require(checked(record['image_file'],record['image_sha256'])==export['png'],'native_export_current_image_does_not_equal_fresh_actual_export')
 require(all(sha(Path(p).read_bytes())==h for p,h in proof['pins'].items()),'native_export_implementation_changed_during_verification')
 return previous,full,export,view
