import json,sqlite3,uuid
from native_worker import W
from tex_dependency_repair_v2 import initialize,publish,TABLE
directory=W/'runtime_tests'/('tex_dependency_v2_'+uuid.uuid4().hex[:12]);directory.mkdir(parents=True)
db=sqlite3.connect(directory/'isolated.sqlite',timeout=2)
db.execute('create table jobs (id TEXT PRIMARY KEY,state TEXT,error TEXT,input_record TEXT,input_manifest TEXT,worker_pid INTEGER,updated_at TEXT,output_record TEXT)');db.commit();initialize(db)
error='failed to open input file "pgfmodulebending.code.tex"';files=[{'name':'pgfmodulebending.code.tex','ok':True}]
for id,state,pid in [('ready','needs_fallback',None),('busy','tikz_rendering',123),('accepted','accepted',None),('changed','needs_fallback',None),('unavailable','needs_fallback',None)]:
    db.execute('insert into jobs values (?,?,?,?,?,?,NULL,?)',(id,state,error,'changed' if id=='changed' else '{}','{}',pid,'preserve-native-output'))
db.commit()
checks={}
for id in ('ready','busy','accepted','changed','unavailable'):
    result=publish(db,(id,error,'{}','{}'),files if id!='unavailable' else [dict(files[0],ok=False)])
    expected='requeued' if id=='ready' else 'dependency_unavailable' if id=='unavailable' else 'stale_or_busy'
    assert result==expected,(id,result);checks[id]=result
assert db.execute('select state,error,output_record from jobs where id="ready"').fetchone()==('queued',None,'preserve-native-output')
db.execute('update jobs set state="needs_fallback",error=? where id="ready"',(error,));db.commit()
checks['no_same_error_loop']=publish(db,('ready',error,'{}','{}'),files);assert checks['no_same_error_loop']=='already_recorded'
checks['availability_change']=publish(db,('unavailable',error,'{}','{}'),files);assert checks['availability_change']=='requeued'
assert db.execute('select count(*) from jobs where output_record="preserve-native-output"').fetchone()[0]==5
out={'ok':True,'checks':checks,'isolated_database':str(directory/'isolated.sqlite'),'production_database_mutated':False}
(W/'tex_dependency_v2_tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
