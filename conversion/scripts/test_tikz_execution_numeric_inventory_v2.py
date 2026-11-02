"""Factual categories must not turn paint geometry into semantic edge claims."""
import unittest
from tikz_execution_numeric_inventory_v2 import classify_path,collect_paths


def fixture(soft,ops=('move','line'),refs=(),arrow=False,nodes=0):
 return {'picture':'1','path':'1','begin_count':1,'operations':[{'kind':k,'number':i+1,'sequence':i} for i,k in enumerate(ops)],'references':[{'callback':c,'name':'node','anchor':'center','sequence':i} for i,c in enumerate(refs)],'nodes':[{}]*nodes,'finishes':[{'softpath':soft,'start_arrow':False,'end_arrow':arrow,'arrows_tex':'->' if arrow else '-'}]}


class NumericInventoryTests(unittest.TestCase):
 def test_no_softpath_cursor_and_independently_painted_nodes_are_separate(self):
  self.assertEqual(classify_path(fixture('',ops=('move',),refs=(r'\tikz@@moveto',)))['category'],'no_path_softpaint_cursor_only')
  self.assertEqual(classify_path(fixture('',ops=(),nodes=1))['category'],'no_path_softpaint_node_or_empty')
 def test_closed_paint_does_not_become_open_arrow_from_inherited_flag(self):
  source=r'\pgfsyssoftpath@movetotoken{0pt}{0pt}\pgfsyssoftpath@linetotoken{2pt}{0pt}\pgfsyssoftpath@closepathtoken{0pt}{0pt}'
  fact=classify_path(fixture(source,arrow=True));self.assertEqual(fact['category'],'closed_paint_candidate');self.assertTrue(fact['end_arrow_flag']);self.assertTrue(fact['numeric_or_unbound_by_v1_pairing'])
 def test_open_arrow_stays_unresolved_and_unarrowed_line_does_not_claim_axis(self):
  source=r'\pgfsyssoftpath@movetotoken{0pt}{0pt}\pgfsyssoftpath@linetotoken{2pt}{0pt}'
  self.assertEqual(classify_path(fixture(source,arrow=True))['category'],'open_arrow_terminal_unresolved')
  self.assertEqual(classify_path(fixture(source))['category'],'open_unarrowed_numeric_paint')
  self.assertEqual(classify_path(fixture(source,refs=(r'\tikz@@moveto',)))['category'],'mixed_named_numeric_unarrowed_paint')
 def test_curve_and_named_pairing_are_not_numeric_line_buckets(self):
  curve=r'\pgfsyssoftpath@movetotoken{0pt}{0pt}\pgfsyssoftpath@curvetosupportatoken{1pt}{0pt}\pgfsyssoftpath@curvetosupportbtoken{1pt}{1pt}\pgfsyssoftpath@curvetotoken{2pt}{1pt}'
  self.assertEqual(classify_path(fixture(curve,ops=('move','cubic')))['category'],'open_curve_unarrowed_numeric_paint')
  paired=classify_path(fixture(curve,ops=('move','cubic'),refs=(r'\tikz@@moveto',r'\tikz@curveC'),arrow=True));self.assertEqual(paired['category'],'named_terminals_paired_curve');self.assertFalse(paired['numeric_or_unbound_by_v1_pairing'])
 def test_duplicate_instances_are_counted_without_dropping_earlier_definition(self):
  events=[{'kind':'path','fields':['1','1','begin']},{'kind':'node','fields':['1','1','1','node','I-1','circle','','0pt','0pt','0']},{'kind':'node','fields':['1','1','2','node','I-1','circle','','2pt','0pt','0']}]
  paths,duplicates,nodes=collect_paths(events);self.assertEqual(nodes,2);self.assertEqual(len(paths[('1','1')]['nodes']),2);self.assertEqual(duplicates[0]['definition_count'],2);self.assertEqual([d['serial'] for d in duplicates[0]['definitions']],['1','2'])


if __name__=='__main__':unittest.main()
