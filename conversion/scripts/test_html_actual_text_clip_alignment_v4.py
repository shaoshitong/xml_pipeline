import copy,io,unittest
from importlib.util import find_spec
import xml.etree.ElementTree as E
import html_actual_text_clip_alignment_v4 as clip
from test_html_actual_text_alignment import fixture


def case():
    dom,before,xml=fixture();dom['objects'][0]['sourceClip']={'partial':True,'unmodeled':[],'chain':[{'left':0,'top':0,'right':32,'bottom':21,'clipX':True,'clipY':True,'radius':['0px']*4}]};value='<span style="clip-path:inset(-16px -12px 5px -10px);">AB</span>';root=E.fromstring(xml);root.find('mxCell').set('value',value);xml=E.tostring(root,encoding='unicode');before['actual_clip_boxes']=[{'cell':'2','clips':[{'x':10,'y':16,'width':10,'height':10,'clipPath':'inset(-16px -12px 5px -10px)','text':'AB','fragments':[{'x':10,'y':16,'width':10,'height':10}]}]}];return dom,before,xml

class Tests(unittest.TestCase):
    def test_inner_range_delta_keeps_geometry_and_outer_css_clip(self):
        dom,before,xml=case();candidate,proof=clip.propose_clip_locked(xml,dom,before,[32,32]);self.assertEqual(len(proof['changes']),1);old=E.fromstring(xml).find('mxCell');new=E.fromstring(candidate).find('mxCell');self.assertEqual(old.find('mxGeometry').attrib,new.find('mxGeometry').attrib);self.assertEqual(old.get('style'),new.get('style'));self.assertIn('top:-4px',new.get('value'));self.assertTrue(new.get('value').startswith('<span style="clip-path:inset(-16px -12px 5px -10px);">'))
        after=copy.deepcopy(before)
        for char in after['actual_text_positions'][0]['runs'][0]['chars']:char['y']=12
        self.assertTrue(clip.verify_clip_locked(xml,candidate,proof,dom,before,after,[32,32])['ok'])
    def test_rejected_subset_is_exact_original_without_changing_other_objects(self):
        dom,before,xml=case();candidate,proof=clip.propose_clip_locked(xml,dom,before,[32,32],cells=set())
        self.assertEqual(E.canonicalize(candidate),E.canonicalize(xml));self.assertFalse(proof['changes'])
    def test_moved_mask_or_changed_physical_glyphs_is_rejected(self):
        for damage in ('clip','glyph','font','graph'):
            dom,before,xml=case();candidate,proof=clip.propose_clip_locked(xml,dom,before,[32,32]);after=copy.deepcopy(before)
            for char in after['actual_text_positions'][0]['runs'][0]['chars']:char['y']=12
            if damage=='clip':after['actual_clip_boxes'][0]['clips'][0]['y']+=1
            elif damage=='glyph':after['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.2
            elif damage=='font':after['actual_platform_font_usage'][0]['fonts'][0]['glyphCount']=1
            else:candidate=candidate.replace('width="20"','width="21"')
            with self.assertRaises(AssertionError):clip.verify_clip_locked(xml,candidate,proof,dom,before,after,[32,32])
    def test_unknown_rounded_or_multifragment_clip_is_explicitly_unsupported(self):
        for damage in ('round','fragments','unmodeled','wrong_existing_mask'):
            dom,before,xml=case()
            if damage=='round':dom['objects'][0]['sourceClip']['chain'][0]['radius']=['1px']*4
            elif damage=='fragments':before['actual_clip_boxes'][0]['clips'][0]['fragments']*=2
            elif damage=='unmodeled':dom['objects'][0]['sourceClip']['unmodeled']=['transform']
            else:before['actual_clip_boxes'][0]['clips'][0]['clipPath']='inset(0px)'
            candidate,proof=clip.propose_clip_locked(xml,dom,before,[32,32]);self.assertFalse(proof['changes']);self.assertEqual(len(proof['unsupported']),1);self.assertEqual(E.canonicalize(candidate),E.canonicalize(xml))
    def test_clip_intersection_uses_source_axes_and_verified_global_offset(self):
        dom,_,_=case();chain=dom['objects'][0]['sourceClip']['chain'];chain.append({'left':3,'top':9,'right':15,'bottom':18,'clipX':True,'clipY':False,'radius':['0px']*4})
        self.assertEqual(clip.source_rectangle(dom['objects'][0],[32,32],(4,5)),[7,5,19,26])

@unittest.skipUnless(find_spec('numpy') is not None,'Remote image runtime')
class PixelTests(unittest.TestCase):
    def png(self,rect):
        from PIL import Image,ImageDraw
        image=Image.new('RGB',(32,32),'white')
        if rect:ImageDraw.Draw(image).rectangle(rect,fill='black')
        out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()
    def test_exact_global_clip_mask_and_negative_missing_clip(self):
        group=[{'cell':'2','source_clip_bounds':[0,0,32,21],'influence_box':[8,10,24,28]}];unclipped=self.png((10,12,20,25));candidate=self.png((10,12,20,20));background=self.png(None)
        self.assertTrue(clip.pixel_mask_proof(candidate,unclipped,background,group)['ok']);self.assertFalse(clip.pixel_mask_proof(unclipped,unclipped,background,group)['ok'])
    def test_fractional_boundary_needs_separate_raster_mask_proof(self):
        with self.assertRaises(AssertionError):clip.pixel_mask_proof(self.png(None),self.png(None),self.png(None),[{'cell':'2','source_clip_bounds':[0,0,32,21.5],'influence_box':[0,0,32,32]}])

if __name__=='__main__':unittest.main()
