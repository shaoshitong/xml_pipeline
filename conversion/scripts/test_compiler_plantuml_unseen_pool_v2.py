import unittest
from compiler_plantuml_unseen_pool_v2 import family

def program(a='A',b='B',label='Input',other='Output',shape='rectangle',reverse=False,extra=''):
 edge=f'{b} --> {a}' if reverse else f'{a} --> {b}'
 return f'@startuml\ncomponent "{label}" as {a}\n{shape} "{other}" as {b}\n{edge} : label\n{extra}\n@enduml'

class FamilyTests(unittest.TestCase):
 def test_identifier_and_label_literals_do_not_establish_unseen_family(self):
  self.assertEqual(family(program())[0],family(program('Renamed','Second','Text 2','Other text'))[0])
 def test_native_entity_kind_remains_visible(self):self.assertNotEqual(family(program())[0],family(program(shape='database'))[0])
 def test_relation_direction_between_typed_nodes_remains_visible(self):self.assertNotEqual(family(program())[0],family(program(reverse=True))[0])
 def test_parallel_source_edge_is_not_deduplicated_as_same_program(self):self.assertNotEqual(family(program())[0],family(program(extra='A --> B : another'))[0])

if __name__=='__main__':unittest.main()
