import io,json,sqlite3,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
import numpy as np
from skimage.metrics import structural_similarity
from native_worker import R,W,pair
s=json.loads((W/'harness_repair_pilot.json').read_text());rec,out=sqlite3.connect(W/'jobs.sqlite').execute('SELECT input_record,output_record FROM jobs WHERE id=?',(s['id'],)).fetchone();row=json.loads(rec);data,_=pair(row);p=Path(s['session_directory']);blobs=[data,(R/json.loads(out)['image_file']).read_bytes(),(p/'round2/image.png').read_bytes()];sheet=Image.new('RGB',(1800,660),'#eee');d=ImageDraw.Draw(sheet);arrays=[]
for i,(title,b) in enumerate(zip(['Original reference','Original reconstructed XML','Remote Harness repaired XML'],blobs)):
 im=Image.open(io.BytesIO(b)).convert('RGBA');bg=Image.new('RGBA',im.size,'white');bg.alpha_composite(im);im=bg.convert('RGB');arrays.append(np.array(im.resize((600,600))));thumb=ImageOps.contain(im,(590,620));sheet.paste(thumb,(i*600+(600-thumb.width)//2,30+(620-thumb.height)//2));d.text((i*600+10,8),title,fill='black')
sheet.save(W/'harness_repair_comparison.jpg',quality=94);root=ET.parse(p/'round2/diagram.drawio');cells=list(root.iter('mxCell'));ids={x.get('id') for x in cells};edges=[x for x in cells if x.get('edge')=='1'];result={'id':s['id'],'state':s['state'],'rounds':len(s['rounds']),'vertices':sum(x.get('vertex')=='1' for x in cells),'edges':len(edges),'bound_edges':sum(e.get('source') in ids and e.get('target') in ids for e in edges),'original_to_native_ssim':float(structural_similarity(arrays[0],arrays[1],channel_axis=2,data_range=255)),'original_to_repaired_ssim':float(structural_similarity(arrays[0],arrays[2],channel_axis=2,data_range=255)),'scope':'Pilot diagnostic, pending root visual review; no corpus-wide completion claim.'};(W/'harness_repair_review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
