import base64,io,json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from native_worker import R,W
D=sqlite3.connect(W/'jobs.sqlite');ids=['00340fab31c7c961fea2a69504f4a0e8b2b33c962be0d118813c26f9497fc83a','00f79a876f1b7f8ee064510060d97f4cadbde75131535229770af635322e365c','018ea847066eaeb81e35a9a45ad83f8703424e8dabe02cfdd5864aae3ef77e3d'];sheet=Image.new('RGB',(1200,900),'white');d=ImageDraw.Draw(sheet)
for i,id in enumerate(ids):
 r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);paths=[R/r['original_reference'],W/'tikz_native'/id[:2]/id/'source_render.png',R/r['image_file']]
 for j,path in enumerate(paths):
  im=ImageOps.contain(Image.open(path).convert('RGB'),(390,265));sheet.paste(im,(j*400+(400-im.width)//2,i*300+25+(265-im.height)//2));d.text((j*400+3,i*300+3),id[:6]+' '+['ORIGINAL','PDF RECONSTRUCTION','DRAWIO'][j],fill='black')
sheet.save(W/'tikz_overflow_review.jpg',quality=85);buf=io.BytesIO();sheet.save(buf,format='JPEG',quality=45);print(base64.b64encode(buf.getvalue()).decode())
