"""Same-paper accepted reference contact sheets to catch near variants visually."""
from pathlib import Path
import argparse,json,hashlib,math,time
from PIL import Image,ImageDraw,ImageFont
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/goal500_progress_v1'
p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);a=p.parse_args();folder=a.folder.resolve();assert folder.is_relative_to(D)
manifest=json.loads((folder/'review_manifest.json').read_text());papers={r['paper'] for r in manifest}
for attempt in range(5):
 try:rows=list(map(json.loads,(D/'accepted_new_pairs.jsonl').read_text().splitlines()));break
 except ValueError:time.sleep(.2)
rows=[r for r in rows if r.get('paper') in papers];refs=[];font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
for page in range(math.ceil(len(rows)/4)):
 sheet=Image.new('RGB',(1800,1400),'#e6f1e9');draw=ImageDraw.Draw(sheet)
 for pos,row in enumerate(rows[page*4:(page+1)*4]):
  f=R/row['image_file'];b=f.read_bytes();assert hashlib.sha256(b).hexdigest()==row['image_sha256'];im=Image.open(f).convert('RGBA');white=Image.new('RGBA',im.size,'white');white.alpha_composite(im);im=white.convert('RGB');im.thumbnail((880,640));x=pos%2*900;y=pos//2*700;sheet.paste(im,(x+(900-im.width)//2,y+50+(640-im.height)//2));n=page*4+pos+1;draw.text((x+8,y+8),f'ACCEPTED REF {n} | {row["paper"]} | {row["goal500_pair_id"][:12]}',font=font,fill='black');refs.append({k:row[k] for k in ['goal500_pair_id','paper','code_sha256','image_file','image_sha256']})
 sheet.save(folder/f'reference_{page+1:02d}.jpg',quality=90)
(folder/'reference_manifest.json').write_text(json.dumps(refs,indent=2)+'\n');print(json.dumps(dict(candidate_rows=len(manifest),accepted_same_paper_references=len(refs),reference_pages=math.ceil(len(refs)/4))))
