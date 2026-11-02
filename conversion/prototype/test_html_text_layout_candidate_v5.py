import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from importlib.util import find_spec
from unittest.mock import patch
import xml.etree.ElementTree as E
import html_actual_text_alignment as glyph
import html_text_layout_candidate_v5 as candidate
import html_text_layout_registration_v5 as registration
import auto_quality_source_vector_v2 as source
from test_html_text_whitespace_advance_v5 import fixture

@unittest.skipUnless(find_spec('skimage') is not None and find_spec('pyarrow') is not None,'Run full isolated builder tests on HKUST3')
class BuilderRollbackTests(unittest.TestCase):
    def run_case(self,root,kerning=False,metric_revert=False):
        from PIL import Image
        import native_worker
        import auto_quality_common as common
        root=Path(root);clean=root/'clean';clean.mkdir();image=io.BytesIO();Image.new('RGB',(64,64),'white').save(image,format='PNG');png=image.getvalue();code=b'<html>A B C D</html>';(clean/'source.html').write_bytes(code);(clean/'reference.png').write_bytes(png);(clean/'old.png').write_bytes(png)
        dom,before,part=fixture();second=copy.deepcopy(dom['objects'][0]);second.update(id=2,text='C D',y=32)
        for c in second['actualSourceGlyphs']:c['y']=32;c['text']={'A':'C','B':'D'}.get(c['text'],c['text']);c['raw']={'A':'C','B':'D'}.get(c['raw'],c['raw'])
        dom['objects'].append(second);dom['_source_paint_order']={'1':0,'2':1};second_native=copy.deepcopy(before['actual_text_positions'][0]);second_native['cell']='3'
        for c in second_native['runs'][0]['chars']:c['y']=32;c['text']={'A':'C','B':'D'}.get(c['text'],c['text'])
        before['actual_text_positions'].append(second_native);second_fonts=copy.deepcopy(before['actual_platform_font_usage'][0]);second_fonts['cell']='3';before['actual_platform_font_usage'].append(second_fonts)
        tree=E.fromstring('<mxfile><diagram><mxGraphModel pageWidth="64" pageHeight="64"><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>');graph=tree.find('.//root');a=E.fromstring(part).find('mxCell');a.set('style','shape=text;fontSize=10;fontColor=#000000;opacity=100;');graph.append(a);b=copy.deepcopy(a);b.set('id','3');b.set('value','C D');b.find('mxGeometry').set('y','32');graph.append(b);xml=E.tostring(tree,encoding='unicode');(clean/'old.drawio').write_text(xml)
        record={'id':'fixture','source_format':'html','category':'poster','code_file':'clean/old.drawio','code_sha256':glyph.sha(xml.encode()),'image_file':'clean/old.png','image_sha256':glyph.sha(png),'original_source_code':'clean/source.html','source_code_sha256':glyph.sha(code),'original_reference':'clean/reference.png','source_image_sha256':glyph.sha(png)};capture={'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'viewport':[64,64],'fresh_source_dom_sha256':glyph.sha(json.dumps(dom,sort_keys=True).encode()),'fresh_source_png_sha256':glyph.sha(png)}
        def fake_render(current,*args):
            info=copy.deepcopy(before);cells={c.get('id'):c for c in E.fromstring(current).iter('mxCell')}
            for row in info['actual_text_positions']:
                if 'word-spacing:4px' in cells[row['cell']].get('value',''):
                    chars=row['runs'][0]['chars'];chars[1]['width']+=4;chars[2]['x']+=4
                    if kerning and row['cell']=='2':chars[2]['width']+=.2
            info.update(selected_image='declared_first_page',actual_clip_boxes=[]);return {'ok':True,'png':png,'native_render':info}
        actual_registration=registration.registration_record
        def root_registration(record,reference,xml,*args,**kwargs):return actual_registration(record,reference,xml,root)
        def metrics(reference,before_png,after_png,record,offset,windows):return {key:{'box':box,'before_ssim':1.,'after_ssim':0.5 if key=='2' else 1.,'nonworsening':key!='2'} for key,box in windows.items()}
        with patch.object(candidate,'R',root),patch.object(candidate,'W',root/'conversion'),patch.object(source,'R',root),patch.object(registration,'_base_registration',side_effect=lambda record,reference,xml,root:(record,None)),patch.object(registration,'registration_record',side_effect=root_registration),patch.object(glyph,'capture_source',return_value=(dom,{},png,capture)),patch.object(native_worker.native,'native_job',side_effect=fake_render),patch.object(common,'resource_checks',return_value={'verified_files':[]}),patch.object(common,'structure_checks',return_value={'ok':True}):
            if metric_revert:
                with patch.object(glyph,'same_crop_metrics',side_effect=metrics):result=candidate.build(record,'isolated-builder',{})
            else:result=candidate.build(record,'isolated-builder',{})
        return result,xml
    def test_actual_kerning_failure_reverts_only_that_object_and_replays_rest(self):
        with tempfile.TemporaryDirectory() as root:
            (work,out,proof),old_xml=self.run_case(root,kerning=True);self.assertEqual(proof['changed_cells'],['3']);self.assertEqual(proof['exact_object_rollbacks'][0]['reverted_cells'],['2']);self.assertIn('kerning',proof['exact_object_rollbacks'][0]['reason']);new=E.fromstring((work/'candidate.drawio').read_text());old=E.fromstring(old_xml);self.assertEqual(E.canonicalize(E.tostring(next(c for c in old.iter('mxCell') if c.get('id')=='2'),encoding='unicode')),E.canonicalize(E.tostring(next(c for c in new.iter('mxCell') if c.get('id')=='2'),encoding='unicode')));self.assertFalse(proof['accepted']);self.assertFalse(proof['published']);self.assertFalse((Path(root)/out['code_file']).exists())
    def test_original_crop_regression_reverts_exact_object_without_parameter_search(self):
        with tempfile.TemporaryDirectory() as root:
            (work,out,proof),_=self.run_case(root,metric_revert=True);self.assertEqual(proof['changed_cells'],['3']);self.assertEqual(proof['exact_object_rollbacks'][0]['reverted_cells'],['2']);self.assertEqual(proof['steps'][0]['proof']['changes'][0]['targets'][0]['extra_advance'],4)

if __name__=='__main__':unittest.main()
