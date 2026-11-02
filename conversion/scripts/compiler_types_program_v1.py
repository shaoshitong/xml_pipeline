"""Finite prepare/seal/validate/release program; never waits for an agent.

This module is new. Existing Python production and frozen quality code are read
only. prepare never dispatches. launch starts one identity-bound supervisor.
"""
from __future__ import annotations
import argparse,ast,collections,fcntl,hashlib,importlib,importlib.util,json,os,sqlite3,subprocess,sys,time,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';FLOOR=R/'release/compiler_types_v1';PROGRAMS=FLOOR/'programs';S=W/'scripts'
AUDIT_UNITS={'drawio':'native_drawio_graph_v1','mermaid':'mermaid_flat_source_svg_v1','html':'html_poster_DOM_CSS_heuristic_v1'}
QUALITY_PREFIX='round2_full_source_native_quality_v1'
REQUIRED_CHECKS={'structure','resources','source','render','text_paint','fonts','visual','native_editing'}
ASSETS=(('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('metadata_file','metadata_sha256'))
def raw(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def module(name):return importlib.import_module(name)
def modules():return module('compiler_types_batch_v1'),module('fixed_batch_pipeline_v1'),module('compiler_types_case_v1')
def safe_name(v):
 if not isinstance(v,str) or not v or not all(c.isalnum() or c in '-_' for c in v):raise ValueError('invalid_program_name')
 return v
def owned(p):
 p=Path(p).resolve()
 if not p.is_relative_to(PROGRAMS.resolve()) or p==PROGRAMS.resolve():raise ValueError('program_outside_owner')
 return p
def readrows(p):return [json.loads(x) for x in Path(p).read_bytes().splitlines() if x]
def immutable(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  if p.read_bytes()!=b:raise ValueError('immutable_program_asset_changed:'+str(p))
  return asset(p)
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 return asset(p)
def atomic(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
 with tmp.open('xb') as f:f.write(raw(v));f.flush();os.fsync(f.fileno())
 tmp.replace(p)
def asset(p):
 p=Path(p).resolve(strict=True)
 if not p.is_relative_to(R.resolve()):raise ValueError('asset_outside_root')
 return {'file':str(p),'sha256':sha(p.read_bytes())}
def checked(ref,clean=False):
 if not isinstance(ref,dict) or not all(isinstance(ref.get(k),str) for k in ('file','sha256')):raise ValueError('invalid_asset_reference')
 p=Path(ref['file']);p=(p if p.is_absolute() else R/p).resolve(strict=True)
 if not p.is_relative_to((R/'clean' if clean else R).resolve()):raise ValueError('evidence_outside_owned_root')
 b=p.read_bytes()
 if sha(b)!=ref['sha256']:raise ValueError('evidence_hash_changed:'+str(p))
 return p,b
def ast_hash(path,names):
 tree=ast.parse(Path(path).read_text());parts=[ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
 if len(parts)!=len(names):raise ValueError('predicate_AST_missing')
 return sha('\n'.join(parts).encode())
def implementation_template():
 """Identity API for root's seen-controls producer; performs no conversion."""
 controller,base,case=modules();qa=module('auto_quality_batch_v4b');reg=module('round2_font_canvas_registration_v1');r2=module('round2_case_v1')
 cfg=reg.configuration();bindings={'frozen_qa_policy':getattr(qa,'_round2_frozen_policy',qa.POLICY),'registration_policy':cfg['policy'],'registration_pins':cfg['pins'],'case_sha256':sha(Path(r2.__file__).read_bytes())}
 pins={**base.pins(),**cfg['pins']};todo=[Path(__file__),Path(controller.__file__),Path(case.__file__),S/'compiler_validation_reservation_v1.py',S/'compiler_types_controls_v1.py',S/'compiler_types_source_ir_v1.py',S/'compiler_validation_dot_ir_v2.py',S/'compiler_native_languages_v1.py',S/'round2_case_v1.py']+[S/(n+'.py') for n in r2.MODULES.values()];seen=set()
 while todo:
  p=todo.pop().resolve()
  if p in seen or not p.is_file():continue
  seen.add(p);pins[str(p)]=sha(p.read_bytes())
  sibling=p.with_suffix('.js')
  if sibling.is_file():pins[str(sibling)]=sha(sibling.read_bytes())
  if p.suffix!='.py':continue
  for n in ast.walk(ast.parse(p.read_text())):
   names=[a.name.split('.')[0] for a in n.names] if isinstance(n,ast.Import) else [n.module.split('.')[0]] if isinstance(n,ast.ImportFrom) and n.module else []
   for name in names:
    q=S/(name+'.py')
    if q.is_file():todo.append(q)
   if isinstance(n,ast.Constant) and isinstance(n.value,str) and '/' not in n.value and n.value.endswith(('.py','.js')) and (S/n.value).is_file():todo.append(S/n.value)
 predicate=ast_hash(case.__file__,{'static_support','unit'});irsha=sha((S/'compiler_types_source_ir_v1.py').read_bytes())
 predicates={case.unit(fmt):sha(raw({'case_support_AST':predicate,'source_IR_sha256':irsha,'format':fmt,'audit_unit':AUDIT_UNITS.get(fmt),'blocked_without_audited_group':fmt not in AUDIT_UNITS})) for fmt in case.FORMATS}
 freeze={'compiler_version':'compiler_types_v1','pins':pins,'predicate_hashes':predicates,'qa_bindings':bindings,'qa_policy_sha256':sha(raw(bindings))}
 freeze['quality_policy']=QUALITY_PREFIX+':'+freeze['qa_policy_sha256'][:20];freeze['implementation_identity']=controller.implementation_identity(freeze);freeze['implementation_identity_sha256']=controller.implementation_digest(freeze);return freeze

def full_quality(result,qa,request,freeze):
 if (qa.get('id'),qa.get('policy'),result.get('quality_policy'))!=(request['id'],freeze['quality_policy'],freeze['quality_policy']):raise ValueError('quality_policy_or_original_identity_changed')
 if sha(raw(qa.get('round2_quality_bindings')))!=freeze['qa_policy_sha256']:raise ValueError('quality_bindings_changed')
 if result.get('status')!='qualified' or qa.get('state')!='qualified' or qa.get('failures'):raise ValueError('not_full_qualified')
 checks=qa.get('checks',{})
 if not REQUIRED_CHECKS<=set(checks) or any(checks[k].get('ok') is not True for k in ('source','visual','native_editing')):raise ValueError('full_quality_gate_missing')
 if checks['fonts'].get('all_rendered_fonts_embedded') is not True:raise ValueError('font_portability_not_passed')
 manifest=result.get('manifest') or {}
 if (manifest.get('id'),manifest.get('source_code_sha256'),manifest.get('source_image_sha256'))!=(request['id'],request['source']['code_sha256'],request['source']['image_sha256']):raise ValueError('qualified_manifest_source_changed')
 for f,h in ASSETS:checked({'file':manifest[f],'sha256':manifest[h]},clean=True)
 _,metadata=checked({'file':manifest['metadata_file'],'sha256':manifest['metadata_sha256']},clean=True);metadata=json.loads(metadata)
 for k in ('id','code_sha256','image_sha256','source_code_sha256','source_image_sha256'):
  if metadata.get(k)!=manifest.get(k):raise ValueError('qualified_metadata_binding_changed')
 if metadata.get('automatic_quality_policy')!=freeze['quality_policy']:raise ValueError('qualified_metadata_policy_changed')
 if (R/metadata.get('automatic_quality_audit','')).resolve()!=(R/result.get('quality_report','')).resolve():raise ValueError('qualified_metadata_QA_pointer_changed')
 if (qa.get('input_code_sha256'),qa.get('new_png_sha256'))!=(manifest['code_sha256'],manifest['image_sha256']):raise ValueError('quality_not_bound_to_pair')
 render=checks['render']
 if (render.get('code_sha256'),render.get('image_sha256'),render.get('strict_outside_page_pixels'))!=(manifest['code_sha256'],manifest['image_sha256'],0):raise ValueError('fresh_native_pair_not_bound')
 return True

def structure_rejection(xml,reason):
 try:module('auto_quality_batch_v4b').structure_checks(xml)
 except (ValueError,AssertionError) as e:return bool(reason and reason in str(e))
 return False

def validate_control_bundle(proof,freeze,required_units):
 controller,_,_=modules()
 if proof.get('schema')!='compiler_types_controls_proof_v1' or proof.get('implementation_identity')!=controller.implementation_identity(freeze) or proof.get('implementation_identity_sha256')!=controller.implementation_digest(freeze):raise ValueError('controls_implementation_identity_changed')
 sets=[]
 for k in ('controls_manifest','expectations','outcomes'):
  _,b=checked(proof[k]);rr=[json.loads(x) for x in b.splitlines() if x];index={r['control_id']:r for r in rr}
  if len(index)!=len(rr):raise ValueError('controls_duplicate_ID')
  sets.append(index)
 manifest,expectations,outcomes=sets
 if set(manifest)!=set(expectations) or set(manifest)!=set(outcomes):raise ValueError('control_sets_differ')
 counts=collections.defaultdict(collections.Counter);positives=collections.defaultdict(set);evidence=[]
 for ident,row in manifest.items():
  kind=row.get('kind');unit=row.get('compiler_unit');expected=expectations[ident];out=outcomes[ident]
  if kind not in ('positive','negative','development') or expected.get('kind')!=kind or expected.get('compiler_unit',unit)!=unit:raise ValueError('control_declaration_changed')
  request_assets=[];source_assets=[];bound={}
  for ref in row.get('input_assets',[]):
   p,b=checked(ref);bound[p]=b
   if ref.get('role')=='request':request_assets.append(json.loads(b))
   if ref.get('role')=='source_record':source_assets.append((ref['sha256'],json.loads(b)))
  if len(request_assets)!=1 or len(source_assets)!=1:raise ValueError('control_request_or_source_record_missing')
  request=request_assets[0];_,rb=checked(out['result']);result=json.loads(rb);_,ib=checked(out['isolation']);isolation=json.loads(ib)
  if not isolation.get('ok') or isolation.get('returncode')!=0 or isolation.get('cleanup_complete') is not True or isolation.get('deadline_exceeded'):raise ValueError('control_process_not_clean')
  if result.get('infrastructure_failure') or result.get('model_calls')!=0 or result.get('status') not in ('qualified','abandoned'):raise ValueError('control_infra_or_model_violation')
  if (request.get('id'),request.get('compiler_unit'),request.get('seq'))!=(result.get('id'),unit,result.get('seq')):raise ValueError('control_identity_changed')
  if request.get('source',{}).get('pair_sha256')!=request['id'] or request.get('pins')!=freeze['pins']:raise ValueError('control_request_source_or_pins_changed')
  source_hash,source_record=source_assets[0]
  if source_hash!=request.get('source_record_sha256'):raise ValueError('control_source_record_bytes_not_frozen')
  for r in [source_record]:
   if (r.get('id'),r.get('source_code_sha256'),r.get('source_image_sha256'))!=(request['id'],request['source']['code_sha256'],request['source']['image_sha256']):raise ValueError('control_source_record_identity_changed')
  if request.get('development_candidate'):
   p=Path(request['development_candidate']).resolve(strict=True)
   if p not in bound:raise ValueError('control_override_not_frozen')
  if kind=='development':counts[unit][kind]+=1;continue
  _,qb=checked(out['quality_audit']);qa=json.loads(qb)
  if (R/result.get('quality_report','')).resolve()!=Path(out['quality_audit']['file']).resolve():raise ValueError('control_quality_path_changed')
  if (qa.get('id'),qa.get('policy'),result.get('quality_policy'))!=(request['id'],freeze['quality_policy'],freeze['quality_policy']) or sha(raw(qa.get('round2_quality_bindings')))!=freeze['qa_policy_sha256']:raise ValueError('control_quality_policy_changed')
  if kind=='positive':
   if request.get('evaluation_phase')!='baseline' or result.get('repair_steps')!=[]:raise ValueError('positive_control_must_be_unrepaired_baseline')
   candidate=json.loads(bound[Path(request['development_candidate']).resolve()])
   if (result.get('candidate_code_sha256'),result.get('candidate_image_sha256'))!=(candidate['code_sha256'],candidate['image_sha256']) or (result.get('manifest',{}).get('code_sha256'),result.get('manifest',{}).get('image_sha256'))!=(candidate['code_sha256'],candidate['image_sha256']):raise ValueError('positive_original_payload_changed')
   if expected.get('expected_status')!='qualified' or expected.get('expected_failure_stage') is not None:raise ValueError('positive_expectation_changed')
   full_quality(result,qa,request,freeze);positives[unit].add(request['id'])
  else:
   stage=expected.get('expected_failure_stage');gate=qa.get('checks',{}).get(stage,{})
   rejection=bool(gate.get('ok') is False or gate.get('failures') or gate.get('errors'))
   if stage=='structure':
    reason=expected.get('expected_failure_reason');candidate=json.loads(bound[Path(request['development_candidate']).resolve()]);_,xml=checked({'file':candidate['code_file'],'sha256':candidate['code_sha256']},clean=True)
    rejection=bool(reason and reason in json.dumps(qa.get('failures',[])) and qa.get('input_code_sha256')==candidate['code_sha256'] and result.get('candidate_code_sha256')==candidate['code_sha256'] and structure_rejection(xml.decode(),reason))
   if expected.get('expected_status')!='abandoned' or result['status']!='abandoned' or request.get('negative_control') is not True or stage not in ('source','structure','text_paint') or qa.get('state')=='qualified' or not qa.get('failures') or not rejection:raise ValueError('negative_not_rejected_by_declared_gate')
  counts[unit][kind]+=1;evidence.append({'control_id':ident,'kind':kind,'compiler_unit':unit,'result':out['result'],'quality_audit':out['quality_audit']})
 for unit in required_units:
  if counts[unit]['positive']<1 or counts[unit]['negative']<1:raise ValueError('unit_requires_actual_positive_and_negative_controls:'+unit)
  required=set(proof.get('required_positive_ids',{}).get(unit,[]))
  if not required or not required<=positives[unit]:raise ValueError('required_prior_positive_regression_missing:'+unit)
 return {'counts':{u:dict(c) for u,c in counts.items()},'verified_outcomes':evidence,'infrastructure_errors':0,'controls_passed_units':sorted(required_units)}
def check_controls_proof(path,freeze,required_units):
 p,b=checked(asset(path));proof=json.loads(b);result=validate_control_bundle(proof,freeze,set(required_units));return {**result,'file':str(p),'sha256':sha(b)}

def load_first(path):
 r=readrows(path);d={x['id']:x for x in r}
 if len(d)!=len(r) or any(x.get('status') not in ('qualified','abandoned') for x in r):raise ValueError('initial_first_screen_not_complete_or_unique')
 return d

def classify_job(job):
 ir=module('compiler_types_source_ir_v1');iso=module('compiler_validation_dot_ir_v2');source=json.loads(job[4]);m=json.loads(job[11] or '{}');p=(R/m['source_code']).resolve(strict=True)
 if not p.is_relative_to(R.resolve()):raise ValueError('source_outside_root')
 code=p.read_bytes()
 if sha(code)!=source['code_sha256']:raise ValueError('source_hash_changed')
 fmt=job[2]
 if fmt=='drawio':
  sp=importlib.util.spec_from_file_location('types_old_xml',R/'release/round2_heldout_v1/unseen_protocol_20261101_v2/frozen_sampler.py');old=importlib.util.module_from_spec(sp);sp.loader.exec_module(old);unit,g,e=ir.native(code.decode('utf-8-sig'),old)
 elif fmt=='mermaid':unit,g,e=ir.language(code.decode('utf-8-sig'),fmt,module('compiler_native_languages_v1'))
 elif fmt=='html':unit,g,e=ir.html_ir(code.decode('utf-8-sig'))
 else:raise ValueError('source_audit_unit_not_released')
 return {'source_audit_unit':unit,'semantic_invariant':iso.invariant(g),'evidence':e}
def canonical_task(job,first,seq,audit_unit,cluster=None,allow_unsupported=False):
 _,_,case=modules();s=json.loads(job[4]);r=json.loads(job[9] or '{}')
 support=case.static_support(job);actual=(r.get('code_sha256'),r.get('image_sha256'))
 if not support['supported'] and not allow_unsupported:raise ValueError('existing_native_IR_not_supported')
 historical=(first.get('candidate_code_sha256'),first.get('candidate_image_sha256'))
 if support['supported'] and all(historical) and actual!=historical:raise ValueError('first_candidate_revision_not_frozen')
 # An audited source may have no reusable IR. Keep it in the preregistered
 # denominator; the case records a typed refusal in both phases. Never refill.
 return {'id':job[0],'seq':seq,'source':s,'compiler_unit':case.unit(job[2]),'source_audit_unit':audit_unit,'cluster':cluster,'source_record_sha256':sha((job[9] or '').encode()),'first_result':first,'first_result_sha256':sha(raw(first)),'baseline_code_sha256':actual[0],'baseline_image_sha256':actual[1],'existing_IR_admission':support,'historical_first_candidate_comparable':all(historical) and actual==historical}
def prepare(audit_dir,scope_manifest,first_processed,controls_proof,run_id):
 controller,base,case=modules();run_id=safe_name(run_id);directory=owned(PROGRAMS/run_id)
 if directory.exists():raise ValueError('program_already_prepared_no_automatic_cohort_retry')
 audit=Path(audit_dir).resolve(strict=True)
 if not audit.is_relative_to((R/'release/compiler_types_audit_v1').resolve()):raise ValueError('audit_outside_types_source_owner')
 integrity=json.loads((audit/'compiler_types_integrity.json').read_bytes());method=json.loads((audit/'compiler_types_method.json').read_bytes())
 if not integrity.get('metadata_integrity_passed') or integrity.get('ready_for_validation') is not False:raise ValueError('source_audit_not_frozen_unconsumed')
 for f in integrity['files']:checked(f)
 for name,h in method['method_pins'].items():
  if sha((S/name).read_bytes())!=h:raise ValueError('source_audit_implementation_changed:'+name)
 scope_manifest=Path(scope_manifest).resolve(strict=True);first_processed=Path(first_processed).resolve(strict=True)
 if sha(scope_manifest.read_bytes())!=method['scope_sha256']:raise ValueError('scope_differs_from_source_audit')
 scope=readrows(scope_manifest);first=load_first(first_processed)
 if {r['id'] for r in scope}!=set(first):raise ValueError('scope_first_screen_identity_set_differs')
 selected=readrows(audit/'compiler_types_selected_manifest_closure_verified.jsonl');wanted=[r for r in selected if r['format'] in AUDIT_UNITS and r['source']['format']==r['format'] and r['support_unit']==AUDIT_UNITS[r['format']]]
 groups=collections.defaultdict(list)
 for r in wanted:groups[r['support_unit']].append(r)
 if set(groups)!=set(AUDIT_UNITS.values()) or any(len(rr)!=30 or len({r['audit_cluster'] for r in rr})!=30 for rr in groups.values()):raise ValueError('source_cohort_requires30_clusters_per_declared_group')
 freeze=implementation_template();required={case.unit(fmt) for fmt in AUDIT_UNITS};controls=check_controls_proof(controls_proof,freeze,required)
 db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30);tasks=[]
 try:
  for item in sorted(wanted,key=lambda r:(r['format'],r['pool_rank'])):
   job=db.execute('select * from jobs where id=?',(item['id'],)).fetchone()
   if not job or (json.loads(job[4])['code_sha256'],json.loads(job[4])['image_sha256'])!=(item['source']['code_sha256'],item['source']['image_sha256']):raise ValueError('selected_original_source_changed')
   classify=classify_job(job)
   if classify['source_audit_unit']!=item['support_unit'] or classify['semantic_invariant']!=item['semantic_invariant']:raise ValueError('selected_actual_source_IR_changed')
   task=canonical_task(job,first[item['id']],len(tasks)+1,item['support_unit'],item['audit_cluster'],allow_unsupported=True);task['cluster_keys']=item['cluster_keys'];tasks.append(task)
 finally:db.close()
 phase_runs={p:str(FLOOR/(run_id+'_'+p)) for p in ('B','C')}
 for p in phase_runs.values():
  if Path(p).exists():raise ValueError('validation_run_already_exists')
 reserve=module('compiler_validation_reservation_v1').reserve
 reservation=reserve(R/'release/compiler_v1/validation_registry.sqlite',wanted,audit=audit,run_prefix=run_id,implementation_identity_sha256=freeze['implementation_identity_sha256'],phase_runs=phase_runs,selected_manifest_sha256=sha((audit/'compiler_types_selected_manifest_closure_verified.jsonl').read_bytes()),protocol_sha256=sha((audit/'compiler_types_protocol.json').read_bytes()),controls_proof_sha256=controls['sha256'])
 directory.mkdir(parents=True);immutable(directory/'scope.jsonl',scope_manifest.read_bytes());immutable(directory/'first_processed.jsonl',first_processed.read_bytes());immutable(directory/'implementation.json',raw(freeze));receipt={'schema':'compiler_types_program_v1','run_id':run_id,'audit_dir':str(audit),'source_audit_units':AUDIT_UNITS,'scope':asset(directory/'scope.jsonl'),'first_snapshot':asset(directory/'first_processed.jsonl'),'implementation_identity_sha256':freeze['implementation_identity_sha256'],'controls_proof':controls,'reservation':reservation,'runs':{},'ready_for_dispatch':True,'source_cohort_counts':{u:len(rr) for u,rr in groups.items()},'quality_policy':freeze['quality_policy'],'blocked_audit_units':{'svg':'insufficient30_or_frontend_not_ready','plantuml':'insufficient30_or_frontend_not_ready','tikz':'static_inventory_only_insufficient30'}}
 for phase in ('B','C'):
  rr=[dict(r,evaluation_phase='baseline' if phase=='B' else 'candidate') for r in tasks];manifest=directory/(phase+'.jsonl');immutable(manifest,b''.join(raw(r) for r in rr));f={**freeze,'input_sha256':sha(manifest.read_bytes()),'controls_proof':controls,'validation_reservation_id':reservation['reservation_id']};fp=directory/(phase+'.freeze.json');immutable(fp,raw(f));controller.create(phase_runs[phase],manifest,fp,'validation');receipt['runs'][phase]={'directory':phase_runs[phase],'manifest':asset(manifest),'freeze':asset(fp)}
 immutable(directory/'receipt.json',raw(receipt));return {'program_dir':str(directory),'receipt':receipt,'dispatched':False}

def decisions(pairs,controls_units):
 groups=collections.defaultdict(list)
 for r in pairs:groups[r['compiler_unit']].append(r)
 out={}
 for unit,rr in groups.items():
  n=len(rr);clusters={r['cluster'] for r in rr};q=sum(r['C']=='qualified' for r in rr);new=sum(r['C']=='qualified' and r['B']!='qualified' for r in rr);reg=sum(r['B']=='qualified' and r['C']!='qualified' for r in rr);infra=sum(bool(r.get('infrastructure_failure')) for r in rr)
  out[unit]={'samples':n,'audited_clusters':len(clusters),'full_qualified':q,'full_qualified_rate':q/n if n else 0,'new_qualified_clusters':new,'positive_regressions':reg,'infrastructure_errors':infra,'provenance_or_cluster_audit_passed':True,'passed':n>=30 and len(clusters)==n and q/n>=.20 and new>=5 and reg==infra==0 and unit in controls_units}
 return out

def phase_rows(run,freeze,phase):
 controller,base,_=modules();snap=controller.snapshot(run)
 if not snap['metadata'].get('finished') or snap['infrastructure_stop'] or any(k not in base.TERMINAL for k in snap['counts']):raise ValueError('validation_not_complete_or_infrastructure_stopped')
 targets=readrows(Path(run)/'targets.jsonl')
 if sha(raw(freeze))!=snap['metadata'].get('freeze_sha256') or sha((Path(run)/'targets.jsonl').read_bytes())!=freeze['input_sha256']:raise ValueError('validation_target_manifest_changed')
 d=sqlite3.connect('file:'+str(Path(run)/'status.sqlite')+'?mode=ro',uri=True);stored=d.execute('select seq,id,source,status,attempts,result from samples order by seq').fetchall();d.close()
 if len(stored)!=len(targets):raise ValueError('validation_result_count_changed')
 out={}
 for q,(seq,i,body,status,attempts,result) in zip(targets,stored):
  r=json.loads(result)
  if json.loads(body)!=q or (seq,i,attempts,status)!=(q['seq'],q['id'],1,r['status']) or q.get('evaluation_phase')!=('baseline' if phase=='B' else 'candidate'):raise ValueError('validation_once_or_phase_identity_changed')
  for k,v in [('id',i),('seq',seq),('compiler_unit',q['compiler_unit']),('cluster',q['cluster']),('source_code_sha256',q['source']['code_sha256']),('source_image_sha256',q['source']['image_sha256'])]:
   if r.get(k)!=v:raise ValueError('validation_result_identity_changed:'+k)
  if r.get('case_cleanup_complete') is not True or r.get('model_calls')!=0:raise ValueError('validation_cleanup_or_model_violation')
  if r.get('quality_report'):
   p=R/r['quality_report'];qa=json.loads(p.read_bytes())
   if (qa.get('id'),qa.get('policy'))!=(i,freeze['quality_policy']) or sha(raw(qa.get('round2_quality_bindings')))!=freeze['qa_policy_sha256']:raise ValueError('validation_actual_policy_changed')
   if r['status']=='qualified':full_quality(r,qa,q,freeze)
  elif r['status']=='qualified':raise ValueError('qualified_without_QA')
  if phase=='B' and (r.get('candidate_code_sha256'),r.get('candidate_image_sha256'))!=(q['baseline_code_sha256'],q['baseline_image_sha256']):raise ValueError('baseline_candidate_changed')
  out[i]={'request':q,'result':r}
 return out

def evaluate(program_dir,write=True):
 controller,_,_=modules();p=owned(program_dir);receipt=json.loads((p/'receipt.json').read_bytes());freeze=json.loads((p/'implementation.json').read_bytes());controller.check_pins(freeze['pins']);controller.check_implementation_identity(freeze);checked(receipt['controls_proof']);checked(receipt['scope']);checked(receipt['first_snapshot']);controls=check_controls_proof(receipt['controls_proof']['file'],freeze,{r for r in freeze['predicate_hashes'] if r.split('_existing_native')[0] in AUDIT_UNITS});phases={}
 for phase in ('B','C'):
  _,b=checked(receipt['runs'][phase]['freeze']);f=json.loads(b)
  if controller.implementation_identity(f)!=controller.implementation_identity(freeze):raise ValueError('B_C_implementation_mismatch')
  phases[phase]=phase_rows(receipt['runs'][phase]['directory'],f,phase)
 if set(phases['B'])!=set(phases['C']):raise ValueError('B_C_original_ID_sets_differ')
 pairs=[]
 for i,c in phases['C'].items():
  b=phases['B'][i]
  for k in ('source','source_record_sha256','first_result_sha256','cluster','source_audit_unit','compiler_unit'):
   if b['request'][k]!=c['request'][k]:raise ValueError('B_C_bound_input_differs:'+k)
  pairs.append({'id':i,'compiler_unit':c['request']['compiler_unit'],'source_audit_unit':c['request']['source_audit_unit'],'cluster':c['request']['cluster'],'B':b['result']['status'],'C':c['result']['status'],'infrastructure_failure':bool(b['result'].get('infrastructure_failure') or c['result'].get('infrastructure_failure'))})
 units=decisions(pairs,set(controls['controls_passed_units']));gate={'schema':'compiler_types_release_gate_v1','implementation_identity':controller.implementation_identity(freeze),'implementation_identity_sha256':controller.implementation_digest(freeze),'approved_units':sorted(u for u,v in units.items() if v['passed']),'units':units,'controls_passed':True,'infrastructure_errors':sum(v['infrastructure_errors'] for v in units.values()),'paired_results':pairs,'source_program_receipt':asset(p/'receipt.json'),'quality_policy':freeze['quality_policy'],'statistics_scope':'Precommitted operational input clusters; hidden generator independence/unbiased yield not proven','model_calls':0};
 if write:immutable(p/'release_gate.json',raw(gate))
 return gate

def verify_release_gate(gate_file,freeze,units):
 controller,_,_=modules();p,b=checked({'file':str(gate_file),'sha256':freeze['release_gate']['sha256']});gate=json.loads(b);receipt=gate['source_program_receipt'];rp,_=checked(receipt);directory=owned(rp.parent)
 if rp.name!='receipt.json':raise ValueError('gate_receipt_not_program_receipt')
 rebuilt=evaluate(directory,write=False)
 if rebuilt!=gate or not set(units)<=set(rebuilt['approved_units']) or rebuilt['implementation_identity']!=controller.implementation_identity(freeze):raise ValueError('release_gate_not_rebuilt_from_actual_evidence')
 return rebuilt

def build_mass(program_dir,gate):
 controller,base,case=modules();p=owned(program_dir);receipt=json.loads((p/'receipt.json').read_bytes());freeze=json.loads((p/'implementation.json').read_bytes());checked(receipt['scope']);checked(receipt['first_snapshot']);scope=readrows(p/'scope.jsonl');first=load_first(p/'first_processed.jsonl');approved=set(gate['approved_units']);validation={r['id'] for r in readrows(p/'C.jsonl')};rows=[];coverage=[];db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)
 try:
  for original in scope:
   i=original['id'];fmt=original['format'];state='blocked_unit_not_validated';detail=None
   if first[i]['status']=='qualified':state='preserved_prior_qualified'
   elif i in validation:state='already_processed_this_compiler_validation'
   elif fmt=='python':state='outside_this_program_python_managed_separately'
   elif fmt not in AUDIT_UNITS:state='not_released_this_round_insufficient_or_unsupported_unit'
   elif case.unit(fmt) in approved:
    try:
     job=db.execute('select * from jobs where id=?',(i,)).fetchone()
     if not job:raise ValueError('canonical_job_missing')
     source=json.loads(job[4])
     if (source['code_sha256'],source['image_sha256'])!=(original['source_code_sha256'],original['source_image_sha256']):raise ValueError('scope_source_identity_changed')
     observed=classify_job(job)
     if observed['source_audit_unit']!=AUDIT_UNITS[fmt]:raise ValueError('actual_source_classifier_not_approved_unit')
     task=canonical_task(job,first[i],len(rows)+1,AUDIT_UNITS[fmt]);rows.append(task);state='queued_for_exactly_once_compiler_version'
    except Exception as e:state='unsupported_existing_IR_or_source_static_unit';detail=str(e)[:300]
   coverage.append({'id':i,'format':fmt,'scope_seq':original['seq'],'state':state,'detail':detail,'converted_by_this_program':False,**({'separate_program':str(R/'release/compiler_v2/graphviz_batch_20261101_v2_renderdomain'),'separate_incremental_index_included':False} if fmt=='python' else {})})
 finally:db.close()
 immutable(p/'scope_disposition.jsonl',b''.join(raw(r) for r in coverage));manifest=p/'mass.jsonl';immutable(manifest,b''.join(raw(r) for r in rows))
 if not rows:return {'targets':0,'scope_states':dict(collections.Counter(r['state'] for r in coverage)),'directory':None}
 f={**freeze,'input_sha256':sha(manifest.read_bytes()),'release_gate':asset(p/'release_gate.json')};fp=p/'mass.freeze.json';immutable(fp,raw(f));run=FLOOR/(receipt['run_id']+'_mass');
 if run.exists():
  if (run/'targets.jsonl').read_bytes()!=manifest.read_bytes() or json.loads((run/'freeze.json').read_bytes())!=f:raise ValueError('existing_mass_run_freeze_differs')
 else:controller.create(run,manifest,fp,'batch')
 return {'targets':len(rows),'directory':str(run),'scope_states':dict(collections.Counter(r['state'] for r in coverage))}

def final_scope_export(p,receipt,mass):
 rows=readrows(p/'scope_disposition.jsonl');byid={r['id']:r for r in rows}
 runs=[receipt['runs']['C']['directory']]+([mass['directory']] if mass.get('directory') else [])
 for run in runs:
  d=sqlite3.connect('file:'+str(Path(run)/'status.sqlite')+'?mode=ro',uri=True)
  try:
   for identifier,status,body in d.execute('select id,status,result from samples'):
    if identifier not in byid:raise ValueError('program_result_outside_frozen_scope')
    target=byid[identifier]
    if target['state']=='preserved_prior_qualified':target['additional_validation_status']=status;continue
    target.update(state='program_'+status,program_attempted=status!='queued',converted_by_this_program=False)
    if body:
     result=json.loads(body);target['reason']=result.get('reason');target['result_run']=str(run)
     target['converted_by_this_program']=bool(result.get('candidate_code_sha256') and any(step.get('ok') is True for step in result.get('repair_steps',[])))
  finally:d.close()
 immutable(p/'scope_final_disposition.jsonl',b''.join(raw(r) for r in rows))
 return dict(collections.Counter(r['state'] for r in rows))

def ensure_complete(run):
 controller,base,_=modules();snap=controller.snapshot(run)
 if not snap['metadata'].get('finished') or snap['infrastructure_stop'] or any(k not in base.TERMINAL for k in snap['counts']):raise RuntimeError('deterministic_phase_not_complete_or_infrastructure:'+str(run))
 return snap

def wait_ack(path,identity,nonce,deadline_seconds=10):
 deadline=time.monotonic()+deadline_seconds
 while time.monotonic()<deadline:
  try:
   ack=json.loads(Path(path).read_bytes())
   if ack==identity:return True
  except (OSError,ValueError):pass
  time.sleep(.05)
 raise RuntimeError('launch_ack_missing_or_identity_changed:'+nonce)

def run_controller_phase(run,workers,case_timeout,p):
 controller,_,_=modules();run=Path(run);nonce=uuid.uuid4().hex;handshake=run/('program_start_'+nonce+'.json');ack=run/('program_ack_'+nonce+'.json')
 argv=[sys.executable,'-B',str(Path(controller.__file__).resolve()),'run','--run-id',run.name,'--workers',str(workers),'--case-timeout',str(case_timeout),'--program-start',str(handshake),'--program-ack',str(ack),'--program-nonce',nonce]
 with (p/(run.name+'.log')).open('ab') as log:child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 from initial_conversion_process_v1 import identity
 birth=identity(child.pid);deadline=time.monotonic()+10;confirmed=None
 while time.monotonic()<deadline:
  if child.poll() is not None:raise RuntimeError('controller_child_exited_before_handshake')
  try:
   h=json.loads(handshake.read_bytes());now=identity(child.pid);args=Path('/proc',str(child.pid),'cmdline').read_bytes().rstrip(b'\0').split(b'\0')
   if birth and now and h.get('pid')==child.pid and h.get('start_ticks')==birth['start_ticks']==now['start_ticks'] and h.get('nonce')==nonce and args==[x.encode() for x in argv]:confirmed=h;break
  except (OSError,ValueError):pass
  time.sleep(.05)
 if confirmed is None:raise RuntimeError('controller_child_identity_handshake_timeout')
 immutable(ack,raw(confirmed));immutable(p/(run.name+'.child.json'),raw({'pid':child.pid,'birth':birth,'argv':argv,'nonce':nonce,'handshake':asset(handshake)}))
 rc=child.wait()
 if rc!=0:raise RuntimeError('controller_child_failed:'+str(rc))
 return ensure_complete(run)

def merged_exports(p,receipt,mass):
 first=load_first(p/'first_processed.jsonl');qualified={i:r['manifest'] for i,r in first.items() if r['status']=='qualified'};failed=[]
 for run in [receipt['runs']['C']['directory']]+([mass['directory']] if mass.get('directory') else []):
  db=sqlite3.connect('file:'+str(Path(run)/'status.sqlite')+'?mode=ro',uri=True)
  try:
   for body,status in db.execute('select result,status from samples'):
    if not body:continue
    r=json.loads(body)
    if status=='qualified':qualified[r['id']]=r['manifest']
    elif status=='abandoned':failed.append(r)
  finally:db.close()
 for manifest in qualified.values():
  for f,h in ASSETS:checked({'file':manifest[f],'sha256':manifest[h]},clean=True)
 atomic(p/'qualified_merged.jsonl.tmp_summary',{'count':len(qualified)})
 immutable(p/'qualified_merged.jsonl',b''.join(raw(qualified[i]) for i in sorted(qualified)));immutable(p/'failed_attempts.jsonl',b''.join(raw(r) for r in failed))
 return {'qualified':len(qualified),'prior_qualified_preserved':sum(r['status']=='qualified' for r in first.values()),'failed_attempts':len(failed),'separate_Python_production_incremental_index_included':False,'all_merged_5_clean_assets_verified':True}

def supervise(program_dir,workers,case_timeout,nonce):
 controller,_,_=modules();p=owned(program_dir)
 with (p/'program.lock').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);freeze=json.loads((p/'implementation.json').read_bytes());controller.check_pins(freeze['pins']);identity=controller.process_identity();owner={'pid':os.getpid(),'start_ticks':identity['start_ticks'],'nonce':nonce,'argv':sys.argv,'implementation_identity_sha256':freeze['implementation_identity_sha256'],'program_dir':str(p),'watch':False};atomic(p/'program_owner.json',owner);receipt=json.loads((p/'receipt.json').read_bytes())
  try:
   wait_ack(p/('launch_ack_'+nonce+'.json'),owner,nonce)
   if (p/'program_infrastructure_stop.json').exists():raise RuntimeError('existing_program_infrastructure_stop_requires_new_freeze')
   for phase in ('B','C'):
    atomic(p/'program_state.json',{'stage':'validation_'+phase});run_controller_phase(receipt['runs'][phase]['directory'],workers,case_timeout,p)
   gate=evaluate(p);atomic(p/'program_state.json',{'stage':'scope_release','approved_units':gate['approved_units']});mass=build_mass(p,gate);immutable(p/'mass_launch_receipt.json',raw(mass))
   if mass['directory']:run_controller_phase(mass['directory'],workers,case_timeout,p)
   scope_states=final_scope_export(p,receipt,mass);merged=merged_exports(p,receipt,mass)
   atomic(p/'program_summary.json',{'state':'finite_program_complete','scope_final_states':scope_states,'indexes':merged,'approved_units':gate['approved_units'],'validation_gate':asset(p/'release_gate.json'),'mass':mass,'model_calls':0,'requires_agent_watch':False})
  except BaseException as e:
   if not (p/'scope_disposition.jsonl').exists():
    ff=load_first(p/'first_processed.jsonl');immutable(p/'scope_disposition.jsonl',b''.join(raw({'id':r['id'],'format':r['format'],'state':'preserved_prior_qualified' if ff[r['id']]['status']=='qualified' else 'blocked_program_infrastructure_not_converted','converted_by_this_program':False}) for r in readrows(p/'scope.jsonl')))
   atomic(p/'program_infrastructure_stop.json',{'stage':'supervisor','error_type':type(e).__name__,'reason':str(e),'model_calls':0});raise
 return json.loads((p/'program_summary.json').read_bytes())

def launch(program_dir,workers=4,case_timeout=900):
 if not 1<=workers<=24 or not 1<=case_timeout<=1800:raise ValueError('resource_limits')
 p=owned(program_dir);controller,_,_=modules();freeze=json.loads((p/'implementation.json').read_bytes());controller.check_pins(freeze['pins'])
 if (p/'launch_receipt.json').exists() or (p/'program_owner.json').exists():raise ValueError('program_already_launched_no_automatic_retry')
 nonce=uuid.uuid4().hex;argv=[sys.executable,'-B',str(Path(__file__).resolve()),'supervise','--program-dir',str(p),'--workers',str(workers),'--case-timeout',str(case_timeout),'--nonce',nonce]
 with (p/'supervisor.log').open('ab') as log:child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
 from initial_conversion_process_v1 import identity
 birth=identity(child.pid);deadline=time.monotonic()+10;owner=None
 while time.monotonic()<deadline:
  if child.poll() is not None:raise RuntimeError('program_exited_before_identity_handshake')
  try:
   owner=json.loads((p/'program_owner.json').read_bytes());current=identity(child.pid);command=Path('/proc',str(child.pid),'cmdline').read_bytes().split(b'\0')
   if birth and current and owner.get('pid')==child.pid and owner.get('nonce')==nonce and owner.get('start_ticks')==birth['start_ticks']==current['start_ticks'] and str(Path(__file__).resolve()).encode() in command and str(p).encode() in command:break
  except (OSError,ValueError):pass
  time.sleep(.05)
 else:raise RuntimeError('program_identity_handshake_timeout')
 immutable(p/('launch_ack_'+nonce+'.json'),raw(owner))
 result={'pid':child.pid,'start_ticks':birth['start_ticks'],'argv':argv,'nonce':nonce,'owner':owner,'program_dir':str(p),'log':str(p/'supervisor.log'),'finite':True,'watch':False};immutable(p/'launch_receipt.json',raw(result));return result

def status(program_dir):
 p=owned(program_dir);return {n:json.loads((p/n).read_bytes()) for n in ('program_owner.json','program_state.json','program_summary.json','program_infrastructure_stop.json','mass_launch_receipt.json') if (p/n).exists()}
def cli():
 p=argparse.ArgumentParser();p.add_argument('action',choices=('identity','prepare','launch','supervise','evaluate','status'));p.add_argument('--program-dir');p.add_argument('--audit-dir');p.add_argument('--scope-manifest');p.add_argument('--first-processed');p.add_argument('--controls-proof');p.add_argument('--run-id');p.add_argument('--workers',type=int,default=4);p.add_argument('--case-timeout',type=float,default=900);p.add_argument('--nonce');a=p.parse_args()
 if a.action=='identity':result=implementation_template()
 elif a.action=='prepare':result=prepare(a.audit_dir,a.scope_manifest,a.first_processed,a.controls_proof,a.run_id)
 elif a.action=='launch':result=launch(a.program_dir,a.workers,a.case_timeout)
 elif a.action=='supervise':result=supervise(a.program_dir,a.workers,a.case_timeout,a.nonce)
 elif a.action=='evaluate':result=evaluate(a.program_dir)
 else:result=status(a.program_dir)
 print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':cli()
