import io,tempfile,unittest
from pathlib import Path
from PIL import Image
import tikz_pdftex_execution_v1 as execution
from pdf_fonts_pdftex_v1 import type1_transport
from tikz_pdf_glyph_layout_v1 import offsets,validate

class DensityAndRuntimeInputs(unittest.TestCase):
 def png(self,dpi=None):
  stream=io.BytesIO();im=Image.new('RGB',(12,10),'white');im.save(stream,format='PNG',**({'dpi':dpi} if dpi else {}));return stream.getvalue()
 def test_declared_density_is_required(self):
  with self.assertRaisesRegex(ValueError,'does_not_declare'):execution.density(self.png())
 def test_density_must_be_equal_and_supported(self):
  for dpi in ((100,150),(96,96)):
   with self.assertRaisesRegex(ValueError,'does_not_declare'):execution.density(self.png(dpi))
 def test_rounded_png_phyS100_is_accepted(self):self.assertEqual(execution.density(self.png((100,100))),100)
 def test_recorder_pins_original_case_bytes(self):
  with tempfile.TemporaryDirectory() as name:
   p=Path(name);(p/'original_source.tex').write_bytes(b'original bytes');(p/'source.fls').write_text('INPUT /work/original_source.tex\nINPUT /work/original_source.tex\n')
   pins=execution.recorder_inputs(p);self.assertEqual(set(pins),{'case/original_source.tex'});self.assertEqual(pins['case/original_source.tex']['sha256'],execution.sha(b'original bytes'))
 def test_recorder_rejects_nonruntime_global_inputs(self):
  with tempfile.TemporaryDirectory() as name:
   p=Path(name);(p/'source.fls').write_text('INPUT /etc/passwd\n')
   with self.assertRaisesRegex(ValueError,'unpinned_nonruntime'):execution.recorder_inputs(p)

class Type1Transport(unittest.TestCase):
 def test_clear_and_encrypted_original_program_bytes_are_unchanged(self):
  original=b'%!PS-AdobeFont-1.0\ncurrentfile eexec\n'+bytes(range(256))
  wrapped=type1_transport(original);parts=[];index=0
  while wrapped[index:index+2]!=bytes([128,3]):
   length=int.from_bytes(wrapped[index+2:index+6],'little');parts.append(wrapped[index+6:index+6+length]);index+=6+length
  self.assertEqual(parts[0]+parts[1],original);self.assertIn(b'cleartomark',parts[2]);self.assertEqual(len(parts),3)
 def test_existing_PFB_transport_is_unchanged(self):
  data=bytes([128,1])+b'example';self.assertIs(type1_transport(data),data)
 def test_missing_eexec_program_boundary_is_not_invented(self):
  with self.assertRaisesRegex(ValueError,'boundary_missing'):type1_transport(b'%!PS malformed')

class GlyphMapping(unittest.TestCase):
 def setup_rows(self):
  fonts=[{'postScriptName':'EmbeddedOriginal','glyphCount':2,'isCustomFont':True}]
  chars=[{'text':'a','x':10.,'y':20.,'width':5.,'height':9.},{'text':'b','x':15.,'y':20.,'width':6.,'height':9.}]
  expected={'run':{'chars':chars,'actual_fonts':fonts}};native={'actual_text_positions':[{'cell':'run','runs':[{'chars':[dict(c) for c in chars]}]}],'actual_platform_font_usage':[{'cell':'run','fonts':fonts}]}
  return expected,native
 def test_exact_actual_graphemes_pass(self):
  expected,native=self.setup_rows();self.assertTrue(validate(expected,native)['ok'])
 def test_whole_run_rounding_has_one_correction(self):
  expected,native=self.setup_rows()
  for c in native['actual_text_positions'][0]['runs'][0]['chars']:c['x']+=.4;c['y']-=.2
  change=offsets(expected,native)['run'];self.assertAlmostEqual(change['dx'],-.4);self.assertAlmostEqual(change['dy'],.2)
  with self.assertRaisesRegex(ValueError,'anchor_mismatch'):validate(expected,native)
 def test_changed_glyph_is_not_fixed_as_position(self):
  expected,native=self.setup_rows();native['actual_text_positions'][0]['runs'][0]['chars'][1]['text']='c'
  with self.assertRaisesRegex(ValueError,'graphemes_changed'):offsets(expected,native)
 def test_changed_spacing_is_not_fixed_as_translation(self):
  expected,native=self.setup_rows();native['actual_text_positions'][0]['runs'][0]['chars'][1]['x']+=.2
  with self.assertRaisesRegex(ValueError,'spacing_differs'):offsets(expected,native)

if __name__=='__main__':unittest.main()
