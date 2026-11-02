"""Synthetic full-proof replay, source-profile reuse, corruption and rollback tests."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from importlib.util import find_spec
from unittest.mock import patch
import xml.etree.ElementTree as E
import html_text_layout_registration_v5 as registration
import html_text_whitespace_advance_v5 as spaces
import html_actual_text_clip_alignment_v4 as clip
import html_actual_text_alignment as glyph
from test_html_text_whitespace_advance_v5 import fixture as space_fixture


def synthetic(root,with_clip=True):
    from PIL import Image
    root=Path(root);work=root/registration.OWNER/'fixture';work.mkdir(parents=True);clean=root/'clean';clean.mkdir();source=b'<html>A B CD</html>';image=io.BytesIO();Image.new('RGB',(32,32),'white').save(image,format='PNG');png=image.getvalue();(clean/'source.html').write_bytes(source);(clean/'reference.png').write_bytes(png)
    dom,before,xml=space_fixture();obj=dom['objects'][0];obj['actualSourceGlyphs']=[{**c,'rectCount':1} for c in obj['actualSourceGlyphs']];dom['_source_paint_order']={'1':0}
    root_xml=E.fromstring('<mxfile><diagram><mxGraphModel pageWidth="32" pageHeight="32"><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>');graph=root_xml.find('.//root');spacecell=E.fromstring(xml).find('mxCell');spacecell.set('style','shape=text;fontSize=10;fontColor=#000000;opacity=100;');graph.append(spacecell)
    if with_clip:
        obj={'id':2,'type':'text','text':'CD','x':10,'y':24.25,'w':10,'h':10,'fontSize':10,'color':{'color':'#000000','opacity':1},'opacity':1,'actualSourceGlyphs':[{'text':text,'raw':text,'x':10+index*5,'y':24.25,'width':5,'height':10,'rectCount':1} for index,text in enumerate('CD')],'actualSourceCss':{'fontSize':10},'actualSourcePhysicalFonts':{'fonts':[{'postScriptName':'FixtureFace','glyphCount':2}],'basis':'actual_text_node'},'sourceClip':{'partial':True,'unmodeled':[],'chain':[{'left':0,'top':0,'right':32,'bottom':31,'clipX':True,'clipY':True,'radius':['0px']*4}]}};dom['objects'].append(obj);dom['_source_paint_order']['2']=1
        cell=E.SubElement(graph,'mxCell',{'id':'3','parent':'1','vertex':'1','value':'<span style="clip-path:inset(-24.5px -12px 3.5px -10px);">CD</span>','style':'shape=text;fontSize=10;fontColor=#000000;opacity=100;'});E.SubElement(cell,'mxGeometry',{'x':'10','y':'24.25','width':'10','height':'10'});before['actual_text_positions'].append({'cell':'3','runs':[{'font':'10px Embedded','chars':[{'text':text,'x':10+index*5,'y':24.5,'width':5,'height':10} for index,text in enumerate('CD')]}]});before['actual_platform_font_usage'].append({'cell':'3','fonts':[{'postScriptName':'FixtureFace','glyphCount':2,'isCustomFont':True}]});before['actual_clip_boxes']=[{'cell':'3','clips':[{'x':10,'y':24.5,'width':10,'height':10,'clipPath':'inset(-24.5px -12px 3.5px -10px)','text':'CD','fragments':[{'x':10,'y':24.5,'width':10,'height':10}]}]}]
    xml=E.tostring(root_xml,encoding='unicode');old={'id':'fixture','source_format':'html','category':'poster','source_code_sha256':glyph.sha(source),'source_image_sha256':glyph.sha(png),'original_source_code':'clean/source.html','original_reference':'clean/reference.png','code_sha256':glyph.sha(xml.encode()),'image_sha256':glyph.sha(png)}
    def save(name,blob):path=work/name;path.write_bytes(blob);return {'file':str(path.relative_to(root)),'sha256':glyph.sha(blob)}
    def js(name,value):return save(name,json.dumps(value,sort_keys=True).encode())
    capture={'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'viewport':[32,32],'fresh_source_dom_sha256':glyph.sha(json.dumps(dom,sort_keys=True).encode()),'fresh_source_png_sha256':glyph.sha(png)}
    files={'previous_record':js('previous_record.json',old),'before_xml':save('before.drawio',xml.encode()),'before_png':save('before.png',png),'baseline_fresh_png':save('baseline.png',png),'baseline_render':js('baseline.json',before),'source_dom':js('dom.json',dom),'source_capture':js('capture.json',capture),'source_png':save('source.png',png)}
    spaced,spaceproof=spaces.propose(xml,spaces.plan(dom,before,xml));after_spaces=copy.deepcopy(before);chars=after_spaces['actual_text_positions'][0]['runs'][0]['chars'];chars[1]['width']+=4;chars[2]['x']+=4
    space_xml=save('spaces.drawio',spaced.encode());space_info=js('spaces.json',after_spaces);space_png=save('spaces.png',png);steps=[{'kind':'space_advance_v5','proof':spaceproof,'before_xml':files['before_xml'],'before_render':files['baseline_render'],'after_xml':space_xml,'after_render':space_info,'after_png':space_png,'pixel_groups':[]}];current_xml,current_info=spaced,after_spaces
    if with_clip:
        current_xml,clipproof=clip.propose_clip_locked(spaced,dom,after_spaces,[32,32]);current_info=copy.deepcopy(after_spaces)
        for char in current_info['actual_text_positions'][1]['runs'][0]['chars']:char['y']=24.25
        groups=[]
        for index,group in enumerate(clip.disjoint_clip_groups(clipproof,current_info)):
            unclipped,background=clip.diagnostic_variants(current_xml,{row['cell'] for row in group});groups.append({'group':group,'unclipped_xml':save('unclipped.drawio',unclipped.encode()),'unclipped_png':save('unclipped.png',png),'background_xml':save('background.drawio',background.encode()),'background_png':save('background.png',png)})
        steps.append({'kind':'clip_locked_v4','proof':clipproof,'before_xml':space_xml,'before_render':space_info,'after_xml':save('clipped.drawio',current_xml.encode()),'after_render':js('clipped.json',current_info),'after_png':save('clipped.png',png),'pixel_groups':groups})
    files.update(current_xml=save('current.drawio',current_xml.encode()),current_png=save('current.png',png),current_render=js('current.json',current_info));changed=['2','3'] if with_clip else ['2'];windows=glyph.reference_windows(before,current_info,set(changed),[32,32]);local=glyph.same_crop_metrics(png,png,png,old,(0,0),windows)
    proof={'version':5,'policy':'synthetic-v5','id':'fixture','accepted':False,'input_code_sha256':old['code_sha256'],'input_image_sha256':old['image_sha256'],'output_code_sha256':glyph.sha(current_xml.encode()),'output_image_sha256':glyph.sha(png),'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'files':files,'steps':steps,'source_dom_offset':[0,0],'source_viewport':[32,32],'reference_offset':[0,0],'changed_cells':changed,'reference_windows':windows,'local_reference_validation':local};entry=js('evidence.json',proof);link={key:proof[key] for key in ('version','policy','input_code_sha256','input_image_sha256','output_code_sha256','output_image_sha256','source_code_sha256','source_image_sha256','changed_cells')};link.update(proof=entry['file'],proof_sha256=entry['sha256'],previous_record=files['previous_record']['file'],previous_record_sha256=files['previous_record']['sha256']);record={**old,'code_sha256':glyph.sha(current_xml.encode()),registration.FIELD:link};return record,png,current_xml,proof,work/'evidence.json',dom,current_info


@unittest.skipUnless(find_spec('skimage') is not None,'Remote verification runtime')
class ReplayTests(unittest.TestCase):
    def resolver(self,record,reference,xml,root):return record,None
    def write(self,record,proof,path):path.write_text(json.dumps(proof));record[registration.FIELD]['proof_sha256']=glyph.sha(path.read_bytes())
    def test_composed_whitespace_then_clip_replays_with_identity_registration(self):
        with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
            record,reference,xml,*_=synthetic(root);verified,contract=registration.registration_record(record,reference,xml,root);self.assertIsNone(contract);scope=verified['_verified_html_text_layout'];self.assertEqual(scope['whitespace_cells'],['2']);self.assertEqual(scope['clip_cells'],['3']);self.assertEqual(scope['combined_glyph_cells'],['3']);self.assertTrue(scope['original_fixed_crops_nonworsening_recomputed'])
    def test_optional_prior_canvas_font_and_glyph_context_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            record,reference,xml,*_=synthetic(root,with_clip=False)
            def resolver(record,reference,xml,root):return record,{'reference_page':[32,32],'output_page':[32,32],'original_page_offset':[0,0],'font_only_delta_verified':True,'glyph_alignment_delta_verified':True}
            with patch.object(registration,'_base_registration',side_effect=resolver):verified,contract=registration.registration_record(record,reference,xml,root)
            self.assertTrue(contract['font_only_delta_verified']);self.assertTrue(contract['glyph_alignment_delta_verified']);self.assertTrue(contract['html_text_layout_delta_verified'])
    def test_graph_text_font_style_page_or_unrelated_geometry_damage_rejected(self):
        for replace in [('width="18"','width="19"'),('fontSize=10','fontSize=11'),('pageWidth="32"','pageWidth="33"'),('word-spacing:4px','word-spacing:5px')]:
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,reference,xml,proof,path,*_=synthetic(root);bad=xml.replace(*replace);self.assertNotEqual(xml,bad);digest=glyph.sha(bad.encode());record['code_sha256']=digest;record[registration.FIELD]['output_code_sha256']=digest;proof['output_code_sha256']=digest;entry=proof['files']['current_xml'];(Path(root)/entry['file']).write_text(bad);entry['sha256']=digest;self.write(record,proof,path)
                with self.assertRaises(AssertionError):registration.registration_record(record,reference,bad,root)
    def test_original_source_font_canvas_and_archive_metadata_cannot_be_relabelled(self):
        for key,value in [('previous_candidate_archive','conversion/auto_quality_html_text_layout_v5/not-a-Harness-origin'),('native_embedded_fonts',[{'file':'other-font'}]),('source_pair_sha256','other-pair'),('html_actual_text_alignment',{'version':3}),('native_canvas_contract',{'offset':[1,1]})]:
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,reference,xml,*_=synthetic(root);record[key]=value
                with self.assertRaises(AssertionError):registration.registration_record(record,reference,xml,root)
    def test_step_order_scope_delta_or_glyph_damage_rejected(self):
        for mode in ('order','scope','delta','glyph'):
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,reference,xml,proof,path,*_=synthetic(root)
                if mode=='order':proof['steps'].reverse()
                elif mode=='scope':proof['changed_cells']=['2'];record[registration.FIELD]['changed_cells']=['2']
                elif mode=='delta':proof['steps'][0]['proof']['changes'][0]['targets'][0]['extra_advance']=5
                else:
                    entry=proof['steps'][0]['after_render'];target=Path(root)/entry['file'];info=json.loads(target.read_text());info['actual_text_positions'][0]['runs'][0]['chars'][2]['x']+=.2;target.write_text(json.dumps(info));entry['sha256']=glyph.sha(target.read_bytes())
                self.write(record,proof,path)
                with self.assertRaises(AssertionError):registration.registration_record(record,reference,xml,root)
    def test_wrong_pixel_mask_diagnostic_or_missing_group_rejected(self):
        for mode in ('pixel','diagnostic','missing'):
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,reference,xml,proof,path,*_=synthetic(root);group=proof['steps'][1]['pixel_groups'][0]
                if mode=='missing':proof['steps'][1]['pixel_groups']=[]
                elif mode=='diagnostic':entry=group['unclipped_xml'];target=Path(root)/entry['file'];target.write_text(target.read_text().replace('clip-path:none','clip-path:inset(0px)'));entry['sha256']=glyph.sha(target.read_bytes())
                else:
                    from PIL import Image,ImageDraw
                    target=Path(root)/group['unclipped_png']['file'];image=Image.open(target).convert('RGB');ImageDraw.Draw(image).point((12,26),fill='black');image.save(target);group['unclipped_png']['sha256']=glyph.sha(target.read_bytes())
                self.write(record,proof,path)
                with self.assertRaises(AssertionError):registration.registration_record(record,reference,xml,root)
    def test_hash_fake_offset_current_physical_font_or_crop_damage_rejected(self):
        for mode in ('hash','offset','font','crop','viewport'):
            with tempfile.TemporaryDirectory() as root,patch.object(registration,'_base_registration',side_effect=self.resolver):
                record,reference,xml,proof,path,*_=synthetic(root)
                if mode=='hash':(Path(root)/proof['files']['source_dom']['file']).write_bytes(b'damage')
                elif mode=='offset':proof['reference_offset']=[1,0]
                elif mode=='viewport':proof['source_viewport']=[33,32]
                elif mode=='crop':proof['reference_windows']['2'][0]+=1
                else:
                    entry=proof['steps'][1]['after_render'];target=Path(root)/entry['file'];info=json.loads(target.read_text());info['actual_platform_font_usage'][0]['fonts'][0]['isCustomFont']=False;target.write_text(json.dumps(info));entry['sha256']=glyph.sha(target.read_bytes())
                self.write(record,proof,path)
                with self.assertRaises(AssertionError):registration.registration_record(record,reference,xml,root)

if __name__=='__main__':unittest.main()
