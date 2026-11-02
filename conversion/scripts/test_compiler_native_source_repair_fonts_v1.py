import copy
import unittest
import compiler_native_source_repair_fonts_v1 as fonts


def run():return dict(index=0,text='fallback',actual_fonts=[dict(postScriptName='Fallback',glyphCount=8,isCustomFont=False)],primary_metric_fonts=[dict(postScriptName='Primary',glyphCount=1,isCustomFont=False)],fontWeight='400',fontStyle='italic')
def faces():return dict(primary=dict(family='PrimaryAlias',physical_bold=False,physical_italic=True),fallback=dict(family='FallbackAlias',physical_bold=False,physical_italic=False))


class SourceFontRunTests(unittest.TestCase):
    def test_source_primary_metrics_and_actual_fallback_face_are_both_preserved(self):
        result=fonts.spec(run(),dict(Primary='primary',Fallback='fallback'),faces())
        self.assertEqual(result['family'],'PrimaryAlias,FallbackAlias');self.assertEqual(result['source_primary_metric_postscript'],'Primary');self.assertEqual(result['physical_postscript'],['Fallback']);self.assertEqual(result['style'],'italic')

    def test_actual_italic_face_is_not_synthetically_italicized_again(self):
        row=run();row['actual_fonts'][0]['postScriptName']='Primary';result=fonts.spec(row,dict(Primary='primary'),faces())
        self.assertEqual(result['family'],'PrimaryAlias');self.assertEqual(result['style'],'normal')

    def test_actual_bold_face_absorbs_bold_without_changing_nonfont_markup(self):
        row=run();row.update(fontWeight='700',fontStyle='normal');f=faces();f['fallback']['physical_bold']=True
        self.assertEqual(fonts.spec(row,dict(Primary='primary',Fallback='fallback'),f)['weight'],'normal')

    def test_unpainted_whitespace_remains_original_layout_data(self):
        row=run();row.update(text=' \n',actual_fonts=[])
        self.assertTrue(fonts.spec(row,{},{}).get('preserve_unpainted_whitespace'))

    def test_unobserved_visible_run_cannot_be_guessed(self):
        row=run();row['actual_fonts']=[]
        with self.assertRaisesRegex(ValueError,'no_observed_physical_face'):fonts.spec(row,{},{} )

    def test_mixed_physical_style_in_one_complete_text_node_stays_pending(self):
        row=run();row['actual_fonts'].append(dict(postScriptName='Primary',glyphCount=1,isCustomFont=False))
        with self.assertRaisesRegex(ValueError,'same_text_node_mixed_physical_styles'):fonts.spec(row,dict(Primary='primary',Fallback='fallback'),faces())

    def test_ambiguous_primary_font_metric_witness_is_rejected(self):
        row=run();row['primary_metric_fonts']=[]
        with self.assertRaisesRegex(ValueError,'metric_face_ambiguous'):fonts.spec(row,dict(Primary='primary',Fallback='fallback'),faces())

    def test_new_graph_mutations_are_not_hidden_by_font_value_elision(self):
        original='<mxfile><diagram><mxGraphModel pageWidth="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="n" parent="1" vertex="1" value="text" style="shape=text;fontFamily=Arial;"><mxGeometry x="10" y="20"/></mxCell><mxCell id="e" source="n" target="n" edge="1"/></root></mxGraphModel></diagram></mxfile>'
        canonical=fonts.nonfont_graph_identity(original,rich_cells=['n'])
        for changed in (original.replace('x="10"','x="11"'),original.replace('source="n"','source="missing"'),original.replace('shape=text','shape=image'),original.replace('pageWidth="100"','pageWidth="101"')):
            self.assertNotEqual(canonical,fonts.nonfont_graph_identity(changed,rich_cells=['n']))

    def test_named_style_order_and_default_reset_are_source_semantics(self):
        original='<mxfile><diagram><mxGraphModel><root><mxCell id="n" style=";namedA;namedB;fontFamily=Arial;"/></root></mxGraphModel></diagram></mxfile>'
        canonical=fonts.nonfont_graph_identity(original,ordinary_cells=['n'])
        for changed in (original.replace(';namedA;namedB;','namedA;namedB;'),original.replace('namedA;namedB','namedB;namedA')):
            self.assertNotEqual(canonical,fonts.nonfont_graph_identity(changed,ordinary_cells=['n']))
        self.assertEqual(canonical,fonts.nonfont_graph_identity(original.replace('Arial','PortableAlias'),ordinary_cells=['n']))


if __name__=='__main__':unittest.main()
