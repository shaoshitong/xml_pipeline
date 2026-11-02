import tempfile,unittest
from unittest.mock import patch
import xml.etree.ElementTree as E
from pathlib import Path
import tikz_closed_paint_quality_adapter_v1 as a
class AdapterTests(unittest.TestCase):
 def test_unused_cache_addition_does_not_change_program_policy(self):
  import tikz_source_only_failure_v1 as source
  import tikz_closed_paint_projection_v1 as projection
  with tempfile.TemporaryDirectory() as t:
   root=Path(t).resolve();w=root/'conversion';scripts=w/'scripts';scripts.mkdir(parents=True)
   for name in ('tikz_closed_paint_quality_adapter_v1.py','tikz_closed_paint_candidate_v1.py','tikz_closed_paint_projection_v1.py','tikz_closed_paint_bridge_v1.py','tikz_closed_paint_bridge_v1.js','svg_convert_v5.py','svg_convert_v6.py'):(scripts/name).write_text(name)
   original={'/software/used':{'sha256':'1'*64,'bytes':1}}
   with patch.object(a,'R',root),patch.object(a,'W',w),patch.object(source,'configuration',return_value={'pins':{},'policy':'qa'}),patch.object(projection,'pins'),patch.object(source,'environment_files',return_value=original):before=a.configuration(root)
   extra={**original,'/software/not_used':{'sha256':'2'*64,'bytes':1}}
   with patch.object(a,'R',root),patch.object(a,'W',w),patch.object(source,'configuration',return_value={'pins':{},'policy':'qa'}),patch.object(projection,'pins'),patch.object(source,'environment_files',return_value=extra):after=a.configuration(root)
   self.assertEqual(before['policy'],after['policy']);self.assertEqual(before['pins'],after['pins']);self.assertEqual(after['environment']['/software/used'],original['/software/used'])
 def test_unregistered_data_root_cannot_be_used_as_authoritative_source(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'registered HKUST'):a.configuration(Path(t))
 def test_any_incomplete_source_failure_never_sets_complete_coverage(self):
  with tempfile.TemporaryDirectory() as t:
   r=a.check_source({},'<mxfile/>','wrong',Path(t));self.assertFalse(r['ok']);self.assertFalse(r['supported']);self.assertFalse(r['evidence']['complete_source_coverage']);self.assertEqual(r['evidence']['required_text_cell_ids'],[])
 def test_missing_manifest_never_becomes_a_success(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(ValueError):a.registration_record({},b'not-image','<mxfile/>',Path(t))
 def test_editing_requires_complete_source_not_partial_graph_or_paint(self):
  for p in ({},{'supported':True,'ok':True,'evidence':{'complete_source_coverage':False}}):
   with self.assertRaisesRegex(ValueError,'complete original source'):a.audit_editing({},'<mxfile/>',p,a.R)
 def test_editing_current_revision_is_hash_bound(self):
  with self.assertRaisesRegex(ValueError,'revision differs'):a.audit_editing({'code_sha256':'wrong'},'<mxfile/>',{'supported':True,'ok':True,'evidence':{'complete_source_coverage':True,'candidate_code_sha256':'wrong'}},a.R)
 def test_closed_editing_route_cannot_waive_a_free_or_bound_connector(self):
  xml='<mxfile><mxGraphModel><root><mxCell id="edge" edge="1"/></root></mxGraphModel></mxfile>';h=a.sha(xml.encode());record={'code_sha256':h};profile={'supported':True,'ok':True,'evidence':{'complete_source_coverage':True,'candidate_code_sha256':h}}
  with self.assertRaisesRegex(ValueError,'cannot waive'):a.audit_editing(record,xml,profile,a.R)
if __name__=='__main__':unittest.main()
