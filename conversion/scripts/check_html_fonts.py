import json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';D=sqlite3.connect(W/'jobs.sqlite');rows=[]
for id,raw in D.execute('select id,output_record from jobs where format="html" and output_record is not null order by id limit 8'):
 o=json.loads(raw);old=W/'version_archive'/id/'html_v2/conversion.json';a=json.loads(old.read_text()) if old.exists() else {};rows.append({'id':id,'before':a.get('metrics'),'after':o['metrics'],'fonts':o.get('rendered_font_mapping'),'quality':o['quality_state']})
print(json.dumps(rows))
