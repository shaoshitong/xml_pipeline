import json,sqlite3,collections
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/round2_heldout_v1/unseen_protocol_20261101_v2'
rows=[json.loads(x) for x in (P/'manifest.jsonl').read_text().splitlines()]
db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True)
out=[]
for fmt in sorted({r['source']['format'] for r in rows}):
 r=next(r for r in rows if r['source']['format']==fmt)
 x=db.execute('select source,input_record,input_manifest from jobs where id=?',(r['id'],)).fetchone()
 rec=json.loads(x[1]);man=json.loads(x[2])
 out.append({'format':fmt,'provider':x[0],'record_keys':sorted(rec),'manifest_keys':sorted(man),'record_nested_keys':{k:sorted(v)[:60] for k,v in rec.items() if isinstance(v,dict)},'nonmedia_values':{k:v for k,v in rec.items() if k.lower() in ('split','source','dataset','provider','repo','source_file','source_row','row_index','index','sample_id','record_id','original_id','metadata','original_metadata') and not isinstance(v,dict)}})
print(json.dumps(out,ensure_ascii=False))
