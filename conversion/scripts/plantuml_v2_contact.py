import io,json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from native_worker import R,W
D=sqlite3.connect(W/'jobs.sqlite');ids=['003ac6c589d230952350e02d172bc5eeb920e31be1efc738f87d272de9962337','02248d55c2d82022c490febf18344e685d66671feb8be88e9dabbd351948de11','4b9f5161955963bf7502185ac81bfd2d83d13a3c4dfd2e0183a8c7e4f40e6759'];canvas=Image.new('RGB',(1400,1800),'#eeeeee');draw=ImageDraw.Draw(canvas)
for i,id in enumerate(ids):
 inp=json.loads(D.execute('select input_manifest from jobs where id=?',(id,)).fetchone()[0]);new=W/('plantuml_translation_probe' if i==2 else 'plantuml_v2_probe')/id/('0.png' if i==2 else 'image.png')
 for j,(title,path) in enumerate([('original',R/inp['reference_image']),('new native',new)]):
  im=Image.open(path).convert('RGB');im=ImageOps.contain(im,(680,555));canvas.paste(im,(700*j+(700-im.width)//2,i*600+30));draw.text((j*700+8,i*600+8),id[:10]+' '+title,fill='black')
canvas.save(W/'plantuml_v2_contact.jpg',quality=72)
