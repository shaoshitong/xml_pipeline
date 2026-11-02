"""Read-only factual path inventory for the completed PGF execution cohort.

No classification is an acceptance rule or a claim of semantic intent. In
particular, closed paint with an inherited arrow flag is not counted as an
unresolved open connector; an unarrowed numeric line may be an axis, decoration,
plot segment, leader, or real connection. All such cases retain v1 gates.
"""
import argparse,collections,datetime,hashlib,json,os,re,sqlite3
from pathlib import Path
from tikz_execution_graph import ROLES,parse_events

R=Path(os.environ.get('IMG2CODE_ROOT','/backup/shaoshitong/img2code_20261029')).resolve()
W=R/'conversion'
POLICY='pgf_execution_candidate_v1:bc199b55e7dc7b08836f'
SOFT=re.compile(r'\\pgfsyssoftpath@([A-Za-z]+)token')
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda b:hashlib.sha256(b).hexdigest()

CATEGORY_DESCRIPTIONS={
 'incomplete_path_finish_coverage':'The trace did not provide exactly one finish event for this path.',
 'no_path_softpaint_node_or_empty':'No main-path softpath and no operations; nodes may have painted independently.',
 'no_path_softpaint_cursor_only':'No main-path softpath; only move operations were executed. This does not assert semantic connectivity.',
 'no_path_softpaint_nonmove_operations':'No main-path softpath despite nonmove operations; keep unresolved.',
 'softpath_move_only':'A softpath contains only moves/rounding metadata, without a recorded line/curve/closed segment.',
 'closed_paint_candidate':'A closepath or rectangle operator exists. This may be a region, box, decoration, or another closed paint shape; arrow flags do not decide intent.',
 'open_arrow_terminal_unresolved':'An open softpath has an arrow flag and numeric/mixed/unpaired terminals. It may be a real connection or a free arrow; no endpoint is inferred.',
 'open_unarrowed_numeric_paint':'Open unarrowed noncurve softpath with no named terminal references. Axis, plot, decoration and genuine numeric connection remain indistinguishable.',
 'open_curve_unarrowed_numeric_paint':'Open unarrowed curve softpath with no named terminal references. No semantic intent is inferred.',
 'mixed_named_numeric_unarrowed_paint':'Open unarrowed path has some named terminal references but not a complete operation/reference pairing.',
 'named_terminals_paired_straight':'Operation/reference roles are paired and all nonmove operations are straight. This is a trace fact, not proven node-instance binding or native acceptance.',
 'named_terminals_paired_curve':'Operation/reference roles are paired with cubic operations; exact native curve support remains separate.',
 'open_unpaired_other_paint':'Open paint has terminal/operation facts that do not fit a narrower factual category.',
 'unclassified_softpath_paint':'Nonempty softpath facts remain unclassified; no relaxation applies.'
}


def collect_paths(events):
 paths={};duplicates=collections.defaultdict(list);node_count=0
 for sequence,event in enumerate(events):
  kind=event['kind'];f=event['fields']
  if kind=='path':
   key=(f[0],f[1]);paths.setdefault(key,{'picture':f[0],'path':f[1],'begin_count':0,'operations':[],'references':[],'nodes':[],'finishes':[]})['begin_count']+=1
  elif kind in ('operation','ref','node','finish'):
   key=(f[0],f[1]);p=paths.setdefault(key,{'picture':f[0],'path':f[1],'begin_count':0,'operations':[],'references':[],'nodes':[],'finishes':[]})
   if kind=='operation':p['operations'].append({'kind':f[2],'number':int(f[3]),'sequence':sequence})
   elif kind=='ref':p['references'].append({'callback':f[2],'name':f[3],'anchor':f[4],'sequence':sequence})
   elif kind=='node':
    node_count+=1;p['nodes'].append({'serial':f[2],'role':f[3],'name':f[4],'shape':f[5]})
    if f[4] and f[3]!='label':duplicates[(f[0],f[4])].append({'serial':f[2],'sequence':sequence,'center_pt':[f[7],f[8]],'path':f[1]})
   else:p['finishes'].append({'start_arrow':f[3]=='1','end_arrow':f[4]=='1','arrows_tex':f[2],'softpath':f[5]})
 return paths,[{'picture':k[0],'name':k[1],'definition_count':len(v),'definitions':v} for k,v in duplicates.items() if len(v)>1],node_count


def classify_path(path):
 ops=path['operations'];refs=[r for r in path['references'] if r['callback'] in ROLES];kinds=[o['kind'] for o in ops]
 paired=bool(ops) and len(ops)==len(refs) and all(op['kind']==ROLES[ref['callback']] for op,ref in zip(ops,refs))
 facts={'picture':path['picture'],'path':path['path'],'operation_count':len(ops),'named_terminal_reference_count':len(refs),'operation_reference_count_gap':len(ops)-len(refs),'operation_kinds':dict(collections.Counter(kinds)),'node_events':len(path['nodes']),'operation_reference_roles_paired':paired,'finish_count':len(path['finishes']),'begin_count':path['begin_count']}
 if len(path['finishes'])!=1:facts['category']='incomplete_path_finish_coverage';return facts
 finish=path['finishes'][0];soft=finish['softpath'].strip();operators=collections.Counter(SOFT.findall(soft));closed=bool(operators['closepath'] or operators['rectcorner'] or operators['rectsize']);curve=any(operators[k] for k in ('curveto','curvetosupporta','curvetosupportb','quadraticto'));arrow=finish['start_arrow'] or finish['end_arrow']
 facts.update(softpath_operators=dict(operators),main_path_softpath_empty=not soft,closed_operator=closed,curve_operator=curve,start_arrow_flag=finish['start_arrow'],end_arrow_flag=finish['end_arrow'],arrows_tex=finish['arrows_tex'],terminal_status='paired_named' if paired else 'mixed_or_unpaired_named' if refs else 'no_named_terminal_references',numeric_or_unbound_by_v1_pairing=bool(ops) and not paired)
 if not soft:
  category='no_path_softpaint_node_or_empty' if not ops else 'no_path_softpaint_cursor_only' if set(kinds)<={'move'} else 'no_path_softpaint_nonmove_operations'
 elif closed:category='closed_paint_candidate'
 elif operators and not any(operators[k] for k in ('lineto','curveto','curvetosupporta','curvetosupportb','quadraticto')):category='softpath_move_only'
 elif arrow and not paired:category='open_arrow_terminal_unresolved'
 elif paired:category='named_terminals_paired_curve' if 'cubic' in kinds else 'named_terminals_paired_straight'
 elif not refs and not arrow:category='open_curve_unarrowed_numeric_paint' if curve else 'open_unarrowed_numeric_paint'
 elif refs and not arrow:category='mixed_named_numeric_unarrowed_paint'
 else:category='open_unpaired_other_paint'
 facts['category']=category;return facts


def _owned(path):
 p=Path(path).resolve()
 if not p.is_relative_to(W/'tikz_execution_candidates_v1'):raise ValueError('Proof is outside the owned execution batch workspace')
 return p


def find_proof(row,policy):
 record=json.loads(row['record'])
 if record.get('work'):
  path=_owned(R/record['work'])/'proof/execution/execution_graph.json'
  if path.exists():return path
 folder=W/'tikz_execution_candidates_v1'/row['id']/(row['code_hash']+'_'+row['image_hash'][:16])/policy.rsplit(':',1)[-1]
 paths=list(folder.glob('*/proof/execution/execution_graph.json'))
 return max(paths,key=lambda p:p.stat().st_mtime_ns) if paths else None


def inspect_case(row,policy):
 report=json.loads(row['record']);case={k:row[k] for k in ('id','state','code_hash','image_hash','updated_at')};case['producer_error']=str(report.get('error',''))[:500];case['published_by_inventory']=False;proof=find_proof(row,policy)
 if proof is None:case.update(proof_status='proof_not_generated_or_missing',trace_status='not_available');return case
 proof=_owned(proof);sidecar_blob=proof.read_bytes();sidecar=json.loads(sidecar_blob);case.update(proof_file=str(proof.relative_to(R)),proof_sha256=sha(sidecar_blob),sidecar_ok=bool(sidecar.get('ok')),compile_runs={k:v.get('returncode') for k,v in sidecar.get('runs',{}).items()})
 runs=sidecar.get('runs',{})
 if not runs.get('baseline') or runs['baseline'].get('returncode')!=0:case['compile_status']='baseline_failed_or_incomplete'
 elif not runs.get('instrumented') or runs['instrumented'].get('returncode')!=0:case['compile_status']='instrumented_failed_or_incomplete'
 else:case['compile_status']='both_succeeded'
 equivalence=sidecar.get('instrumentation_pdf_pixel_equivalence',[]);case['pdf_pixels_recorded_identical']=bool(equivalence) and all(p.get('pixel_identical') is True for p in equivalence)
 trace=proof.parent/'instrumented/source.iic'
 if not trace.is_file():case['trace_status']='missing';return case
 data=trace.read_bytes();case['trace_sha256']=sha(data);case['trace_matches_sidecar_digest']=bool(sidecar.get('execution_trace_sha256')) and sidecar['execution_trace_sha256']==case['trace_sha256']
 try:events=parse_events(data.decode())
 except Exception as error:case.update(trace_status='incomplete_or_unparseable',trace_error=type(error).__name__+': '+str(error)[:400]);return case
 paths,duplicates,node_count=collect_paths(events);facts=[classify_path(path) for path in paths.values()];case.update(trace_status='complete_parsed',event_count=len(events),path_count=len(paths),node_event_count=node_count,duplicate_node_name_groups=duplicates,duplicate_group_count=len(duplicates),duplicate_redefinitions=sum(d['definition_count']-1 for d in duplicates),path_category_counts=dict(collections.Counter(f['category'] for f in facts)),path_facts=facts)
 source_proof=case['compile_status']=='both_succeeded' and case['pdf_pixels_recorded_identical'] and case['trace_matches_sidecar_digest'] and sidecar.get('source_bytes_unchanged') is True
 case['trace_and_pdf_source_identity_recorded']=source_proof
 failures=sidecar.get('graph',{}).get('failures',[]);v1_numeric={(str(x.get('picture')),str(x.get('path'))) for x in failures if x.get('reason')=='numeric_or_unbound_path_terminal'};case['v1_failure_reason_counts']=dict(collections.Counter(f.get('reason','unknown') for f in failures));case['v1_numeric_failure_path_count']=len(v1_numeric);case['v1_numeric_failure_categories']=dict(collections.Counter(f['category'] for f in facts if (f['picture'],f['path']) in v1_numeric));case['numeric_or_unpaired_fact_category_counts']=dict(collections.Counter(f['category'] for f in facts if f.get('numeric_or_unbound_by_v1_pairing')))
 return case


def _totals(cases):
 category=collections.Counter();numeric=collections.Counter();v1_numeric=collections.Counter();operators=collections.Counter();closed_arrow=0;rows_with_numeric=0
 for case in cases:
  category.update(case.get('path_category_counts',{}));numeric.update(case.get('numeric_or_unpaired_fact_category_counts',{}));v1_numeric.update(case.get('v1_numeric_failure_categories',{}));rows_with_numeric+=bool(case.get('v1_numeric_failure_path_count'))
  for fact in case.get('path_facts',[]):
   operators.update(fact.get('softpath_operators',{}));closed_arrow+=bool(fact.get('closed_operator') and (fact.get('start_arrow_flag') or fact.get('end_arrow_flag')))
 return {'cases':len(cases),'paths':sum(c.get('path_count',0) for c in cases),'path_category_counts':dict(category),'numeric_or_unpaired_fact_categories':dict(numeric),'v1_numeric_failure_categories':dict(v1_numeric),'v1_numeric_failure_paths':sum(c.get('v1_numeric_failure_path_count',0) for c in cases),'cases_with_v1_numeric_failures':rows_with_numeric,'closed_paint_paths_with_arrow_flags':closed_arrow,'softpath_operator_counts':dict(operators)}


def main(args):
 from tikz_execution_candidate_batch_v1 import implementation
 pinned_before=implementation();db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('pragma query_only=ON');db.execute('begin');all_rows=db.execute('select id,code_hash,image_hash,state,record,updated_at from tikz_execution_candidates_v1 where policy=? order by updated_at,id',(args.policy,)).fetchall();db.commit();db.close();captured=now();completed=[dict(row) for row in all_rows if row['state']!='running'];rows=completed[:args.limit] if args.limit else completed;cases=[]
 for row in rows:
  try:cases.append(inspect_case(row,args.policy))
  except Exception as error:cases.append({'id':row['id'],'state':row['state'],'trace_status':'inventory_read_error','error':repr(error)[:500]})
 complete=[c for c in cases if c.get('trace_status')=='complete_parsed'];trusted=[c for c in complete if c.get('trace_and_pdf_source_identity_recorded')];duplicates=[c for c in complete if c.get('duplicate_group_count')];trace_status=collections.Counter(c.get('trace_status','unknown') for c in cases);compile_status=collections.Counter(c.get('compile_status','proof_not_available') for c in cases)
 out={'version':'actual_trace_numeric_path_inventory_v2','captured_at':captured,'policy':args.policy,'published':False,'acceptance_or_gate_changes':False,'jobs_opened_read_only':True,'snapshot_rows_total':len(all_rows),'snapshot_running_rows_excluded':len(all_rows)-len(completed),'completed_rows_available':len(completed),'completed_rows_audited':len(rows),'cohort_snapshot_sha256':sha(json.dumps(rows,sort_keys=True).encode()),'sampling':'Completed rows of the current ordered producer cohort; this is not a random sample or a dataset-wide prevalence estimate.','producer_state_counts':dict(collections.Counter(row['state'] for row in rows)),'trace_status_counts':dict(trace_status),'compile_status_counts':dict(compile_status),'complete_trace_fraction':len(complete)/max(1,len(cases)),'complete_trace_and_pdf_identity_fraction':len(trusted)/max(1,len(cases)),'all_complete_trace_totals':_totals(complete),'trace_and_pdf_identity_totals':_totals(trusted),'duplicate_node_name_cases':len(duplicates),'duplicate_node_name_groups':sum(c['duplicate_group_count'] for c in duplicates),'duplicate_redefinitions':sum(c['duplicate_redefinitions'] for c in duplicates),'duplicate_examples':[{'id':c['id'],'groups':c['duplicate_node_name_groups']} for c in duplicates[:10]],'category_descriptions':CATEGORY_DESCRIPTIONS,'boundaries':['Path classifications describe actual recorded operations, softpath operators and arrow flags only. They never identify semantic intent or permit node/edge binding.','No-path softpaint may still contain independently painted nodes; it does not mean the entire source has no visible object.','Closed paint is separated before examining arrow flags because inherited arrows do not establish that a box/region is a connection.','Open unarrowed numeric lines are not automatically treated as mandatory connectors; axis/decoration/plot/leader/connection intent remains unresolved.','Open numeric/mixed arrow paths remain unresolved; no source node pair is inferred from proximity.','Source-PDF equivalence and trace digest facts are recorded from existing immutable sidecars; this read-only inventory does not recompile or rerender.','v1 duplicate-name rejection remains unchanged.'], 'cases':cases,'frozen_producer_policy_unchanged':implementation()==pinned_before}
 if not out['frozen_producer_policy_unchanged']:raise RuntimeError('Frozen producer implementation changed during read-only inventory')
 output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);temporary=output.with_suffix(output.suffix+'.inventory.tmp');temporary.write_text(json.dumps(out,indent=2)+'\n');temporary.replace(output)
 print(json.dumps({k:v for k,v in out.items() if k not in ('cases','category_descriptions','duplicate_examples','boundaries')},indent=2))


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--policy',default=POLICY);parser.add_argument('--limit',type=int,default=0);parser.add_argument('--output',default=str(W/'tikz_execution_numeric_inventory_v2.json'));arguments=parser.parse_args()
 if arguments.limit<0:parser.error('limit must be nonnegative')
 main(arguments)
