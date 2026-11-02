"""Actual frozen bridge schema; native jobs are mocked, never rendered."""
import copy,hashlib,json,os
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import clip_canvas_render_v4b as bridge
import visual_failure_clip_evidence_v1 as reader
import struct,zlib
def png(width=20,height=10):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\xff\xff'*width)*height))+chunk(b'IEND',b'')


def native(manifest,strict=False):
    info={'selected_image':'declared_first_page','output_size':[20,10],'canvas':[20,10],
          'scale':1,'translate':[0,0],'content_outside_declared_canvas':False,'native_graph_bounds_outside_declared_canvas':False,
          'runtime_cache_manifest_sha256':bridge.sha(manifest.read_bytes()),'runtime_cache_id':'exact-runtime',
          'viewer_bundle_sha256':'a'*64,'runtime_cache_provenance':{'version':1,'commit':'pinned'},
          'actual_platform_font_usage':[{'cell':'2','selectors':['#temporary_clip_selector'],'fonts':[{'postScriptName':'PS','familyName':'Face','isCustomFont':True,'glyphCount':1}]}],
          'actual_text_positions':[{'cell':'2','runs':[{'text':'x','font':'10px Face','fontKerning':'auto','fontFeatureSettings':'normal','letterSpacing':'normal','lineHeight':'normal','chars':[{'text':'x','x':1,'y':2,'width':3,'height':4}]}]}],
          'actual_clip_boxes':[{'cell':'2','clips':[{'clipPath':'inset(0px)','text':'x'}]}]}
    if strict:
        info.pop('actual_clip_boxes');info['actual_platform_font_usage'][0]['selectors']=['#a_different_temporary_selector']
        info['probe_includes_actual_dom_paint_bounds']=True
        info['outside_page_pixel_audit']={'padded_native_render_size':[84,74],'offset':[32,32],'nonwhite_outside_pixels':0,'white_threshold':255,'minimum_probe_margin':32,'audit_always_performed':True}
    return {'ok':True,'png':png(),'native_render':info,'native_selected':True,'seconds':0.1}

class EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.owned=self.root/'conversion/prototype/evidence_fixture/case';self.owned.mkdir(parents=True);self.paths={k:self.root/v for k,v in reader.PIN_PATHS.items()};self.adapter_source=Path(bridge.__file__).read_bytes();self.gate_source=Path(bridge.__file__).with_name('strict_canvas_gate.py').read_bytes()
  for key,path in self.paths.items():
   path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.adapter_source if key=='adapter' else self.gate_source if key=='strict_canvas_gate' else b'{"runtime":"pinned"}' if key=='runtime_manifest' else ('frozen_'+key).encode())
  self.clip=native(self.paths['runtime_manifest']);self.strict=native(self.paths['runtime_manifest'],True);self.xml='<mxfile/>';self.code=reader.sha(self.xml.encode());self.report=None;self.build()
 def build(self,nonclip=False,canonical=False):
  settings={'R':self.root,'W':self.root/'conversion','CLIP_RENDERER':self.paths['clip_renderer'],'STRICT_RENDERER':self.paths['strict_renderer'],'OWNER':'conversion/clip_canvas_render_v4b' if canonical else str((self.owned/'clip_canvas_evidence').relative_to(self.root)),'__file__':str(self.paths['adapter'])};patches=[patch.object(bridge,k,v) for k,v in settings.items()]
  for p in patches:p.start()
  try:
   with patch.object(bridge,'_native_job',side_effect=[self.strict] if nonclip else [self.clip,self.strict]) as calls:result=bridge.render(self.xml,20,10,180,self.paths['strict_renderer'] if nonclip else self.paths['clip_renderer'],8192,self.paths['runtime_manifest'])
   self.assertEqual(calls.call_count,1 if nonclip else 2);self.assertTrue(result['ok'],result)
  finally:
   for p in reversed(patches):p.stop()
  self.native_file=self.owned/'observed.native_info.json';self.native_file.write_bytes(reader.compact(result['native_render'])+b'\n');self.png_file=self.owned/'observed.png';self.png_file.write_bytes(result['png']);self.info=result['native_render'];self.report={'pins':{str(p):reader.sha(p.read_bytes()) for p in self.paths.values()},'fresh_qa':{'same_render_result_objects_returned':True,'observer_errors':[],'blocked_mutation_attempts':[],'observations':[{'kind':'primary_clip_render','ok':True,'code_sha256':self.code,'canvas':[20,10],'renderer':str(self.paths['strict_renderer'] if nonclip else self.paths['clip_renderer']),'renderer_sha256':reader.sha(self.paths['strict_renderer' if nonclip else 'clip_renderer'].read_bytes()),'returned_original_result_object':True,'native_info':self.entry(self.native_file),'png':self.entry(self.png_file)}],'report':{'checks':{'render':{'strict_clip_canvas_proof':self.info.get('clip_canvas_strict_proof_v4b'),'code_sha256':self.code,'image_sha256':reader.sha(result['png']),'canvas':[20,10]}}}}}
  if not nonclip:
   self.proof_path=self.root/self.info['clip_canvas_strict_proof_v4b']['file'];self.base=self.proof_path.parent
 def entry(self,path):return {'file':str(path),'sha256':reader.sha(path.read_bytes()),'bytes':path.stat().st_size}
 def inspect(self):return reader.inspect(self.report,self.root,self.owned)
 def reject(self,needle=None):
  result=self.inspect();self.assertFalse(result['complete'],result)
  if needle:self.assertIn(needle,result['reason'])
  return result
 def rewrite_info(self,info):
  self.native_file.write_bytes(reader.compact(info)+b'\n');self.report['fresh_qa']['observations'][0]['native_info']=self.entry(self.native_file)
 def reseal(self,transform=None):
  proof=json.loads(self.proof_path.read_bytes())
  if transform:transform(proof)
  for value in proof['artifacts'].values():
   path=self.root/value['file']
   if path.is_file():value['sha256']=reader.sha(path.read_bytes())
  self.proof_path.write_bytes(reader.bridge_json(proof));link={**self.info['clip_canvas_strict_proof_v4b'],'sha256':reader.sha(self.proof_path.read_bytes()),'code_sha256':proof['code_sha256'],'png_sha256':proof['png_sha256']};self.info['clip_canvas_strict_proof_v4b']=link;self.report['fresh_qa']['report']['checks']['render']['strict_clip_canvas_proof']=copy.deepcopy(link);self.rewrite_info(self.info)
 def mutate_artifact(self,key,fn):
  proof=json.loads(self.proof_path.read_bytes());p=self.root/proof['artifacts'][key]['file'];doc=json.loads(p.read_bytes());fn(doc);p.write_bytes(reader.bridge_json(doc));self.reseal()
 def test_complete_actual_bridge_schema_collects_every_declared_file_and_combined(self):
  before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()};r=self.inspect();self.assertTrue(r['applicable']);self.assertTrue(r['complete'],r);self.assertEqual(len(r['files']),15);self.assertTrue(any(x['file'].endswith('/combined.native_render.json') for x in r['files']));self.assertEqual({str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()},before)
 def test_canonical_CLIP_namespace_is_legal_without_broadening_to_clean(self):
  self.build(canonical=True);r=self.inspect();self.assertTrue(r['applicable']);self.assertTrue(r['complete'],r)
 def test_ancestor_symlink_is_not_followed_even_inside_root(self):
  actual=self.base.with_name(self.base.name+'_actual');self.base.rename(actual);self.base.symlink_to(actual,target_is_directory=True);self.reject()
 def test_nonclip_is_explicit_and_complete(self):
  self.build(nonclip=True);r=self.inspect();self.assertFalse(r['applicable']);self.assertTrue(r['complete'],r)
 def test_missing_or_unknown_observations_never_defaults_to_complete(self):
  for report in ({},{'fresh_qa':{}},{'fresh_qa':{'observations':[]}}):self.assertFalse(reader.inspect(report,self.root,self.owned)['complete'])
 def test_missing_primary_native_info_known_clip_remains_applicable_incomplete(self):
  self.native_file.unlink();r=self.reject();self.assertTrue(r['applicable'])
 def test_primary_info_or_png_tampering_detected(self):
  self.png_file.write_bytes(self.png_file.read_bytes()+b'tamper');self.reject('sha256_mismatch')
 def test_missing_or_unknown_proof_schema_rejected(self):
  self.reseal(lambda p:p.update(version=2));self.reject('unknown_CLIP_proof_schema')
 def test_unknown_declared_artifact_is_not_silently_ignored(self):
  self.reseal(lambda p:p['artifacts'].update(extra=p['artifacts']['xml']));self.reject('missing_or_unknown_declared')
 def test_missing_every_declared_artifact_rejected(self):
  proof=json.loads(self.proof_path.read_bytes())
  for key,entry in proof['artifacts'].items():
   p=self.root/entry['file'];original=p.read_bytes();p.unlink();self.reject();p.write_bytes(original)
 def test_missing_combined_protocol_file_rejected(self):
  (self.base/'combined.native_render.json').unlink();self.reject()
 def test_combined_info_must_equal_exact_actual_clip_with_strict_overlay(self):
  p=self.base/'combined.native_render.json';doc=json.loads(p.read_bytes());doc['actual_clip_boxes']=[];p.write_bytes(reader.bridge_json(doc));self.reject('combined_or_primary')
 def test_each_declared_artifact_stays_same_audit_directory(self):
  self.reseal(lambda p:p['artifacts']['xml'].update(file=str(self.native_file.relative_to(self.root))));self.reject('cross_namespace')
 def test_parent_escape_and_external_paths_rejected(self):
  self.info['clip_canvas_strict_proof_v4b']['file']='../outside';self.rewrite_info(self.info);self.reject('locator_escape')
 def test_symlink_file_and_ancestor_are_not_followed(self):
  p=self.base/'strict.png';actual=p.with_name('real.png');p.rename(actual);p.symlink_to(actual);self.reject()
 def test_proof_namespace_cannot_escape_owned_or_canonical(self):
  wrong=self.root/'clean'/self.code/self.base.name;wrong.mkdir(parents=True);target=wrong/'proof.json';target.write_bytes(self.proof_path.read_bytes());self.info['clip_canvas_strict_proof_v4b']['file']=str(target.relative_to(self.root));self.rewrite_info(self.info);self.reject('namespace_not_owned_or_canonical')
 def test_renderer_and_runtime_hashes_are_pinned_to_collector(self):
  self.report['pins'][str(self.paths['strict_renderer'])]='f'*64;self.reject('not_bound_to_frozen_collector')
 def test_renderer_source_modification_rejected(self):
  self.paths['clip_renderer'].write_bytes(b'changed');self.reject('sha256_mismatch')
 def test_new_adapter_source_even_if_resealed_is_unsupported(self):
  self.paths['adapter'].write_bytes(b'new protocol');self.report['pins'][str(self.paths['adapter'])]=reader.sha(b'new protocol');self.reseal(lambda p:p['pins']['adapter'].update(sha256=reader.sha(b'new protocol')));self.reject('unsupported_frozen_CLIP_adapter_source')
 def test_old_clip_overflow_is_never_waived(self):
  self.mutate_artifact('clip_info',lambda d:d.update(native_graph_bounds_outside_declared_canvas=True));self.reject('Old clip renderer')
 def test_strict_outside_and_real_probe_requirements(self):
  self.mutate_artifact('strict_info',lambda d:d['outside_page_pixel_audit'].update(nonwhite_outside_pixels=1));self.reject('outside_page_pixels_not_zero')
 def test_missing_strict_field_is_not_defaulted_to_zero(self):
  self.mutate_artifact('strict_info',lambda d:d['outside_page_pixel_audit'].pop('nonwhite_outside_pixels'));self.reject()
 def test_page_origin_and_canvas_changes_rejected(self):
  self.mutate_artifact('strict_info',lambda d:d.update(translate=[1,0]));self.reject('scale_or_origin')
 def test_dual_png_byte_difference_rejected_even_same_dimensions(self):
  p=self.base/'strict.png';p.write_bytes(p.read_bytes()+b'trailing');self.reseal();self.reject('dual_native_PNG_bytes')
 def test_actual_physical_font_identity_and_count_rechecked(self):
  self.mutate_artifact('strict_info',lambda d:d['actual_platform_font_usage'][0]['fonts'][0].update(postScriptName='Wrong'));self.reject('font_or_character_signature')
 def test_actual_character_position_rechecked(self):
  self.mutate_artifact('strict_info',lambda d:d['actual_text_positions'][0]['runs'][0]['chars'][0].update(x=1.1));self.reject('font_or_character_signature')
 def test_declared_signature_digest_cannot_be_trusted(self):
  self.reseal(lambda p:p.update(actual_font_signature_sha256='f'*64));self.reject('signature_digest_mismatch')
 def test_qacheck_receipt_must_match_primary_actual_receipt(self):
  self.report['fresh_qa']['report']['checks']['render']['strict_clip_canvas_proof']={};self.reject('not_bound_to_actual_CLIP_receipt')
 def test_invalid_request_and_pin_schema_rejected(self):
  self.mutate_artifact('request',lambda d:d.update(timeout=-1));self.reject('request_canvas_or_size')
 def test_primary_renderer_mixed_with_clip_proof_rejected(self):
  self.report['fresh_qa']['observations'][0]['renderer']=str(self.paths['strict_renderer']);self.reject('renderer_or_receipt_missing_or_mixed')
 def test_declared_length_tamper_rejected(self):
  self.report['fresh_qa']['observations'][0]['native_info']['bytes']+=1;self.reject('byte_length_mismatch')
if __name__=='__main__':unittest.main(verbosity=2)
