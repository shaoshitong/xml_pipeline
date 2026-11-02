"""Common QA gates with independently verified reference-page registration."""
import hashlib,json,xml.etree.ElementTree as E
from pathlib import Path
from auto_quality_common import *
from auto_quality_common import image_quality as _image_quality
from native_worker import R,W

POLICY='source_coverage_registered_canvas_native_render_and_local_fidelity_v2'

def registration_record(record,reference,xml):
 record={k:v for k,v in record.items() if not k.startswith('_verified_')}
 contract=None
 if record.get('auto_quality_canvas_repair'):
  from auto_quality_canvas_repair import validate_registration,validate_registration_origin
  try:contract=validate_registration(record,reference,xml)
  except AssertionError:
   contract=validate_registration_origin(record,reference)
   contract=font_only_registration(record,xml,contract)
 elif record.get('native_canvas_contract') or record.get('native_page_padding'):
  from harness_canvas_contract import validate,require_xml_page
  contract=validate(record,reference);require_xml_page(xml,contract)
 if contract:
  assert contract['reference_page']==list(rgb(reference).size),'Reference registration dimensions changed'
  page=E.fromstring(xml).find('.//mxGraphModel');assert [float(page.get(k,'nan')) for k in ('pageWidth','pageHeight')]==contract['output_page'],'Current XML changed the registered page'
  record={**record,'_verified_reference_registration':contract}
 return record,contract

def font_only_registration(record,xml,contract):
 """An origin proves page dimensions; a separate exact font delta proves reuse."""
 from native_font_embedding_batch import canonical
 proof=record.get('native_font_validation') or {};assert proof.get('input_code_sha256')==contract['origin_code_sha256'],'Canvas registration needs an independently proven current delta'
 assert proof.get('output_code_sha256')==record['code_sha256']==sha(xml.encode()),'Font delta is stale'
 assert proof.get('native_pixels_unchanged') and proof.get('physical_faces_and_glyph_counts_preserved') and proof.get('all_actual_fonts_custom'),'Incomplete font-only delta proof'
 folder=(R/proof['audit']).resolve().parent;assert folder.is_relative_to(W/'auto_quality_font_repair_v1'),'Unowned font delta'
 assert json.loads((folder/'report.json').read_text())==proof,'Font delta report changed'
 details=json.loads((folder/'font_details.json').read_text());changed={c['cell'] for c in details['changes']};assert changed
 origin=(R/contract['frozen_origin_code']).resolve();assert origin.is_relative_to(W/'auto_quality_canvas_repair_v1');baseline=origin.read_text();assert sha(baseline.encode())==contract['origin_code_sha256']
 assert sha((folder/'before.drawio').read_bytes())==contract['origin_code_sha256'],'Font delta baseline is not the proven canvas'
 assert canonical(baseline,changed)==canonical(xml,changed),'Canvas lineage changed non-font graph content'
 assert all((c['before_flags']&~3)==(c['after_flags']&~3) for c in details['changes']),'Font delta changed other text formatting'
 current=checked(R,record['image_file'],record['image_sha256']);original=(R/contract['frozen_origin_image']).read_bytes();assert sha(original)==contract['origin_image_sha256']
 assert rgb(current).size==rgb(original).size and rgb(current).tobytes()==rgb(original).tobytes(),'Canvas font delta changed native pixels'
 return {**contract,'current_revision_verified':True,'font_only_delta_verified':True,'font_delta_report':proof['audit'],'font_delta_report_sha256':sha((folder/'report.json').read_bytes()),'scope':'Frozen reference registration plus independently checked font-only graph and native-pixel delta. Current source, fresh render, actual fonts and editability remain separate gates.'}

def image_quality(reference,png,record,text_positions=None):
 contract=record.get('_verified_reference_registration')
 if contract:
  # The alias is supplied only after validating hashes/geometry/frozen pixel
  # evidence, never from an unchecked user-provided offset.
  record={**record,'native_canvas_contract':{**contract,'offset':contract['original_page_offset']}}
 result=_image_quality(reference,png,record,text_positions)
 if contract:result['reference_registration']={k:contract[k] for k in ('reference_page','output_page','original_page_offset')}
 return result
