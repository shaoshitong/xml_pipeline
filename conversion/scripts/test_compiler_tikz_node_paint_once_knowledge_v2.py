from pathlib import Path
import json,sqlite3,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import compiler_tikz_node_paint_source_contract_v1 as contract
import compiler_tikz_node_paint_iteration_case_v1 as case
import compiler_tikz_node_paint_iteration_pool_v2 as pool
import compiler_source_core_attempts_v3 as history

class SourceCoreIdentityTests(unittest.TestCase):
 def test_unit_adapter_keeps_only_original_frontend_pins_in_source_core(self):
  import compiler_tikz_node_paint_viewport_v2 as original
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);path=root/contract.CATALOG;path.parent.mkdir(parents=True);path.write_bytes(b'catalog')
   raw=dict(policy='source_semantics_frozen',pins={'/frozen/source_core.py':'a'*64},units={'tikz':original.UNITS['tikz']})
   expected={**raw,'unit':original.UNITS['tikz']};identity=history.core_identity(expected)
   with patch.object(contract,'R',root),patch.object(contract,'CATALOG_SHA256',contract.sha(path.read_bytes())),patch.object(contract,'CORE_KEY',identity['key']),patch.object(original,'configuration',return_value=raw):result=contract.configuration()
   self.assertEqual(result,expected);self.assertEqual(result['pins'],raw['pins']);self.assertNotIn(str(Path(case.__file__)),result['pins'])
 def test_actual_once_guard_uses_new_catalog_and_excludes_only_current_run(self):
  configuration=dict(unit='unit',policy='policy',pins={'source':'a'*64});compiler=SimpleNamespace(configuration=lambda:configuration)
  with patch.object(history,'guard',return_value=dict(already_attempted=False,events=[]))as read:case.once_guard('id',{},compiler,'/owned/current_C')
  self.assertEqual(read.call_args.kwargs['catalog'],contract.CATALOG);self.assertEqual(read.call_args.kwargs['current_run'],'current_C')

class GlobalSeenKnowledgeTests(unittest.TestCase):
 def test_all_ledger_attempted_IDs_exclude_scores_and_preserve_fresh_bulk_eligibility(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);ledgers=[]
   for number,items in enumerate(([('prior_mass',1),('queued_only',0)],[('prior_development',1),('baseline_seen',1)])):
    path=root/(str(number)+'.sqlite');ledgers.append(path)
    with sqlite3.connect(path)as db:
     db.execute('create table samples(id text,attempts integer,result text)');db.executemany('insert into samples values(?,?,?)',[(identifier,count,'THIS IS DELIBERATELY NOT RESULT JSON')for identifier,count in items])
   with patch('compiler_mermaid_alpha_qualifications_v2.discover_ledger_paths',return_value=ledgers):observed=pool.all_prior_attempted_ids()
   self.assertEqual(observed,{'prior_mass','prior_development','baseline_seen'})
   # This set is only a fresh-validation knowledge exclusion. Source static
   # support and the entire supported bulk population retain these sources.
   self.assertNotIn('queued_only',observed)

class CanonicalClaimPrecallTests(unittest.TestCase):
 def test_live_or_uncertain_claim_defers_only_this_target_before_normal(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);work=root/'conversion/compiler_iterations/run/one';work.mkdir(parents=True)
   source=dict(pair_sha256='a'*64,source='provider',format='tikz',category='scientific_diagram',code_sha256='b'*64,image_sha256='c'*64)
   job=(source['pair_sha256'],source['category'],'tikz',source['source'],json.dumps(source),'pending',None,0,None,None,None,None,123)
   snapshot=dict(id=job[0],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256']);compiler=SimpleNamespace(UNIT='unit',VERSION='mock',static_support=Mock(return_value=dict(supported=True,source_capture_snapshot=snapshot)),original=Mock(side_effect=lambda record,given:(record,given)),convert=Mock())
   request=dict(id=job[0],seq=1,source=source,compiler_unit='unit',work=str(work),pins={},mode='validation',evaluation_phase='candidate',source_capture_snapshot=snapshot);path=work/'request.json';path.write_text(json.dumps(request))
   db=Mock();db.__enter__=Mock(return_value=db);db.__exit__=Mock(return_value=False);db.execute.return_value.fetchone.return_value=job
   with patch.object(case,'W',root/'conversion'),patch.object(case,'R',root),patch.object(case,'bindings',return_value=(compiler,None)),patch.object(case,'ordinary_overlap_guard'),patch.object(case,'qualified_guard'),patch.object(case,'once_guard'),patch.object(case.sqlite3,'connect',return_value=db),patch('compiler_plantuml_engine_canonical_claim_v1.diagnose',return_value=dict(conversion_allowed=False)):
    result=case.run(path)
   self.assertEqual(result['phase'],'input');self.assertEqual(result['detail'],'deferred_live_or_unproved_canonical_worker_claim');self.assertFalse(result['infrastructure_failure']);compiler.convert.assert_not_called();self.assertFalse(history.normal_was_called(request,result,None))

if __name__=='__main__':unittest.main()
