import copy
import json
import unittest
import xml.etree.ElementTree as ET

import compiler_graphviz_visibility_scene_v1 as compiler


class VisibilityIRTests(unittest.TestCase):
    def document(self):
        return {'bb':'0,0,100,100','directed':True,'_subgraph_cnt':0,
                'objects':[{'_gvid':0,'name':'a','_draw_':[{'op':'E','rect':[20,20,10,10]}]},
                           {'_gvid':1,'name':'b','_draw_':[{'op':'P','points':[[40,40],[60,40],[60,60],[40,60]]}]}],
                'edges':[{'_gvid':0,'tail':0,'head':1,'tailport':'out:e',
                          '_draw_':[{'op':'b','points':[[20,20],[20,30],[30,40],[40,40]]}],
                          '_hdraw_':[{'op':'P','points':[[40,40],[38,42],[38,38]]}]},
                         {'_gvid':1,'tail':1,'head':0,'tailport':'s','headport':'e',
                          'style':'invis','weight':'7','constraint':'true','pos':'e,20,20 40,40 30,30 25,25 20,20'}]}

    def test_complete_partition_preserves_every_source_identity_and_attributes(self):
        document=self.document();before=copy.deepcopy(document);scene=compiler.graphviz_to_scene(document)
        self.assertEqual(document,before)
        self.assertEqual((scene['source_edge_count'],scene['visible_edge_count'],scene['nonpainting_edge_count']),(2,1,1))
        constraint=scene['layout_constraints'][0]
        self.assertEqual((constraint['source_id'],constraint['source_name'],constraint['target_name'],constraint['source_port'],constraint['target_port']),(1,'b','a','s','e'))
        self.assertEqual(constraint['source_attributes']['pos'],document['edges'][1]['pos'])
        self.assertEqual(constraint['source_attributes']['weight'],'7')
        self.assertEqual(constraint['source_payload_sha256'],compiler.sha(compiler.raw(document['edges'][1])))
        self.assertEqual(scene['edges'][0]['drawing'],{k:document['edges'][0][k] for k in ('_draw_','_hdraw_')})

    def test_unexplained_missing_visible_path_remains_rejected(self):
        document=self.document();document['edges'][1].pop('style')
        with self.assertRaisesRegex(ValueError,'one_visible_path'):compiler.graphviz_to_scene(document)

    def test_invisible_style_cannot_hide_actual_arrow_paint(self):
        document=self.document();document['edges'][1]['_hdraw_']=[{'op':'P','points':[[0,0],[1,1],[2,0]]}]
        with self.assertRaisesRegex(ValueError,'invisible_graphviz_edge_has_paint'):compiler.graphviz_to_scene(document)

    def test_invisible_style_cannot_hide_actual_line_paint(self):
        document=self.document();document['edges'][0]['style']='invis'
        with self.assertRaisesRegex(ValueError,'invisible_graphviz_edge_has_paint'):compiler.graphviz_to_scene(document)

    def test_unknown_paint_channel_is_not_discarded(self):
        document=self.document();document['edges'][1]['_otherdraw_']=[]
        with self.assertRaisesRegex(ValueError,'unknown_graphviz_draw_channel'):compiler.graphviz_to_scene(document)

    def test_nonpainting_constraint_still_requires_resolved_endpoints(self):
        document=self.document();document['edges'][1]['head']=999
        with self.assertRaisesRegex(ValueError,'endpoint'):compiler.graphviz_to_scene(document)

    def test_duplicate_identity_across_visible_and_nonpainting_rejected(self):
        document=self.document();document['edges'][1]['_gvid']=0
        with self.assertRaisesRegex(ValueError,'duplicate_graphviz_edge_id'):compiler.graphviz_to_scene(document)

    def test_empty_draw_channels_are_preserved(self):
        document=self.document();document['edges'][1]['_draw_']=[];document['edges'][1]['_ldraw_']=[]
        scene=compiler.graphviz_to_scene(document)
        self.assertEqual(scene['layout_constraints'][0]['drawing'],{'_draw_':[],'_ldraw_':[]})

    def test_xml_roundtrip_retains_all_nonpaint_relationships(self):
        scene=compiler.graphviz_to_scene(self.document())
        xml=compiler.encode_layout_constraints('<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>',scene)
        proof=compiler.validate_layout_constraints(scene,xml)
        self.assertTrue(proof['ok']);self.assertEqual(proof['source_edges'],2)
        self.assertTrue(proof['all_original_source_edge_ids_and_relationships_preserved'])

    def test_deleted_xml_constraint_rejected_even_though_render_would_not_change(self):
        scene=compiler.graphviz_to_scene(self.document())
        with self.assertRaisesRegex(ValueError,'constraints_missing'):
            compiler.validate_layout_constraints(scene,'<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>')

    def test_rehashed_nonpaint_endpoint_change_rejected(self):
        scene=compiler.graphviz_to_scene(self.document())
        xml=compiler.encode_layout_constraints('<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>',scene)
        root=ET.fromstring(xml);model=root.find('.//mxCell[@id="0"]');value=json.loads(model.get(compiler.LAYOUT_ATTRIBUTE));value[0]['target_node']=1
        model.set(compiler.LAYOUT_ATTRIBUTE,json.dumps(value))
        with self.assertRaisesRegex(ValueError,'constraints_changed'):compiler.validate_layout_constraints(scene,ET.tostring(root,encoding='unicode'))


if __name__=='__main__':unittest.main()
