import io,json,sqlite3,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'));from native_worker import pair
conn=sqlite3.connect(R/'conversion/jobs.sqlite');rows=conn.execute('SELECT id,source,state,input_record,output_record,error FROM jobs WHERE state!="queued" ORDER BY source').fetchall();review=[];ok=[r for r in rows if r[4]]
sheet=Image.new('RGB',(1200,330*len(ok)), '#e8e8e8');draw=ImageDraw.Draw(sheet)
for i,(id,source,state,inp,out,error) in enumerate(ok):
 x=json.loads(out);data,_=pair(json.loads(inp));draw.text((8,i*330+5),source+' | original versus normalized XML render',fill='black')
 for c,b in enumerate((data,(R/x['image_file']).read_bytes())):
  image=Image.open(io.BytesIO(b)).convert('RGB');image=ImageOps.contain(image,(590,290));sheet.paste(image,(c*600+(600-image.width)//2,i*330+30+(290-image.height)//2))
 review.append({k:x[k] for k in ('id','source','vertices','edges','bound_edges','source_page_count','metrics','image_file','code_file')})
path=R/'conversion/native_pilot_comparison.jpg';sheet.save(path,quality=90)
print(json.dumps({'samples':review,'failures':[{'id':id,'source':source,'error':error} for id,source,state,inp,out,error in rows if not out],'sheet':str(path)},ensure_ascii=False))
