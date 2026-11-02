import base64,io,json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from native_worker import R,W
id='0001784b9f3b28598732c2dc034369bd2dc5274e31e8a2a945bb3bc4a6fb15c2';db=sqlite3.connect(W/'jobs.sqlite');inp=json.loads(db.execute('select input_manifest from jobs where id=?',(id,)).fetchone()[0]);paths=[R/inp['reference_image'],W/'pdf_native_pilot'/id/'image.png',W/'pdf_native_connected_pilot'/id/'image.png'];sheet=Image.new('RGB',(1500,960),'white');d=ImageDraw.Draw(sheet)
for i,path in enumerate(paths):
 im=ImageOps.contain(Image.open(path).convert('RGB'),(1490,290));sheet.paste(im,((1500-im.width)//2,i*320+25));d.text((5,i*320+4),['ORIGINAL','UNBOUND VECTORS','SOURCE-BOUND CONNECTORS'][i],fill='black')
sheet.save(W/'tikz_connected_review.jpg',quality=90);buf=io.BytesIO();sheet.thumbnail((1100,704));sheet.save(buf,format='JPEG',quality=45);print(base64.b64encode(buf.getvalue()).decode())
