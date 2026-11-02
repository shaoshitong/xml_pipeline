import io,json,sqlite3
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
import numpy as np
from skimage.metrics import structural_similarity
from native_worker import R,W,pair
s=json.loads((W/'html_pilot.json').read_text());rec=sqlite3.connect(W/'jobs.sqlite').execute('SELECT input_record FROM jobs WHERE id=?',(s['id'],)).fetchone()[0];data,_=pair(json.loads(rec));p=Path(s['directory']);blobs=[data,(p/'source_html.png').read_bytes(),(p/'image.png').read_bytes()];sheet=Image.new('RGB',(2100,650),'#eeeeee');d=ImageDraw.Draw(sheet);a=[]
for i,(title,b) in enumerate(zip(['Original paired image','Original HTML rendered','Converted native drawio rendered'],blobs)):
 im=Image.open(io.BytesIO(b)).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);im=bg.convert('RGB');a.append(np.array(im.resize((1000,600))));thumb=ImageOps.contain(im,(690,610));sheet.paste(thumb,(i*700+(700-thumb.width)//2,30+(610-thumb.height)//2));d.text((i*700+8,8),title,fill='black')
sheet.save(W/'html_pilot_comparison.jpg',quality=93)
print(json.dumps({'objects':s['objects'],'text_objects':s['text_objects'],'raster_assets':s['raster_assets'],'unsupported':s['unsupported'],'original_vs_source_html_ssim':float(structural_similarity(a[0],a[1],channel_axis=2,data_range=255)),'source_html_vs_xml_ssim':float(structural_similarity(a[1],a[2],channel_axis=2,data_range=255))}))
