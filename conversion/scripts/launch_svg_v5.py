import json,sqlite3,subprocess
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');owner=W/'svg_v5_repair_owner.json'
if owner.exists():
 o=json.loads(owner.read_text());p=Path('/proc')/str(o['pid'])/'cmdline';assert not (p.exists() and b'svg_v5_repair_batch.py' in p.read_bytes()),'v5 already running'
for id in ['003be89c70c277f8f2ff9158c8cd54feca9bd48f4e7a03896f3cd22dd97dda16','007a96b73bbe8a013947b63ba530c03e8387a08945b76e9389d7aab1306dafdc']:
 r=json.loads((W/'vee_native_pilot'/id/'report.json').read_text());assert r['source_coverage']['ok'];assert len(r['movement']['moves'])==2*r['source_coverage']['native_edges']
d=sqlite3.connect(W/'jobs.sqlite',timeout=60);id='003be89c70c277f8f2ff9158c8cd54feca9bd48f4e7a03896f3cd22dd97dda16';row=d.execute('select * from svg_v5_repairs where id=?',(id,)).fetchone();(W/'vee_native_pilot'/id/'previous_batch_failure.json').write_text(json.dumps(row)+'\n');d.execute('delete from svg_v5_repairs where id=? and state="failed"',(id,));d.commit()
with (W/'svg_v5_repair.log').open('ab') as log:
 p=subprocess.Popen(['/home/shaoshitong/anaconda3/bin/python',str(W/'scripts/svg_v5_repair_batch.py'),'--workers','4'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'pid':p.pid,'workers':4,'scope':'Remaining Graphviz arrow candidates; strict vee geometry matching, source-port bindings, actual native renders and no automatic acceptance.'}))
