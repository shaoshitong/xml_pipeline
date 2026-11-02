import collections,json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite',timeout=60);by={}
for fmt in ['python','svg']:
 rows=[(i,json.loads(r)) for i,r in db.execute('select id,output_record from jobs where format=? and output_record is not null',(fmt,)) if '_v2' in json.loads(r).get('conversion_method','')];issues=collections.Counter();missing=0;ssims=[]
 for i,r in rows:
  issues.update(x['reason'] for x in r['svg_conversion']['issues']);missing+=sum(not (R/r[k]).exists() for k in ['code_file','image_file','original_reference','original_source_code']);ssims.append(r['metrics'].get('source_render_vs_drawio_ssim_512',r['metrics'].get('drawio_vs_source_render_ssim_512')))
 by[fmt]={'v2_outputs':len(rows),'missing_payloads':missing,'issues':dict(issues),'source_vs_native_ssim_min':min(ssims) if ssims else None}
print(json.dumps(by))
