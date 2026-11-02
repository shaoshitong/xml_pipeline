import base64
import json
from pathlib import Path
import tempfile
import unittest
import urllib.parse
import zlib

import native_source_dynamic_label_guard_v1 as guard


class NativeDynamicSourceGuardTests(unittest.TestCase):
    def xml(self,label='&lt;b&gt;%name%&lt;/b&gt;',attrs='placeholders="1" name="Example"',tag='UserObject',style='namedStyle;html=1;'):
        return '<mxGraphModel pageWidth="100" pageHeight="100"><root><mxCell id="0"/><mxCell id="1" parent="0"/><'+tag+' id="a" label="'+label+'" '+attrs+'><mxCell parent="1" vertex="1" style="'+style+'"/></'+tag+'></root></mxGraphModel>'
    def inspect(self,*args,**kwargs):return guard.inspect_xml(self.xml(*args,**kwargs))
    def test_any_XML_object_tag_with_native_expression_is_pending(self):
        for tag in ('UserObject','object','ArbitraryMetadata','root'):
            report=self.inspect(tag=tag);self.assertFalse(report['supported']);self.assertEqual(report['findings'][0]['wrapper_tag'],tag)
    def test_named_style_and_missing_html_flag_cannot_hide_dynamic_label(self):
        for style in ('namedHtmlStyle;','html=0;','', 'otherStyle;html=1;'):
            self.assertFalse(self.inspect(style=style)['supported'])
    def test_wrapper_activation_is_exact_attribute_value(self):
        for attrs in ('placeholders="0"','placeholders="true"','', 'placeholder="name"'):
            self.assertTrue(self.inspect(attrs=attrs)['supported'])
    def test_plain_mxCell_value_does_not_inherit_style_placeholders_activation(self):
        xml='<mxGraphModel><root><mxCell id="a" value="%name%" style="placeholders=1;html=1;"/></root></mxGraphModel>'
        report=guard.inspect_xml(xml);self.assertTrue(report['supported']);self.assertEqual(report['style_only_placeholder_flags'],1)
    def test_direct_property_placeholder_with_no_percent_label_is_pending(self):
        report=self.inspect(label='literal label',attrs='placeholders="1" placeholder="name" name="First"');self.assertFalse(report['supported']);self.assertIn('property_role',report['findings'][0]['reason'])
    def test_empty_property_role_is_conservatively_pending(self):self.assertFalse(self.inspect(label='',attrs='placeholders="1" placeholder=""')['supported'])
    def test_localized_label_expression_is_guarded(self):self.assertFalse(self.inspect(label='literal',attrs='placeholders="1" label_fr="%name%"')['supported'])
    def test_literal_percent_without_native_expression_is_safe(self):
        for label in ('100%','50% complete','%foo=bar%','%foo;bar%','%{foo}%'):
            self.assertTrue(self.inspect(label=label)['supported'])
    def test_native_date_and_spaces_pattern_are_not_guessed_variable_names(self):
        for label in ('%date{yyyy-mm-dd}%','%field with space%','%arbitrary-unseen-property%'):
            self.assertFalse(self.inspect(label=label)['supported'])
    def test_native_date_line_terminators_do_not_match(self):
        for terminator in ('&#10;','&#13;','&#8232;','&#8233;'):
            self.assertTrue(self.inspect(label='%date{year'+terminator+'month}%')['supported'])
    def test_reserved_and_escape_syntax_remain_conservatively_pending(self):
        for label in ('%label%','%tooltip%','%%name%'):
            report=self.inspect(label=label);self.assertFalse(report['supported']);self.assertTrue(report['findings'][0]['conservative_reserved_or_escape_deferral'])
    def test_nested_XML_envelope_cannot_hide_enabled_source_expression(self):
        xml='<mxGraphModel><root><Outer id="outer" placeholders="1" label="%name%"><Inner id="inner"><mxCell vertex="1"/></Inner></Outer></root></mxGraphModel>'
        report=guard.inspect_xml(xml);self.assertFalse(report['supported']);self.assertEqual(report['findings'][0]['wrapper_tag'],'Outer');self.assertEqual(report['findings'][0]['wrapper_depth'],2)

    def test_wrapper_attribute_inheritance_does_not_enable_a_string_child(self):
        xml='<mxGraphModel><root><UserObject id="parent" placeholders="1" label="Parent" name="X"><mxCell parent="1"/></UserObject><mxCell id="child" parent="parent" value="%name%"/></root></mxGraphModel>'
        self.assertTrue(guard.inspect_xml(xml)['supported'])
    def test_disabled_wrapper_with_style_placeholder_flag_is_safe(self):self.assertTrue(self.inspect(attrs='',style='namedStyle;placeholders=1;')['supported'])
    def test_all_pages_including_compressed_page_are_checked(self):
        risky=self.xml();compressed=base64.b64encode(zlib.compress(urllib.parse.quote(risky).encode())[2:-4]).decode();safe=self.xml(label='literal')
        xml='<mxfile><diagram>'+safe+'</diagram><diagram>'+compressed+'</diagram></mxfile>'
        report=guard.inspect_xml(xml);self.assertFalse(report['supported']);self.assertEqual(report['findings'][0]['page'],1)
    def test_unknown_source_XML_is_pending_and_never_irrecoverable(self):
        for xml in ('not XML','<svg/>','<mxfile/>','<mxfile><diagram/></mxfile>'):
            report=guard.inspect_xml(xml);self.assertFalse(report['supported']);self.assertTrue(report['pending_for_source_preserving_core'])
    def test_raw_label_inventory_stays_internal_and_reports_only_hashes(self):
        label='&lt;b&gt;%highly-sensitive-property%&lt;/b&gt;';report=self.inspect(label=label)
        self.assertNotIn('highly-sensitive-property',json.dumps(report));self.assertIn('%highly-sensitive-property%',guard.label_records(self.xml(label=label))[2]['labels']['label'])
    def test_complete_canonical_payload_is_bound_without_reading_images(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);p=root/'source.xml';p.write_text(self.xml());source=dict(pair_sha256='id',category='scientific_diagram',format='drawio',source='provider',code_sha256=guard.sha(p.read_bytes()),image_sha256='unread-image')
            job=('id',source['category'],'drawio','provider',json.dumps(source),'pending',None,0,None,None,None,json.dumps(dict(source_code='source.xml',reference_image='does-not-exist.png')),None)
            report=guard.inspect_job(job,root);self.assertFalse(report['supported']);self.assertEqual(report['source_code_sha256'],source['code_sha256'])
            p.write_text('changed')
            with self.assertRaisesRegex(RuntimeError,'payload_hash_changed'):guard.inspect_job(job,root)
    def test_five_field_summary_and_short_tuple_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'full13'):guard.inspect_job(('id',)*5)


if __name__=='__main__':unittest.main()
