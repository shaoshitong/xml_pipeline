import copy,unittest
from tikz_execution_binding import TEX_PT_TO_PDF_BP
from tikz_execution_node_instances_v2 import map_circle_instances,ellipse_geometry


class CircleInstanceTests(unittest.TestCase):
 def fixture(self):
  positions=[(0,0),(10,0),(0,10),(10,10)];objects=[];nodes=[];s=TEX_PT_TO_PDF_BP
  for i,(x,y) in enumerate(positions):
   cx,cy=s*x+40,-s*y+50;objects.append({'id':'shape'+str(i),'type':'shape','tag':'circle','attrs':{'cx':cx,'cy':cy,'r':3},'matrix':[1,0,0,1,0,0],'bbox':{'x':cx-3,'y':cy-3,'w':6,'h':6},'style':{'fill':'gray','stroke':'none','strokeWidth':0}});nodes.append({'instance_id':'v2n'+str(i),'name':'v2n'+str(i),'source_name':'I-1' if i in (0,2) else 'I-2','name_generation':1 if i<2 else 2,'shape':'circle','center_pt':[str(x)+'pt',str(y)+'pt'],'serial':str(i),'definition_sequence':i})
  return {'objects':objects},{'identity_ok':True,'ok':True,'pictures':1,'nodes':nodes},[1,0,0,1,0,0]
 def test_same_empty_source_names_map_to_distinct_source_shapes(self):
  dom,graph,root=self.fixture();result=map_circle_instances(dom,graph,root);self.assertTrue(result['ok'],result);mapping=result['evidence']['coordinate_mapping'];self.assertEqual(mapping['instances']['v2n0']['source_object_id'],'shape0');self.assertEqual(mapping['instances']['v2n2']['source_object_id'],'shape2');self.assertLess(mapping['max_center_error_px'],1e-8)
 def test_ambiguous_overlap_wrong_scale_and_wrong_source_center_reject(self):
  dom,graph,root=self.fixture();dom['objects'].append({**copy.deepcopy(dom['objects'][0]),'id':'overlap'});self.assertFalse(map_circle_instances(dom,graph,root)['ok'])
  dom,graph,root=self.fixture();root[0]=2;self.assertFalse(map_circle_instances(dom,graph,root)['ok'])
  dom,graph,root=self.fixture();graph['nodes'][0]['center_pt']=['1pt','0pt'];self.assertFalse(map_circle_instances(dom,graph,root)['ok'])
 def test_square_bbox_is_not_enough_to_claim_circle(self):
  dom,graph,root=self.fixture();obj=dom['objects'][0];obj['tag']='path';obj['d']='M37 47 L43 47 L43 53 L37 53 Z';self.assertIsNone(ellipse_geometry(obj));self.assertFalse(map_circle_instances(dom,graph,root)['ok'])


if __name__=='__main__':unittest.main()
