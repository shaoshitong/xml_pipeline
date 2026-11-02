"""Full existing-candidate regressions and actual rerendered semantic negatives."""
import copy,io,json,sqlite3,uuid,xml.etree.ElementTree as ET
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
ROOT=W/'tikz_node_paint_normal_development_v2/67924c6fa8f74a1bb3893d9af058df0d'
OUTPUT=R/'release/compiler_iterations/controls/tikz_node_paint_QA5_controls_20261101_v1'
IDS=('8689389d1f64000151962180f407dadaaef208bb7dfcf18b5746f14d9826cd17','0593a28ecc6e324f9bd19cdd673619ddf61a96328c03b396f26ec8dfc3f5e693')


def run():
 import compiler_types_program_v1 as common
 import compiler_tikz_node_paint_source_contract_v1 as contract
 import compiler_tikz_node_paint_iteration_case_v1 as case
 import compiler_tikz_node_paint_quality_ro_v5 as quality
 import compiler_source_core_attempts_v3 as history
 from tikz_native_export_frame_v1 import produce
 from tikz_node_paint_export_contract_v4 import registration
 from PIL import Image
 config=contract.configuration();before=history.collect(config,root=R,catalog=contract.CATALOG);history.validate(before,config,root=R);assert len(before)==2
 OUTPUT.mkdir(parents=True,exist_ok=False);work=W/'tikz_node_paint_QA5_controls_v1'/uuid.uuid4().hex;work.mkdir(parents=True,exist_ok=False)
 positives=[];negative=[];jobs={};quality_cfg=None;records={}
 for identifier in IDS:
  old=json.loads((ROOT/identifier/'summary.json').read_bytes());summary=json.loads((ROOT/identifier/'QA5_existing_candidate_summary.json').read_bytes());candidate=Path(old['candidate_file']);record=json.loads(candidate.read_bytes());qa_path=Path(summary['quality_report']);qa=json.loads(qa_path.read_bytes());case.full_quality(qa,record)
  cfg=dict(policy=qa['quality_policy'],pins=qa['implementation_pins'])
  if quality_cfg is None:quality_cfg=cfg
  else:assert quality_cfg==cfg
  with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:job=db.execute('select*from jobs where id=?',(identifier,)).fetchone()
  jobs[identifier]=job;records[identifier]=(record,qa,qa_path,candidate)
  positives.append(dict(id=identifier,candidate=common.asset(candidate),qa=common.asset(qa_path),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],fresh_png=common.asset(qa_path.parent/'fresh.png'),actual_full_quality=True))
 for index,(name,identifier)in enumerate((('source_owned_label_group_shifted',IDS[0]),('source_endpoint_role_changed',IDS[1])),1):
  original,_,_,_=records[identifier];files=original['compiler_tikz_node_paint_viewport_v2']['files'];unshifted=(R/files['unshifted_native_xml']['file']).read_text();root=ET.fromstring(unshifted);cells=list(root.iter('mxCell'));intervention={}
  if index==1:
   cell=next(c for c in cells if(c.get('id')or'').startswith('tikz_label_'));geometry=cell.find('mxGeometry');old=float(geometry.get('x','0'));geometry.set('x',format(old+.25*100/72,'.17g'));intervention=dict(cell=cell.get('id'),field='x',source_units='100dpi_physical_px',delta_px=.25*100/72,delta_bp=.25)
  else:
   edge=next(c for c in cells if c.get('edge')=='1');geometry=edge.find('mxGeometry');vertices=[c for c in cells if c.get('vertex')=='1'and c.get('id')not in('0','1')]
   for side in('source','target'):
    if edge.get(side):
     replacement=next(c.get('id')for c in vertices if c.get('id')!=edge.get(side));intervention=dict(edge=edge.get('id'),side=side,original_terminal=edge.get(side),wrong_terminal=replacement);edge.set(side,replacement);break
    point=geometry.find("mxPoint[@as='"+side+"Point']")
    if point is not None:
     old=float(point.get('x','0'));point.set('x',format(old+17,'.17g'));intervention=dict(edge=edge.get('id'),side=side,explicit_source_coordinate_delta=[17,0]);break
   assert intervention
  modified=ET.tostring(root,encoding='unicode');width,height=original['compiler_tikz_node_paint_viewport_v2']['frame']['reference_viewport'];bad_xml,export_proof,assets=produce(modified,width,height,work/name/'native_export')
  clean=R/'clean/tikz_node_paint_semantic_negative_controls_v1'/uuid.uuid4().hex;clean.mkdir(parents=True,exist_ok=False);record=copy.deepcopy(original);p=record['compiler_tikz_node_paint_viewport_v2'];p['files']=copy.deepcopy(p['files'])
  for key,(payload,extension)in assets.items():
   target=clean/(key+'.'+extension);common.immutable(target,payload);p['files'][key]=dict(file=str(target.relative_to(R)),sha256=common.sha(payload))
  bad_png=assets['native_export_after_png'][0];code=clean/'candidate.drawio';image=clean/'candidate.png';common.immutable(code,bad_xml.encode());common.immutable(image,bad_png);record.update(code_file=str(code.relative_to(R)),code_sha256=common.sha(bad_xml.encode()),image_file=str(image.relative_to(R)),image_sha256=common.sha(bad_png));p['candidate_code_sha256']=record['code_sha256'];p['files']['candidate_xml']=dict(file=record['code_file'],sha256=record['code_sha256']);p['files']['candidate_png']=dict(file=record['image_file'],sha256=record['image_sha256']);candidate=clean/'record.json';common.immutable(candidate,common.raw(record))
  reference=(R/record['original_reference']).read_bytes();registration(record,reference,bad_xml,R)
  old_png=(R/original['image_file']).read_bytes();old_image=Image.open(io.BytesIO(old_png)).convert('RGBA');new_image=Image.open(io.BytesIO(bad_png)).convert('RGBA');changed=old_image.size!=new_image.size or old_image.tobytes()!=new_image.tobytes();assert changed and record['code_sha256']!=original['code_sha256']and record['image_sha256']!=original['image_sha256']
  qa_dir=W/'prototype/candidate_quality_ro_v1'/('tikz_node_paint_semantic_negative_'+name+'_'+uuid.uuid4().hex);qa=quality.verify(identifier,candidate,R,contract.QUALITY_PLUGIN_FILE,qa_dir)
  source=qa.get('checks',{}).get('source_preliminary',{});reasons=[row.get('reason','')for row in source.get('failures',[])]
  assert qa.get('ok')is False and case.quality_failure_diagnosis(qa)['infrastructure_failure']is False
  assert 'reference_registration'in qa['checks']and'resources'in qa['checks']and any('fresh_source_geometry_text_marker_or_endpoint_changed'in reason for reason in reasons)
  negative.append(dict(name=name,id=identifier,intervention=intervention,candidate=common.asset(candidate),qa=common.asset(qa_dir/'report.json'),fresh_png=common.asset(image),source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],actual_rerendered_pixels_changed=True,code_and_image_rehashed=True,internally_consistent_export_contract_passed=True,independent_fresh_source_semantics_rejected=True,expected_source_reason='fresh_source_geometry_text_marker_or_endpoint_changed'))
 manifests=[]
 for identifier in IDS:
  record,qa,qa_path,candidate=records[identifier];source=json.loads(jobs[identifier][4]);manifest=case.publish(record,source,qa,qa_path.parent);manifests.append(manifest)
 with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:assert all(db.execute('select*from jobs where id=?',(identifier,)).fetchone()==job for identifier,job in jobs.items())
 after=history.collect(config,root=R,catalog=contract.CATALOG);history.validate(after,config,root=R);assert after==before
 common.immutable(OUTPUT/'qualified.jsonl',b''.join(common.raw(row)for row in manifests));common.immutable(OUTPUT/'normal_history_before.jsonl',b''.join(common.raw(row)for row in before));common.immutable(OUTPUT/'normal_history_after.jsonl',b''.join(common.raw(row)for row in after))
 precision_root=W/'tikz_node_paint_editing_precision_actual_controls_v1/3ed14449d355428497ea6890fc1a0740/proof.json';assert common.sha(precision_root.read_bytes())=='dd867a1f1df94aa147853b619657a7432dfcd0910923f485a1374b80277279da'
 proof=dict(schema='tikz_node_paint_QA5_complete_controls_v1',producer=common.asset(Path(__file__)),frozen_frontend=config,source_core=history.core_identity(config),quality_configuration=quality_cfg,positive_cases=positives,negative_cases=negative,qualified_manifest=common.asset(OUTPUT/'qualified.jsonl'),editing_precision_actual_controls=common.asset(precision_root),manual_catalog=common.asset(R/contract.CATALOG),normal_history_before=common.asset(OUTPUT/'normal_history_before.jsonl'),normal_history_after=common.asset(OUTPUT/'normal_history_after.jsonl'),same_core_normal_history=2,normal_frontend_calls=0,canonical_original_jobs_unchanged=True,model_calls=0,goal_complete=False)
 common.immutable(OUTPUT/'proof.json',common.raw(proof));print(json.dumps(common.asset(OUTPUT/'proof.json')),flush=True)

if __name__=='__main__':run()
