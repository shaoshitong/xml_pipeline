import json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from native_worker import R,W
id='003ac6c589d230952350e02d172bc5eeb920e31be1efc738f87d272de9962337';D=sqlite3.connect(W/'jobs.sqlite');out=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);canvas=Image.new('RGB',(1040,850),'#eeeeee');draw=ImageDraw.Draw(canvas)
for i,key in enumerate(['original_reference','image_file']):
 im=ImageOps.contain(Image.open(R/out[key]).convert('RGB'),(500,810));canvas.paste(im,(i*520+(520-im.width)//2,30));draw.text((i*520+10,8),key,fill='black')
canvas.save(W/'plantuml_font_actual_contact.jpg',quality=80)
print(json.dumps({'font_mappings':list({(x['family'],x['selected']) for x in out['svg_conversion']['physical_font_resolution']['runs']}),'needs_glyph_review':out['svg_conversion']['physical_font_resolution']['needs_glyph_fallback_review']}))
