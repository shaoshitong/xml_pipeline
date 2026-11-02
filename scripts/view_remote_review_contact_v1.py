"""Emit an inline contact sheet without saving research images on the Mac."""
import argparse,subprocess
p=argparse.ArgumentParser();p.add_argument('review');p.add_argument('--offset',type=int,default=0);a=p.parse_args()
code='''from pathlib import Path
import json,io,base64,hashlib
from PIL import Image,ImageDraw
R=Path('/backup/shaoshitong/img2code_20261029')
P=Path(REVIEW)/'reviewed_pairs.jsonl'
rows=[json.loads(x)for x in P.read_text().splitlines()][OFFSET:OFFSET+4]
sheet=Image.new('RGB',(1500,1150),'#dddddd');d=ImageDraw.Draw(sheet)
for i,row in enumerate(rows):
 b=(R/row['pair']['image_file']).read_bytes();assert hashlib.sha256(b).hexdigest()==row['pair']['image_sha256'];im=Image.open(io.BytesIO(b)).convert('RGB');im.thumbnail((740,535));x=(i%2)*750;y=(i//2)*575;sheet.paste(im,(x+(750-im.width)//2,y+30));d.text((x+5,y+5),str(i+OFFSET+1)+' '+row['id'][:12],fill='black')
f=io.BytesIO();sheet.save(f,format='JPEG',quality=84);print(base64.b64encode(f.getvalue()).decode())
'''.replace('REVIEW',repr(a.review)).replace('OFFSET',str(a.offset))
r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','hkust3','/home/shaoshitong/anaconda3/bin/python','-'],input=code,text=True,capture_output=True,timeout=25)
assert r.returncode==0,r.stderr
print(r.stdout,end='')
