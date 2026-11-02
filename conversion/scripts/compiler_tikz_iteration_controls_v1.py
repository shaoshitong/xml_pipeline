"""Finite actual positive/negative controls before source-only fresh validation.

Negatives receive a newly rendered, internally valid integer-padding bundle,
not stale hashes. Only fresh full original-PGF/PDF replay may reject them. All
four must fail before already verified development positives are published.
"""
from pathlib import Path
import argparse,copy,fcntl,json,sqlite3,sys,uuid,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_tikz_poppler_source_v2 as compiler
import compiler_tikz_iteration_case_v1 as case
from compiler_tikz_quality_ro_v2 import verify
from compiler_types_program_v1 import asset,checked,immutable,raw,sha,atomic
from tikz_native_page_v1 import produce,STRICT
from native_worker import native
DIRECTORY=R/'release/compiler_iterations/controls/tikz_pdftex2025_v2_controls_20261101_v1'

def styles(cell):return dict(x.split('=',1) for x in cell.get('style','').split(';') if '=' in x)

def mutate(xml,name):
 root=ET.fromstring(xml);cells=list(root.iter('mxCell'));edges=[c for c in cells if c.get('edge')=='1'];arrow=[e for e in edges if any(styles(e).get(k,'none')!='none' for k in ('startArrow','endArrow'))]
 if not arrow:raise ValueError('source_negative_control_requires_actual_original_arrow')
 edge=arrow[0]
 if name=='delete_arrow':
  s=styles(edge);s.update(startArrow='none',endArrow='none');edge.set('style',';'.join(k+'='+v for k,v in s.items())+';')
 elif name=='change_endpoint':
  if edge.get('target'):
   candidates=[c.get('id') for c in cells if c.get('vertex')=='1' and c.get('id') not in (edge.get('source'),edge.get('target'))]
   if not candidates:raise ValueError('negative_control_requires_other_valid_vertex')
   edge.set('target',candidates[0])
  else:
   p=edge.find("mxGeometry/mxPoint[@as='targetPoint']");assert p is not None;p.set('x',str(float(p.get('x'))+17))
 elif name=='delete_text':next(c for c in cells if c.get('value','').strip()).set('value','')
 elif name=='opaque_text_mask':
  text=next(c for c in cells if c.get('value','').strip());g=copy.deepcopy(text.find('mxGeometry'));g.set('as','geometry')
  mask=ET.SubElement(root.find('.//mxGraphModel/root'),'mxCell',{'id':'tikz_source_negative_opaque_mask','parent':text.get('parent','1'),'vertex':'1','style':'fillColor=#FFFFFF;strokeColor=none;opacity=100;fillOpacity=100;' });mask.append(g)
 else:raise ValueError('unknown_negative_source_mutation')
 return ET.tostring(root,encoding='unicode')

def main(development):
 development=Path(development).resolve(strict=True);assert development.is_relative_to(W/compiler.VERSION/'development')
 report=json.loads(development.read_bytes());assert report['unseen_consumed']==report['model_calls']==0
 rows=sorted((x for x in report['records'] if x.get('independent_quality_ok') is True),key=lambda x:x['id'])
 if not rows:raise ValueError('actual_full_quality_development_positive_required')
 DIRECTORY.mkdir(parents=True,exist_ok=False)
 with (DIRECTORY/'producer.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);config=compiler.configuration()
  proof={'schema':'compiler_tikz_iteration_controls_v1','producer':asset(__file__),'development':asset(development),'frozen_frontend':config,'positives':[],'negatives':[],'positive_cases':[],'negative_cases':[],'model_calls':0,'unseen_consumed':0,'canonical_mutations':0,'qualified_manifest':None}
  chosen=rows[:2];records=[]
  for row in chosen:
   record=json.loads(Path(row['record_file']).read_bytes());qa=json.loads(Path(row['quality_report']).read_bytes());case.full_quality(qa,record)
   assert qa['input_record_sha256']==asset(row['record_file'])['sha256'];records.append(record)
   proof['positives'].append(asset(row['quality_report']));proof['positive_cases'].append({'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':asset(row['record_file']),'qa':asset(row['quality_report'])})
  base=next(r for r in records if any(any(styles(e).get(k,'none')!='none' for k in ('startArrow','endArrow')) for e in ET.fromstring((R/r[compiler.FIELD]['files']['unshifted_native_xml']['file']).read_text()).iter('mxCell') if e.get('edge')=='1'))
  original=(R/base[compiler.FIELD]['files']['unshifted_native_xml']['file']).read_text();source_canvas=json.loads((R/base[compiler.FIELD]['files']['native_padding_proof']['file']).read_bytes())['source_canvas']
  for name in ('delete_arrow','change_endpoint','delete_text','opaque_text_mask'):
   raw_xml=mutate(original,name);work=W/compiler.VERSION/'controls'/(name+'_'+uuid.uuid4().hex);changed,padding,payloads=produce(raw_xml,*source_canvas,work)
   model=ET.fromstring(changed).find('.//mxGraphModel');width,height=[int(model.get(k)) for k in ('pageWidth','pageHeight')]
   rendered=native.native_job(changed,width,height,180,STRICT,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert rendered.get('ok')
   from strict_canvas_gate import require_declared_page
   require_declared_page(rendered['native_render'],width,height)
   payloads.update(candidate_xml=(changed.encode(),'drawio'),candidate_png=(rendered['png'],'png'))
   target=R/'clean/compiler_tikz_iteration_controls_v1'/base['id']/name;target.mkdir(parents=True,exist_ok=False);record=copy.deepcopy(base)
   for key,(data,extension) in payloads.items():
    p=target/(key+'.'+extension);immutable(p,data);record[compiler.FIELD]['files'][key]={'file':str(p.relative_to(R)),'sha256':sha(data)}
   record.update(code_file=str((target/'candidate_xml.drawio').relative_to(R)),code_sha256=sha(changed.encode()),image_file=str((target/'candidate_png.png').relative_to(R)),image_sha256=sha(rendered['png']),accepted=False,quality_state='actual_rehashed_original_source_negative_never_accepted')
   record[compiler.FIELD]['candidate_code_sha256']=record['code_sha256'];immutable(target/'record.json',raw(record))
   quality_work=W/'prototype/candidate_quality_ro_v1'/('tikz_actual_negative_'+name+'_'+uuid.uuid4().hex);qa=verify(record['id'],target/'record.json',R,Path(compiler.__file__),quality_work)
   source=qa.get('checks',{}).get('source_preliminary',{})
   if qa.get('ok') is not False or source.get('ok') is not False or not any(x.get('reason')=='fresh_source_geometry_text_marker_or_endpoint_changed' for x in source.get('failures',[])):
    atomic(DIRECTORY/'invalid_control.json',{'name':name,'qa':qa});raise ValueError('actual_negative_not_rejected_by_complete_fresh_original_source:'+name)
   proof['negatives'].append(asset(qa['evidence_file']));proof['negative_cases'].append({'name':name,'id':record['id'],'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'candidate':asset(target/'record.json'),'qa':asset(qa['evidence_file']),'new_valid_whole_graph_padding_proof':True,'rehashed_XML_and_actual_native_PNG':True})
   atomic(DIRECTORY/'progress.json',{'positives_verified':len(chosen),'negatives_rejected':len(proof['negatives']),'published':False});print(json.dumps({'mutation':name,'ok':qa['ok'],'intended_fresh_source_rejected':True}),flush=True)
  manifests=[]
  with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
   for row,record in zip(chosen,records):
    job=db.execute('select * from jobs where id=?',(record['id'],)).fetchone();source=json.loads(job[4]);qa=json.loads(Path(row['quality_report']).read_bytes());manifests.append(case.publish(record,source,qa,Path(row['quality_report']).parent));assert db.execute('select * from jobs where id=?',(record['id'],)).fetchone()==job
  immutable(DIRECTORY/'qualified.jsonl',b''.join(raw(x) for x in manifests));proof['qualified_manifest']=asset(DIRECTORY/'qualified.jsonl');assert compiler.configuration()==config;immutable(DIRECTORY/'proof.json',raw(proof));print(json.dumps({'proof':str(DIRECTORY/'proof.json'),'positive_qualified':len(manifests),'actual_rehashed_source_negatives':len(proof['negatives']),'new_heldout_dispatched':False}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--development-report',type=Path,required=True);args=p.parse_args();main(args.development_report)
