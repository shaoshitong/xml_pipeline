"""Finite two source-pass seen candidate controls; original four stay reported.

No unseen selection, model calls, canonical mutation or acceptance. B and C use
the identical independent source checker; C metadata is never required.
"""
import copy,json,sqlite3,sys,uuid
from pathlib import Path
import xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_plantuml_natural_candidate_v7 as c
IDS=('05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798','741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd')
SOURCE_REPORT=W/'compiler_plantuml_integer_canvas_v2/development/3ddd68f2bca74f3789c733f0131185c6/report.json'

def compact(result):
 return {'ok':result['ok'],'supported':result.get('supported'),'failures':result.get('failures'),
         'markers':result.get('evidence',{}).get('source_native_markers'),'producer_Cproof_consulted':result.get('evidence',{}).get('producer_Cproof_consulted')}

def main():
 config=c.configuration();base=W/c.VERSION/'development'/uuid.uuid4().hex;base.mkdir(parents=True);db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30);db.execute('pragma query_only=ON');results=[]
 selection={'ids':list(IDS),'reason':'Continue exactly the two fixed already-seen source-pass controls; original four source outcomes preserved unchanged; no unseen selection','original_source_report':str(SOURCE_REPORT),'original_source_report_sha256':c.sha(SOURCE_REPORT.read_bytes()),'configuration':config};(base/'selection.json').write_bytes(c.raw(selection));print(json.dumps({'development_directory':str(base),'ids':list(IDS),'policy':config['policy']}),flush=True)
 for identifier in IDS:
  work=base/identifier;work.mkdir();columns=[r[1] for r in db.execute('pragma table_info(jobs)')];snapshot=db.execute('select * from jobs where id=?',(identifier,)).fetchone();job=dict(zip(columns,snapshot));old=json.loads(job['output_record']);row={'id':identifier,'baseline_source_checker':None,'candidate_source_checker':None,'negatives':[],'target_full_QA_executed':False,'model_calls':0}
  # B is evaluated directly from preserved original source and its actual XML,
  # with no C proof field or source-layout producer metadata requirement.
  bxml=(R/old['code_file']).read_text();bcheck=c.validate_source(old,bxml);(work/'baseline_source_check.json').write_bytes(c.raw(bcheck));row['baseline_source_checker']=compact(bcheck)
  attempt=c.convert(old,job,work/'candidate');row['candidate_produced']=attempt['ok'];row['conversion_reason']=attempt.get('reason');row['conversion_detail']=attempt.get('detail')
  if attempt['ok']:
   record=attempt['record'];xml=(R/record['code_file']).read_text();check=c.validate_source(record,xml);(work/'candidate_source_check.json').write_bytes(c.raw(check));row['candidate_source_checker']=compact(check);row['candidate_record']=attempt['record_file']
   # Cell-ID renaming must not depend on C source tags or expected XML bytes.
   root=ET.fromstring(xml);mapping={cell.get('id'):'renamed_'+cell.get('id') for cell in root.iter('mxCell') if cell.get('id') not in ('0','1')}
   for cell in root.iter('mxCell'):
    for k in ('id','parent','source','target'):
     if cell.get(k) in mapping:cell.set(k,mapping[cell.get(k)])
   renamed=ET.tostring(root,encoding='unicode');r=copy.deepcopy(record);r['code_sha256']=c.sha(renamed.encode());renamecheck=c.validate_source(r,renamed);(work/'renamed_source_check.json').write_bytes(c.raw(renamecheck));row['renamed_ID_control']=compact(renamecheck)
   def negative(name,change):
    tree=ET.fromstring(xml);change(tree);changed=ET.tostring(tree,encoding='unicode');r=copy.deepcopy(record);r['code_sha256']=c.sha(changed.encode());v=c.validate_source(r,changed);(work/(name+'.json')).write_bytes(c.raw(v));row['negatives'].append({'case':name,'rehashed_candidate':True,'producer_proof_required':False,'rejected':not v['ok'],'failures':v['failures']})
   negative('deleted_source_label',lambda root:next(cell for cell in root.iter('mxCell') if cell.get('value','').strip()).set('value',''))
   def edge(root):
    e=next(cell for cell in root.iter('mxCell') if cell.get('edge')=='1');e.set('target',e.get('source'))
   negative('changed_edge_terminal',edge)
   def cover(root):
    model=root.find('.//mxGraphModel/root');t=next(cell for cell in root.iter('mxCell') if cell.get('value','').strip());g=t.find('mxGeometry');mask=ET.SubElement(model,'mxCell',{'id':'opaque_negative','vertex':'1','parent':t.get('parent','1'),'style':'fillColor=#FFFFFF;strokeColor=none;opacity=100;'});ET.SubElement(mask,'mxGeometry',dict(g.attrib))
   negative('opaque_text_cover',cover)
   negative('source_font_changed',lambda root:next(cell for cell in root.iter('mxCell') if cell.get('value','').strip()).set('style','shape=text;fillColor=none;strokeColor=none;fontFamily=Arial;fontSize=14;'))
   from deterministic_candidate_quality_ro_v1 import verify
   quality=verify(identifier,attempt['record_file'],R,Path(c.__file__),W/'prototype/candidate_quality_ro_v1'/('plantuml_natural_v7_'+identifier[:12]+'_'+uuid.uuid4().hex));row.update(target_full_QA_executed=True,target_full_QA_ok=quality['ok'],target_full_QA_failures=quality['failures'],target_full_QA_report=quality['evidence_file'])
  row['canonical_job_unchanged']=db.execute('select * from jobs where id=?',(identifier,)).fetchone()==snapshot;results.append(row);(work/'summary.json').write_bytes(c.raw(row));print(json.dumps(row),flush=True)
 db.close();unchanged=c.configuration()==config;report={'version':'plantuml_natural_finite_candidate_development_v7','unit':c.UNIT,'configuration':config,'configuration_unchanged':unchanged,'original_four_source_report':str(SOURCE_REPORT),'original_four_results_retained':True,'results':results,'state':'development_passed_pending_root_freeze' if unchanged and all(r.get('target_full_QA_ok') and all(n['rejected'] for n in r['negatives']) and r['canonical_job_unchanged'] for r in results) else 'development_not_ready','unseen_consumed':0,'new_model_calls':0,'canonical_mutations':0,'automatic_rollout':False,'report':str(base/'report.json')};(base/'report.json').write_bytes(c.raw(report));print(json.dumps({k:v for k,v in report.items() if k not in ('configuration','results')}),flush=True)

if __name__=='__main__':main()
