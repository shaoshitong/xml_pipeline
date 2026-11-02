import base64,io,json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite');report=json.loads((W/'code_svg_v3_pilot.json').read_text());rows=[]
for row in report['results']:
 if row['source']!='allenai--CoSyn-400K' or row['state']=='needs_fallback':continue
 inp,out=db.execute('select input_manifest,output_record from jobs where id=?',(row['id'],)).fetchone();inp=json.loads(inp);out=json.loads(out);paths=[R/inp['reference_image'],W/'code_svg_v3_pilot'/row['id']/'source_render.png',R/out['image_file']];sheet=Image.new('RGB',(1440,440),'#ddd');d=ImageDraw.Draw(sheet)
 for n,p in enumerate(paths):
  im=Image.open(p).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);im=ImageOps.contain(bg.convert('RGB'),(470,410));sheet.paste(im,(n*480+(480-im.width)//2,25+(410-im.height)//2));d.text((n*480+5,3),row['id'][:8]+' '+['ORIGINAL','SOURCE SVG','DRAWIO'][n],fill='black')
 rows.append(sheet)
canvas=Image.new('RGB',(1440,440*len(rows)),'white')
for i,s in enumerate(rows):canvas.paste(s,(0,i*440))
canvas.save(W/'python_review_v3.jpg',quality=85);b=io.BytesIO();canvas.save(b,format='JPEG',quality=78);print(base64.b64encode(b.getvalue()).decode())
