"""Finite actual-QA controls for the frozen Mermaid CLI compiler.

Publishes only the already verified three development positives. Four corrupted
but well-formed, rehashed XML/actual-PNG pairs must fail the independent source
replay. This never selects or exposes a new heldout source or writes jobs.
"""
import copy,fcntl,json,os,sqlite3,sys,uuid,xml.etree.ElementTree as ET
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_languages_source_layout_v3 as compiler
import compiler_mermaid_iteration_case_v1 as case
from compiler_types_program_v1 import asset,checked,immutable,raw,sha,atomic
from deterministic_candidate_quality_ro_v1 import verify
from native_worker import native
from PIL import Image

DIRECTORY=R/'release/compiler_iterations/controls/mermaid_cli_export_v3_controls_20261101_v1'
DEVELOPMENT=W/'compiler_languages_source_layout_v3/development/4b4ba8956dbc433e99ba30c80016fb2b/official_QA.json'

def mutate(xml,name):
 root=ET.fromstring(xml);cells=list(root.iter('mxCell'));edge=next(c for c in cells if c.get('edge')=='1')
 if name=='delete_arrow':
  pairs=[x for x in edge.get('style','').split(';') if x and not x.startswith(('startArrow=','endArrow='))];edge.set('style',';'.join(pairs)+';startArrow=none;endArrow=none;')
 elif name=='change_endpoint':edge.set('target',edge.get('source'))
 elif name=='delete_text':next(c for c in cells if c.get('value','').strip()).set('value','')
 elif name=='opaque_text_mask':
  text=next(c for c in cells if c.get('value','').strip());parent=text.get('parent','1');g=copy.deepcopy(text.find('mxGeometry'));g.set('as','geometry');mask=ET.SubElement(root.find('.//mxGraphModel/root'),'mxCell',{'id':'mermaid_negative_source_text_mask','parent':parent,'vertex':'1','style':'fillColor=#FFFFFF;strokeColor=none;opacity=100;fillOpacity=100;'});mask.append(g)
 else:raise ValueError('unknown_control_mutation')
 return ET.tostring(root,encoding='unicode')

def main():
 DIRECTORY.mkdir(parents=True,exist_ok=False)
 with (DIRECTORY/'producer.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  config=compiler.configuration();proof={'schema':'compiler_mermaid_iteration_controls_v1','producer':asset(__file__),'development':asset(DEVELOPMENT),'frozen_frontend':config,'positives':[],'negatives':[],'positive_cases':[],'negative_cases':[],'model_calls':0,'unseen_consumed':0,'canonical_mutations':0,'qualified_manifest':None}
  positives=json.loads(DEVELOPMENT.read_bytes())['results'];assert len(positives)==3 and all(x['ok'] for x in positives)
  manifests=[]
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
   for item in positives:
    record=json.loads(Path(item['record_file']).read_bytes());qa=json.loads(Path(item['evidence_file']).read_bytes());case.full_quality(qa,record);source=json.loads(db.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()[0]);manifest=case.publish(record,source,qa,Path(item['evidence_file']).parent);manifests.append(manifest);proof['positives'].append(asset(item['evidence_file']));proof['positive_cases'].append({'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':asset(item['record_file']),'qa':asset(item['evidence_file'])})
  payload=b''.join(raw(x) for x in manifests);immutable(DIRECTORY/'qualified.jsonl',payload);proof['qualified_manifest']=asset(DIRECTORY/'qualified.jsonl')
  record=json.loads(Path(positives[0]['record_file']).read_bytes());xml=(R/record['code_file']).read_text();width,height=Image.open(R/record['image_file']).size
  for name in ('delete_arrow','change_endpoint','delete_text','opaque_text_mask'):
   changed=mutate(xml,name);rr=copy.deepcopy(record);rr['code_sha256']=sha(changed.encode());rr[compiler.FIELD]['candidate_code_sha256']=rr['code_sha256']
   target=R/'clean/compiler_mermaid_iteration_controls_v1'/record['id']/name;target.mkdir(parents=True,exist_ok=False);immutable(target/'candidate.drawio',changed.encode())
   render=native.native_job(changed,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
   if not render.get('ok'):raise RuntimeError('control_actual_native_render_failed:'+name)
   immutable(target/'candidate.png',render['png']);rr.update(code_file=str((target/'candidate.drawio').relative_to(R)),image_file=str((target/'candidate.png').relative_to(R)),image_sha256=sha(render['png']),accepted=False,quality_state='corrupted_rehashed_source_negative_control_never_accepted')
   immutable(target/'record.json',raw(rr));work=W/'prototype/candidate_quality_ro_v1'/('mermaid_cli_control_'+name+'_'+uuid.uuid4().hex);qa=verify(rr['id'],target/'record.json',R,Path(compiler.__file__),work)
   profile=qa.get('checks',{}).get('source_preliminary') or qa.get('checks',{}).get('source') or {}
   if qa.get('ok') is not False or not qa.get('failures') or profile.get('ok') is not False or not any(x.get('reason')=='source_geometry_text_or_paint_changed' for x in profile.get('failures',[])):
    atomic(DIRECTORY/'rejected_controls.json',{'name':name,'qa':qa});raise ValueError('negative_not_rejected_by_fresh_original_source_replay:'+name)
   proof['negatives'].append(asset(qa['evidence_file']));proof['negative_cases'].append({'name':name,'id':rr['id'],'source_code_sha256':rr['source_code_sha256'],'source_image_sha256':rr['source_image_sha256'],'candidate':asset(target/'record.json'),'qa':asset(qa['evidence_file']),'rehashed_XML_and_actual_native_PNG':True,'intended_fresh_source_rejection':True});atomic(DIRECTORY/'progress.json',{'positive':len(proof['positives']),'negative':len(proof['negatives']),'models':0,'unseen_consumed':0});print(json.dumps({'control':name,'ok':qa['ok'],'failure':qa['failures'],'actual_fresh_source_rejected':True}),flush=True)
  assert compiler.configuration()==config
  immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':str(DIRECTORY/'proof.json'),'qualified_development_controls':len(manifests),'actual_negatives':len(proof['negatives']),'model_calls':0,'heldout_dispatched':False}),flush=True)

if __name__=='__main__':main()
