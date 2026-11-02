"""Pure adversarial tests of independently replayed HTML font deltas."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E

import native_html_font_quality_v3 as q


def font(ps,count=1,custom=False):return {'postScriptName':ps,'glyphCount':count,'isCustomFont':custom}


class Probe:
    def __init__(self):self.calls=[]
    def graphemes(self,text):return list(text)
    def fonts(self,family,flags,size,text):
        self.calls.append((family,flags,size,text))
        return [font('ArialMT' if text=='M' else 'MathPS')]


class FontDeltaTests(unittest.TestCase):
    def fixture(self,extra_primary=True):
        root=E.Element('mxfile');cells=E.SubElement(E.SubElement(E.SubElement(root,'diagram'),'mxGraphModel'),'root')
        E.SubElement(cells,'mxCell',id='base',vertex='1',value='M',style='namedStyle;fontFamily=Arial;fontStyle=0;fontSize=12;')
        E.SubElement(cells,'mxCell',id='s',vertex='1',value='𝒥',style='namedStyle;fontFamily=Arial;fontStyle=0;fontSize=12;')
        before=E.tostring(root,encoding='unicode');after=E.fromstring(before)
        after.find('.//mxCell[@id="s"]').set('style','namedStyle;fontFamily=' + ('Base,Math' if extra_primary else 'Math') + ';fontStyle=0;fontSize=12;')
        xml=E.tostring(after,encoding='unicode')
        rows=[{'cell':'base','label':'M','style':{'fontFamily':'Arial','fontStyle':0,'fontSize':12},'actual_fonts':[font('ArialMT')]},{'cell':'s','label':'𝒥','style':{'fontFamily':'Arial','fontStyle':0,'fontSize':12},'actual_fonts':[font('MathPS')]}]
        faces={'Base':{'postscript':'ArialMT','bold':False,'italic':False},'Math':{'postscript':'MathPS','bold':False,'italic':False}}
        cmaps={'ArialMT':{ord('M')},'MathPS':{ord('𝒥')}}
        body={'schema':q.ORDER_SCHEMA,'family':'Arial','flags':0,'size':12.0,'observations':[{'text':'𝒥','fonts':[],'wanted_postscript':'MathPS','basis':'unique_original_observed_cmap_face'}],'constraints':[],'ordered_postscript':['ArialMT','MathPS'] if extra_primary else ['MathPS'],'no_target_image_score_used':True}
        body['sha256']=q.sha(json.dumps(body,sort_keys=True,ensure_ascii=False).encode())
        details={'issues':[],'changes':[{'cell':'s','families':['Base','Math'] if extra_primary else ['Math'],'before_family':'Arial','before_flags':0,'after_flags':0,'actual_fonts':[font('MathPS')],'primary_strut':{'postscript':'ArialMT','family':'Base','basis':'same_original_graph_observed_requested_primary_face'} if extra_primary else None,'physical_fallback_precedence':body}]}
        return [before,xml,details,rows,faces,Probe(),cmaps]

    def run_delta(self,args=None):return q.verify_changes(*(args or self.fixture()))
    def refresh(self,args):
        proof=args[2]['changes'][0]['physical_fallback_precedence'];proof['sha256']=q.sha(json.dumps({k:v for k,v in proof.items() if k!='sha256'},sort_keys=True,ensure_ascii=False).encode())

    def test_same_graph_primary_and_unique_original_cmap_face_pass(self):
        args=self.fixture();result=self.run_delta(args)
        self.assertEqual(result['changed_cells'],['s'])
        self.assertEqual(args[5].calls,[('Arial',0,12.0,'M')])

    def test_no_extra_primary_is_required_for_fallback_only_cell(self):
        self.assertEqual(self.run_delta(self.fixture(False))['primary_strut_checks'],[])

    def test_unobserved_primary_is_rejected(self):
        args=self.fixture();args[3][0]['actual_fonts']=[font('OtherPS')]
        with self.assertRaisesRegex(ValueError,'primary_not_observed'):self.run_delta(args)

    def test_same_graph_different_original_flags_does_not_prove_primary(self):
        args=self.fixture();args[3][0]['style']['fontStyle']=1
        with self.assertRaisesRegex(ValueError,'primary_not_observed'):self.run_delta(args)

    def test_primary_must_match_fresh_original_css_M_probe(self):
        args=self.fixture();args[5].fonts=lambda *a:[font('OtherPS')]
        with self.assertRaisesRegex(ValueError,'fresh_M'):self.run_delta(args)

    def test_unproven_extra_font_is_rejected(self):
        args=self.fixture();args[2]['changes'][0]['primary_strut']=None
        with self.assertRaisesRegex(ValueError,'without_primary_proof'):self.run_delta(args)

    def test_claimed_primary_must_remain_first(self):
        args=self.fixture();args[1]=args[1].replace('fontFamily=Base,Math','fontFamily=Math,Base');args[2]['changes'][0]['families']=['Math','Base']
        with self.assertRaisesRegex(ValueError,'not_first'):self.run_delta(args)

    def test_nonfont_geometry_or_markup_is_rejected(self):
        for before,after in [('value="𝒥"','value="B"'),('vertex="1"','vertex="0"'),('namedStyle;','')]:
            args=self.fixture();args[1]=args[1].replace(before,after)
            with self.subTest(after=after),self.assertRaisesRegex(ValueError,'nonfont_graph'):self.run_delta(args)

    def test_added_extra_stack_face_is_rejected_even_with_forged_order(self):
        args=self.fixture();args[1]=args[1].replace('fontFamily=Base,Math','fontFamily=Base,Math,Extra');args[2]['changes'][0]['families'].append('Extra');args[4]['Extra']={'postscript':'UnobservedPS','bold':False,'italic':False}
        with self.assertRaisesRegex(ValueError,'unobserved_extra'):self.run_delta(args)

    def test_mixed_physical_styles_are_rejected(self):
        args=self.fixture();args[4]['Base']['italic']=True
        with self.assertRaisesRegex(ValueError,'mixed_physical_styles'):self.run_delta(args)

    def test_tampered_precedence_hash_is_rejected(self):
        args=self.fixture();args[2]['changes'][0]['physical_fallback_precedence']['no_target_image_score_used']=False
        with self.assertRaisesRegex(ValueError,'hash_mismatch'):self.run_delta(args)

    def test_score_fitting_claim_is_rejected_even_rehashed(self):
        args=self.fixture();args[2]['changes'][0]['physical_fallback_precedence']['no_target_image_score_used']=False;self.refresh(args)
        with self.assertRaisesRegex(ValueError,'score_fitting'):self.run_delta(args)

    def test_unique_cmap_does_not_trust_isolated_wrong_font(self):
        args=self.fixture(False);args[5].fonts=lambda *a:[font('WrongPS')]
        self.assertEqual(self.run_delta(args)['changed_cells'],['s'])

    def test_forged_unique_cmap_basis_is_rejected(self):
        args=self.fixture(False);proof=args[2]['changes'][0]['physical_fallback_precedence'];proof['observations'][0]['wanted_postscript']='ArialMT';self.refresh(args)
        with self.assertRaisesRegex(ValueError,'wanted_or_inventory_basis'):self.run_delta(args)

    def test_record_must_be_html_font_revision(self):
        with patch.object(q,'R',Path('/nonexistent/independent-font-unit-test')):
            self.assertEqual(q.verify({'source_format':'svg','format':'drawio'})['reason'],'html_font_only_html_native_revisions_supported')

    def test_ambiguous_cmap_uses_actual_probe_and_enforces_precedence(self):
        args=self.fixture(False);args[3][1]['label']='𝒥';args[3][1]['actual_fonts']=[font('MathPS'),font('SansPS')];args[2]['changes'][0]['actual_fonts']=copy.deepcopy(args[3][1]['actual_fonts']);args[4]['Sans']={'postscript':'SansPS','bold':False,'italic':False};args[6]['SansPS']={ord('𝒥')};args[1]=args[1].replace('fontFamily=Math;','fontFamily=Math,Sans;');args[2]['changes'][0]['families']=['Math','Sans']
        proof=args[2]['changes'][0]['physical_fallback_precedence'];proof.update(observations=[{'text':'𝒥','fonts':[font('MathPS')],'wanted_postscript':'MathPS','basis':'isolated_original_CSS_physical_font_probe'}],constraints=[['MathPS','SansPS']],ordered_postscript=['MathPS','SansPS']);self.refresh(args)
        self.assertEqual(self.run_delta(args)['grapheme_order_checks'][0]['constraints'],1)
        args[1]=args[1].replace('fontFamily=Math,Sans;','fontFamily=Sans,Math;');args[2]['changes'][0]['families']=['Sans','Math'];proof['ordered_postscript']=['SansPS','MathPS'];self.refresh(args)
        with self.assertRaisesRegex(ValueError,'violates_original'):self.run_delta(args)


if __name__=='__main__':unittest.main()
