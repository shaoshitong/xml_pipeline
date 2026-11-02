import json,tempfile,unittest,xml.etree.ElementTree as E
from pathlib import Path
import tikz_closed_paint_candidate_v1 as b
class ImmutableTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);(self.root/'clean').mkdir();self.raw=b'original immutable payload';self.src=self.root/'private.bin';self.src.write_bytes(self.raw);self.entries={'clean/payload.'+b.sha(self.raw)+'.bin':{'source':str(self.src),'sha256':b.sha(self.raw),'bytes':len(self.raw)}}
 def tearDown(self):self.t.cleanup()
 def test_staging_is_immutable_idempotent_and_hash_checked(self):
  a=b.immutable_files(self.root,self.entries);self.assertEqual(len(a['written']),1);self.assertEqual(b.immutable_files(self.root,self.entries)['written'],[]);self.assertEqual(b.checked(self.root,{'file':next(iter(self.entries)),'sha256':b.sha(self.raw)}),self.raw)
 def test_changed_private_payload_rejected_before_final_write(self):
  self.src.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'staged'):b.immutable_files(self.root,self.entries)
 def test_conflicting_existing_hash_path_not_overwritten(self):
  locator=next(iter(self.entries));(self.root/locator).write_bytes(b'wrong')
  with self.assertRaisesRegex(ValueError,'conflict'):b.immutable_files(self.root,self.entries)
  self.assertEqual((self.root/locator).read_bytes(),b'wrong')
 def test_source_target_cannot_escape_clean(self):
  with self.assertRaisesRegex(ValueError,'outside clean'):b.immutable_files(self.root,{'outside.bin':next(iter(self.entries.values()))})
 def test_symlink_payload_is_rejected_even_when_target_bytes_match(self):
  path=self.root/'clean/link.bin';path.symlink_to(self.src)
  with self.assertRaises(ValueError):b.checked(self.root,{'file':'clean/link.bin','sha256':b.sha(self.raw)})
 def fixture(self):
  fields={};
  for key in ('original_source','original_reference','baseline_pdf','projected_svg'):
   raw=key.encode();p=self.root/'clean'/key;p.write_bytes(raw);fields[key]={'file':str(p.relative_to(self.root)),'sha256':b.sha(raw),'bytes':len(raw)}
  m={'version':b.VERSION,'id':'case','source_code_sha256':fields['original_source']['sha256'],'source_image_sha256':fields['original_reference']['sha256'],'files':fields};raw=b.canonical(m);(self.root/'clean/manifest.json').write_bytes(raw);root=E.Element('mxfile',{b.ROOT_ATTRIBUTE:b.sha(raw)});xml=E.tostring(root,encoding='unicode');(self.root/'clean/code.drawio').write_text(xml);(self.root/'clean/image.png').write_bytes(b'fixture-only');r={'id':'case','source_pair_sha256':'case','source_format':'tikz','format':'drawio','source_code_sha256':m['source_code_sha256'],'source_image_sha256':m['source_image_sha256'],'code_file':'clean/code.drawio','code_sha256':b.sha(xml.encode()),'image_file':'clean/image.png','image_sha256':b.sha(b'fixture-only'),b.FIELD:{'version':1,'file':'clean/manifest.json','sha256':b.sha(raw)}}
  for out,key,digest in [('original_source_code','original_source','source_code_sha256'),('original_reference','original_reference','source_image_sha256'),('source_render_pdf','baseline_pdf','source_render_pdf_sha256'),('source_render_svg','projected_svg','source_render_svg_sha256')]:r[out]=fields[key]['file'];r[digest]=fields[key]['sha256']
  return r,xml
 def test_complete_clean_source_manifest_and_native_root_binding(self):
  r,x=self.fixture();self.assertEqual(b.load_manifest(self.root,r,x)['id'],'case')
 def test_source_format_cannot_be_relabelled_svg(self):
  r,x=self.fixture();r['source_format']='svg'
  with self.assertRaisesRegex(ValueError,'relabelled'):b.load_manifest(self.root,r,x)
 def test_changed_native_root_source_proof_SHA_rejected(self):
  r,x=self.fixture();x=x.replace(r[b.FIELD]['sha256'],'0'*64);r['code_sha256']=b.sha(x.encode());(self.root/r['code_file']).write_text(x)
  with self.assertRaisesRegex(ValueError,'not bound'):b.load_manifest(self.root,r,x)
 def test_missing_trace_or_source_file_rejected(self):
  r,x=self.fixture();(self.root/r['source_render_pdf']).unlink()
  with self.assertRaises(ValueError):b.load_manifest(self.root,r,x)
if __name__=='__main__':unittest.main()
