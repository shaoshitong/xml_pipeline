import json,sqlite3,uuid
from native_worker import W
from tex_xcolor_repair_batch import initialize,claim,publish
folder=W/'runtime_tests'/('xcolor_state_'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True);db=sqlite3.connect(folder/'isolated.sqlite',timeout=2)
db.execute('create table jobs (id TEXT PRIMARY KEY,state TEXT,error TEXT,input_record TEXT,input_manifest TEXT,output_record TEXT,worker_pid INTEGER,attempts INTEGER,updated_at TEXT)');db.execute('create table tikz_renders (id TEXT PRIMARY KEY,state TEXT,record TEXT,error TEXT,updated_at TEXT)');db.commit();initialize(db)
expected=('needs_fallback','Option clash for package xcolor.','{}','{}','preserved',None);pid=98765
for id in ('ready','busy','accepted','changed','ownership'):
    vals=list(expected)
    if id=='busy':vals[0]='tikz_rendering';vals[-1]=123
    if id=='accepted':vals[0]='accepted'
    if id=='changed':vals[2]='new'
    db.execute('insert into jobs values (?,?,?,?,?,?,?,0,NULL)',(id,*vals))
db.commit();checks={}
for id in ('ready','busy','accepted','changed'):
    ok=claim(db,id,expected,pid);assert ok==(id=='ready');checks[id]=ok
publish(db,'ready',expected,pid,{'source_preparation':{'method':'test'}},None,'compiled')
assert db.execute('select state,worker_pid,output_record,attempts from jobs where id="ready"').fetchone()==('tikz_source_rendered',None,'preserved',1)
assert not claim(db,'ready',expected,pid)
assert claim(db,'ownership',expected,pid);db.execute('update jobs set worker_pid=123 where id="ownership"');db.commit()
try:publish(db,'ownership',expected,pid,None,'fake','compile_failed')
except AssertionError:db.rollback();checks['changed_ownership_rejected']=True
else:raise AssertionError('ownership overwrite')
out={'ok':True,'checks':checks,'production_database_mutated':False,'isolated_database':str(folder/'isolated.sqlite')};(W/'xcolor_state_tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
