import json
import concurrent.futures
import multiprocessing
import sys
import os
from pathlib import Path
import tempfile
import unittest

import visual_failure_finite_v1 as f

class FiniteTests(unittest.TestCase):
 def manifest(self):
  items=[];i=0
  for fmt,count in f.EXPECTED.items():
   for _ in range(count):
    i+=1;items.append({'id':f'{i:064x}','source_format':fmt,'logical_visual_route_class':'current_visual_catalog_routes_terminal_or_inapplicable'})
  return {'full_scope':131904,'items':items}
 def test_exact1730_coverage_fixed_formats_and_unique(self):
  out=f.manifest_items(self.manifest());self.assertEqual(len(out),1730);self.assertEqual(len({x['id'] for x in out}),1730)
  self.assertEqual(out[0]['source_format'],'python');self.assertEqual(out[-1]['source_format'],'html')
 def test_missing_extra_or_duplicate_id_refuses(self):
  for kind in ('missing','extra','duplicate'):
   doc=self.manifest()
   if kind=='missing':doc['items'].pop()
   elif kind=='extra':doc['items'].append({**doc['items'][0],'id':'f'*64})
   else:doc['items'][0]['id']=doc['items'][1]['id']
   with self.assertRaises(ValueError):f.manifest_items(doc)
 def test_cohort_outside_fixedclass_is_not_added(self):
  doc=self.manifest();doc['items'].append({'id':'f'*64,'source_format':'mermaid','logical_visual_route_class':'reachable'})
  self.assertEqual(len(f.manifest_items(doc)),1730)
 def test_clip_missing_never_effective_proposal(self):
  self.assertEqual(f.effective_decision({'proposal':True,'reason':'visual'}, {'complete':False}), (False,'clip_dependency_closure_not_complete'))
 def test_nonclip_or_complete_clip_retains_raw_proposal_only(self):
  self.assertEqual(f.effective_decision({'proposal':True,'reason':'visual'}, {'complete':True}), (True,'visual'))
  self.assertEqual(f.effective_decision({'proposal':False,'reason':'retain_pending'}, {'complete':True}), (False,'retain_pending'))
 def test_unrendered_or_unknown_pending_not_relabelled_as_clip_failure(self):
  self.assertEqual(f.effective_decision({'proposal':False,'reason':'retain_pending'}, {'complete':False}), (False,'retain_pending'))
 def test_late_start_event_cannot_reset_terminal_or_attempts(self):
  states={'a':{'state':'fresh_visual_failure_evidence_proposal','attempts_this_run':1}};workers={}
  f.apply_event({'kind':'case_started','id':'a','at':'late','worker':{'pid':123}},states,workers)
  self.assertEqual(states['a'],{'state':'fresh_visual_failure_evidence_proposal','attempts_this_run':1})
 def test_start_event_binds_worker_birth_without_reclaim(self):
  states={'a':{'state':'scheduled','attempts_this_run':1}};workers={};worker={'pid':123,'start_ticks':456}
  f.apply_event({'kind':'case_started','id':'a','at':'now','worker':worker},states,workers)
  self.assertEqual(states['a']['state'],'running');self.assertEqual(states['a']['worker'],worker);self.assertEqual(states['a']['attempts_this_run'],1)
 def test_ready_event_records_exact_spawn_identity(self):
  workers={};event={'kind':'worker_ready','worker':{'pid':123,'start_ticks':456},'at':'now'};f.apply_event(event,{},workers)
  self.assertEqual(workers['123'],event)
 def test_immutable_manifest_is_readonly_and_never_overwritten(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'manifest.json';entry=f.write(p,{'count':1730},immutable=True)
   self.assertEqual(p.stat().st_mode&0o777,0o444);self.assertEqual(f.sha(p.read_bytes()),entry['sha256'])
   with self.assertRaises(FileExistsError):f.write(p,{'count':0},immutable=True)
   self.assertEqual(json.loads(p.read_text()),{'count':1730})
 def test_retained_byte_inventory_does_not_follow_external_symlinks(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'owned';root.mkdir();outside=Path(tmp)/'outside';outside.write_bytes(b'x'*100000)
   (root/'file').write_bytes(b'owned');(root/'link').symlink_to(outside)
   result=f.disk(root);self.assertEqual(result['files_retained'],2);self.assertLess(result['logical_bytes_retained'],100000)
 def test_birth_reads_actual_linux_identity_or_unavailable_without_signalling(self):
  item=f.birth()
  if Path('/proc/self/stat').exists():self.assertEqual(item['pid'],os.getpid());self.assertGreater(item['start_ticks'],0)
  else:self.assertIsNone(item)

 @unittest.skipUnless(sys.platform.startswith('linux'),'Real pidfd spawn/subreaper integration requires Linux')
 def test_real_spawn_slot_runs_only_private_child_and_cleans_all_births(self):
  import initial_conversion_process_v1 as process
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve();run=root/'run';work=run/'cases'/'a';work.mkdir(parents=True);impl=run/'implementation';impl.mkdir()
   stub=impl/'visual_failure_finite_v1.py'
   stub.write_text("import json,pathlib,sys\np=pathlib.Path(sys.argv[2]);q=json.loads(p.read_text());(p.parent/'case_result.json').write_text(json.dumps({'id':q['id'],'effective_proposal':False,'state':'pending_fixture','reason':'private no-render fixture'}))\n")
   manifest=run/'manifest.json';entry=f.write(manifest,{'implementation':{'supervisor':f.sha(stub.read_bytes()),'process':f.sha(Path(process.__file__).read_bytes())}},immutable=True)
   task={'root':str(root),'run':str(run),'id':'a','manifest_file':str(manifest),'manifest_sha256':entry['sha256']};f.write(work/'request.json',task,immutable=True)
   events=multiprocessing.get_context('spawn').Queue()
   try:
    with concurrent.futures.ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'),initializer=f.init_worker,initargs=(events,)) as pool:
     value=pool.submit(f.run_one,task).result(timeout=30)
    self.assertFalse(value['fatal'],value);self.assertTrue(value['outer_execution']['cleanup_complete']);self.assertEqual(value['matching_live_owned_births'],[])
    self.assertEqual(value['state'],'pending_fixture');self.assertEqual(value['outer_execution']['returncode'],0)
    kinds=[events.get(timeout=3)['kind'],events.get(timeout=3)['kind']];self.assertEqual(set(kinds),{'worker_ready','case_started'})
   finally:events.close();events.join_thread()

if __name__=='__main__':unittest.main()
