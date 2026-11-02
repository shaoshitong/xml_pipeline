import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import compiler_html_source_chain_once_v1 as finalizer

class PreparationTests(unittest.TestCase):
 def fixture(self,directory):
  files={'source_audit.jsonl':b'{}\n'*24739,'supported_population.jsonl':b'{}\n'*200,'selected.jsonl':b'{}\n'*100}
  for name,data in files.items():(directory/name).write_bytes(data)
  freeze={'inputs':{'scope':{'sha256':'scope'},'development':{'sha256':'development'},'global_development':{'sha256':'global'}},'source_frontend_configuration':{'policy':'fixed'},'controls_proof':{'sha256':'controls'},'pins':{'method':'digest',str(finalizer.GLOBAL_DEVELOPMENT):'global'}}
  info={'scope':24739,'source_only':True,'conversion_or_rendering':False,'scope_index_sha256':'scope','development_input_sha256':'development','development_inputs':{str(finalizer.GLOBAL_DEVELOPMENT):'global'},'audited_scope_rows':24739,'frozen_implementation':{'policy':'fixed'},'controls_proof':{'sha256':'controls'},'files':{n:{'sha256':finalizer.sha(d),'bytes':len(d)} for n,d in files.items()},'excluded_accepted':1,'counters':{'supported_remaining_population':200},'selected':100,'minimum100_met':True,'method_pins':{'method':'digest'}}
  (directory/'summary.json').write_text(json.dumps(info));return freeze,info
 def test_completed_scope_and_full_population_are_required(self):
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp);freeze,info=self.fixture(directory)
   self.assertEqual(finalizer.validate_summary(directory,freeze)['scope'],24739)
   info['audited_scope_rows']=24738;(directory/'summary.json').write_text(json.dumps(info))
   with self.assertRaisesRegex(ValueError,'all_24739'):finalizer.validate_summary(directory,freeze)
 def test_changed_actual_file_cannot_use_old_summary(self):
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp);freeze,_=self.fixture(directory);(directory/'selected.jsonl').write_bytes(b'{}\n'*99)
   with self.assertRaisesRegex(ValueError,'incomplete_asset'):finalizer.validate_summary(directory,freeze)
 def test_input_SHA_and_frozen_configuration_are_bound(self):
  for field,value in [('scope_index_sha256','other'),('frozen_implementation',{'policy':'changed'}),('controls_proof',{'sha256':'other'})]:
   with tempfile.TemporaryDirectory() as tmp:
    directory=Path(tmp);freeze,info=self.fixture(directory);info[field]=value;(directory/'summary.json').write_text(json.dumps(info))
    with self.assertRaisesRegex(ValueError,'changed'):finalizer.validate_summary(directory,freeze)
 def test_population_counter_and_full_100_cannot_be_downgraded(self):
  for field,value in [('counters',{'supported_remaining_population':199}),('selected',99),('minimum100_met',False)]:
   with tempfile.TemporaryDirectory() as tmp:
    directory=Path(tmp);freeze,info=self.fixture(directory);info[field]=value;(directory/'summary.json').write_text(json.dumps(info))
    with self.assertRaises(ValueError):finalizer.validate_summary(directory,freeze)
 def test_unfrozen_source_pool_method_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp);freeze,info=self.fixture(directory);info['method_pins']['method']='other';(directory/'summary.json').write_text(json.dumps(info))
   with self.assertRaisesRegex(ValueError,'method_not_in_preparation_freeze'):finalizer.validate_summary(directory,freeze)
 def test_reused_PID_is_not_treated_as_a_running_original_scan(self):
  with patch.object(finalizer,'identity',return_value={'start_ticks':2,'state':'R'}):
   with self.assertRaisesRegex(RuntimeError,'PID_reused'):finalizer.source_running({'pid':1,'start_ticks':1,'argv':['original']})
 def test_finished_or_absent_source_does_not_wait_for_other_work(self):
  for actual in (None,{'start_ticks':1,'state':'Z'}):
   with patch.object(finalizer,'identity',return_value=actual):self.assertFalse(finalizer.source_running({'pid':1,'start_ticks':1,'argv':['original']}))
 def test_wait_timeout_never_restarts_or_prepares(self):
  with patch.object(finalizer,'source_running',return_value=True),patch.object(finalizer.time,'monotonic',side_effect=[0,2]),patch.object(finalizer.program,'prepare') as prepare,patch.object(finalizer.subprocess,'Popen') as child:
   with self.assertRaisesRegex(TimeoutError,'no_restart'):finalizer.wait_source({},1)
   prepare.assert_not_called();child.assert_not_called()

if __name__=='__main__':unittest.main()
