"""Short explicit writer transactions with bounded retries for WAL contention."""
import sqlite3,time,random

def begin(db,seconds=300):
 if db.in_transaction:raise RuntimeError('Begin retry requires no open transaction')
 until=time.monotonic()+seconds;attempts=0
 while True:
  try:db.execute('begin immediate');return attempts
  except sqlite3.OperationalError as e:
   if not ('locked' in str(e).lower() or 'busy' in str(e).lower()) or time.monotonic()>=until:raise
   db.rollback();attempts+=1;time.sleep(min(2,.08*(1.3**min(attempts,15)))+random.uniform(0,.1))

def commit(db,seconds=60):
 until=time.monotonic()+seconds
 while True:
  try:db.commit();return
  except sqlite3.OperationalError as e:
   if not ('locked' in str(e).lower() or 'busy' in str(e).lower()) or time.monotonic()>=until:raise
   # SQLITE_BUSY at COMMIT leaves the transaction active; retry it, never replay mutations.
   time.sleep(.1+random.uniform(0,.1))
