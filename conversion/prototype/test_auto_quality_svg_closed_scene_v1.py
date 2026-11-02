import base64,copy,io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as E
import auto_quality_svg_closed_scene_v1 as profile
import svg_source_scene_dom_v1 as scene
import auto_quality_source_vector_v2 as prior
from svg_convert_v2 import build

ROOT=Path('/backup/shaoshitong/img2code_20261029')

@unittest.skipUnless(os.environ.get('IMG2CODE_SVG_SCENE_BROWSER_TESTS')=='1','Run real offline Chromium tests on HKUST')
class BrowserTests(unittest.TestCase):
    def fixture(self,source):
        from PIL import Image
        temporary=tempfile.TemporaryDirectory(prefix='svg-closed-test-',dir=ROOT/'conversion/prototype');self.addCleanup(temporary.cleanup);root=Path(temporary.name);clean=root/'clean';clean.mkdir();raw=source.encode();(clean/'source.svg').write_bytes(raw);buffer=io.BytesIO();Image.new('RGB',(120,100),'white').save(buffer,format='PNG');reference=buffer.getvalue();(clean/'reference.png').write_bytes(reference);record={'id':'synthetic','source_format':'svg','category':'diagram','original_source_code':'clean/source.svg','source_code_sha256':profile.sha(raw),'original_reference':'clean/reference.png','source_image_sha256':profile.sha(reference),'code_sha256':'0'*64}
        with patch.object(scene,'ROOT',root):dom=profile.capture_closed_scene(record)
        xml,stats=build(dom,120,100);record['code_sha256']=profile.sha(xml.encode());return root,record,dom,xml,stats
    def check(self,source):return self.fixture('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="100" viewBox="0 0 120 100">'+source+'</svg>')
    def test_path_encoded_basic_frame_is_supported_while_old_guard_refuses(self):
        root,record,dom,xml,stats=self.check('<path d="M10,10 H100 V70 H10 Z" fill="white" stroke="black"/><text x="20" y="40" font-family="Arial" font-size="12">AB</text>');self.assertFalse(prior._decorative_profile(dom)['ok']);result=profile.check_scene_coverage(dom,xml);self.assertTrue(result['supported'],result['failures']);self.assertTrue(result['ok'],result['failures'])
    def test_drop_path_wrong_control_color_matrix_and_extra_rotation_are_rejected(self):
        _,_,dom,xml,_=self.check('<path d="M10,10 H100 V70 H10 Z" fill="white" stroke="black"/><text x="20" y="40">AB</text>')
        for mode in ('drop','color','payload','geometry','rotation'):
            tree=E.fromstring(xml);cell=next(c for c in tree.iter('mxCell') if c.get('id')=='v1')
            if mode=='drop':next(p for p in tree.iter() if cell in list(p)).remove(cell)
            elif mode=='color':cell.set('style',cell.get('style').replace('fillColor=#ffffff','fillColor=#ff0000'))
            elif mode=='payload':cell.set('style',cell.get('style').replace('stencil(','stencil(bad'))
            elif mode=='geometry':cell.find('mxGeometry').set('x','11')
            else:cell.set('style',cell.get('style')+'rotation=90;')
            result=profile.check_scene_coverage(dom,E.tostring(tree,encoding='unicode'));self.assertFalse(result['ok'],mode)
    def test_extra_opaque_paint_and_reordered_occluding_source_shape_are_rejected(self):
        _,_,dom,xml,_=self.check('<path d="M10,10 H100 V70 H10 Z" fill="white"/><text x="20" y="40">AB</text>');tree=E.fromstring(xml);root=tree.find('.//root');shape=next(c for c in root if c.get('id')=='v1');root.remove(shape);root.append(shape);self.assertFalse(profile.check_scene_coverage(dom,E.tostring(tree,encoding='unicode'))['ok']);tree=E.fromstring(xml);extra=copy.deepcopy(next(c for c in tree.iter('mxCell') if c.get('id')=='v1'));extra.set('id','extra');tree.find('.//root').append(extra);self.assertFalse(profile.check_scene_coverage(dom,E.tostring(tree,encoding='unicode'))['ok'])
    def test_hidden_object_ancestor_locked_object_or_text_image_wrapper_rejected(self):
        _,_,dom,xml,_=self.check('<path d="M10,10 H100 V70 H10 Z" fill="white"/><text x="20" y="40">AB</text>')
        for mode in ('hidden','ancestor','locked','image_in_text'):
            tree=E.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')};text=next(c for c in cells.values() if c.get('value'))
            if mode=='hidden':text.set('visible','0')
            elif mode=='ancestor':cells['1'].set('visible','0')
            elif mode=='locked':text.set('style',text.get('style')+'movable=0;')
            else:text.set('value','<img src="data:image/png;base64,AAAA"/>'+text.get('value'))
            self.assertFalse(profile.check_scene_coverage(dom,E.tostring(tree,encoding='unicode'))['ok'],mode)
    def test_whole_reference_raster_replacing_native_stencil_rejected(self):
        _,_,dom,xml,_=self.check('<path d="M10,10 H100 V70 H10 Z" fill="white"/>');tree=E.fromstring(xml);cell=next(c for c in tree.iter('mxCell') if c.get('id')=='v1');cell.set('style','shape=image;image=data:image/png,AAAA;');result=profile.check_scene_coverage(dom,E.tostring(tree,encoding='unicode'));self.assertFalse(result['ok'])
    def test_native_extra_effects_offsets_labels_duplicate_ids_cannot_hide_behind_exact_stencil(self):
        _,_,dom,xml,_=self.check('<path d="M10,10 H100 V70 H10 Z" fill="white" stroke="black"/><text x="20" y="40">AB</text>')
        for mode in ('shadow','gradient','dashed','sketch','named_style','offset','relative','label','duplicate','text_opacity','font_size_markup'):
            tree=E.fromstring(xml);cell=next(c for c in tree.iter('mxCell') if c.get('id')=='v1');text=next(c for c in tree.iter('mxCell') if c.get('value'))
            if mode=='shadow':cell.set('style',cell.get('style').replace('shadow=0','shadow=1'))
            elif mode in ('gradient','dashed','sketch'):cell.set('style',cell.get('style')+{'gradient':'gradientColor=#ff0000;','dashed':'dashed=1;','sketch':'sketch=1;'}[mode])
            elif mode=='named_style':cell.set('style','someStyle;'+cell.get('style'))
            elif mode=='offset':E.SubElement(cell.find('mxGeometry'),'mxPoint',{'as':'offset','x':'30','y':'0'})
            elif mode=='relative':cell.find('mxGeometry').set('relative','1')
            elif mode=='label':cell.set('value','EXTRA')
            elif mode=='duplicate':tree.find('.//root').append(copy.deepcopy(cell))
            elif mode=='text_opacity':text.set('style',text.get('style')+'textOpacity=1;')
            else:text.set('value','<font size="7">AB</font>')
            self.assertFalse(profile.check_scene_coverage(dom,E.tostring(tree,encoding='unicode'))['ok'],mode)
    def test_marker_head_missing_side_or_floating_cannot_use_closed_scene_gate(self):
        source='<defs><marker id="head" viewBox="0 0 10 10" markerWidth="10" markerHeight="10" refX="10" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 Z"/></marker></defs><rect x="2" y="30" width="20" height="20"/><rect x="90" y="30" width="20" height="20"/><path d="M22,40 L90,40" fill="none" stroke="black" marker-end="url(#head)"/>'
        _,_,dom,xml,stats=self.check(source);self.assertGreater(stats['counts'].get('bound_edges',0),0)
        for mode in ('floating','missing','wrong_side'):
            tree=E.fromstring(xml)
            if mode=='missing':
                for cell in list(tree.iter('mxCell')):
                    if cell.get('id') in {o['id'] for o in dom['objects'] if o.get('markerOwner')}:next(p for p in tree.iter() if cell in list(p)).remove(cell)
            elif mode=='wrong_side':
                for cell in tree.iter('mxCell'):
                    if cell.get('edge')=='1':cell.set('style',cell.get('style')+'startArrow=block;endArrow=none;')
            result=profile.check_scene_coverage(dom,E.tostring(tree,encoding='unicode'));self.assertFalse(result['supported']);self.assertFalse(result['ok'])
    def test_unknown_closed_arrow_and_untyped_open_path_not_called_decoration(self):
        for source in ('<path d="M10,30 H50 V20 L80,40 L50,60 V50 H10 Z"/>','<path d="M10,10 C30,20 70,50 100,80" fill="none" stroke="black"/>'):
            _,_,dom,xml,_=self.check(source);result=profile.check_scene_coverage(dom,xml);self.assertFalse(result['supported']);self.assertFalse(result['ok'])
    def test_source_style_effects_not_silently_accepted(self):
        sources=['<path d="M10,10 H100 V70 H10 Z" fill="white" stroke="black" transform="scale(1.1,0.8)"/>','<path d="M10,10 H100 V70 H10 Z" fill="white" stroke="black" stroke-dasharray="3 2" stroke-dashoffset="2"/>','<g opacity=".5"><path d="M10,10 H100 V70 H10 Z" fill="red"/><rect x="20" y="20" width="20" height="20"/></g>','<path d="M10,10 H100 V70 H10 Z" fill="rgba(0,0,0,.5)"/>','<defs><clipPath id="c"><rect width="30" height="30"/></clipPath></defs><path d="M10,10 H100 V70 H10 Z" clip-path="url(#c)"/>']
        for source in sources:
            _,_,dom,xml,_=self.check(source);result=profile.check_scene_coverage(dom,xml);self.assertFalse(result['supported'],source);self.assertFalse(result['ok'])
    def test_viewport_css_clipping_and_three_dimensional_transform_are_not_ignored(self):
        for source in ('<style>svg{background:red}</style><rect x="10" y="10" width="40" height="40"/>','<rect x="-5" y="10" width="40" height="40"/>','<rect x="10" y="10" width="40" height="40" style="transform:perspective(200px) rotateY(30deg)"/>'):
            _,_,dom,xml,_=self.check(source);result=profile.check_scene_coverage(dom,xml);self.assertFalse(result['supported'],source);self.assertFalse(result['ok'])
    def test_resource_gate_error_cannot_leave_success_true(self):
        root,record,dom,xml,_=self.check('<path d="M10,10 H100 V70 H10 Z"/>')
        with patch.object(scene,'ROOT',root),patch.object(prior,'R',root),patch.object(profile,'R',root),patch('auto_quality_common.resource_checks',side_effect=ValueError('whole_reference_image_wrapper')):
            result=profile.check_svg_profile(record,xml);self.assertFalse(result['ok']);self.assertTrue(result['failures'])
    def test_font_glyph_use_and_closed_collection_roles_are_supported(self):
        source='<defs><path id="DejaVuSans-41" d="M0,0 L8,10 L10,0 L7,4 L3,4 Z"/></defs><g id="text_1"><use href="#DejaVuSans-41" x="10" y="20"/></g><g id="PathCollection_1"><path d="M60,20 L70,35 L50,35 Z"/></g>'
        _,_,dom,xml,_=self.check(source);result=profile.check_scene_coverage(dom,xml);self.assertTrue(result['ok'],result['failures'])
    def test_unused_warnings_do_not_replace_capture_hash_or_hide_current_revision(self):
        root,record,dom,xml,_=self.check('<path d="M10,10 H100 V70 H10 Z"/>')
        with patch.object(scene,'ROOT',root),patch.object(prior,'R',root),patch.object(profile,'R',root):
            result=profile.check_svg_profile(record,xml);self.assertTrue(result['ok'],result['failures']);bad={**record,'code_sha256':'f'*64};self.assertFalse(profile.check_svg_profile(bad,xml)['ok']);(root/'clean/source.svg').write_bytes(b'changed');self.assertFalse(profile.check_svg_profile(record,xml)['ok'])

if __name__=='__main__':unittest.main()
