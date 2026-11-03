import unittest
from arxiv_native_framework_layout_gate_v1 import check

def graph(groups=1,gap=200,port=False):
 cells=['<mxCell id="0"/><mxCell id="1" parent="0"/>']
 for group in range(groups):
  for i in range(20):
   ident=f'v{group}_{i}';cells.append(f'<mxCell id="{ident}" vertex="1" parent="1" value="Research module {i}"><mxGeometry x="{group*gap+i*50}" y="0" width="40" height="30"/></mxCell>')
   if port:cells.append(f'<mxCell id="p{group}_{i}" vertex="1" parent="{ident}"><mxGeometry x="1" y="0.5" width="2" height="2" relative="1"/></mxCell>')
  for i in range(19):
   a=f'p{group}_{i}' if port else f'v{group}_{i}';b=f'p{group}_{i+1}' if port else f'v{group}_{i+1}';cells.append(f'<mxCell id="e{group}_{i}" edge="1" source="{a}" target="{b}"/>')
 return ('<mxGraphModel><root>'+''.join(cells)+'</root></mxGraphModel>').encode()
class LayoutGateTest(unittest.TestCase):
 def test_complete_connected_framework(self):self.assertTrue(check(graph())['ok'])
 def test_copied_disconnected_drafts_held(self):self.assertFalse(check(graph(groups=2,gap=2000))['ok'])
 def test_distinct_disconnected_research_panels_are_valid(self):
  b=graph(groups=2,gap=1500).replace(b'value="Research module 0" parent',b'value="Research module 0" parent')
  # Change the second panel's scientific labels without changing its topology.
  text=b.decode();second=text.index('<mxCell id="v1_0"');text=text[:second]+text[second:].replace('Research module','Different method')
  self.assertTrue(check(text.encode())['ok'])
 def test_disconnectedness_alone_is_not_a_layout_failure(self):
  import re
  b=re.sub(br'<mxCell id="e[^>]*?/>',b'',graph());self.assertTrue(check(b)['ok'])
 def test_relative_ports_are_joined_to_their_modules(self):self.assertTrue(check(graph(port=True))['ok'])
 def test_far_isolated_decoration_held(self):
  b=graph().replace(b'</root>',b'<mxCell id="far" vertex="1" parent="1"><mxGeometry x="10000" y="0" width="50" height="30"/></mxCell></root>');self.assertIn('extreme_empty_axis_interval',check(b)['reasons'])
 def test_input_bytes_remain_unchanged(self):
  b=graph();before=bytes(b);check(b);self.assertEqual(b,before)
 def test_parent_cycle_is_not_accepted(self):
  b=graph().replace(b'id="v0_0" vertex="1" parent="1"',b'id="v0_0" vertex="1" parent="v0_1"').replace(b'id="v0_1" vertex="1" parent="1"',b'id="v0_1" vertex="1" parent="v0_0"');self.assertFalse(check(b)['ok'])
if __name__=='__main__':unittest.main()
