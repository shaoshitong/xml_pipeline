"""Direct redeclarations, immutable alias instances and actual read ownership."""
import copy,unittest
from tikz_execution_graph_v2 import graph_from_events,parse_events


class Trace:
 def __init__(self):self.events=[];self.path=0;self.nodes=0;self.add('header','1','3.1.9a');self.add('extension','2','actual-node-table-instance-and-anchor-read');self.add('picture','1','begin')
 def add(self,kind,*fields):
  if kind=='anchorread' and len(fields)==7:fields=(*fields,*fields[-2:])
  self.events.append({'kind':kind,'fields':list(map(str,fields))})
 def begin(self):self.path+=1;self.add('path','1',self.path,'begin')
 def finish(self,soft=''):self.add('finish','1',self.path,'','0','0',soft)
 def node(self,name,x,y):
  self.begin();self.nodes+=1;instance='v2n'+str(self.nodes);self.add('instance','1',self.path,instance,name,'rectangle',x,y);self.add('node','1',self.path,self.nodes,'node',name,'rectangle',name,x,y,'0');self.add('nodelink','1',self.path,self.nodes,instance);self.finish();return instance
 def edge(self,a,aid,ap,b,bid,bp,anchor='center'):
  self.begin()
  for number,(name,id,point,kind,callback) in enumerate(((a,aid,ap,'move',r'\tikz@@moveto'),(b,bid,bp,'line',r'\tikz@@lineto')),1):
   self.add('anchor','1',self.path,name,anchor);self.add('anchorread','1',self.path,name,anchor,id,*point);self.add('ref','1',self.path,callback,name,anchor,*point,'0');self.add('operation','1',self.path,kind,number)
  self.finish(r'\pgfsyssoftpath@movetotoken {'+ap[0]+'}{'+ap[1]+r'}\pgfsyssoftpath@linetotoken {'+bp[0]+'}{'+bp[1]+'}')
 def complete(self):self.add('picture','1','end');self.add('complete','1',self.path,self.nodes);return self.events


class InstanceTests(unittest.TestCase):
 def fixture(self):
  t=Trace();a=t.node('a','0pt','0pt');b=t.node('b','10pt','0pt');t.edge('a',a,['0pt','0pt'],'b',b,['10pt','0pt']);t.add('alias','1',t.path,'saved','a',a);new=t.node('a','0pt','-10pt');t.edge('a',new,['0pt','-10pt'],'b',b,['10pt','0pt']);t.edge('saved',a,['0pt','0pt'],'b',b,['10pt','0pt']);return t
 def test_redefinition_and_alias_bind_each_historical_instance(self):
  graph=graph_from_events(self.fixture().complete());self.assertTrue(graph['ok'],graph['failures']);self.assertEqual([e['source'] for e in graph['edges']],['v2n1','v2n3','v2n1']);self.assertEqual(len(graph['nodes']),3);self.assertEqual(graph['executed_nodes_accounted'],3);self.assertEqual(graph['duplicate_name_generations'][0]['instances'],['v2n1','v2n3'])
 def test_rename_alias_retains_copied_instance(self):
  t=self.fixture();t.add('alias','1',t.path,'renamed','a','v2n3');t.add('unbind','1',t.path,'a','rename');t.edge('renamed','v2n3',['0pt','-10pt'],'b','v2n2',['10pt','0pt']);g=graph_from_events(t.complete());self.assertTrue(g['ok'],g['failures']);self.assertEqual(g['edges'][-1]['source'],'v2n3')
 def test_actual_noncenter_anchor_reads_carry_identity(self):
  t=Trace();a=t.node('a','0pt','0pt');b=t.node('b','10pt','0pt');t.edge('a',a,['2pt','0pt'],'b',b,['12pt','0pt'],anchor='east');g=graph_from_events(t.complete());self.assertTrue(g['ok'],g['failures']);self.assertEqual(g['reference_instance_ownership'][0]['anchor'],'east')
 def test_stale_identity_and_wrong_center_never_pass(self):
  for identity,center in (('v2n1',['0pt','0pt']),('v2n3',['0pt','0pt'])):
   t=self.fixture();t.edge('a',identity,center,'b','v2n2',['10pt','0pt']);g=graph_from_events(t.complete());self.assertFalse(g['identity_ok']);self.assertTrue(any(f['reason'] in ('anchor_read_identity_not_current_installed_table','anchor_read_center_disagrees_with_instance') for f in g['failures']))
 def test_missing_instance_link_rejects(self):
  events=self.fixture().complete();events=[e for e in events if not(e['kind']=='nodelink' and e['fields'][2]=='1')];g=graph_from_events(events);self.assertFalse(g['ok']);self.assertTrue(any(f['reason']=='instance_node_event_coverage_incomplete' for f in g['failures']))
 def test_empty_cursor_is_accounted_but_numeric_painted_edge_rejects(self):
  t=self.fixture();t.begin();t.add('anchorread','1',t.path,'a','center','v2n3','0pt','-10pt');t.add('ref','1',t.path,r'\tikz@@moveto','a','center','0pt','-10pt','0');t.add('operation','1',t.path,'move','1');t.finish();g=graph_from_events(t.complete());self.assertTrue(g['ok'],g['failures']);self.assertEqual(len(g['nonpainted_cursor_paths']),1)
  t=self.fixture();t.begin();t.add('operation','1',t.path,'move','1');t.add('operation','1',t.path,'line','2');t.finish(r'\pgfsyssoftpath@movetotoken {0pt}{0pt}\pgfsyssoftpath@linetotoken {3pt}{0pt}');g=graph_from_events(t.complete());self.assertFalse(g['ok']);self.assertTrue(any(f['reason']=='numeric_or_unbound_path_terminal' for f in g['failures']))
 def test_parser_requires_v2_extension(self):
  events=self.fixture().complete();text='\n'.join('\\IIC'+e['kind']+''.join('{'+x+'}' for x in e['fields']) for e in events);self.assertEqual(parse_events(text),events)
  with self.assertRaises(ValueError):parse_events(text.replace(r'\IICextension{2}{actual-node-table-instance-and-anchor-read}',''))


if __name__=='__main__':unittest.main()
