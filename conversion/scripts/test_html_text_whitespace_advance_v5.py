import copy,unittest,xml.etree.ElementTree as E
import html_text_whitespace_advance_v5 as whitespace
from html_actual_text_alignment import _plain


def fixture():
    source=[{'text':'A','raw':'A','x':10,'y':12,'width':5,'height':10},{'text':' ','raw':'  ','x':15,'y':12,'width':8,'height':10},{'text':'B','raw':'B','x':23,'y':12,'width':5,'height':10}]
    obj={'id':1,'type':'text','text':'A B','x':10,'y':12,'w':18,'h':10,'fontSize':10,'color':{'color':'#000000','opacity':1},'opacity':1,'actualSourceGlyphs':source,'actualSourceCss':{'fontSize':10},'actualSourcePhysicalFonts':{'fonts':[{'postScriptName':'FixtureFace','glyphCount':4}],'basis':'actual_text_node'}}
    dom={'objects':[obj]};native={'actual_text_positions':[{'cell':'2','runs':[{'font':'10px Embedded','chars':[{'text':'A','x':10,'y':12,'width':5,'height':10},{'text':' ','x':15,'y':12,'width':4,'height':10},{'text':'B','x':19,'y':12,'width':5,'height':10}]}]}],'actual_platform_font_usage':[{'cell':'2','fonts':[{'postScriptName':'FixtureFace','glyphCount':3,'isCustomFont':True}]}]};xml='<mxfile><mxCell id="2" parent="1" vertex="1" value="A B" style="shape=text;fontSize=10;"><mxGeometry x="10" y="12" width="18" height="10"/></mxCell></mxfile>'
    return dom,native,xml

class Tests(unittest.TestCase):
    def test_raw_source_space_width_yields_single_deterministic_advance(self):
        dom,before,xml=fixture();plan=whitespace.plan(dom,before,xml);self.assertEqual(plan['eligible_count'],1);self.assertEqual(plan['objects'][0]['targets'][0]['extra_advance'],4);candidate,proof=whitespace.propose(xml,plan);cell=E.fromstring(candidate).find('mxCell');self.assertEqual(_plain(cell.get('value')),'A B');self.assertIn('word-spacing:4px',cell.get('value'));after=copy.deepcopy(before);chars=after['actual_text_positions'][0]['runs'][0]['chars'];chars[1]['width']+=4;chars[2]['x']+=4;self.assertTrue(whitespace.verify(xml,candidate,proof,dom,before,after)['ok'])
    def test_baseline_nonspace_height_is_preserved_instead_of_fitted(self):
        dom,before,xml=fixture();dom['objects'][0]['actualSourceGlyphs'][0]['height']=11;plan=whitespace.plan(dom,before,xml);self.assertEqual(plan['eligible_count'],1);candidate,proof=whitespace.propose(xml,plan);after=copy.deepcopy(before);chars=after['actual_text_positions'][0]['runs'][0]['chars'];chars[1]['width']+=4;chars[2]['x']+=4;self.assertTrue(whitespace.verify(xml,candidate,proof,dom,before,after)['ok'])
    def test_normal_collapsed_space_or_unexplained_nonspace_width_is_not_proposed(self):
        dom,before,xml=fixture();dom['objects'][0]['actualSourceGlyphs'][1]['raw']=' ';self.assertEqual(whitespace.plan(dom,before,xml)['eligible_count'],0)
        dom,before,xml=fixture();dom['objects'][0]['actualSourceGlyphs'][2]['width']+=1;plan=whitespace.plan(dom,before,xml);self.assertEqual(plan['eligible_count'],0);self.assertTrue(plan['unsupported'])
    def test_fixed_clip_unresolved_face_or_css_size_remains_explicit(self):
        for mode in ('clip','face','size'):
            dom,before,xml=fixture()
            if mode=='clip':dom['objects'][0]['sourceClip']={'partial':True}
            elif mode=='face':before['actual_platform_font_usage'][0]['fonts'][0]['postScriptName']='OtherFace'
            else:before['actual_text_positions'][0]['runs'][0]['font']='11px Embedded'
            plan=whitespace.plan(dom,before,xml);self.assertEqual(plan['eligible_count'],0);self.assertTrue(plan['unsupported'])
    def test_current_nonspace_glyph_font_count_or_graph_changes_are_rejected(self):
        for mode in ('y','width','font','graph'):
            dom,before,xml=fixture();candidate,proof=whitespace.propose(xml,whitespace.plan(dom,before,xml));after=copy.deepcopy(before);chars=after['actual_text_positions'][0]['runs'][0]['chars'];chars[1]['width']+=4;chars[2]['x']+=4
            if mode=='y':chars[0]['y']+=.2
            elif mode=='width':chars[0]['width']+=.2
            elif mode=='font':after['actual_platform_font_usage'][0]['fonts'][0]['glyphCount']+=1
            else:candidate=candidate.replace('width="18"','width="19"')
            with self.assertRaises(AssertionError):whitespace.verify(xml,candidate,proof,dom,before,after)
    def test_entities_markup_and_unicode_logical_offsets_are_preserved(self):
        value='<font face="Keep">A&amp;😀 B</font>';parser=whitespace._Wrap(value,{3:{'extra_advance':4}});parser.feed(value);parser.close();after=parser.result();self.assertEqual(_plain(value),_plain(after));self.assertIn('<font face="Keep">',after);self.assertIn('word-spacing:4px',after)

if __name__=='__main__':unittest.main()
