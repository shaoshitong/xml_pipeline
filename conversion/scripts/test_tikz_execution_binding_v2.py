"""Fixed marker negatives include missing/tiny/reversed heads, color and drift."""
import io,unittest
from PIL import Image,ImageDraw
from tikz_execution_binding_v2 import marker_metrics,native_marker_polygon


class MarkerV2Tests(unittest.TestCase):
 def image(self,points=None,outside=False,color='blue'):
  image=Image.new('RGB',(120,100),'white');draw=ImageDraw.Draw(image);draw.line([(15,50),(70,50)],fill='blue',width=2)
  if points is not None:draw.polygon(points,fill=color)
  if outside:image.putpixel((1,1),(0,0,0))
  stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()
 def inputs(self):
  points=[(70,44),(82,50),(70,56)];style={'strokeWidth':2,'fill':'blue'}
  dom={'objects':[{'id':'arrow','tag':'path','attrs':{'d':'M70 44 L82 50 L70 56 Z'},'d':'M70 44 L82 50 L70 56 Z','bbox':{'x':70,'y':44,'w':12,'h':12},'matrix':[1,0,0,1,0,0],'style':style},{'id':'e','tag':'path','attrs':{'d':'M15 50 L75 50'},'d':'M15 50 L75 50','bbox':{'x':15,'y':50,'w':60,'h':0},'matrix':[1,0,0,1,0,0],'style':style}]}
  xml='<mxfile><diagram><mxGraphModel><root><mxCell id="e" edge="1" source="a" target="b" style="endArrow=block;endSize=10;endFill=1;endFillColor=blue;endStrokeColor=transparent;"/></root></mxGraphModel></diagram></mxfile>'
  proof={'native_arrowheads':[{'source_object':'arrow','edge':'e','side':'end','marker':'block','native_marker_stroke':'transparent'}]};return points,xml,dom,proof
 def test_exact_and_scale_reporting(self):
  points,xml,dom,proof=self.inputs();result=marker_metrics(self.image(points),self.image(points),xml,dom,proof);self.assertTrue(result['ok'],result);entry=result['markers'][0];self.assertEqual(entry['ink_iou'],1);self.assertEqual(entry['source_stroke_width_device_px'],2);self.assertEqual(entry['source_head_path_length_device_px'],12);self.assertEqual(entry['roi_size_device_px'],[22,22])
 def test_missing_tiny_reversed_and_outside_heads_reject(self):
  points,xml,dom,proof=self.inputs();before=self.image(points)
  for bad in (None,[(70,49),(73,50),(70,51)],[(82,44),(70,50),(82,56)]):
   with self.subTest(bad=bad):self.assertFalse(marker_metrics(before,self.image(bad),xml,dom,proof)['ok'])
  self.assertFalse(marker_metrics(before,self.image(points,outside=True),xml,dom,proof)['ok'])
 def test_color_and_native_type_changes_reject(self):
  points,xml,dom,proof=self.inputs();before=self.image(points)
  self.assertFalse(marker_metrics(before,self.image(points,color='red'),xml,dom,proof)['ok'])
  self.assertFalse(marker_metrics(before,before,xml.replace('endFillColor=blue','endFillColor=red'),dom,proof)['ok'])
  self.assertFalse(marker_metrics(before,before,xml.replace('endArrow=block','endArrow=classic'),dom,proof)['ok'])
 def test_native_factory_formula(self):
  p,end=native_marker_polygon('blockThin',4,1,point=(10,0));self.assertEqual(len(p),3);self.assertAlmostEqual(p[0][0],8.882);self.assertAlmostEqual(end[0],3.882)


if __name__=='__main__':unittest.main()
