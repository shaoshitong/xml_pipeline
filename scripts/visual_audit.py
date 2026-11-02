#!/usr/bin/env python3
"""Build deterministic, remote-only stratified inspection sheets and locators."""
import argparse, collections, hashlib, importlib.util, io, json, random
from pathlib import Path
import pyarrow.parquet as pq
from PIL import Image, ImageDraw, ImageFont, ImageOps

def main(root):
    spec=importlib.util.spec_from_file_location('pair_curator',root/'scripts/curate_pairs.py')
    curator=importlib.util.module_from_spec(spec);spec.loader.exec_module(curator)
    dest=root/'reports/visual_audit';dest.mkdir(exist_ok=True)
    rng=random.Random(20261029);groups=collections.defaultdict(list);seen=collections.Counter()
    for kind in ('clean','derived'):
        for line in (root/kind/'manifest.jsonl').open():
            record=json.loads(line);key=(kind,record['source'],record['category'],record['format'])
            seen[key]+=1
            if len(groups[key])<2:groups[key].append(record)
            else:
                position=rng.randrange(seen[key])
                if position<2:groups[key][position]=record
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12)
    samples=[(key,row) for key,rows in sorted(groups.items()) for row in rows]
    inventory=[];page=None;errors=[];sheets=[]
    for i,(key,record) in enumerate(samples):
        if i%12==0:page=Image.new('RGB',(1440,960),'#dcdcdc');draw=ImageDraw.Draw(page)
        cellx=(i%4)*360;celly=((i//4)%3)*320
        try:
            if record.get('clean_file'):
                pf=pq.ParquetFile(root/record['clean_file']);offset=record['clean_row']
                for group in range(pf.metadata.num_row_groups):
                    count=pf.metadata.row_group(group).num_rows
                    if offset<count:break
                    offset-=count
                row=pf.read_row_group(group).slice(offset,1).to_pylist()[0]
                data=curator.image_bytes(row[record['image_key']],root/'raw'/record['source'])
                code=(curator.code_value(row)[0] if record['code_key'] in ('messages','conversations','conversation')
                    else curator.text_content(row.get(record['code_key'])))
            else:
                data=(root/(record.get('reference_image') or record.get('image_file'))).read_bytes()
                code=(root/record['code_file']).read_text()
            if hashlib.sha256(data).hexdigest()!=record['image_sha256']:raise ValueError('image hash mismatch')
            image=Image.open(io.BytesIO(data)).convert('RGB');image=ImageOps.contain(image,(350,255))
            page.paste(image,(cellx+(360-image.width)//2,celly+55+(255-image.height)//2))
            title=f'{i:03d} {key[0]} {key[2]} {key[3]}\n{key[1]}'
            draw.multiline_text((cellx+5,celly+5),title,font=font,fill='black')
            inventory.append({'sample_id':i,'stratum':key,'stratum_population':seen[key],
                'locator':record,'code_prefix_for_manual_audit':code[:3000]})
        except Exception as exc:
            errors.append({'sample_id':i,'stratum':key,'error':type(exc).__name__+': '+str(exc)})
            draw.text((cellx+5,celly+60),'READ ERROR',font=font,fill='red')
        if i%12==11 or i==len(samples)-1:
            path=dest/f'sheet_{i//12:02d}.jpg';page.save(path,quality=90);sheets.append(str(path))
    result={'seed':20261029,'sampling':'up to2 per source/category/format/kind stratum',
        'samples':len(samples),'strata':len(groups),'read_errors':errors,'sheets':sheets,
        'caveat':'Small inspection sample, not exhaustive semantic verification.'}
    (dest/'sample_locators.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2))
    (dest/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);a=parser.parse_args();main(a.root)
