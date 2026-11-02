"""Pure synthetic trace validation; actual compilation tests run only on HKUST."""
import copy
import unittest
from tikz_execution_graph import graph_from_events,parse_events

def event(kind,*fields):return {'kind':kind,'fields':list(map(str,fields))}
def fixture():
 return [event('header',1,'3.1.10'),event('picture',1,'begin'),event('path',1,1,'begin'),event('node',1,1,1,'node','a','rectangle','First','0pt','0pt',0),event('node',1,1,2,'node','b','rectangle','Second','60pt','0pt',0),event('ref',1,1,r'\tikz@@moveto','a','east','10pt','0pt',0),event('operation',1,1,'move',1),event('ref',1,1,r'\tikz@@lineto','b','west','50pt','0pt',0),event('operation',1,1,'line',2),event('node',1,1,3,'label','auto','rectangle','Go','30pt','5pt',2),event('finish',1,1,'->',0,1,r'\pgfsyssoftpath@movetotoken{10pt}{0pt}\pgfsyssoftpath@linetotoken{50pt}{0pt}'),event('picture',1,'end'),event('complete',1,1,3)]

class ExecutionGraphTraceTests(unittest.TestCase):
 def test_roundtrip_positive(self):
  events=fixture();raw='\n'.join('\\IIC'+e['kind']+''.join('{'+f+'}' for f in e['fields']) for e in events)
  parsed=parse_events(raw);self.assertEqual(parsed,events);graph=graph_from_events(parsed);self.assertTrue(graph['ok'],graph)
  self.assertEqual([(e['source'],e['target'],e['expanded_labels_tex'],e['end_arrow']) for e in graph['edges']],[('a','b',['Go'],True)])
 def test_rejects_unbound_unknown_duplicate_incomplete(self):
  for name,mutate in {
   'numeric_terminal':lambda es:es.pop(7),
   'missing_finish':lambda es:es.pop(10),
   'duplicate_name':lambda es:es[4]['fields'].__setitem__(4,'a'),
   'unknown_node':lambda es:es[7]['fields'].__setitem__(3,'missing'),
   'counter_mismatch':lambda es:es[-1]['fields'].__setitem__(2,'10'),
   'untracked_cycle':lambda es:es[10]['fields'].__setitem__(5,es[10]['fields'][5]+r'\pgfsyssoftpath@closepathtoken{0pt}{0pt}'),
   'direct_pgf_paint':lambda es:es.insert(10,event('unsupportedpaint',1,1,'stroke')),
  }.items():
   with self.subTest(case=name):
    events=copy.deepcopy(fixture());mutate(events);self.assertFalse(graph_from_events(events)['ok'])
  for raw in ('\\IICheader{1}{3.1}','\\IICunknown{x}', '\\IICheader{1}{3.1}\n\\IICnode{1}'):
   with self.subTest(raw=raw):
    with self.assertRaises(ValueError):parse_events(raw)
 def test_balanced_tex_labels_not_executed(self):
  events=fixture();events[3]['fields'][6]=r'\textbf{A} \{literal\}'
  raw='\n'.join('\\IIC'+e['kind']+''.join('{'+f+'}' for f in e['fields']) for e in events)
  self.assertEqual(parse_events(raw),events)

if __name__=='__main__':unittest.main()
