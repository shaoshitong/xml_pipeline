import json,tempfile,unittest
from pathlib import Path
from budget_exhausted_outcomes_v3 import candidates
class HistoryCoverage(unittest.TestCase):
 def read(self,data):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'history.json';p.write_text(json.dumps(data));return candidates(p)
 def test_full_list_not_old_current_qa_subset(self):
  rows=[{'id':str(i),'same_revision_failed_qa':(['old'] if i<42 else [])} for i in range(344)]
  self.assertEqual(self.read(rows),[str(i) for i in range(344)])
 def test_duplicate_original_ids_reject(self):
  with self.assertRaises(AssertionError):self.read([{'id':'same'},{'id':'same'}])
 def test_unknown_history_schema_reject(self):
  with self.assertRaises(AssertionError):self.read({'unrecognized':[]})
if __name__=='__main__':unittest.main()
