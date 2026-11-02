"""Birth-verified owner catalog; selected-ID SQL only, no full queued-row scan."""
import json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
def owners():
 from compiler_mermaid_alpha_qualifications_v2 import discover_ledger_paths
 from compiler_mermaid_alpha_iteration_overlap_v2 import live_owner
 result=[]
 for p in discover_ledger_paths(R):
  f=p.parent/'freeze.json'
  if not f.is_file():continue
  frozen=json.loads(f.read_bytes());owner=live_owner(p.parent/'owner.json',frozen)
  if owner:result.append({'ledger':str(p),'owner':owner,'freeze':str(f)})
 return result
def guard(ident,catalog):
 from initial_conversion_process_v1 import identity,same_birth
 active=[]
 for entry in catalog:
  born=entry['owner'];current=identity(born['pid'])
  if current is None or current['state']in('Z','X')or str(current['start_ticks'])!=str(born['start_ticks']):continue
  with sqlite3.connect('file:'+entry['ledger']+'?mode=ro',uri=True,timeout=30)as db:
   row=db.execute('select status from samples where id=?',(ident,)).fetchone()
  if row and row[0]in('queued','running'):
   control=Path(entry['ledger']).parent/'control.json'
   # The existing controller's stop flag drains running cases and forbids new
   # claims. Its untouched queued sources no longer have a future dispatch.
   if row[0]=='queued'and control.is_file()and json.loads(control.read_bytes()).get('stop_dispatch')is True:continue
   active.append({'ledger':entry['ledger'],'owner':born,'status':row[0]})
 return {'id':ident,'active':bool(active),'owners':active,'read_only':True,'query_scope':'indexed_selected_ID_only'}
def qualification_hint(ident):
 """Current status hint only; caller verifies complete accepted assets if true."""
 from compiler_mermaid_alpha_qualifications_v2 import discover_ledger_paths
 evidence=[]
 for path in discover_ledger_paths(R):
  with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=30)as db:
   if 'samples'not in {r[0]for r in db.execute("select name from sqlite_master where type='table'")}:continue
   columns={r[1]for r in db.execute('pragma table_info(samples)')}
   if not{'id','status'}<=columns:continue
   row=db.execute('select status from samples where id=?',(ident,)).fetchone()
  if row and row[0]=='qualified':evidence.append({'ledger':str(path),'id':ident,'status':'qualified'})
 return {'qualified_hint':bool(evidence),'evidence':evidence,'query_scope':'indexed_selected_ID_only','read_only':True}
