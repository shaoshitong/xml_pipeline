"""Compile any specified immutable real source then run the nonpublishing binder."""
import argparse,hashlib,json,sqlite3,subprocess,uuid
from pathlib import Path
from native_worker import R,W
from tikz_execution_graph import compile_execution_graph
p=argparse.ArgumentParser();p.add_argument('--id',required=True);a=p.parse_args()
db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);raw,=db.execute('select output_record from jobs where id=?',(a.id,)).fetchone();db.close();record=json.loads(raw)
source=(R/record['original_source_code']).resolve();assert source.is_relative_to(R/'clean');data=source.read_bytes();assert hashlib.sha256(data).hexdigest()==record['source_code_sha256']
work=W/'tikz_execution_graph_prototype'/('additional_'+uuid.uuid4().hex[:12])/a.id
result=compile_execution_graph(data,work);print(json.dumps({'id':a.id,'execution_graph_ok':result['ok'],'error':result.get('error'),'graph_failures':result.get('graph',{}).get('failures'),'proof':str(work/'execution_graph.json')}),flush=True)
if result['ok']:
 r=subprocess.run(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/tikz_execution_binding_pilot.py'),'--id',a.id,'--proof',str(work/'execution_graph.json')]);raise SystemExit(r.returncode)
