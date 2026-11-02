import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

import clip_canvas_render_v4b as b


def png(width=20,height=10):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\xff\xff'*width)*height))+chunk(b'IEND',b'')


def native(manifest,strict=False):
    info={'selected_image':'declared_first_page','output_size':[20,10],'canvas':[20,10],
          'scale':1,'translate':[0,0],'content_outside_declared_canvas':False,'native_graph_bounds_outside_declared_canvas':False,
          'runtime_cache_manifest_sha256':b.sha(manifest.read_bytes()),'runtime_cache_id':'exact-runtime',
          'viewer_bundle_sha256':'a'*64,'runtime_cache_provenance':{'version':1,'commit':'pinned'},
          'actual_platform_font_usage':[{'cell':'2','selectors':['#temporary_clip_selector'],'fonts':[{'postScriptName':'PS','familyName':'Face','isCustomFont':True,'glyphCount':1}]}],
          'actual_text_positions':[{'cell':'2','runs':[{'text':'x','font':'10px Face','fontKerning':'auto','fontFeatureSettings':'normal','letterSpacing':'normal','lineHeight':'normal','chars':[{'text':'x','x':1,'y':2,'width':3,'height':4}]}]}],
          'actual_clip_boxes':[{'cell':'2','clips':[{'clipPath':'inset(0px)','text':'x'}]}]}
    if strict:
        info.pop('actual_clip_boxes');info['actual_platform_font_usage'][0]['selectors']=['#a_different_temporary_selector']
        info['probe_includes_actual_dom_paint_bounds']=True
        info['outside_page_pixel_audit']={'padded_native_render_size':[84,74],'offset':[32,32],'nonwhite_outside_pixels':0,'white_threshold':255,'minimum_probe_margin':32,'audit_always_performed':True}
    return {'ok':True,'png':png(),'native_render':info,'native_selected':True,'seconds':0.1}


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.work=self.root/'conversion';self.clip=self.work/'rendering_clipbox_strict/remote_render.py';self.paint=self.work/'rendering_paintbounds_strict/remote_render.py';self.manifest=self.root/'evaluation/runtime/manifest.json'
        for path,data in [(self.clip,b'clip renderer frozen'),(self.paint,b'strict renderer frozen'),(self.manifest,b'{"runtime":"pinned"}')]:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        self.patches=[patch.object(b,'R',self.root),patch.object(b,'W',self.work),patch.object(b,'CLIP_RENDERER',self.clip),patch.object(b,'STRICT_RENDERER',self.paint)]
        for item in self.patches:item.start()
        self.c=native(self.manifest);self.p=native(self.manifest,True)
    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()
    def run_pair(self,c=None,p=None,effect=None):
        with patch.object(b,'_native_job',side_effect=effect or [c if c is not None else self.c,p if p is not None else self.p]) as mock:
            result=b.render('<mxfile/>',20,10,180,self.clip,8192,self.manifest)
        return result,mock
    def rejected(self,c=None,p=None,effect=None):
        result,mock=self.run_pair(c,p,effect);self.assertFalse(result['ok'],result);self.assertNotIn('png',result)
        entry=result['clip_canvas_strict_audit'];raw=(self.root/entry['file']).read_bytes();self.assertEqual(b.sha(raw),entry['sha256']);self.assertFalse(json.loads(raw)['ok']);return result,mock
    def test_success_preserves_clip_info_and_binds_two_real_render_artifacts_without_mutating_inputs(self):
        original=copy.deepcopy(self.c);result,mock=self.run_pair();self.assertTrue(result['ok'],result);self.assertEqual(mock.call_count,2)
        self.assertEqual(result['native_render']['actual_clip_boxes'],self.c['native_render']['actual_clip_boxes']);self.assertEqual(self.c,original)
        self.assertEqual(result['native_render']['outside_page_pixel_audit'],self.p['native_render']['outside_page_pixel_audit'])
        entry=result['clip_canvas_strict_audit'];raw=(self.root/entry['file']).read_bytes();self.assertEqual(b.sha(raw),entry['sha256']);proof=json.loads(raw)
        self.assertEqual(proof['code_sha256'],b.sha(b'<mxfile/>'));self.assertEqual(proof['png_sha256'],b.sha(self.c['png']));self.assertFalse(proof['accepted'])
        for value in proof['artifacts'].values():self.assertEqual(b.sha((self.root/value['file']).read_bytes()),value['sha256'])
        self.assertEqual(proof['pins']['clip_renderer']['sha256'],b.sha(self.clip.read_bytes()));self.assertEqual(proof['pins']['strict_renderer']['sha256'],b.sha(self.paint.read_bytes()));self.assertEqual(proof['runtime']['runtime_cache_manifest_sha256'],b.sha(self.manifest.read_bytes()))
    def test_nonclip_is_exact_single_native_passthrough(self):
        value={'ok':False,'reason':'native original error'}
        with patch.object(b,'_native_job',return_value=value) as mock:
            self.assertIs(b.render('xml',20,10,1,self.paint,8192,None),value)
        mock.assert_called_once_with('xml',20,10,1,self.paint,8192,None);self.assertFalse((self.root/b.OWNER).exists())
    def test_either_renderer_failure_rejects(self):
        self.rejected(c={'ok':False,'reason':'clip failed'})
        self.rejected(p={'ok':False,'reason':'strict failed'})
    def test_either_renderer_exception_rejects_without_second_retry(self):
        _,mock=self.rejected(effect=RuntimeError('native failure'));self.assertEqual(mock.call_count,1)
        self.rejected(effect=[self.c,RuntimeError('strict failure')])
    def test_png_bytes_must_be_identical_even_if_dimensions_and_pixels_same(self):
        self.p['png']+=b'trailing metadata';result,_=self.rejected();self.assertIn('PNG bytes differ',result['error'])
    def test_output_canvas_declared_selection_and_png_size_are_exact(self):
        for kind in ('clip','paint'):
            for field,value in [('canvas',[21,10]),('output_size',[20,9]),('selected_image','complete_tight_graph')]:
                with self.subTest(kind=kind,field=field):
                    c,p=copy.deepcopy(self.c),copy.deepcopy(self.p);(c if kind=='clip' else p)['native_render'][field]=value;self.rejected(c,p)
            c,p=copy.deepcopy(self.c),copy.deepcopy(self.p);(c if kind=='clip' else p)['png']=png(19,10);self.rejected(c,p)
    def test_actual_page_origin_and_scale_must_match(self):
        for field,value in [('scale',2),('translate',[1,0])]:
            p=copy.deepcopy(self.p);p['native_render'][field]=value;self.rejected(p=p)
    def test_old_clip_overflow_is_never_ignored_even_with_strict_zero_pixels(self):
        for field,value in [('content_outside_declared_canvas',True),('native_graph_bounds_outside_declared_canvas',True)]:
            c=copy.deepcopy(self.c);c['native_render'][field]=value;_,mock=self.rejected(c=c);self.assertEqual(mock.call_count,1)
        self.c['native_render']['outside_page_pixel_audit']=copy.deepcopy(self.p['native_render']['outside_page_pixel_audit']);self.c['native_render']['outside_page_pixel_audit']['nonwhite_outside_pixels']=1;self.rejected()
    def test_true_strict_outside_nonzero_nonwhite_threshold_or_missing_proof_reject(self):
        for field,value in [('nonwhite_outside_pixels',1),('white_threshold',254),('audit_always_performed',False),('minimum_probe_margin',0),('offset',[0,0]),('padded_native_render_size',[83,74])]:
            p=copy.deepcopy(self.p);p['native_render']['outside_page_pixel_audit'][field]=value;self.rejected(p=p)
        p=copy.deepcopy(self.p);del p['native_render']['outside_page_pixel_audit'];self.rejected(p=p)
        p=copy.deepcopy(self.p);p['native_render']['probe_includes_actual_dom_paint_bounds']=False;self.rejected(p=p)
    def test_physical_faces_custom_flags_families_and_all_glyph_counts_must_agree(self):
        for field,value in [('postScriptName','WrongPS'),('familyName','WrongFamily'),('isCustomFont',False),('glyphCount',2)]:
            p=copy.deepcopy(self.p);p['native_render']['actual_platform_font_usage'][0]['fonts'][0][field]=value;self.rejected(p=p)
        p=copy.deepcopy(self.p);p['native_render']['actual_platform_font_usage']=[];self.rejected(p=p)
    def test_text_sequence_individual_geometry_and_css_must_agree(self):
        for field,value in [('x',1.01),('y',2.01),('width',3.01),('height',4.01),('text','y')]:
            p=copy.deepcopy(self.p);p['native_render']['actual_text_positions'][0]['runs'][0]['chars'][0][field]=value;self.rejected(p=p)
        for field,value in [('font','11px Face'),('fontKerning','none'),('fontFeatureSettings','"kern" 0'),('letterSpacing','1px'),('lineHeight','20px'),('fontVariationSettings','"wght" 900')]:
            p=copy.deepcopy(self.p);p['native_render']['actual_text_positions'][0]['runs'][0][field]=value;self.rejected(p=p)
    def test_missing_clip_text_or_physical_font_evidence_fails_closed(self):
        for key in ('actual_clip_boxes','actual_platform_font_usage','actual_text_positions'):
            c=copy.deepcopy(self.c);del c['native_render'][key];self.rejected(c=c)
    def test_duplicate_cell_invalid_count_and_nonfinite_position_reject(self):
        p=copy.deepcopy(self.p);p['native_render']['actual_platform_font_usage']*=2;self.rejected(p=p)
        p=copy.deepcopy(self.p);p['native_render']['actual_platform_font_usage'][0]['fonts'][0]['glyphCount']=-1;self.rejected(p=p)
        p=copy.deepcopy(self.p);p['native_render']['actual_text_positions'][0]['runs'][0]['chars'][0]['x']=float('nan');self.rejected(p=p)
    def test_runtime_identity_current_manifest_and_viewer_are_bound(self):
        for field,value in [('runtime_cache_manifest_sha256','b'*64),('runtime_cache_id','another-runtime'),('viewer_bundle_sha256','c'*64),('runtime_cache_provenance',{'commit':'another'})]:
            p=copy.deepcopy(self.p);p['native_render'][field]=value;self.rejected(p=p)
    def test_renderer_pin_change_during_render_rejects(self):
        calls=[]
        def change(*args):
            calls.append(args)
            if len(calls)==1:return self.c
            self.paint.write_bytes(b'changed renderer');return self.p
        self.rejected(effect=change)
    def test_audit_png_tampering_during_render_rejects(self):
        calls=[]
        def change(*args):
            calls.append(args)
            if len(calls)==1:return self.c
            next((self.root/b.OWNER).rglob('clip.png')).write_bytes(b'changed audited png');return self.p
        self.rejected(effect=change)
    def test_stable_cell_order_font_row_order_and_ephemeral_selectors_do_not_create_false_difference(self):
        c=copy.deepcopy(self.c);p=copy.deepcopy(self.p)
        for r in (c,p):
            text=copy.deepcopy(r['native_render']['actual_text_positions'][0]);text['cell']='3';r['native_render']['actual_text_positions'].append(text)
            font=copy.deepcopy(r['native_render']['actual_platform_font_usage'][0]);font['cell']='3';r['native_render']['actual_platform_font_usage'].append(font)
        p['native_render']['actual_text_positions'].reverse();p['native_render']['actual_platform_font_usage'].reverse()
        result,_=self.run_pair(c,p);self.assertTrue(result['ok'],result)
    def test_unique_attempts_do_not_overwrite_any_prior_proof(self):
        a,_=self.run_pair();first=(self.root/a['clip_canvas_strict_audit']['file']).read_bytes();second,_=self.run_pair();self.assertNotEqual(a['clip_canvas_strict_audit'],second['clip_canvas_strict_audit']);self.assertEqual((self.root/a['clip_canvas_strict_audit']['file']).read_bytes(),first)


if __name__=='__main__':unittest.main()
