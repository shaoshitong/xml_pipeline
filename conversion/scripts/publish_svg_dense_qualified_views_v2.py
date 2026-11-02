"""Publish newly selected rich SVGs only with existing full8 and clean hashes."""
from pathlib import Path
import collections,concurrent.futures,datetime,hashlib,json,os,sqlite3,sys
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean/complexity_curation_20261102T054553Z_v1'
D=R/'clean/priority_svg_dense_source_screen_v2';sys.path[:0]=[str(R/'conversion/scripts'),str(R/'env')]
from priority_svg_dense_source_screen_v2 import features,select
from compiler_svg_general_iteration_case_v2 import full_quality
from compiler_iteration_inventory_v1 import check_manifest
FIELDS=[('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]
sha=lambda b:hashlib.sha256(b).hexdigest()
def raw(x):return (json.dumps(x,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode()
def rows(p):return [json.loads(l) for l in p.open() if l.strip()]
def path(name):
 p=Path(name);p=p if p.is_absolute() else R/p;p=p.resolve(strict=True)
 assert p.is_relative_to((R/'clean').resolve()) and p.is_file(),('payload_outside_clean',name)
 return p
def write(p,data):
 with p.open('xb') as f:f.write(data)
 return {'file':str(p.relative_to(R)),'sha256':sha(data),'bytes':len(data)}
def jsonlines(p,items):
 return {**write(p,b''.join((json.dumps(x,ensure_ascii=True,sort_keys=True)+'\n').encode() for x in items)),'rows':len(items)}
def canonical(ids):
 found={}
 with sqlite3.connect((R/'conversion/jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  db.execute('begin');keys=sorted(ids)
  for start in range(0,len(keys),400):
   batch=keys[start:start+400]
   found.update((i,json.loads(b)) for i,b in db.execute('select id,input_record from jobs where id in ('+','.join('?' for _ in batch)+')',batch))
 return found
def main():
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 out=C/('published_current_'+stamp+'_v4');out.mkdir();(out/'existing_QA').mkdir()
 screen=rows(D/'new_complex_candidates.jsonl');selection={x['id']:x for x in screen};policy=json.loads((D/'policy.json').read_text())
 assert policy['producer_sha256']==sha((R/'conversion/scripts/priority_svg_dense_source_screen_v2.py').read_bytes())
 current=json.loads((C/'current.json').read_text());basepath=R/current['views']['paired_priority_complex']['file']
 assert sha(basepath.read_bytes())==current['views']['paired_priority_complex']['sha256']
 base=rows(basepath);baseids={x['id'] for x in base};qualified={};provenance={}
 for q in rows(C/'qualified/input_manifest.jsonl'):
  if q['id'] in selection:qualified[q['id']]=q;provenance[q['id']]={'frozen_manifest':str((C/'qualified/input_manifest.jsonl').relative_to(R))}
 run=R/'release/compiler_iterations/runs/svg_general_coordinates_restored_20261101_round5_mass'
 with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True) as db:
  db.execute('begin')
  for i,b in db.execute("select id,result from samples where status='qualified'"):
   if i in selection:
    result=json.loads(b);qualified[i]=result['manifest'];provenance[i]={'ledger':str((run/'status.sqlite').relative_to(R)),'result_sha256':sha(b.encode()),'quality_report':result['quality_report']}
 source=canonical(set(qualified)|baseids);ready=[];audits=[];pending_errors=[]
 def audit(item):
  i,q=item
  try:
   c=selection[i];s=source[i];cache={};check_manifest(R,i,s,q,cache)
   assert (s['source'],s['format'],s['code_sha256'],s['image_sha256'])==(c['source'],c['source_format'],c['code_sha256_manifest'],c['image_sha256_manifest'])
   metadata=json.loads(path(q['metadata_file']).read_bytes())
   for k in ['id','source_pair_sha256','source_code_sha256','source_image_sha256','code_sha256','image_sha256']:assert metadata[k]==q[k],('metadata_identity',i,k)
   code=path(q['original_source_code']).read_bytes();f=features(code)
   assert f==c['source_layout_features_v2'] and select(f)==c['source_layout_rules_v2'] and select(f)
   qp=provenance[i].get('quality_report') or metadata.get('automatic_quality_audit')
   assert qp,('full8_report_locator_absent',i)
   reportpath=Path(qp);reportpath=reportpath if reportpath.is_absolute() else R/reportpath
   reportdata=reportpath.read_bytes();report=json.loads(reportdata);full_quality(report,metadata)
   assert report['id']==i and report['checks']['render']['image_sha256']==q['image_sha256'],('QA_identity_or_PNG_binding',i)
   proof=write(out/'existing_QA'/(i+'.json'),reportdata)
   accepted={**q,'curation':{'selection':'rich_SVG_source_layout_v2','source_prior_status':c['prior_curation_status'],
    'source_features':f,'source_reasons':c['source_layout_rules_v2'],'source_provenance':c['provenance'],
    'logical_graph_node_count_claimed':False,'scientific_merit_individually_certified':False,
    'source_screen_policy':str((D/'policy.json').relative_to(R)),'source_screen_policy_sha256':sha((D/'policy.json').read_bytes()),
    'existing_full8_QA_reverified':proof,'existing_qualification_authority':provenance[i],
    'new_conversion_or_QA_or_model_calls':0}}
   return accepted,{'id':i,'ok':True,'source_fresh_structural_features_exact':True,'full8_report_reverified':proof,
                   'required_asset_hashes':[{'field':a,'file':str(path(q[a]).relative_to(R)),'sha256':q[b]} for a,b in FIELDS]},None
  except Exception as e:return None,None,{'id':i,'state':'pending_asset_or_existing_QA_audit','reason':type(e).__name__+':'+str(e)[:1200]}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for q,a,e in pool.map(audit,qualified.items()):
   if q and q['id'] not in baseids:ready.append(q);audits.append(a)
   if e:pending_errors.append(e)
 # Keep the current published main's qualifications unchanged, recheck its five required files.
 def baseline(q):check_manifest(R,q['id'],source[q['id']],q,{});return q
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:base=list(pool.map(baseline,base))
 merged=sorted(base+ready,key=lambda r:r['id']);assert len({r['id'] for r in merged})==len(merged)
 done={q['id'] for q in ready};pending=[]
 for c in screen:
  if c['id'] in done or c['id'] in baseids:continue
  pending.append({**c,'conversion_target_state':'source_structurally_complex_conversion_pending','conversion_qualified':False})
 files={'paired_priority_complex':jsonlines(out/'paired_priority_complex.jsonl',merged),
        'new_structural_SVG_qualified':jsonlines(out/'new_structural_SVG_qualified.jsonl',ready),
        'additional_structural_SVG_targets':jsonlines(out/'additional_structural_SVG_targets.jsonl',pending),
        'new_SVG_existing_QA_asset_audit':jsonlines(out/'new_SVG_existing_QA_asset_audit.jsonl',audits),
        'qualification_audit_pending':jsonlines(out/'qualification_audit_pending.jsonl',pending_errors)}
 oldsummary=json.loads((R/current['summary']['file']).read_text());assert sha((R/current['summary']['file']).read_bytes())==current['summary']['sha256']
 summary={**oldsummary,'schema':'curated_current_original_reference_snapshot_v4','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'paired_priority_complex':len(merged),'paired_priority_by_source':dict(collections.Counter(q['source'] for q in merged)),
  'paired_priority_by_format':dict(collections.Counter(q['source_format'] for q in merged)),
  'additional_structurally_complex_SVG_sources':len(screen),'new_full8_qualified_structural_SVG_pairs':len(ready),
  'additional_pending_structural_SVG_targets':len(pending),'prior_main_preserved':len(base),
  'source_selection_change':'Rich complete research drawings need grouped/dense labels and layout; explicit logical graph metadata is not required. Glyph/path counts remain excluded as graph node counts.',
  'pending_complex_targets':oldsummary['pending_complex_targets']+len(pending),
  'pending_target_view_note':'Prior immutable pending overlay plus additional_structural_SVG_targets; source IDs are disjoint.',
  'qualification_audit_pending_count':len(pending_errors),'source_screen_summary':str((D/'summary.json').relative_to(R)),
  'files_new_in_this_snapshot':files,'new_conversions':0,'new_QA_calls':0,'new_models':0,'goal_complete':False}
 sf=write(out/'summary.json',raw(summary));previous=write(out/'previous_current_snapshot.json',raw(current))
 nextpointer={**current,'schema':'curated_current_pointer_v4','at_utc':summary['at_utc'],'snapshot':str(out.relative_to(R)),
  'summary':sf,'views':{**current['views'],**files},'paired_priority_complex':len(merged),
  'new_structurally_selected_SVG_qualified':len(ready),'additional_structural_SVG_pending':len(pending),'previous_current_snapshot':previous}
 nextpointer.pop('hash_inventory',None)
 q=C/'current.tmp.v4.json';q.write_bytes(raw(nextpointer));os.replace(q,C/'current.json')
 for p in out.rglob('*'):
  if p.is_file():p.chmod(0o444)
 print(json.dumps({'current':str(C/'current.json'),'main_pairs':len(merged),'previous_main':len(base),
 'new_full8_SVG_pairs':len(ready),'new_source_candidates':len(screen),'new_pending_SVG_targets':len(pending),
 'audit_pending':len(pending_errors),'files':files,'summary':sf,'new_conversion_QA_model_calls':0,'goal_complete':False}))
if __name__=='__main__':main()
