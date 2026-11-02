import base64,io,json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';report=json.loads((W/'svg_pilot.json').read_text());db=sqlite3.connect(W/'jobs.sqlite');rows=[]
for row in report['results']:
 d=Path(row['directory']);inp=json.loads(db.execute('select input_manifest from jobs where id=?',(row['id'],)).fetchone()[0]);paths=[R/inp['reference_image'],d/'source_svg.png',d/'image.png'];sheet=Image.new('RGB',(1500,380),'#ddd');draw=ImageDraw.Draw(sheet)
 for n,p in enumerate(paths):
  if not p.exists():continue
  im=Image.open(p).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);im=ImageOps.contain(bg.convert('RGB'),(490,340));sheet.paste(im,(n*500+(500-im.width)//2,35+(340-im.height)//2));draw.text((n*500+5,4),row['source']+' '+['ORIGINAL','SOURCE SVG','DRAWIO'][n],fill='black')
 rows.append(sheet)
canvas=Image.new('RGB',(1500,380*len(rows)),'white')
for i,s in enumerate(rows):canvas.paste(s,(0,i*380))
canvas.save(W/'svg_review.jpg',quality=88);out=io.BytesIO();canvas.save(out,format='JPEG',quality=88);print(base64.b64encode(out.getvalue()).decode())
