import base64,io,json,sqlite3
from PIL import Image,ImageOps,ImageDraw
from native_worker import R,W
D=sqlite3.connect(W/'jobs.sqlite');ids=['004880fe35701c4e800c46d26c1ffc2826cbb50e0e0d2049e620cfcd7d4791de','00023a00be2645e09244bba7115224bc58e689ae0f0b6b8d5f5ce76aa4ae684e'];sheet=Image.new('RGB',(1200,850),'white');draw=ImageDraw.Draw(sheet)
for i,id in enumerate(ids):
 out=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);base=R/out['previous_candidate_archive'];old=json.loads((base/'conversion.json').read_text());paths=[R/out['original_reference'],base/'image.png',R/out['image_file']]
 for j,path in enumerate(paths):
  im=ImageOps.contain(Image.open(path).convert('RGB'),(392,390));sheet.paste(im,(j*400+(400-im.width)//2,i*425+30+(390-im.height)//2));draw.text((j*400+5,i*425+5),id[:6]+' '+['ORIGINAL','BEFORE','HARNESS V2'][j],fill='black')
sheet.save(W/'harness_v2_review.jpg',quality=90);buf=io.BytesIO();sheet.save(buf,format='JPEG',quality=50);print(base64.b64encode(buf.getvalue()).decode())
