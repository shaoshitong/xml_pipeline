import base64,io,json,sqlite3
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
from native_worker import R,W
from svg_batch import metric
D=sqlite3.connect(W/'jobs.sqlite');items=json.loads((W/'tikz_pilot.json').read_text())['results'];item=items[1];id=item['id'];work=W/'pdf_native_pilot'/id;inp=json.loads(D.execute('select input_manifest from jobs where id=?',(id,)).fetchone()[0]);paths=[R/inp['reference_image'],Path(item['directory'])/'page0_poppler.png',work/'reconstructed_source.png',work/'image.png'];sheet=Image.new('RGB',(1600,450),'white');d=ImageDraw.Draw(sheet)
for i,path in enumerate(paths):
 im=Image.open(path).convert('RGB');im=ImageOps.contain(im,(395,420));sheet.paste(im,(i*400+(400-im.width)//2,25+(420-im.height)//2));d.text((i*400+5,3),['ORIGINAL','COMPILED PDF','RECONSTRUCTED SVG','DRAWIO'][i],fill='black')
sheet.save(W/'pdf_native_review.jpg',quality=88);b=io.BytesIO();sheet.save(b,format='JPEG',quality=70);print(base64.b64encode(b.getvalue()).decode())
