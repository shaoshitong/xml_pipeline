import json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/round2_heldout_v1/unseen_protocol_20261101_v2'
rows=[json.loads(x) for x in (P/'manifest.jsonl').read_text().splitlines()]
db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True)
out=[]
for provider in sorted({r['provider'] for r in rows}):
 r=next(r for r in rows if r['provider']==provider);x=db.execute('select input_record,input_manifest from jobs where id=?',(r['id'],)).fetchone();rec=json.loads(x[0]);man=json.loads(x[1])
 out.append({'provider':provider,'format':r['source']['format'],'record':{k:v for k,v in rec.items() if k in ('profile','raw_file','raw_row','clean_file','clean_row','code_key','image_key','source_manifest','source_manifest_line','gold_code_provenance','image_provenance','provenance')},'annotation_provenance':{k:v for k,v in rec.get('annotation',{}).items() if k in ('arxiv_id','paper_id','paper_file','template_archive','template_dir')},'source_metadata':man.get('source_metadata')})
print(json.dumps(out,ensure_ascii=False))
