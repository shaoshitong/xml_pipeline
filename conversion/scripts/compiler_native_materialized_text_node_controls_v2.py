"""Finite real native-source positives and rerendered semantic negatives."""
import argparse
import copy
import json
from pathlib import Path
import re
import uuid
import xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
DEFAULT=R/'release/compiler_native_materialized_text_node_v2/controls/actual_20261101_v1'
POSITIVES=(('0133a0d0b8a43ed69b38b18150c948107bf1d59575f71e92a9d689cfa1e91a69','finite_0133_clean_originals_full_quality_20261101_v1'),('04e7525044d8bc4417177303924cf8df108333af303376a297c36055d2a174b5','finite_04e_full_quality_20261101_v1'))


def run(output=DEFAULT):
 import compiler_native_source_repair_frontend_v2 as frontend
 import compiler_native_source_repair_quality_ro_v2 as quality
 import compiler_native_source_repair_fonts_v2 as fonts
 import compiler_types_program_v1 as common
 from native_export_reference_v4 import repair as export
 import sqlite3
 output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);config=frontend.configuration();positive=[];negative=[]
 for identifier,directory in POSITIVES:
  if identifier.startswith('04e752'):
   existing=W/'compiler_native_materialized_text_node_dev_v2/7b0125ea9e664ba2ad4a59b6ea7e467e'/identifier/'frontend_result.json'
  else:existing=W/'compiler_native_source_repair_v1'/directory/'frontend_result.json'
  front=json.loads(existing.read_bytes());candidate=Path(front['record_file']);record=json.loads(candidate.read_bytes())
  quality_work=W/'prototype/candidate_quality_ro_v1'/('materialized_backend_positive_'+uuid.uuid4().hex)
  qa=quality.verify(identifier,candidate,R,frontend.__file__,quality_work);report_path=quality_work/'report.json'
  if not qa['ok']or not qa['accepted']or qa['implementation_pins']!=config['pins']:raise ValueError('native_source_real_positive_or_pins_changed:'+json.dumps(qa.get('failures')))
  for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:common.checked(dict(file=record[field],sha256=record[digest]),clean=True)
  positive.append(dict(id=identifier,candidate=common.asset(Path(front['record_file'])),qa=common.asset(report_path),code=common.asset(R/record['code_file']),fresh_png=common.asset(R/record['image_file']),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],actual_full_QA=True))
 base=positive[0];record=json.loads(Path(base['candidate']['file']).read_bytes());xml=(R/record['code_file']).read_text();width,height=record['render']['canvas']
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:job=db.execute('select*from jobs where id=?',(record['id'],)).fetchone()
 for kind in ('named_endpoint_changed','font_run_physical_family_changed'):
  root=ET.fromstring(xml);cells=list(root.iter('mxCell'))
  if kind=='named_endpoint_changed':
   edge=next(cell for cell in cells if cell.get('edge')=='1');side='source'if edge.get('source')else'target'if edge.get('target')else None
   if side:
    before=edge.get(side);replacement=next(cell.get('id')for cell in cells if cell.get('vertex')=='1'and cell.get('id')and cell.get('id')!=before);edge.set(side,replacement);intervention=dict(cell=edge.get('id'),field=side,before=before,after=replacement)
   else:
    point=edge.find("mxGeometry/mxPoint[@as='sourcePoint']");before=point.get('x');after=str(float(before)+23);point.set('x',after);intervention=dict(cell=edge.get('id'),field='explicit_sourcePoint_x',before=before,after=after)
  else:
   cell=next(cell for cell in cells if'data-native-source-font-run-v1'in cell.get('value','')and any(c.isalpha()for c in re.sub('<[^>]+>','',cell.get('value',''))));value=cell.get('value');match=re.search(r'(font-family: )([^;]+)(;)',value)
   if match is None:raise ValueError('native_control_source_font_wrapper_missing')
   changed=value[:match.start(2)]+'monospace'+value[match.end(2):];cell.set('value',changed);intervention=dict(cell=cell.get('id'),field='one_run_font_family',before=match.group(2),after='monospace')
  changed=ET.tostring(root,encoding='unicode');destination=R/'clean/compiler_native_materialized_text_node_controls_v2'/record['id'][:2]/record['id']/uuid.uuid4().hex;destination.mkdir(parents=True,exist_ok=False);fonts.save(destination/'diagram.drawio',changed.encode())
  modified={**record,'code_file':str((destination/'diagram.drawio').relative_to(R)),'code_sha256':fonts.sha(changed.encode())};modified.pop('native_export_reference_v4',None)
  attempt=export(modified,job,W/'compiler_native_materialized_text_node_controls_v2'/('negative_export_'+uuid.uuid4().hex))
  if not attempt.get('ok'):raise ValueError('native_semantic_negative_export_not_rebuilt:'+str(attempt))
  candidate=attempt['record']
  if candidate['image_sha256']==record['image_sha256']:raise ValueError('native_semantic_negative_did_not_change_actual_pixels')
  candidate_file=destination/'candidate_record.json';fonts.save(candidate_file,fonts.raw(candidate));directory=W/'prototype/candidate_quality_ro_v1'/('native_source_negative_'+uuid.uuid4().hex);qa=quality.verify(record['id'],candidate_file,R,frontend.__file__,directory)
  if qa['ok']or qa.get('infrastructure_failure')or not any('native_run_candidate_not_independently_rederived_font_only_XML'in failure['reason']for failure in qa['failures']):raise ValueError('native_semantic_negative_not_rejected_at_independent_source_semantics')
  negative.append(dict(name=kind,id=record['id'],intervention=intervention,candidate=common.asset(candidate_file),qa=common.asset(directory/'report.json'),code=common.asset(R/candidate['code_file']),fresh_png=common.asset(R/candidate['image_file']),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],actual_rerendered_pixels_changed=True,code_and_image_rehashed=True,export_proof_rebuilt_for_changed_code=True,rejected=True))
 receipt=dict(schema='native_materialized_text_node_actual_controls_v2',ok=True,configuration=config,producer=common.asset(Path(__file__)),positive=positive,negative=negative,models=0,new_heldout_consumed=0,canonical_mutations=0)
 fonts.save(output/'receipt.json',fonts.raw(receipt));return dict(receipt=common.asset(output/'receipt.json'),positive=len(positive),negative=len(negative))


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=DEFAULT);args=p.parse_args();print(json.dumps(run(args.output)))
