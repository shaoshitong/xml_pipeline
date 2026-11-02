import base64,collections,io,json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite');rows=[]
for id,raw in db.execute('select id,output_record from jobs where format="html" and output_record is not null order by id limit 4'):
 out=json.loads(raw);sheet=Image.new('RGB',(1200,470),'#ddd');d=ImageDraw.Draw(sheet)
 for n,key in enumerate(['original_reference','image_file']):
  im=Image.open(R/out[key]).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);im=ImageOps.contain(bg.convert('RGB'),(590,430));sheet.paste(im,(n*600+(600-im.width)//2,30+(430-im.height)//2));d.text((n*600+4,3),id[:8]+' '+['ORIGINAL','DRAWIO'][n],fill='black')
 rows.append(sheet)
canvas=Image.new('RGB',(1200,470*len(rows)),'white')
for i,row in enumerate(rows):canvas.paste(row,(0,470*i))
canvas.save(W/'html_batch_review.jpg',quality=88);b=io.BytesIO();canvas.save(b,format='JPEG',quality=70);print(base64.b64encode(b.getvalue()).decode())
