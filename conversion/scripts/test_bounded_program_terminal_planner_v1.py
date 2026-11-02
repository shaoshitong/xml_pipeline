import copy,hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
import bounded_program_terminal_planner_v1 as m
import failure_equivalence_tikz_v1 as equivalence

class Guards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'clean/pair').mkdir(parents=True);(self.root/'conversion').mkdir()
  self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
  self.db.executescript('create table jobs(id primary key,'+m.JOB_COLUMNS.replace(',',',')+');create table processing_outcomes_v2(id primary key,category,format,source_code_hash,source_image_hash,status,reason,record,updated_at);create table auto_quality_audits_v1(id,code_hash,image_hash,policy,state,record,updated_at);create table harness_queue_v3(id,state,worker_pid);')
  self.identifier=m.sha(b'original');self.record={'id':self.identifier,'source_pair_sha256':self.identifier,'source':'source','source_format':'tikz','category':'scientific_diagram'}
  for key,digest,name,blob in [('code_file','code_sha256','diagram.drawio',b'<mxfile/>'),('image_file','image_sha256','image.png',b'png'),('original_reference','source_image_sha256','source.png',b'reference'),('original_source_code','source_code_sha256','source.tex',b'original')]:
   path=self.root/'clean/pair'/name;path.write_bytes(blob);self.record[key]=str(path.relative_to(self.root));self.record[digest]=m.sha(blob)
  self.original={'pair_sha256':self.identifier,'source':'source','format':'tikz','category':'scientific_diagram','code_sha256':self.record['source_code_sha256'],'image_sha256':self.record['source_image_sha256']}
  self.db.execute('insert into jobs values('+','.join('?' for _ in range(11))+')',(self.identifier,'needs_quality_repair',None,json.dumps(self.original),json.dumps(self.record),'old',None,1,'source','scientific_diagram','tikz'))
  self.db.execute('insert into processing_outcomes_v2 values(?,?,?,?,?,?,?,?,?)',(self.identifier,'scientific_diagram','tikz',self.original['code_sha256'],self.original['image_sha256'],'pending',None,None,'old'))
  self.audit={'id':self.identifier,'state':'repair_required','accepted':False,'input_code_sha256':self.record['code_sha256'],'input_image_sha256':self.record['image_sha256'],'source_code_sha256':self.original['code_sha256'],'source_image_sha256':self.original['image_sha256'],'failures':['source_profile_not_implemented: grammar'], 'checks':{'source':{'supported':False,'ok':False,'failures':['unsupported']}}}
  self.db.execute('insert into auto_quality_audits_v1 values(?,?,?,?,?,?,?)',(self.identifier,self.record['code_sha256'],self.record['image_sha256'],'current','repair_required',json.dumps(self.audit),'old'));self.db.commit()
  owner=self.root/'conversion/auto_quality_owner.json';owner.write_text('{}');self.config={'root':str(self.root),'policy':'current','owner_sha256':m.sha(owner.read_bytes()),'equivalences':{},'model_allowlist':[]}
  self.stub=lambda *a:{'reason_code':'verified_semantic_fixture','source_construct_classes':['numeric_or_unbound_path_terminal']}
 def prepare(self):return m.prepare(self.db,self.identifier,self.config,terminal_verifier=self.stub)
 def test_plan_is_readonly_and_revalidates(self):
  changes=self.db.total_changes;plan=self.prepare();self.assertTrue(plan['proposal_only']);self.assertFalse(plan['apply_available']);self.assertEqual(self.db.total_changes,changes);self.assertEqual(m.revalidate(self.db,plan,self.config),'current')
 def test_busy_job_rejected(self):
  self.db.execute('update jobs set worker_pid=4');self.db.commit()
  with self.assertRaises(m.Pending):self.prepare()
 def test_model_owned_rejected(self):
  self.db.execute('insert into harness_queue_v3 values(?,?,?)',(self.identifier,'held',99));self.db.commit()
  with self.assertRaises(m.Pending):self.prepare()
 def test_any_running_deterministic_stage_rejected(self):
  self.db.execute('create table other_stage(id,state)');self.db.execute('insert into other_stage values(?,?)',(self.identifier,'running'));self.db.commit()
  with self.assertRaises(m.Pending):self.prepare()
 def test_qualified_never_abandoned(self):
  self.db.execute("update processing_outcomes_v2 set status='qualified'");self.db.commit()
  with self.assertRaises(m.Pending):self.prepare()
 def test_model_allowlist_reserved(self):
  self.config['model_allowlist']=[self.identifier]
  with self.assertRaises(m.Pending):self.prepare()
 def test_source_identity_mismatch_rejected(self):
  bad={**self.record,'source_code_sha256':m.sha(b'other')};self.db.execute('update jobs set output_record=?',(json.dumps(bad),));self.db.commit()
  with self.assertRaises(m.Pending):self.prepare()
 def test_ssim_failure_alone_never_terminal(self):
  self.audit['failures']=['raster_anomaly: global_fidelity_below_0.90'];self.audit['checks']['source']={'supported':True,'ok':True};self.db.execute('update auto_quality_audits_v1 set record=?',(json.dumps(self.audit),));self.db.commit()
  with self.assertRaises(m.Pending):self.prepare()
 def test_mutated_candidate_stales_plan(self):
  plan=self.prepare();self.db.execute("update jobs set error='changed'");self.db.commit();self.assertEqual(m.revalidate(self.db,plan,self.config),'stale_or_ineligible')
 def test_changed_audit_stales_plan(self):
  plan=self.prepare();self.db.execute("update auto_quality_audits_v1 set updated_at='new'");self.db.commit();self.assertEqual(m.revalidate(self.db,plan,self.config),'stale_or_ineligible')
 def test_changed_payload_stales_plan(self):
  plan=self.prepare();(self.root/self.record['code_file']).write_bytes(b'changed');self.assertEqual(m.revalidate(self.db,plan,self.config),'stale_or_ineligible')
 def test_changed_owner_stales_plan(self):
  plan=self.prepare();(self.root/'conversion/auto_quality_owner.json').write_text('{"new":true}');self.assertEqual(m.revalidate(self.db,plan,self.config),'stale_or_ineligible')
 def test_source_payload_outside_clean_rejected(self):
  outside=self.root/'outside';outside.write_bytes(b'original');(self.root/self.record['original_source_code']).unlink();(self.root/self.record['original_source_code']).symlink_to(outside)
  with self.assertRaises(m.Pending):self.prepare()
 def test_old_read_transaction_rejected(self):
  self.db.execute('begin')
  with self.assertRaises(m.Pending):self.prepare()

class Semantics(unittest.TestCase):
 def test_known_semantic_trace_failure(self):self.assertEqual(m.semantic_classes({'ok':False,'failures':[{'reason':'numeric_or_unbound_path_terminal','picture':'1','path':'2'}]},[]),['numeric_or_unbound_path_terminal'])
 def test_instrumentation_integrity_not_program_semantics(self):
  with self.assertRaises(m.Pending):m.semantic_classes({'ok':False,'failures':[{'reason':'execution_counter_mismatch'}]},[])
 def test_missing_labels_only_explained_by_unsupported_paths(self):
  graph={'ok':False,'failures':[{'reason':'numeric_or_unbound_path_terminal','picture':'1','path':'2'},{'reason':'node_or_label_event_coverage_incomplete','missing':['3'],'extra':[]}]};node={'kind':'node','fields':['1','2','3','label','','','x','1pt','2pt','1']};self.assertIn('node_or_label_event_coverage_incomplete',m.semantic_classes(graph,[node]))
  node['fields'][1]='9'
  with self.assertRaises(m.Pending):m.semantic_classes(graph,[node])
 def test_empty_graph_success_not_terminal(self):
  with self.assertRaises(m.Pending):m.semantic_classes({'ok':True,'failures':[]},[])

class Equivalence(unittest.TestCase):
 def source(self,extra=''):
  return '''def source_baseline(record,xml):\n return record,xml\ndef profile(record,xml,source,native_info=None):\n fmt=record['source_format']\n if fmt=='drawio':return changed_native()\n '''+extra+'''\n return graph(record,xml,source)\ndef require_coverage(coverage):\n if not coverage['supported']:raise ValueError('unsupported')\ndef verify(item):\n try:\n  r=item\n  glyph_profile=bool(r.get('html_actual_text_alignment'))\n  coverage=None if glyph_profile else profile(r,'xml','source')\n  if coverage is not None:require_coverage(coverage)\n  render_native()\n except Exception:pass\n'''
 def test_unrelated_native_HTML_changes_do_not_recheck_TikZ(self):
  old=self.source();new=old.replace('return changed_native()','return completely_new_native()').replace("bool(r.get('html_actual_text_alignment'))","bool(r.get('html_actual_text_alignment') or r.get('html_text_layout_v5'))").replace('  render_native()','  render_with_new_HTML_clip_adapter()');self.assertTrue(equivalence.compare_sources(old,new))
 def test_changed_TikZ_gate_rejected(self):
  old=self.source();new=old.replace('return graph(record,xml,source)','return unsafe_new_graph(record,xml,source)')
  with self.assertRaises(ValueError):equivalence.compare_sources(old,new)
 def test_changed_prefix_resource_gate_rejected(self):
  old=self.source();new=old.replace('  r=item','  r=item\n  skip_source_resources(r)')
  with self.assertRaises(ValueError):equivalence.compare_sources(old,new)
 def test_new_HTML_lineage_cannot_claim_plain_TikZ(self):
  with self.assertRaises(ValueError):equivalence.family_assumptions({'source_format':'tikz','original_source_code':'x','original_reference':'y','html_text_layout_v5':{'proof':'p'}})

if __name__=='__main__':unittest.main()
