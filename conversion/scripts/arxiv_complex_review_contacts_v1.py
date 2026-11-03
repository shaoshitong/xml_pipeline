"""Small review contact sheets from real validated PNGs, never final-pair counts."""
from pathlib import Path
import datetime,hashlib,json,math,time
from PIL import Image,ImageDraw,ImageFont
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/goal500_progress_v1'
for _ in range(5):
 try:
  rows=[json.loads(l) for l in (D/'selected_pending_visual_policy_review.jsonl').read_text().splitlines()];break
 except (ValueError,FileNotFoundError):time.sleep(.2)
approval=json.loads((D/'value_policy_approval.json').read_text());known=set(approval.get('reviewed_accepted_goal500_ids',[]))|set(approval.get('reviewed_held_goal500_ids',[]))
rows=[r for r in rows if r['goal500_pair_id'] not in known]
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=D/('review_'+stamp);out.mkdir()
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
manifest=[]
for page in range(math.ceil(len(rows)/4)):
 canvas=Image.new('RGB',(1800,1400),'#e9edf1');draw=ImageDraw.Draw(canvas)
 for pos,row in enumerate(rows[page*4:page*4+4]):
  x=(pos%2)*900;y=(pos//2)*700
  path=R/row['image_file'];blob=path.read_bytes();assert hashlib.sha256(blob).hexdigest()==row['image_sha256']
  im=Image.open(path).convert('RGB');im.thumbnail((880,640));canvas.paste(im,(x+(900-im.width)//2,y+50+(640-im.height)//2))
  label=f'{page*4+pos+1} | {row.get("paper")} | {row["goal500_pair_id"][:12]}'
  draw.text((x+8,y+8),label,font=font,fill='black')
  manifest.append(dict(number=page*4+pos+1,page=page+1,id=row['goal500_pair_id'],paper=row.get('paper'),image_file=row['image_file'],image_sha256=row['image_sha256'],curation_view=row['curation_view'],code_sha256=row['code_sha256']))
 canvas.save(out/f'contact_{page+1:02d}.jpg',quality=90)
(out/'review_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(dict(folder=str(out),rows=len(rows),pages=math.ceil(len(rows)/4))))
