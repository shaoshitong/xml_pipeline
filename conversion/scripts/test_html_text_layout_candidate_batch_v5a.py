import copy
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as E

import html_text_layout_candidate_batch_v5a as c


class PartialClipTests(unittest.TestCase):
    def test_fractional_or_unsupported_clip_preserves_the_whole_object(self):
        proof={'changes':[{'cell':'fractional','source_clip_bounds':[.5,0,10,10]},
                          {'cell':'integer','source_clip_bounds':[0,0,10,10]}],
               'unsupported':[{'cell':'rounded','reason':'rounded mask unsupported'}]}
        spaces,clips,issues=c.supported_scopes({'fractional','rounded','space'},proof)
        self.assertEqual(spaces,{'space'});self.assertEqual(clips,{'integer'})
        self.assertEqual({r['cell'] for r in issues},{'fractional','rounded'})

    def test_overlapping_or_inherited_primitive_is_not_reapplied(self):
        proof={'changes':[{'cell':v,'source_clip_bounds':[0,0,10,10]} for v in ['both','inherited','clip']], 'unsupported':[]}
        spaces,clips,issues=c.supported_scopes({'both','space'},proof,['inherited'])
        self.assertEqual(spaces,{'space'});self.assertEqual(clips,{'clip'})
        self.assertEqual({r['cell'] for r in issues},{'both','inherited'})

    def operation(self):
        before={'xml':'before','xml_entry':{'file':'before'},'render_entry':{'file':'before-render'}}
        after={'xml':'after','png':b'candidate','native':{},'xml_entry':{'file':'after'},
               'render_entry':{'file':'after-render'},'png_entry':{'file':'after-png'}}
        return {'kind':'clip_locked_v4','before':before,'after':after,'proof':{'changes':[{'cell':'good'},{'cell':'bad'}]}}

    def fake_clip(self,pixel=False):
        return types.SimpleNamespace(disjoint_clip_groups=lambda proof,info:[proof['changes']],
          diagnostic_variants=lambda xml,cells:('unclipped:'+','.join(sorted(cells)),'background:'+','.join(sorted(cells))),
          pixel_mask_proof=lambda a,b,d,group:{'ok':not pixel or 'bad' not in {r['cell'] for r in group}})

    def render(self,code,label):
        if 'bad' in code:raise AssertionError('Diagnostic actual paint outside declared canvas')
        return {'png':code.encode(),'xml_entry':{'file':label+'.xml'},'png_entry':{'file':label+'.png'}}

    def test_group_overflow_is_reduced_to_only_the_unsupported_object(self):
        operation=self.operation();step,issues=c.diagnostic_clip_step(operation,self.fake_clip(),self.render,'probe')
        self.assertIsNone(step);self.assertEqual([r['cell'] for r in issues],['bad'])
        operation['proof']['changes']=[{'cell':'good'}]
        step,issues=c.diagnostic_clip_step(operation,self.fake_clip(),self.render,'retained')
        self.assertEqual(issues,[]);self.assertEqual(step['pixel_groups'][0]['group'],[{'cell':'good'}])

    def test_mask_mismatch_is_a_single_object_rollback_not_a_waiver(self):
        def render(code,label):return {'png':code.encode(),'xml_entry':{'file':label+'.xml'},'png_entry':{'file':label+'.png'}}
        step,issues=c.diagnostic_clip_step(self.operation(),self.fake_clip(pixel=True),render,'probe')
        self.assertIsNone(step);self.assertEqual([r['cell'] for r in issues],['bad'])

    def test_retained_object_equality_includes_style_geometry_and_text(self):
        before='<mxfile><diagram><mxGraphModel><root><mxCell id="a" value="original"><mxGeometry x="1"/></mxCell></root></mxGraphModel></diagram></mxfile>'
        self.assertTrue(c.retained_objects(before,before,[{'cell':'a'}])[0]['unchanged'])
        with self.assertRaises(AssertionError):c.retained_objects(before,before.replace('x="1"','x="2"'),[{'cell':'a'}])


try:
    import test_html_text_layout_candidate_v5 as frozen_tests
except ImportError:
    frozen_tests=None


if frozen_tests is not None:
    class FullBuilderTests(frozen_tests.BuilderRollbackTests):
        def run_case(self,*args,**kwargs):
            with patch.object(frozen_tests,'candidate',c):return super().run_case(*args,**kwargs)

        def test_fractional_clip_cell_stays_original_while_other_whitespace_is_proven(self):
            import html_actual_text_clip_alignment_v4 as clip
            def fractional(xml,*args,**kwargs):
                return xml,{'changes':[{'cell':'2','source_clip_bounds':[.5,0,64,64]}],'unsupported':[]}
            with tempfile.TemporaryDirectory() as directory,patch.object(clip,'propose_clip_locked',side_effect=fractional):
                (work,out,proof),old=self.run_case(directory)
                self.assertEqual(proof['changed_cells'],['3'])
                self.assertEqual(proof['unsupported_objects_retained_exactly'][0]['cell'],'2')
                oldcell=next(x for x in E.fromstring(old).iter('mxCell') if x.get('id')=='2')
                newcell=next(x for x in E.fromstring((work/'candidate.drawio').read_text()).iter('mxCell') if x.get('id')=='2')
                self.assertEqual(E.canonicalize(E.tostring(oldcell,encoding='unicode')),E.canonicalize(E.tostring(newcell,encoding='unicode')))
                self.assertFalse(proof['accepted']);self.assertFalse(proof['published'])
                self.assertFalse((Path(directory)/out['code_file']).exists())


if __name__=='__main__':unittest.main()
