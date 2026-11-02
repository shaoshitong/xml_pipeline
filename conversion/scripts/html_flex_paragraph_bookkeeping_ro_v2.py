"""Fresh birth metadata discovery; indexed selected-ID owner/qualified lookups."""
import json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
def owners():
 from html_flex_paragraph_bookkeeping_ro_v1 import owners as release_owners
 from initial_conversion_process_v1 import identity
 out=release_owners()
 # Bounded directory metadata discovery, never load queue rows. These are
 # additive fixed-program protocols with a pinned freeze and birth owner.
 for root in sorted((R/'clean').glob('*/fixed_program*/owner.json')):
  try:
   program=root.parent;freeze=program/'freeze.json';ledger=program/'dispatcher.sqlite'
   if not freeze.is_file()or not ledger.is_file():continue
   owner=json.loads(root.read_bytes());current=identity(owner['pid'])
   if current is None or current['state']in('Z','X')or str(current['start_ticks'])!=str(owner['start_ticks']):continue
   with sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True,timeout=10)as db:
    schema=db.execute("select sql from sqlite_master where type='table'and name='cases'").fetchone()
   if not schema:continue
   out.append({'ledger':str(ledger),'owner':owner,'freeze':str(freeze),'program':str(program),'table':'cases','phase_ID_index':True})
  except(FileNotFoundError,KeyError,ValueError,sqlite3.Error):continue
 return out

def guard(ident,catalog,exclude_program=None):
 from html_flex_paragraph_bookkeeping_ro_v1 import guard as release_guard
 from initial_conversion_process_v1 import identity
 active=release_guard(ident,[e for e in catalog if e.get('table')!='cases'])['owners']
 exclude=Path(exclude_program).resolve()if exclude_program else None
 for entry in catalog:
  if entry.get('table')!='cases'or exclude==Path(entry['program']).resolve():continue
  born=entry['owner'];current=identity(born['pid'])
  if current is None or current['state']in('Z','X')or str(current['start_ticks'])!=str(born['start_ticks']):continue
  with sqlite3.connect('file:'+entry['ledger']+'?mode=ro',uri=True,timeout=30)as db:
   for phase in('C','mass'):
    row=db.execute('select status from cases where phase=?and id=?',(phase,ident)).fetchone()
    if row and row[0]in('claimed','incomplete'):
     active.append({'ledger':entry['ledger'],'owner':born,'phase':phase,'status':row[0]})
    # Queued fixed-program C/mass are intended owners unless stop-dispatch
    # explicitly closes dispatch, as with prior release ledgers.
    elif row and row[0]=='queued':
     control=Path(entry['program'])/'control.json'
     if not control.is_file()or json.loads(control.read_bytes()).get('stop_dispatch')is not True:active.append({'ledger':entry['ledger'],'owner':born,'phase':phase,'status':row[0]})
 return {'id':ident,'active':bool(active),'owners':active,'read_only':True,'query_scope':'indexed_selected_ID_and_phase_only','new_clean_fixed_programs_discovered':sum(e.get('table')=='cases'for e in catalog)}

def qualification_hint(ident):
 from html_flex_paragraph_bookkeeping_ro_v1 import qualification_hint as lookup
 return lookup(ident)
