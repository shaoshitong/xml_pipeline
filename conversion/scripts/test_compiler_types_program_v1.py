import copy,importlib.util,json,tempfile,unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
S=Path(__file__).parent
spec=importlib.util.spec_from_file_location('program',S/'compiler_types_program_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
U='drawio_existing_native_ir_v1'
class FakeController:
 def implementation_identity(self,f):return f['implementation_identity']
 def implementation_digest(self,f):return f['implementation_identity_sha256']
class ProgramTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.oldroot=m.R;m.R=self.root;self.clean=self.root/'clean';self.clean.mkdir();self.mods=patch.object(m,'modules',return_value=(FakeController(),None,None));self.mods.start();self.n=0
  self.freeze={'quality_policy':'round2_full_source_native_quality_v1:TEST','qa_bindings':{'test':'same_BC'},'qa_policy_sha256':m.sha(m.raw({'test':'same_BC'})),'pins':{'/frozen.py':'a'*64},'implementation_identity':{'test':'identity'},'implementation_identity_sha256':'i'*64}
 def tearDown(self):self.mods.stop();m.R=self.oldroot;self.tmp.cleanup()
 def put(self,name,v,raw=False):
  p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v if raw else m.raw(v));return {'file':str(p),'sha256':m.sha(p.read_bytes())}
 def fixture(self,kind='positive',id='a'*64):
  code=self.put('clean/'+kind+'.drawio',b'<xml/>',True);image=self.put('clean/'+kind+'.png',b'png',True);source=self.put('clean/'+kind+'.source',b'source',True);ref=self.put('clean/'+kind+'.ref',b'ref',True)
  manifest={'id':id,'code_file':str(Path(code['file']).relative_to(self.root)),'code_sha256':code['sha256'],'image_file':str(Path(image['file']).relative_to(self.root)),'image_sha256':image['sha256'],'original_source_code':str(Path(source['file']).relative_to(self.root)),'source_code_sha256':source['sha256'],'original_reference':str(Path(ref['file']).relative_to(self.root)),'source_image_sha256':ref['sha256']}
  metadata={**manifest,'automatic_quality_policy':self.freeze['quality_policy'],'automatic_quality_audit':kind+'/audit.json'};meta=self.put('clean/'+kind+'.metadata',metadata);manifest.update(metadata_file=str(Path(meta['file']).relative_to(self.root)),metadata_sha256=meta['sha256'])
  s={'pair_sha256':id,'format':'drawio','code_sha256':source['sha256'],'image_sha256':ref['sha256']};record={**manifest};sr=self.put(kind+'/source_record.json',record);request={'id':id,'seq':1,'compiler_unit':U,'source':s,'pins':self.freeze['pins'],'source_record_sha256':sr['sha256']}
  candidate=self.put('clean/'+kind+'_override.json',record);request['development_candidate']=candidate['file']
  if kind=='negative':request['negative_control']=True
  else:request['evaluation_phase']='baseline'
  req=self.put(kind+'/request.json',request);qa={'id':id,'policy':self.freeze['quality_policy'],'round2_quality_bindings':self.freeze['qa_bindings'],'input_code_sha256':code['sha256'],'new_png_sha256':image['sha256'],'state':'qualified','failures':[],'checks':{'source':{'ok':True},'visual':{'ok':True},'native_editing':{'ok':True},'fonts':{'all_rendered_fonts_embedded':True},'structure':{},'resources':{},'text_paint':{},'render':{'code_sha256':code['sha256'],'image_sha256':image['sha256'],'strict_outside_page_pixels':0}}}
  if kind=='negative':qa.update(state='rejected',failures=['dangling_parent']);qa['checks'].pop('structure')
  qf=self.put(kind+'/audit.json',qa);result={'id':id,'seq':1,'compiler_unit':U,'source_code_sha256':source['sha256'],'source_image_sha256':ref['sha256'],'quality_report':str(Path(qf['file']).relative_to(self.root)),'quality_policy':self.freeze['quality_policy'],'model_calls':0,'status':'qualified' if kind=='positive' else 'abandoned','manifest':manifest,'repair_steps':[],'candidate_code_sha256':code['sha256'],'candidate_image_sha256':image['sha256']};rf=self.put(kind+'/result.json',result);iso=self.put(kind+'/isolation.json',{'ok':True,'returncode':0,'cleanup_complete':True,'deadline_exceeded':False})
  inputs=[dict(req,role='request'),dict(sr,role='source_record')]
  inputs.append(dict(candidate,role='development_candidate'))
  row={'control_id':kind,'kind':kind,'compiler_unit':U,'input_assets':inputs};expect={'control_id':kind,'kind':kind,'compiler_unit':U,'expected_status':'qualified' if kind=='positive' else 'abandoned','expected_failure_stage':None if kind=='positive' else 'structure','expected_failure_reason':None if kind=='positive' else 'dangling_parent'};out={'control_id':kind,'result':rf,'quality_audit':qf,'isolation':iso}
  return row,expect,out,result,qa,request
 def bundle(self):
  p=self.fixture();n=self.fixture('negative','b'*64);proof={'schema':'compiler_types_controls_proof_v1','implementation_identity':self.freeze['implementation_identity'],'implementation_identity_sha256':self.freeze['implementation_identity_sha256'],'required_positive_ids':{U:['a'*64]}}
  for key,index in [('controls_manifest',0),('expectations',1),('outcomes',2)]:proof[key]=self.put(key+'.jsonl',b''.join(m.raw(x[index]) for x in (p,n)),True)
  return proof,p,n
 def pairs(self,n=30,q=6,b=0):return [{'id':str(i),'compiler_unit':U,'cluster':str(i),'B':'qualified' if i<b else 'abandoned','C':'qualified' if i<q else 'abandoned'} for i in range(n)]
 def test_gate_exact_six_of30_and_five_new(self):self.assertTrue(m.decisions(self.pairs(b=1),{U})[U]['passed'])
 def test_gate_five_of30_below20percent(self):self.assertFalse(m.decisions(self.pairs(q=5),{U})[U]['passed'])
 def test_gate_new_gain_not_validator_only(self):self.assertFalse(m.decisions(self.pairs(b=3),{U})[U]['passed'])
 def test_gate_positive_regression_blocks(self):
  p=self.pairs();p[-1]['B']='qualified';self.assertFalse(m.decisions(p,{U})[U]['passed'])
 def test_gate_infra_blocks(self):
  p=self.pairs();p[0]['infrastructure_failure']=True;self.assertFalse(m.decisions(p,{U})[U]['passed'])
 def test_gate_duplicate_clusters_blocks(self):
  p=self.pairs();p[0]['cluster']=p[1]['cluster'];self.assertFalse(m.decisions(p,{U})[U]['passed'])
 def test_gate_missing_controls_blocks(self):self.assertFalse(m.decisions(self.pairs(),set())[U]['passed'])
 def test_gate_no_dropped_failure_denominator(self):self.assertEqual(m.decisions(self.pairs(q=6),{U})[U]['samples'],30)
 def test_asset_hash_tamper_rejected(self):
  a=self.put('x',b'a',True);Path(a['file']).write_bytes(b'b');self.assertRaises(ValueError,m.checked,a)
 def test_full_qa_checks_five_assets(self):
  p=self.fixture();self.assertTrue(m.full_quality(p[3],p[4],p[5],self.freeze));Path(self.root/p[3]['manifest']['metadata_file']).write_bytes(b'bad');self.assertRaises(ValueError,m.full_quality,p[3],p[4],p[5],self.freeze)
 def test_full_qa_missing_source_gate(self):
  p=self.fixture();p[4]['checks'].pop('source');self.assertRaises(ValueError,m.full_quality,p[3],p[4],p[5],self.freeze)
 def test_full_qa_policy_not_bool(self):
  p=self.fixture();p[4]['policy']='other';self.assertRaises(ValueError,m.full_quality,p[3],p[4],p[5],self.freeze)
 def test_full_qa_fresh_png_bound(self):
  p=self.fixture();p[4]['checks']['render']['image_sha256']='bad';self.assertRaises(ValueError,m.full_quality,p[3],p[4],p[5],self.freeze)
 def test_controls_reconstruct_negative_missing_structure_with_independent_check(self):
  proof,_,_=self.bundle()
  with patch.object(m,'structure_rejection',return_value=True) as checker:
   result=m.validate_control_bundle(proof,self.freeze,{U});self.assertEqual(result['counts'][U],{'positive':1,'negative':1});checker.assert_called_once()
 def test_controls_failure_string_without_independent_check_rejected(self):
  proof,_,_=self.bundle()
  with patch.object(m,'structure_rejection',return_value=False):self.assertRaises(ValueError,m.validate_control_bundle,proof,self.freeze,{U})
 def test_controls_pass_boolean_ignored(self):
  proof,_,_=self.bundle();proof['passed']=True;proof['controls_manifest']['sha256']='bad';self.assertRaises(ValueError,m.validate_control_bundle,proof,self.freeze,{U})
 def test_controls_preregistered_positive_required(self):
  proof,_,_=self.bundle();proof['required_positive_ids']={U:['c'*64]}
  with patch.object(m,'structure_rejection',return_value=True):self.assertRaises(ValueError,m.validate_control_bundle,proof,self.freeze,{U})
 def test_first_screen_not_complete_rejected(self):
  p=self.root/'first.jsonl';p.write_bytes(m.raw({'id':'x','status':'running'}));self.assertRaises(ValueError,m.load_first,p)
 def test_unsupported_validation_IR_stays_in_cohort_and_denominator(self):
  job=['x',None,'drawio',None,json.dumps({'format':'drawio'}),None,None,None,None,None]
  case=SimpleNamespace(static_support=lambda j:{'supported':False,'reasons':['no_existing_native_ir']},unit=lambda f:U)
  with patch.object(m,'modules',return_value=(None,None,case)):
   row=m.canonical_task(job,{'status':'abandoned'},7,'source-unit','cluster',allow_unsupported=True)
   self.assertEqual(row['id'],'x');self.assertEqual(row['seq'],7);self.assertFalse(row['existing_IR_admission']['supported']);self.assertIsNone(row['baseline_code_sha256'])
   self.assertRaises(ValueError,m.canonical_task,job,{},7,'source-unit')
 def test_supported_IR_revision_drift_still_fails_before_dispatch(self):
  record={'code_sha256':'new','image_sha256':'same'};job=['x',None,'drawio',None,json.dumps({'format':'drawio'}),None,None,None,None,json.dumps(record)]
  case=SimpleNamespace(static_support=lambda j:{'supported':True},unit=lambda f:U)
  with patch.object(m,'modules',return_value=(None,None,case)):
   self.assertRaises(ValueError,m.canonical_task,job,{'candidate_code_sha256':'old','candidate_image_sha256':'same'},1,'source-unit',None,True)
 def test_current_baseline_is_frozen_when_historical_first_candidate_was_absent(self):
  record={'code_sha256':'current','image_sha256':'image'};job=['x',None,'drawio',None,json.dumps({'format':'drawio'}),None,None,None,None,json.dumps(record)]
  case=SimpleNamespace(static_support=lambda j:{'supported':True},unit=lambda f:U)
  with patch.object(m,'modules',return_value=(None,None,case)):
   row=m.canonical_task(job,{'status':'abandoned'},1,'source-unit')
   self.assertEqual(row['baseline_code_sha256'],'current');self.assertFalse(row['historical_first_candidate_comparable'])
 def test_positive_may_not_repair_regression(self):
  proof,p,n=self.bundle();ref=p[2]['result'];v=json.loads(Path(ref['file']).read_bytes());v['repair_steps']=[{'action':'font','ok':True}];Path(ref['file']).write_bytes(m.raw(v));proof['outcomes']=self.put('outcomes.changed',b''.join(m.raw(x) for x in [dict(p[2],result=m.asset(ref['file'])),n[2]]),True)
  with patch.object(m,'structure_rejection',return_value=True):self.assertRaises(ValueError,m.validate_control_bundle,proof,self.freeze,{U})
 def test_negative_false_gate_does_not_bypass_recompute(self):
  proof,p,n=self.bundle();qref=n[2]['quality_audit'];v=json.loads(Path(qref['file']).read_bytes());v['checks']['structure']={'ok':False};Path(qref['file']).write_bytes(m.raw(v));proof['outcomes']=self.put('outcomes.changed',b''.join(m.raw(x) for x in [p[2],dict(n[2],quality_audit=m.asset(qref['file']))]),True)
  with patch.object(m,'structure_rejection',return_value=False):self.assertRaises(ValueError,m.validate_control_bundle,proof,self.freeze,{U})
 def test_wait_ack_timeout_is_fail_closed(self):self.assertRaises(RuntimeError,m.wait_ack,self.root/'missing',{'pid':1},'nonce',0)
 def test_B_infrastructure_prevents_C_dispatch(self):
  p=self.root/'programs'/'x';p.mkdir(parents=True);(p/'implementation.json').write_bytes(m.raw(self.freeze));(p/'receipt.json').write_bytes(m.raw({'runs':{'B':{'directory':'B'},'C':{'directory':'C'}}}));(p/'scope.jsonl').write_bytes(m.raw({'id':'x','format':'html'}));(p/'first_processed.jsonl').write_bytes(m.raw({'id':'x','status':'abandoned'}))
  fake=FakeController();fake.check_pins=lambda p:None;fake.process_identity=lambda:{'start_ticks':1}
  with patch.object(m,'PROGRAMS',self.root/'programs'),patch.object(m,'modules',return_value=(fake,None,None)),patch.object(m,'wait_ack',return_value=True),patch.object(m,'run_controller_phase',side_effect=RuntimeError('infra')) as phase:
   self.assertRaises(RuntimeError,m.supervise,p,1,10,'nonce');self.assertEqual(phase.call_count,1);self.assertTrue((p/'program_infrastructure_stop.json').exists());self.assertFalse((p/'program_summary.json').exists())
 def test_no_source_conversion_from_prepare_or_launch_import(self):
  tree=ast.parse(Path(m.__file__).read_text());self.assertFalse(any(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) for n in tree.body))
import ast
if __name__=='__main__':unittest.main()
