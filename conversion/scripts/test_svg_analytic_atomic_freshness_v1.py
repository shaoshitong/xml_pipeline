import copy,json,sqlite3,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import compiler_validation_identity_alias_v1 as aliases
import compiler_validation_sealed_cohort_v1 as sealed
import compiler_validation_reservation_v2 as reservation
import svg_analytic_cohort_refresh_v1 as refresh
import svg_analytic_iteration_program_v1 as program

def request(index,family=None):
 i=f'{index:064x}';source=dict(pair_sha256=i,category='scientific_diagram',format='svg',source='synthetic_fixture',code_sha256=f'{index+100:064x}',image_sha256=f'{index+200:064x}',retained_nested={'full_source':True})
 return dict(id=i,source=source,compiler_unit='unit',source_capture_snapshot=dict(id=i,source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256']),source_record_sha256=program.sha(b''),baseline_code_sha256=None,baseline_image_sha256=None)
def snapshot(**changes):return {**dict(known_source_ids=[],exclusion_keys=[],same_core_normal_events=[],qualified_ids=[],verified_live_ids=[]),**changes}
def fixture_seal(requests,families=None,foreign=()):
 rows=[dict(request=r,known=True,keys={families[n]if families else 'family_'+r['id']})for n,r in enumerate(requests)]+list(foreign)
 result=sealed.build_components(rows,{r['id']for r in requests})
 # Fixture declarations exercise the binding contract; production build asserts
 # the actual complete manifest cardinalities before writing the sealed file.
 result.update(full_scope_records=131904,target_records=26754);return result
class FreshSelectionTests(unittest.TestCase):
 def setUp(self):self.requests=[request(1),request(2),request(3)];self.seal=fixture_seal(self.requests)
 def choose(self,state=None,keys=()):return refresh.choose(self.seal,self.requests,state or snapshot(),frozenset(keys),seed='fixture',limit=100)
 def test_new_cross_kind_reserved_code_reselects_fresh_component(self):
  keys=aliases.normalize_keys([('hard_cluster','exact_original_code:'+self.requests[0]['source']['code_sha256'])]);choice=self.choose(keys=keys);self.assertEqual({r['id']for r in choice['selected']},{r['id']for r in self.requests[1:]});self.assertTrue(choice['all_remaining_observed_families_selected'])
 def test_fresh_consumed_normal_ID_blocks_its_whole_connected_component(self):
  a=self.requests[0]['id'];state=snapshot(exclusion_keys=[['id',a]],known_source_ids=[a],same_core_normal_events=[{'id':a}]);choice=self.choose(state);self.assertNotIn(a,{r['id']for r in choice['selected']});self.assertEqual(choice['current_same_core_normal_events'],1)
 def test_verified_live_overlap_defers_only_target_not_its_inactive_family_neighbor(self):
  self.seal=fixture_seal(self.requests,['shared','shared','other']);a,b=self.requests[:2];choice=self.choose(snapshot(verified_live_ids=[a['id']]));self.assertIn(b['id'],{r['id']for r in choice['selected']});self.assertNotIn(a['id'],{r['id']for r in choice['selected']})
 def test_foreign_member_development_contaminates_full_transitive_bridge(self):
  a=self.requests[0];foreign=request(9);foreign['source']['code_sha256']=a['source']['code_sha256'];self.seal=fixture_seal(self.requests,foreign=[dict(request=foreign,known=True,keys={'foreign_provenance'})]);choice=self.choose(snapshot(exclusion_keys=[['id',foreign['id']]],known_source_ids=[foreign['id']]));self.assertNotIn(a['id'],{r['id']for r in choice['selected']})
 def test_unknown_connected_component_stays_pending_without_mutating_source_requests(self):
  original=copy.deepcopy(self.requests);self.seal['components'][0]['known']=False;self.assertEqual(len(self.choose()['selected']),2);self.assertEqual(self.requests,original)
 def test_incomplete_global_bridge_declaration_fails_before_selection(self):
  self.seal['full_scope_records']=131903
  with self.assertRaisesRegex(ValueError,'bridge_coverage'):self.choose()

class ActualProgramAtomicBindingTests(unittest.TestCase):
 def test_old_alias_arriving_after_audit_reselects_and_binds_phase_bytes_before_mkdir(self):
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp).resolve();W=root/'conversion';W.mkdir();P=root/'pool';P.mkdir();requests=[request(i)for i in (1,2,3)];jobs=[]
   with sqlite3.connect(W/'jobs.sqlite')as db:
    db.execute('create table jobs(id,category,format,source,input_record,state,route,attempts,updated_at,output_record,error,input_manifest,worker_pid)')
    for r in requests:
     s=r['source'];j=(r['id'],s['category'],s['format'],s['source'],json.dumps(s),'pending',None,0,None,None,None,None,None);jobs.append(j);db.execute('insert into jobs values('+','.join('?'for _ in j)+')',j)
   for name in ('selected.jsonl','supported_population.jsonl'):(P/name).write_bytes(b''.join(program.raw(dict(r,seq=i))for i,r in enumerate(requests,1)))
   for name in ('prior_candidate_attempts.jsonl','preserved_qualified.jsonl'):(P/name).write_bytes(b'')
   (P/'sealed_source_components.json').write_bytes(program.raw(fixture_seal(requests)))
   names=('selected.jsonl','supported_population.jsonl','prior_candidate_attempts.jsonl','preserved_qualified.jsonl','sealed_source_components.json')
   info=dict(seed='fixture',prior_same_SOURCE_frontend_distinct_candidate_attempts=0,all_remaining_observed_families_selected=True,eligible_observed_families=3,source_component_counts={},counters={'supported_remaining_population':3},files={n:dict(sha256=program.sha((P/n).read_bytes()))for n in names});(P/'summary.json').write_bytes(program.raw(info))
   registry=root/'release/compiler_v1/validation_registry.sqlite';registry.parent.mkdir(parents=True)
   db=reservation._open(registry);db.execute('insert into reservations values(?,?,?,?,?)',('someone_else','old_cohort','old_run','reserved','immutable old record'));db.execute('insert into reservation_keys values(?,?,?)',('hard_cluster','exact_original_code:'+requests[0]['source']['code_sha256'],'someone_else'));db.close()
   compiler=SimpleNamespace(UNIT='unit',configuration=lambda:{},original=lambda record,job:(record,job));freeze={'implementation_identity_sha256':'f'*64};target=root/'programs/atomic'
   def run_atomic(path,selector,bind_selected,**kwargs):
    self.assertFalse(target.exists())
    def observe(existing,rawkeys):
     self.assertFalse(target.exists());return selector(existing,rawkeys)
    def bind(rows,selection):
     self.assertFalse(target.exists());return bind_selected(rows,selection)
    return reservation.reserve_fresh(path,observe,bind_selected=bind,**kwargs)
   with patch.object(program,'R',root),patch.object(program,'W',W),patch.object(program.common,'R',root),patch.object(program,'PROGRAMS',root/'programs'),patch.object(program,'template',return_value=freeze),patch.object(program.case,'bindings',return_value=(compiler,None)),patch.object(program,'control_bundle',return_value={}),patch.object(program,'check_controls'),patch.object(program,'runtime_controls',return_value={}),patch.object(program.refresh,'knowledge_snapshot',return_value=snapshot()),patch.object(program,'reserve_fresh',side_effect=run_atomic),patch.object(program.controller,'FLOOR',root/'runs'),patch.object(program.controller,'create')as create:
    result=program.prepare(P,'atomic')
   self.assertTrue(result['reserved']);self.assertFalse(result['dispatched']);self.assertEqual(create.call_count,2);selected=program.readrows(target/'selected.jsonl');self.assertEqual({r['id']for r in selected},{requests[1]['id'],requests[2]['id']});record=json.loads((target/'reservation.json').read_bytes());self.assertTrue(record['selection_under_same_write_transaction']);self.assertEqual(record['selected_manifest_sha256'],program.sha((target/'selected.jsonl').read_bytes()));self.assertEqual(record['protocol_sha256'],program.sha((target/'protocol.json').read_bytes()))
   for phase in ('B','C'):
    self.assertEqual({r['id']for r in program.readrows(target/(phase+'.jsonl'))},{r['id']for r in selected})
   with sqlite3.connect(registry)as db:self.assertEqual(db.execute('select record from reservations where reservation_id=?',('someone_else',)).fetchone()[0],'immutable old record');self.assertEqual(db.execute('select count(*)from reservations').fetchone()[0],2)
if __name__=='__main__':unittest.main()
