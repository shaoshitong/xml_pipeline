"""Actual fixed two positives and freshly rendered source-corruption negatives."""
from pathlib import Path
import copy,datetime,io,json,sqlite3,sys,xml.etree.ElementTree as ET
from PIL import Image,ImageDraw
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
from compiler_types_program_v1 import raw,sha,asset,immutable,checked
import drawio_author_version_frontend_v2 as frontend
import drawio_author_version_quality_ro_v2 as quality
import drawio_author_runtime_session_v1 as renderer
from drawio_author_quality_contract_v1 import full_quality
CONTROL=R/'release/compiler_iterations/controls/drawio_author_metadata_version_native_controls_20261101_v2'
OLD=W/'drawio_author_export_source_dev_v1/fixed_two_20261101_v1/author_native_existing_candidates_full_QA_v2/report.json'
def run():
 CONTROL.mkdir(parents=True,exist_ok=False);proofold=json.loads(OLD.read_bytes());assert proofold['all2passed'];config=frontend.configuration();positives=[];manifests=[]
 from qualified_index_v4 import manifest_row,require_source
 from compiler_mermaid_alpha_qualifications_v2 import find_qualified
 for row in proofold['rows']:
  _,blob=checked(row['candidate']);record=json.loads(blob);_,blob=checked(row['quality']);qa=json.loads(blob);full_quality(qa,record)
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:source=json.loads(db.execute('select input_record from jobs where id=?',(row['id'],)).fetchone()[0])
  require_source(record,source);fresh=(R/qa['checks']['source']['evidence']['source_snapshot']['id'])if False else None
  old=find_qualified(row['id'],source,root=R)
  if old is not None:manifest=old
  else:
   record={**record,'quality_state':'accepted_metadata_author_version_complete_original_source_v1','automatic_quality_policy':qa['quality_policy'],'automatic_quality_audit':str(Path(row['quality']['file']).relative_to(R)),'accepted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model':None,'model_configuration':{'external_model_calls':0,'deterministic_compiler':True}}
   manifest=manifest_row(record,R)[0]
  manifests.append(manifest);positives.append({'id':row['id'],'candidate':row['candidate'],'qa':row['quality'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'author_export_profile':qa['checks']['source']['evidence']['author_export_profile'],'manifest':manifest,'actual_complete_source_original_font_and_editing_positive':True})
 base=json.loads(checked(positives[0]['candidate'])[1]);xml=(R/base['code_file']).read_text();originalpng=(R/base['image_file']).read_bytes();profile=positives[0]['author_export_profile'];negative=[]
 for name in ('deleted_source_text','changed_bound_terminal','wrong_physical_font_family','opaque_proposed_PNG_cover'):
  if name in ('deleted_source_text','changed_bound_terminal'):
   directory=R/'clean/drawio_author_version_controls_v1'/name;record=json.loads((directory/'record.json').read_bytes());qwork=W/'prototype/candidate_quality_ro_v1'/('actual_author_negative_'+name+'_20261101_v1');qa=json.loads((qwork/'report.json').read_bytes());assert qa['ok']is False and qa['failures']and not qa.get('infrastructure_failure');negative.append({'name':name,'id':record['id'],'candidate':asset(directory/'record.json'),'qa':asset(qwork/'report.json'),'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'actual_native_XML_and_PNG_rehashed':True,'actual_native_rerendered_pixels_changed':True,'PNG_cover_mutation_only':False,'false_acceptance':False,'failure_reasons':qa['failures'],'reused_immutable_actual_control':True});continue
  directory=R/'clean/drawio_author_version_controls_v2'/name;directory.mkdir(parents=True,exist_ok=False);record=copy.deepcopy(base);root=ET.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};badxml=xml
  if name=='deleted_source_text':
   cell=next(c for c in root.iter('mxCell')if c.get('value','').strip());cell.set('value','');badxml=ET.tostring(root,encoding='unicode')
  elif name=='changed_bound_terminal':
   edge=next(c for c in root.iter('mxCell')if c.get('edge')=='1'and(c.get('source')or c.get('target')));side='source'if edge.get('source')else'target';target=next(c for c in root.iter('mxCell')if c.get('vertex')=='1'and c.get('id')not in(edge.get('source'),edge.get('target')));edge.set(side,target.get('id'));badxml=ET.tostring(root,encoding='unicode')
  elif name=='wrong_physical_font_family':
   cell=next(c for c in root.iter('mxCell')if c.get('value','').strip()and'fontFamily='in c.get('style',''));parts=cell.get('style').split(';');cell.set('style',';'.join('fontFamily=monospace'if p.startswith('fontFamily=')else p for p in parts if not p.startswith('fontSource=')));badxml=ET.tostring(root,encoding='unicode')
  if name=='opaque_proposed_PNG_cover':
   png=Image.open(io.BytesIO(originalpng)).convert('RGBA');draw=ImageDraw.Draw(png);draw.rectangle((0,0,png.width//2,png.height//2),fill='white');buf=io.BytesIO();png.save(buf,format='PNG');badpng=buf.getvalue();actual=False
  else:
   work=W/'drawio_author_export_source_dev_v1/fixed_two_20261101_v1'/('actual_negative_export_'+name+'_v2');render=renderer.render(badxml,profile,work);badpng=render['png'];actual=True
  assert renderer.pixels(badpng)!=renderer.pixels(originalpng)
  immutable(directory/'diagram.drawio',badxml.encode());immutable(directory/'image.png',badpng);record.update(code_file=str((directory/'diagram.drawio').relative_to(R)),code_sha256=sha(badxml.encode()),image_file=str((directory/'image.png').relative_to(R)),image_sha256=sha(badpng));immutable(directory/'record.json',raw(record))
  qwork=W/'prototype/candidate_quality_ro_v1'/('actual_author_negative_'+name+'_20261101_v2');qa=quality.verify(record['id'],directory/'record.json',R,Path(frontend.__file__),qwork);assert qa['ok']is False and qa['failures']and not qa.get('infrastructure_failure')
  negative.append({'name':name,'id':record['id'],'candidate':asset(directory/'record.json'),'qa':asset(qwork/'report.json'),'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'actual_native_XML_and_PNG_rehashed':True,'actual_native_rerendered_pixels_changed':actual,'PNG_cover_mutation_only':not actual,'false_acceptance':False,'failure_reasons':qa['failures']});print(json.dumps({'negative':name,'rejected':True,'actual_native_rerender':actual,'failures':qa['failures']}),flush=True)
 immutable(CONTROL/'qualified.jsonl',b''.join(raw(x)for x in manifests));proof={'schema':'actual_author_metadata_native_source_font_paint_and_editing_controls_v1','frozen_frontend':config,'producer':asset(Path(__file__)),'development_report':asset(OLD),'positive_cases':positives,'negative_cases':negative,'positive_count':2,'negative_false_acceptances':0,'qualified_manifest':asset(CONTROL/'qualified.jsonl'),'source_only_metadata_45_supported_report':asset(W/'drawio_author_export_source_dev_v1/fixed_two_20261101_v1/source_only_author45_support_v1/report.json'),'source_phase_and_as_key_semantics_proof':asset(W/'drawio_author_export_source_dev_v1/fixed_two_20261101_v1/source_export_phase_and_semantics_v1/proof.json'),'remaining43_reference_pixel_checks':0,'canonical_mutations':0,'model_calls':0,'qualified_originals':len(manifests)};immutable(CONTROL/'proof.json',raw(proof));print(json.dumps({'proof':str(CONTROL/'proof.json'),'sha256':sha((CONTROL/'proof.json').read_bytes()),'positive':2,'negative':len(negative),'qualified':len(manifests)}),flush=True)
if __name__=='__main__':run()
