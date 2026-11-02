import copy,unittest
from compiler_languages_source_layout_v3 import clip_local_scene
class ClipFrameTests(unittest.TestCase):
 def fixture(self):
  return {'objects':[{'id':'a','type':'shape','matrix':[2,0,0,2,18,28],'attrs':{'x':1,'y':2},'d':'M1 2L3 4','bbox':{'x':10,'y':20,'w':30,'h':40},'edge':{'id':'e','bbox':{'x':8,'y':8,'w':80,'h':90}},'sampledPoints':[[10,20],[30,40]],'endpoints':[[10,20],[30,40]]}],'nodes':{'n':{'bbox':{'x':10,'y':20,'w':30,'h':40}}}},{'groups':[{'bbox':{'x':10,'y':20,'left':10,'right':40,'top':20,'bottom':60,'width':30,'height':40}}]}
 def test_global_translation_all_geometry_and_metadata(self):
  d,m=self.fixture();dd,mm=clip_local_scene(d,m,{'x':8,'y':8});o=dd['objects'][0];self.assertEqual(o['matrix'],[2,0,0,2,10,20]);self.assertEqual(o['sampledPoints'],[[2,12],[22,32]]);self.assertEqual(o['edge']['bbox']['x'],0);self.assertEqual(dd['nodes']['n']['bbox']['y'],12);self.assertEqual(mm['groups'][0]['bbox'],{'x':2,'y':12,'left':2,'right':32,'top':12,'bottom':52,'width':30,'height':40})
 def test_source_geometry_style_and_inputs_unchanged(self):
  d,m=self.fixture();before=copy.deepcopy([d,m]);dd,mm=clip_local_scene(d,m,{'x':8,'y':8});self.assertEqual([d,m],before);self.assertEqual(dd['objects'][0]['d'],d['objects'][0]['d']);self.assertEqual(dd['objects'][0]['attrs'],d['objects'][0]['attrs'])
 def test_offscreen_object_never_clamped_or_dropped(self):
  d,m=self.fixture();d['objects'][0]['bbox']['x']=-100;dd,mm=clip_local_scene(d,m,{'x':8,'y':8});self.assertEqual(dd['objects'][0]['bbox']['x'],-108);self.assertEqual(len(dd['objects']),1)
 def test_zero_origin_is_identity(self):
  d,m=self.fixture();dd,mm=clip_local_scene(d,m,{'x':0,'y':0});self.assertEqual([dd,mm],[d,m])
if __name__=='__main__':unittest.main()
