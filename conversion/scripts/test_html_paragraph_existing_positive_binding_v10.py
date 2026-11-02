from pathlib import Path
import json,tempfile,unittest,hashlib
from unittest.mock import patch
import html_paragraph_iteration_case_v10 as case
import compiler_types_program_v1 as common

class HistoricalPositiveBindingTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name).resolve();self.config=dict(unit='H9',policy='current_final',pins={'source':'abc'});self.record=dict(id='known',html_source_paragraph_v9=dict(unit='H9',configuration={'policy':'immutable_earlier_metadata'}));self.candidate=self.root/'clean/candidate.json';self.candidate.parent.mkdir();self.candidate.write_bytes(case.raw(self.record));self.manifest=self.root/'qualified.jsonl';self.row=dict(id='known',metadata_file=str(self.candidate),metadata_sha256=case.sha(self.candidate.read_bytes()));self.manifest.write_bytes(case.raw(self.row));self.proof=self.root/'release/compiler_iterations/controls/html_source_paragraph_controls_20261101_v9/proof.json';self.proof.parent.mkdir(parents=True);self.bundle=dict(frozen_frontend=self.config,qualified_manifest=dict(file=str(self.manifest),sha256=case.sha(self.manifest.read_bytes())));self.proof.write_bytes(case.raw(self.bundle));proofbytes=self.proof.read_bytes();original=case.sha
  patches=[patch.object(case,'R',self.root),patch.object(common,'R',self.root),patch.object(case,'sha',side_effect=lambda b:'f725a48e64443e8d9be9156246652cb7890582d291991dd564855a9554c36187'if b==proofbytes else original(b))]
  for p in patches:p.start();self.addCleanup(p.stop)
 def test_unchanged_historical_configuration_is_bound_to_current_control_manifest(self):
  self.assertEqual(case.existing_positive_binding(self.candidate,self.record,self.config),self.row);self.assertEqual(self.record['html_source_paragraph_v9']['configuration']['policy'],'immutable_earlier_metadata')
 def test_changed_metadata_bytes_cannot_reuse_old_manifest(self):
  self.candidate.write_bytes(case.raw(dict(self.record,unexpected='change')))
  with self.assertRaises(Exception):case.existing_positive_binding(self.candidate,self.record,self.config)
 def test_other_current_core_cannot_use_frozen_controls(self):
  with self.assertRaisesRegex(ValueError,'current_source_core_changed'):case.existing_positive_binding(self.candidate,self.record,dict(self.config,policy='other'))
 def test_unregistered_candidate_path_rejected_even_with_equal_bytes(self):
  other=self.candidate.with_name('copy.json');other.write_bytes(self.candidate.read_bytes())
  with self.assertRaisesRegex(ValueError,'not_frozen_accepted_metadata'):case.existing_positive_binding(other,self.record,self.config)
if __name__=='__main__':unittest.main()
