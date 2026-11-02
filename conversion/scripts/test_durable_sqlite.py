import sqlite3,tempfile,multiprocessing,time,json
from pathlib import Path
from native_worker import W,now
from durable_sqlite import begin,commit

def hold(path,q):
 d=sqlite3.connect(path);d.execute('begin immediate');d.execute('insert into events values ("first")');q.put(True);time.sleep(.8);d.commit();d.close()

def main():
 with tempfile.TemporaryDirectory(dir=W) as td:
  path=str(Path(td)/'test.sqlite');d=sqlite3.connect(path,timeout=.03);d.execute('pragma journal_mode=wal');d.execute('create table events (value text primary key)');d.commit();q=multiprocessing.Queue();p=multiprocessing.Process(target=hold,args=(path,q));p.start();q.get(timeout=5);n=begin(d,5);d.execute('insert into events values ("second")');commit(d);p.join(5);assert p.exitcode==0;assert n>0 and list(d.execute('select value from events order by value'))==[('first',),('second',)];d.execute('begin immediate');d.execute('insert into events values ("rollback")');d.rollback();assert d.execute('select count(*) from events').fetchone()[0]==2;d.close();r={'at':now(),'ok':True,'real_contention_retries':n,'committed_rows':2,'rollback_not_published':True};(W/'durable_sqlite_tests.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
if __name__=='__main__':main()
