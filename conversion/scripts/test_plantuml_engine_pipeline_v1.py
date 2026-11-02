import unittest,copy,uuid,json,tempfile,hashlib,types
from pathlib import Path
import compiler_plantuml_engine_unseen_pool_v1 as pool
import compiler_plantuml_engine_once_v1 as once
class Closure(unittest.TestCase):
 def row(self,i,c,img,keys=(),pending=True,known=True):
  return {'audit':{},'request':{'id':i,'source':{'code_sha256':c,'image_sha256':img}},'keys':{'exact_original_code:'+c,'exact_original_image:'+img}|set(keys),'pending':pending,'known':known}
 def test_transitive_unsupported_bridge(self):
  a=self.row('a','c1','i1',pending=False);b=self.row('b','c1','i2',pending=False);c=self.row('c','c2','i2');e,n=pool.independent_components([a,b,c],{'a'},set(),set(),set());self.assertFalse(e);self.assertIn('transitive',c['audit']['disposition'])
 def test_accepted_bridge_retained(self):
  a=self.row('a','c1','i1',pending=False);b=self.row('b','c1','i2',pending=False);c=self.row('c','c2','i2');e,n=pool.independent_components([a,b,c],set(),{'c1'},set(),set());self.assertFalse(e)
 def test_cross_format_identity_bridge(self):
  a=self.row('a','c1','i1',pending=False);f=self.row('foreign','c1','i2',pending=False);c=self.row('c','c2','i2');e,n=pool.independent_components([a,f,c],{'a'},set(),set(),set());self.assertFalse(e)
 def test_unknown_bridge_does_not_claim_novelty(self):
  a=self.row('a','c1','i1',known=False,pending=False);b=self.row('b','c1','i2');e,n=pool.independent_components([a,b],set(),set(),set(),set());self.assertFalse(e);self.assertIn('unknown',b['audit']['disposition'])
 def test_one_per_connected_component(self):
  a=self.row('a','c1','i1');b=self.row('b','c1','i2');c=self.row('c','c2','i3');e,n=pool.independent_components([a,b,c],set(),set(),set(),set());self.assertEqual(len(e),2)
 def test_reserved_family_contaminates_full_component(self):
  a=self.row('a','c1','i1',{'family:X'});b=self.row('b','c1','i2');e,n=pool.independent_components([a,b],set(),set(),set(),{'family:X'});self.assertFalse(e)
 def test_existing_QA_is_not_normal_conversion(self):self.assertFalse(pool.was_normal_candidate_attempt({'evaluation_phase':'control_positive','existing_development_candidate':'x'},{},False))
 def test_explicit_guard_deferred_is_not_normal_conversion(self):self.assertFalse(pool.was_normal_candidate_attempt({}, {'error_type':'ValueError','reason':'retryable_iteration_case_failure','detail':'deferred_birth_verified_active_conversion_overlap'},False))
 def test_ambiguous_interruption_is_not_reexecuted(self):self.assertTrue(pool.was_normal_candidate_attempt({}, {},False))
 def test_actual_frontend_file_proves_normal_call(self):self.assertTrue(pool.was_normal_candidate_attempt({}, {},True))
 def test_past_C1_is_excluded(self):self.assertIn('05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798',{r['id']for r in pool.prior_candidate_attempts()})
class Once(unittest.TestCase):
 def test_atomic_claim_refuses_repeat_and_conflict(self):
  folder=once.W/'prototype/plantuml_engine_once_test'/uuid.uuid4().hex;folder.mkdir(parents=True);p=folder/'dummy.py';p.write_text('dummy source '+uuid.uuid4().hex);compiler=types.SimpleNamespace(__file__=str(p),configuration=lambda:{'policy':'dummy'});ident='f'*64;src={'code_sha256':'a'*64,'image_sha256':'b'*64};request=folder/'request.json';request.write_text('{}');first=once.claim(ident,src,compiler,request);self.assertTrue(first['normal_frontend_claimed_once'])
  with self.assertRaisesRegex(ValueError,'already_claimed'):once.claim(ident,src,compiler,request)
  with self.assertRaisesRegex(RuntimeError,'identity_conflict'):once.claim(ident,dict(src,code_sha256='c'*64),compiler,request)
  self.assertEqual(len(once.claims(compiler)),1);claim_dir=once.ROOT/once.core(compiler)
  for file in claim_dir.iterdir():file.unlink()
  claim_dir.rmdir()
if __name__=='__main__':unittest.main(verbosity=2)
