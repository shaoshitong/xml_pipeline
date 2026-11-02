import unittest
import compiler_svg_source_viewport_unseen_pool_v1 as pool
family=pool.family
class FamilyTests(unittest.TestCase):
 def source(self,a='head',b='other',p='edge',num='13.5',text='Input',target=None):
  target=a if target is None else target
  return f'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="400"><defs><marker id="{a}"><path d="M0 0L{num} 4L0 8Z"/></marker><marker id="{b}"><path d="M0 0L{num} 9L0 8Z"/></marker><style>#{p}{{marker-end:url(#{target});stroke-width:2px}}</style></defs><path id="{p}" d="M10 20L30 40" marker-start="url(#{a})"/><text x="50" y="70">{text}</text></svg>'
 def test_literals_identifiers_and_coordinates_do_not_establish_unseen_family(self):
  self.assertEqual(family(self.source())[0],family(self.source('renamed0','renamed1','differentName','91.2','Different label'))[0])
 def test_reference_ownership_change_remains_visible(self):
  self.assertNotEqual(family(self.source())[0],family(self.source(target='other'))[0])
 def test_path_grammar_change_visible(self):
  self.assertNotEqual(family(self.source())[0],family(self.source().replace('M10 20L30 40','M10 20Q30 40 50 60'))[0])
 def test_added_source_object_visible(self):
  self.assertNotEqual(family(self.source())[0],family(self.source().replace('</svg>','<rect x="10" y="20" width="50" height="60"/></svg>'))[0])
 def test_duplicate_source_id_rejected(self):
  with self.assertRaisesRegex(ValueError,'duplicate_source_family_id'):family(self.source('same','same'))
class TransitiveComponentTests(unittest.TestCase):
 @staticmethod
 def row(id,keys,known=True,pending=True):return {'audit':{},'request':{'id':id,'source':{'code_sha256':id+'code','image_sha256':id+'image'}},'keys':set(keys),'known':known,'pending':pending}
 def test_unselected_bridge_closes_development_family(self):
  rs=[self.row('bridge',{'dev','shared'},pending=False),self.row('new',{'shared','other'})];eligible,_=pool.independent_components(rs,set(),set(),set(),{'dev'});self.assertEqual(eligible,[])
 def test_unknown_bridge_prevents_independence_but_keeps_input_record(self):
  rs=[self.row('unknown',{'same'},False),self.row('known',{'same','typed'})];eligible,_=pool.independent_components(rs,set(),set(),set(),set());self.assertEqual(eligible,[]);self.assertEqual(len(rs),2)
 def test_exact_image_connects_different_source_families(self):
  rs=[self.row('a',{'image','familyA'}),self.row('b',{'image','familyB'})];eligible,_=pool.independent_components(rs,set(),set(),set(),set());self.assertEqual(len(eligible),1)
 def test_qualified_bridge_does_not_allow_duplicate_development_family(self):
  rs=[self.row('qualified',{'dev','family'},pending=False),self.row('pending',{'family'})];eligible,_=pool.independent_components(rs,set(),set(),set(),{'dev'});self.assertEqual(eligible,[])


class OriginalSourcePathTests(unittest.TestCase):
 def test_canonical_staged_source_inside_remote_root_is_allowed(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);p=root/'conversion/inputs/source.tex';p.parent.mkdir(parents=True);p.write_bytes(b'original TikZ')
   self.assertEqual(pool.checked_original_code('conversion/inputs/source.tex',pool.sha(p.read_bytes()),root),'original TikZ')
 def test_changed_canonical_staged_bytes_rejected(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory()as tmp:
   root=Path(tmp);p=root/'source.tex';p.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'hash_changed'):pool.checked_original_code('source.tex','0'*64,root)
 def test_staged_symlink_cannot_escape_registered_root(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory()as tmp:
   folder=Path(tmp);root=folder/'registered';root.mkdir();other=folder/'outside.tex';other.write_bytes(b'outside');(root/'source.tex').symlink_to(other)
   with self.assertRaisesRegex(ValueError,'outside_registered_root'):pool.checked_original_code('source.tex',pool.sha(other.read_bytes()),root)

class CrossFormatTests(unittest.TestCase):
 def test_global_code_and_image_overlap_are_excluded(self):
  source={'code_sha256':'code','image_sha256':'image'}
  self.assertTrue(pool.identity_overlap('new',source,set(),{'code'},set()))
  self.assertTrue(pool.identity_overlap('new',source,set(),set(),{'image'}))
if __name__=='__main__':unittest.main()
