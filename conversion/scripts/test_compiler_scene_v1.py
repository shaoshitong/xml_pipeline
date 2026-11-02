import copy
import unittest
from compiler_scene_v1 import graphviz_to_scene


class GraphvizSceneTests(unittest.TestCase):
    def document(self):
        return {'bb':'0,0,100,100','directed':True,'_subgraph_cnt':0,
                'objects':[{'_gvid':0,'name':'a','_draw_':[{'op':'E','rect':[20,20,10,10]}]},
                           {'_gvid':1,'name':'b','_draw_':[{'op':'P','points':[[40,40],[60,40],[60,60],[40,60]]}]}],
                'edges':[{'_gvid':0,'tail':0,'head':1,'tailport':'out:e',
                          '_draw_':[{'op':'b','points':[[20,20],[20,30],[30,40],[40,40]]}],
                          '_hdraw_':[{'op':'P','points':[[40,40],[38,42],[38,38]]}]}]}

    def test_semantic_identity_and_ports_preserved(self):
        source=self.document();before=copy.deepcopy(source);scene=graphviz_to_scene(source)
        self.assertEqual(source,before)
        edge=scene['edges'][0]
        self.assertEqual((edge['source_node'],edge['target_node'],edge['source_port']),(0,1,'out:e'))
        self.assertEqual(scene['coordinates']['y_axis'],'up')
        self.assertEqual(edge['drawing']['_draw_'],source['edges'][0]['_draw_'])

    def test_missing_endpoint_rejected(self):
        source=self.document();source['edges'][0]['head']=8
        with self.assertRaisesRegex(ValueError,'endpoint'):graphviz_to_scene(source)

    def test_invisible_edges_not_silently_dropped(self):
        source=self.document();source['edges'][0]['_draw_']=[]
        with self.assertRaisesRegex(ValueError,'one_visible_path'):graphviz_to_scene(source)

    def test_unknown_draw_op_rejected(self):
        source=self.document();source['objects'][0]['_draw_']=[{'op':'Q'}]
        with self.assertRaisesRegex(ValueError,'draw_op'):graphviz_to_scene(source)

    def test_image_draw_op_rejected(self):
        source=self.document();source['objects'][0]['_draw_']=[{'op':'I','name':'asset.png'}]
        with self.assertRaisesRegex(ValueError,'draw_op'):graphviz_to_scene(source)

    def test_gradient_rejected(self):
        source=self.document();source['objects'][0]['_draw_'].insert(0,{'op':'C','grad':'linear'})
        with self.assertRaisesRegex(ValueError,'gradient'):graphviz_to_scene(source)

    def test_duplicate_node_identity_rejected(self):
        source=self.document();source['objects'][1]['_gvid']=0
        with self.assertRaisesRegex(ValueError,'duplicate'):graphviz_to_scene(source)

    def test_nonfinite_layout_rejected(self):
        source=self.document();source['bb']='0,0,nan,100'
        with self.assertRaisesRegex(ValueError,'bbox'):graphviz_to_scene(source)

    def test_parallel_edges_not_deduplicated(self):
        source=self.document();other=copy.deepcopy(source['edges'][0]);other['_gvid']=1;source['edges'].append(other)
        self.assertEqual(len(graphviz_to_scene(source)['edges']),2)


if __name__=='__main__':unittest.main()
