"""Read-only canonical lease proof and one-row private QA metadata binding.

The canonical raw13 tuple never changes. Only a definitely stale worker_pid is
cleared in a private, read-only QA copy; source/model/output fields stay exact.
"""
from pathlib import Path
import hashlib,json,sqlite3
from compiler_plantuml_engine_canonical_claim_v1 import diagnose
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
COLUMNS=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
raw=lambda value:(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()
sha=lambda value:hashlib.sha256(value).hexdigest()
def immutable(path,payload):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('xb')as f:f.write(payload)
 path.chmod(0o444)
def read_row(database,identifier):
 with sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True,timeout=30)as db:
  db.execute('pragma query_only=ON');return db.execute('select*from jobs where id=?',(identifier,)).fetchone()
def quality_database(job,work,database=None):
 database=Path(database or W/'jobs.sqlite').resolve(strict=True);work=Path(work)
 if len(job)!=13 or read_row(database,job[0])!=job:raise RuntimeError('infrastructure_SVG_canonical_raw13_changed_before_quality_lease')
 evidence=diagnose(dict(zip(COLUMNS,job)))
 if not evidence['conversion_allowed']:raise ValueError('deferred_live_or_uncertain_canonical_worker_claim')
 proof=dict(schema='SVG_analytic_private_QA_lease_binding_v1',canonical_database=str(database),canonical_raw13_sha256=sha(raw(list(job))),canonical_row=list(job),claim_before=evidence,canonical_mutations=0,private_copy=False)
 if job[12]is None:return database,proof,None
 if evidence['status']not in ('stale_dead','stale_pid_reused'):raise ValueError('deferred_unproved_canonical_lease_cannot_make_private_QA_copy')
 with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)as db:schema=db.execute("select sql from sqlite_master where type='table'and name='jobs'").fetchone()[0]
 owner=work/'canonical_owner_guard';owner.mkdir(parents=True,exist_ok=False);private=list(job);private[12]=None;private_db=owner/'readonly_QA_metadata.sqlite'
 with sqlite3.connect(private_db)as db:db.execute(schema);db.execute('insert into jobs values('+','.join('?'for _ in private)+')',private)
 stored=read_row(private_db,job[0]);different=[i for i,(a,b)in enumerate(zip(job,stored))if a!=b]
 if different!=[12]or stored[12]is not None:raise RuntimeError('infrastructure_private_QA_copy_changed_original_payload')
 private_db.chmod(0o444);proof.update(private_copy=True,private_database=str(private_db),private_database_sha256=sha(private_db.read_bytes()),private_row_sha256=sha(raw(list(stored))),changed_columns=['worker_pid'])
 immutable(owner/'canonical_raw13.json',raw(list(job)));immutable(owner/'private_raw13.json',raw(list(stored)));immutable(owner/'proof.json',raw(proof))
 if read_row(database,job[0])!=job:raise RuntimeError('infrastructure_SVG_canonical_changed_by_private_lease_preparation')
 return private_db,proof,owner/'proof.json'
def verify_after_quality(job,qa_database,proof,work):
 database=Path(proof['canonical_database'])
 if read_row(database,job[0])!=job or sha(raw(list(job)))!=proof['canonical_raw13_sha256']:raise RuntimeError('infrastructure_SVG_canonical_raw13_changed_during_independent_QA')
 after=diagnose(dict(zip(COLUMNS,job)))
 if not after['conversion_allowed']:raise ValueError('deferred_canonical_worker_claim_became_live_or_uncertain_during_QA')
 expected=list(job)
 if proof['private_copy']:expected[12]=None
 if read_row(qa_database,job[0])!=tuple(expected):raise RuntimeError('infrastructure_SVG_private_QA_raw13_changed')
 if proof['private_copy']and sha(Path(qa_database).read_bytes())!=proof['private_database_sha256']:raise RuntimeError('infrastructure_SVG_readonly_private_QA_database_changed')
 value=dict(schema='SVG_analytic_private_QA_lease_postcheck_v1',canonical_raw13_unchanged=True,private_raw13_unchanged=True,claim_after=after,canonical_mutations=0,private_copy_only_clears_worker_pid=proof['private_copy'])
 immutable(Path(work)/'canonical_owner_guard_after_quality.json',raw(value));return value
