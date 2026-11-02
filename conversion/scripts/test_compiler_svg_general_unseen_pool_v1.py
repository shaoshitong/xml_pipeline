import unittest
from compiler_svg_general_unseen_pool_v1 import family
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
if __name__=='__main__':unittest.main()
