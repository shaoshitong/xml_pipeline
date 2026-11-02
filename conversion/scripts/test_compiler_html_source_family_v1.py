import unittest
from compiler_html_source_family_v1 import family


class TemplateTests(unittest.TestCase):
    def test_labels_geometry_colors_fonts_and_assets_do_not_make_new_template(self):
        a='<style>.box{display:flex;width:300px;color:#abcdef;font-family:Arial}</style><div class="box"><h1>First paper</h1><img src="first.png"></div>'
        b='<style>.renamed { display:flex; width:450px; color:#123456; font-family:Helvetica }</style><div class="renamed"><h1>Different title</h1><img src="second.png"></div>'
        self.assertEqual(family(a)[0],family(b)[0])

    def test_dom_multiplicity_and_order_remain_distinct(self):
        a='<div><h1>Title</h1><p>Body</p></div>'
        self.assertNotEqual(family(a)[0],family('<div><p>Body</p><h1>Title</h1></div>')[0])
        self.assertNotEqual(family(a)[0],family('<div><h1>Title</h1><p>Body</p><p>More</p></div>')[0])

    def test_css_layout_grammar_is_not_normalized_away(self):
        self.assertNotEqual(family('<div style="display:flex"></div>')[0],family('<div style="display:grid"></div>')[0])

    def test_ids_and_selector_reference_sharing_are_preserved(self):
        a='<style>#original{display:flex}</style><div id="original"><span class="a a">Text</span></div>'
        b='<style>#renamed{display:flex}</style><div id="renamed"><span class="b b">Other</span></div>'
        self.assertEqual(family(a)[0],family(b)[0])
        self.assertNotEqual(family(a)[0],family(b.replace('class="b b"','class="b c"'))[0])

    def test_inline_svg_and_void_elements_keep_structure(self):
        a='<div><img src="one"/><span>x</span><svg><text>abc</text></svg></div>'
        b='<div><img src="two"><span>y</span><svg><text>def</text></svg></div>'
        self.assertEqual(family(a)[0],family(b)[0])


if __name__=='__main__':unittest.main()
