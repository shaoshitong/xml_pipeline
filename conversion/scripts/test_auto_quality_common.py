"""Corruption fixtures ensure a batch cannot pass on background-dominated SSIM."""
import io,json
from PIL import Image,ImageDraw
from auto_quality_common import image_quality,native_source_profile

def png(image):
 stream=io.BytesIO();image.save(stream,format='PNG');return stream.getvalue()

reference=Image.new('RGB',(640,480),'white');d=ImageDraw.Draw(reference)
for i in range(5):d.rectangle((25+115*i,60,110+115*i,160),outline='black',width=2)
d.text((50,250),'CRITICAL LABEL 123',fill='black')
position=[{'cell':'t','runs':[{'chars':[{'text':'CRITICAL LABEL 123','x':50,'y':250,'width':110,'height':13}]}]}]
good=image_quality(png(reference),png(reference),{},position);assert good['ok'] and good['exact_reference_pixels']
blank=Image.new('RGB',reference.size,'white');assert not image_quality(png(reference),png(blank),{},position)['ok']
missing=reference.copy();ImageDraw.Draw(missing).rectangle((48,248,165,265),fill='white');bad=image_quality(png(reference),png(missing),{},position);assert not bad['ok'] and 'local_text_line_ssim_below_0.55' in bad['failures'],bad
cropped=reference.crop((0,0,600,480))
try:image_quality(png(reference),png(cropped),{},position);raise AssertionError('unregistered crop accepted')
except ValueError as exc:assert 'unregistered' in str(exc)
source='<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="n" value="original" vertex="1" parent="1"><mxGeometry width="20" height="10" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'
assert native_source_profile({},source,source)['ok']
assert not native_source_profile({},source.replace('original','changed'),source)['ok']
print(json.dumps({'ok':True,'fixtures':6,'hidden_small_label_global_ssim':bad['ssim_1024'],'hidden_small_label_local_ssim':bad['worst_text_regions'][0]['ssim']}))
