import json,sqlite3,pyarrow.parquet as pq
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');d=sqlite3.connect(R/'conversion/jobs.sqlite');id,r=d.execute('select id,input_record from jobs where format="python" and source="allenai--CoSyn-400K" order by id limit 1').fetchone();r=json.loads(r);p=pq.ParquetFile(R/r['clean_file']);off=r['clean_row'];g=0
while off>=p.metadata.row_group(g).num_rows:off-=p.metadata.row_group(g).num_rows;g+=1
print('SCHEMA',str(p.schema_arrow));cols=[name for name in p.schema_arrow.names if name not in ('image','images','panels')];row=p.read_row_group(g,columns=cols).slice(off,1).to_pylist()[0]
for k,v in row.items():print(k,repr(v)[:7000])
