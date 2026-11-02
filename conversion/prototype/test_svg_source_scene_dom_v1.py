"""Synthetic-only source extraction probes. Browser/media fixtures run on HKUST."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import svg_source_scene_dom_v1 as scene


def shape(path,fill='black',stroke='none'):
    return {'id':'v1','tag':'path','type':'shape','d':path,'attrs':{},'matrix':[1,0,0,1,0,0],'style':{'fill':fill,'stroke':stroke,'strokeWidth':1,'fillOpacity':1,'strokeOpacity':1,'opacity':1},'sceneGeometry':{}}


class PureMetadataTests(unittest.TestCase):
    def test_authoritative_closed_and_open_subpaths(self):
        dom={'objects':[shape('M0 0L10 0L10 10Z M20 0L30 0',stroke='black')],'issues':[]}
        out=scene.enrich_scene(dom);meta=out['objects'][0]['sceneGeometry']['topology'];self.assertEqual(meta['closed_subpaths'],1);self.assertEqual(meta['open_subpaths'],1);self.assertTrue(meta['has_open_stroke']);self.assertEqual(meta['coordinate_space'],'source_local')
        out=scene.enrich_scene({'objects':[shape('M0 0L10 0L10 10')],'issues':[]});meta=out['objects'][0]['sceneGeometry']['topology'];self.assertFalse(meta['has_open_stroke']);self.assertTrue(meta['fill_implicitly_closes_open_subpaths']);self.assertFalse(meta['all_subpaths_explicitly_closed'])
    def test_invalid_path_is_an_explicit_issue(self):
        dom=scene.enrich_scene({'objects':[shape('M1 2 C')],'issues':[]});self.assertTrue(dom['objects'][0]['sceneGeometry']['topology'].get('error'));self.assertTrue(any(i['reason']=='scene_source_path_parse_failed' for i in dom['issues']))


@unittest.skipUnless(os.environ.get('IMG2CODE_SCENE_BROWSER_TESTS')=='1','Run synthetic browser fixtures only on HKUST')
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner=Path('/backup/shaoshitong/img2code_20261029/conversion/prototype/svg_source_scene_dom_v1_tests');cls.owner.mkdir(parents=True,exist_ok=True)
    @classmethod
    def tearDownClass(cls):scene.close_worker_runtime()
    def fixture(self,folder,svg,width=320,height=180):
        from PIL import Image
        root=Path(folder);clean=root/'clean';clean.mkdir();code=svg.encode();image=io.BytesIO();Image.new('RGB',(width,height),'white').save(image,format='PNG');png=image.getvalue();(clean/'source.svg').write_bytes(code);(clean/'reference.png').write_bytes(png)
        return {'id':'synthetic','source_format':'svg','code_sha256':'f'*64,'original_source_code':'clean/source.svg','source_code_sha256':scene.sha(code),'original_reference':'clean/reference.png','source_image_sha256':scene.sha(png)}
    def capture(self,svg,width=320,height=180):
        with tempfile.TemporaryDirectory(prefix='case-',dir=self.owner) as folder:
            record=self.fixture(folder,svg,width,height)
            with patch.object(scene,'ROOT',Path(folder)):return scene.capture_scene(record)
    def legacy(self,svg,width=320,height=180):
        browser=scene._browser();context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block');context.route('**/*',lambda r:r.abort())
        try:
            page=context.new_page();page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg)
            page.evaluate("([w,h])=>{const s=document.querySelector('svg');if(!s.viewBox.baseVal.width)s.setAttribute('viewBox',`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}",[width,height]);page.evaluate('document.fonts.ready')
            return page.evaluate(Path('/backup/shaoshitong/img2code_20261029/conversion/scripts/svg_dom_v6.js').read_text())
        finally:context.close()
    def rich_svg(self,overflow='visible'):
        return '''<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180"><defs>
<path id="glyph0-1" d="M0 0H10V10H0Z"/><marker id="head" markerWidth="10" markerHeight="10" refX="10" refY="5" markerUnits="userSpaceOnUse" orient="auto-start-reverse" overflow="'''+overflow+'''" viewBox="0 0 10 10"><path id="arrow-shape" d="M0 0L10 5L0 10Z" fill="context-stroke"/></marker></defs>
<g id="PathCollection_1"><use href="#glyph0-1" x="20" y="20"/></g><path id="ordinary-open" d="M10 60L80 65L110 60" fill="none" stroke="blue"/><path id="two-sided" d="M140 60L260 60" fill="none" stroke="black" marker-start="url(#head)" marker-end="url(#head)"/><text x="12" y="120">A😀B<tspan>中</tspan>C</text></svg>'''
    def test_object_and_utf16_text_ids_match_v6_exactly(self):
        svg=self.rich_svg();old=self.legacy(svg);new=self.capture(svg)
        self.assertEqual([o['id'] for o in old['objects']],[o['id'] for o in new['objects']]);self.assertEqual(new['sceneMetadata']['objectSerialFinal'],max(int(o['id'].split('t')[0][1:]) for o in old['objects']))
        self.assertEqual([(o['id'],o.get('text')) for o in old['objects'] if o['type']=='text'],[(o['id'],o.get('text')) for o in new['objects'] if o['type']=='text'])
        # Additive extraction preserves existing edge/marker sampling exactly.
        a={o['id']:o for o in old['objects']};b={o['id']:o for o in new['objects']}
        for key in a:
            if a[key].get('sampledPoints') is not None:self.assertEqual(a[key]['sampledPoints'],b[key]['sampledPoints'])
        self.assertTrue(new['sceneCapture']['sourcePayloadHashesRecheckedAfterCapture']);self.assertTrue(new['sceneCapture']['completeOfflineSource']);self.assertEqual(new['sceneCapture']['extractorSha256'],scene.sha(scene.EXTRACTOR.read_bytes()))
    def test_marker_side_owner_and_viewport_are_explicit(self):
        dom=self.capture(self.rich_svg('hidden'));owner=next(o for o in dom['objects'] if o.get('sourceId')=='two-sided');markers=[o for o in dom['objects'] if o.get('markerOwner')==owner['id']];self.assertEqual({o['markerSide'] for o in markers},{'start','end'})
        for obj in markers:
            context=dom['sceneMetadata']['markerContexts'][obj['markerContext']];self.assertEqual(context['owner'],owner['id']);self.assertEqual(context['side'],obj['markerSide']);self.assertEqual(context['markerDefinitionId'],'head');self.assertEqual(context['viewport'],{'width':10,'height':10});self.assertEqual(context['refX']['value'],10);self.assertEqual(context['refY']['value'],5);self.assertEqual(context['markerUnits'],'userSpaceOnUse');self.assertEqual(context['orient'],'auto-start-reverse');self.assertFalse(context['viewportClipProven']);self.assertFalse(context['syntheticCloneIsActualMarkerPaint']);self.assertEqual(len(context['viewportScreenPolygon']),4)
        self.assertTrue(any(i['reason']=='scene_marker_viewport_clip_unproven' for i in dom['issues']))
    def test_regular_open_path_and_capped_samples_are_not_discarded(self):
        dom=self.capture('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><path id="long" d="M0 20L100000 20" fill="none" stroke="black"/><path id="closed" d="M5 5H20V15H5Z"/></svg>');long=next(o for o in dom['objects'] if o['sourceId']=='long');meta=long['sceneGeometry'];self.assertEqual(len(long['sampledPoints']),3001);self.assertTrue(meta['samplingCapReached']);self.assertGreater(meta['arcStepDeviceUpperBound'],2);self.assertTrue(meta['topology']['has_open_stroke']);closed=next(o for o in dom['objects'] if o['sourceId']=='closed');self.assertTrue(closed['sceneGeometry']['topology']['all_subpaths_explicitly_closed'])
    def test_styles_ancestry_roles_and_use_opacity_context(self):
        svg='''<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><defs><path id="DejaVuSans-41" d="M0 0H10V10H0Z"/></defs><g id="text_1" opacity="0.5"><use href="#DejaVuSans-41" x="20" y="30"/></g><g class="node" id="n"><path id="styled" d="M100 20H140V60H100Z" fill="none" stroke="black" stroke-width="3" stroke-dasharray="4 2" stroke-dashoffset="2" stroke-miterlimit="7" stroke-linecap="round" stroke-linejoin="bevel" vector-effect="non-scaling-stroke"/></g></svg>'''
        dom=self.capture(svg);styled=next(o for o in dom['objects'] if o['sourceId']=='styled');css=styled['sceneComputedCss'];self.assertEqual(css['vectorEffect'],'non-scaling-stroke');self.assertEqual(css['strokeDashoffset'],'2px');self.assertEqual(css['strokeMiterlimit'],'7');self.assertTrue(any(r['role']=='graphviz_node' for r in styled['sceneGroupRoles']))
        glyph=next(o for o in dom['objects'] if o['sourceId']=='DejaVuSans-41');roles={r['role'] for r in glyph['sceneGroupRoles']};self.assertIn('font_glyph_definition_hint',roles);self.assertIn('matplotlib_text_hint',roles);context=dom['sceneMetadata']['useContexts'][glyph['sceneUseContexts'][0]];self.assertEqual(context['href'],'#DejaVuSans-41');self.assertEqual(context['callOpacityProduct'],.5);self.assertEqual(context['cloneOpacityProduct'],1);self.assertIn('ancestor_or_call_opacity_not_forwarded',context['risks']);self.assertTrue(any(i['reason']=='scene_use_opacity_context_changed' for i in dom['issues']))
    def test_paint_order_rgba_alpha_and_ancestor_blend_metadata(self):
        dom=self.capture('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><g id="blend" style="mix-blend-mode:multiply;isolation:isolate;opacity:.5"><path id="alpha" d="M0 0H20V20H0Z" fill="rgba(255,0,0,.25)" fill-opacity=".8" stroke="rgba(0,0,0,.75)" stroke-opacity=".6" opacity=".7" style="paint-order:stroke fill markers"/></g></svg>');obj=next(o for o in dom['objects'] if o['sourceId']=='alpha');css=obj['sceneComputedCss'];self.assertIn('stroke',css['paintOrder']);self.assertEqual(css['fillColorAlpha'],.25);self.assertEqual(css['strokeColorAlpha'],.75);self.assertEqual(float(css['fillOpacity']),.8);self.assertEqual(float(css['strokeOpacity']),.6);self.assertEqual(float(css['opacity']),.7);ancestor=next(dom['sceneMetadata']['ancestors'][ref] for ref in obj['sceneAncestry'] if dom['sceneMetadata']['ancestors'][ref]['id']=='blend');self.assertEqual(ancestor['mixBlendMode'],'multiply');self.assertEqual(ancestor['isolation'],'isolate');self.assertEqual(ancestor['opacity'],.5)
    def test_raster_aspect_and_reflection_metadata(self):
        from PIL import Image
        output=io.BytesIO();Image.new('RGB',(1,2),'black').save(output,format='PNG');uri='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode();svg='<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><image id="asset" href="'+uri+'" x="0" y="0" width="40" height="10" transform="matrix(-1 0 0 1 100 20)"/></svg>';dom=self.capture(svg);image=next(o for o in dom['objects'] if o['type']=='image');meta=image['sceneImage'];self.assertEqual(meta['intrinsic_size'],[1,2]);self.assertEqual(meta['preserveAspectRatio'],'xMidYMid meet');self.assertTrue(meta['reflection']);self.assertTrue(meta['flipX']);self.assertFalse(meta['intrinsic_ratio_matches_viewport']);self.assertTrue(any(i['reason']=='scene_image_aspect_mapping_unproven' for i in dom['issues']))
    def test_external_resources_are_blocked_and_incomplete_is_explicit(self):
        dom=self.capture('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><image href="https://example.invalid/never-fetch.png" width="100" height="100"/></svg>');self.assertFalse(dom['sceneCapture']['completeOfflineSource']);self.assertIn('https://example.invalid/never-fetch.png',dom['sceneCapture']['blockedResources']);self.assertTrue(any(i['reason']=='scene_external_resources_blocked' for i in dom['issues']))
    def test_hash_recheck_clean_containment_and_concurrent_revision_guard(self):
        with tempfile.TemporaryDirectory(prefix='hash-',dir=self.owner) as directory:
            root=Path(directory);record=self.fixture(root,'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="10" height="10"/></svg>')
            with patch.object(scene,'ROOT',root):
                bad={**record,'source_code_sha256':'0'*64}
                with self.assertRaises(scene.SceneCaptureError):scene.capture_scene(bad)
                outside=root/'outside.svg';outside.write_text('outside');link=root/'clean/link.svg';link.symlink_to(outside)
                with self.assertRaises(scene.SceneCaptureError):scene.capture_scene({**record,'original_source_code':'clean/link.svg'})
                checked=scene._checked_clean;count=[0]
                def tamper(relative,digest):
                    count[0]+=1
                    if count[0]==3:(root/'clean/source.svg').write_bytes(b'changed during capture')
                    return checked(relative,digest)
                with patch.object(scene,'_checked_clean',side_effect=tamper):
                    with self.assertRaises(scene.SceneCaptureError):scene.capture_scene(record)

if __name__=='__main__':unittest.main()
