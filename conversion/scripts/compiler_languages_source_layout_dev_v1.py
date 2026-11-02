"""Exactly six prior-excluded development cases plus two seen regressions.

No heldout read, reselection, model, publication or canonical database writes.
All media and source remain on HKUST. Stdout contains compact metadata only.
"""
import argparse,copy,datetime,hashlib,json,os,sqlite3,subprocess,sys,uuid
from pathlib import Path
import xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_languages_source_layout_v1 as compiler
sha=compiler.sha;raw=compiler.raw
REGRESSIONS={'mermaid':'0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641','plantuml':'741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd'}

def case(identifier,work):
 db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30);db.execute('pragma query_only=ON')
 cols=[x[1] for x in db.execute('pragma table_info(jobs)')];snapshot=db.execute('select * from jobs where id=?',(identifier,)).fetchone();job=dict(zip(cols,snapshot));old=json.loads(job['output_record']) if job['output_record'] else {}
 result=compiler.convert(old,job,work/'convert');summary={'id':identifier,'format':job['format'],'converted':result.get('ok'), 'reason':result.get('reason'),'source_reproduction':result.get('source_reproduction'),'detail':result.get('detail'),'model_calls':0,'full_QA_executed':False,'negatives':[]}
 if result.get('ok'):
  record=result['record'];xml=(R/record['code_file']).read_text();summary['source_validation']=compiler.validate_source(record,xml);summary['fresh_source_reproduction']=compiler.source_reproduction(record,work/'fresh_source')
  summary['native_editing']=compiler.audit_editing(record,xml,summary['source_validation'],R)
  summary['native_editing']={k:v for k,v in summary['native_editing'].items() if k!='details'}
  from deterministic_candidate_quality_ro_v1 import verify
  qwork=W/'prototype/candidate_quality_ro_v1'/('languages_source_layout_dev_'+identifier[:12]+'_'+uuid.uuid4().hex)
  quality=verify(identifier,result['record_file'],R,Path(compiler.__file__),qwork)
  summary.update(full_QA_executed=True,full_QA_ok=quality['ok'],full_QA_failures=quality['failures'],full_QA_report=quality['evidence_file'])
  def mutate(name,change):
   root=ET.fromstring(xml);change(root);changed=ET.tostring(root,encoding='unicode');r=copy.deepcopy(record);r['code_sha256']=sha(changed.encode());r[compiler.FIELD]['candidate_code_sha256']=r['code_sha256']
   # Rehash the submitted revision to exercise independent source replay rather
   # than merely failing the producer's candidate checksum.
   v=compiler.validate_source(r,changed);summary['negatives'].append({'case':name,'rehashed_submission':True,'rejected':not v['ok'],'failures':v['failures']})
  mutate('delete_source_label',lambda root:next(c for c in root.iter('mxCell') if c.get('value','').strip()).set('value',''))
  def change_edge(root):
   e=next(c for c in root.iter('mxCell') if c.get('edge')=='1');targets=[c.get('id') for c in root.iter('mxCell') if c.get('vertex')=='1' and c.get('id') not in (e.get('source'),e.get('target'))];e.set('target',targets[0] if targets else e.get('source'))
  mutate('change_source_edge_target',change_edge)
  def cover(root):
   container=root.find('.//mxGraphModel/root');cell=next(c for c in root.iter('mxCell') if c.get('value','').strip());g=cell.find('mxGeometry');mask=ET.SubElement(container,'mxCell',{'id':'negative_opaque_mask','vertex':'1','parent':cell.get('parent','1'),'style':'fillColor=#FFFFFF;strokeColor=none;opacity=100;'});ET.SubElement(mask,'mxGeometry',{**dict(g.attrib),'as':'geometry'})
  mutate('cover_source_text_with_opaque_object',cover)
  summary['all_negatives_rejected']=all(x['rejected'] for x in summary['negatives'])
 require_same=db.execute('select * from jobs where id=?',(identifier,)).fetchone()==snapshot;db.close();summary['canonical_job_unchanged']=require_same
 (work/'case_summary.json').write_bytes(raw(summary));print(json.dumps({k:v for k,v in summary.items() if k not in ('native_editing','negatives','source_validation','fresh_source_reproduction')},ensure_ascii=False),flush=True)
 return summary

def main():
 p=argparse.ArgumentParser();p.add_argument('--id');p.add_argument('--work');a=p.parse_args()
 if a.id:
  work=Path(a.work);work.mkdir(parents=True,exist_ok=False);case(a.id,work);return
 roster=W/'compiler_native_languages_v1_development/additional_seen_development_ids.jsonl';selected=[json.loads(x) for x in roster.open()]
 assert len(selected)==6 and all(sum(x['language']==k for x in selected)==3 for k in REGRESSIONS)
 fixed=[{'id':x['id'],'format':x['language'],'role':'prior_excluded_development'} for x in selected]+[{'id':v,'format':k,'role':'previously_seen_successful_regression'} for k,v in REGRESSIONS.items()]
 assert len({r['id'] for r in fixed})==8
 base=W/compiler.VERSION/'development'/uuid.uuid4().hex;base.mkdir(parents=True);config=compiler.configuration()
 (base/'selected_metadata.json').write_bytes(raw({'cases':fixed,'selection':'Predeclared existing six IDs and two historical seen regression IDs; no replacements','prior_roster':str(roster),'prior_roster_sha256':sha(roster.read_bytes()),'configuration':config,'unseen_executions':0,'models_called':0}))
 print(json.dumps({'development_directory':str(base),'case_count':8,'ids':fixed,'policy':config['policy']}),flush=True)
 results=[]
 for row in fixed:
  work=base/row['id'];cmd=[sys.executable,str(Path(__file__).resolve()),'--id',row['id'],'--work',str(work)]
  try:
   proc=subprocess.run(cmd,capture_output=True,text=True,timeout=300,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
   if work.exists():(work/'child.stdout').write_text(proc.stdout);(work/'child.stderr').write_text(proc.stderr)
   path=work/'case_summary.json'
   result=json.loads(path.read_bytes()) if path.exists() else {**row,'converted':False,'reason':'bounded_development_process_failed','returncode':proc.returncode,'error':proc.stderr[-1500:]}
  except subprocess.TimeoutExpired:result={**row,'converted':False,'reason':'bounded_development_timeout'}
  results.append(result);print(json.dumps({'id':row['id'],'format':row['format'],'converted':result.get('converted'),'reason':result.get('reason'),'full_QA_ok':result.get('full_QA_ok'),'canonical_job_unchanged':result.get('canonical_job_unchanged')}),flush=True)
 config_after=compiler.configuration();assert config==config_after,'implementation_changed_during_development'
 units={}
 for fmt,unit in compiler.UNITS.items():
  items=[r for r in results if r.get('format')==fmt];passed=all(r.get('converted') and r.get('full_QA_ok') and r.get('all_negatives_rejected') and r.get('canonical_job_unchanged') for r in items)
  units[unit]={'ready_for_unseen':passed,'state':'development_passed_pending_root_freeze' if passed else 'development_not_ready','cases':len(items),'converted':sum(bool(r.get('converted')) for r in items),'full_QA_passed':sum(bool(r.get('full_QA_ok')) for r in items)}
 report={'version':'languages_source_layout_finite_development_v1','units':units,'results':results,'configuration':config,'configuration_unchanged':config==config_after,'unseen_consumed':0,'model_calls':0,'automatic_rollout':False,'canonical_mutations':0,'new_module':str(Path(compiler.__file__).resolve()),'development_directory':str(base)}
 (base/'report.json').write_bytes(raw(report));print(json.dumps({'report':str(base/'report.json'),'units':units,'unseen_consumed':0,'model_calls':0}),flush=True)

if __name__=='__main__':main()
