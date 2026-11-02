"""Small trusted index backed by immutable full metadata and dirty versions.

Publication updates the cache in the job transaction. Bootstrap only reads full
payloads whose exact payload-version is missing, rather than rescanning every
large accepted record for each batch. Legacy acceptances without automatic QA
are explicitly excluded from the qualified training index.
"""
import hashlib,json,sqlite3,uuid
from pathlib import Path
from auto_quality_common import checked,clean_path
from native_worker import R,W,now
from durable_sqlite import begin,commit

TABLE='qualified_index_cache_v4'
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def initialize(db):
    db.execute('''create table if not exists qualified_index_cache_v4(
      id TEXT PRIMARY KEY,payload_version INTEGER NOT NULL,trusted INTEGER NOT NULL,
      manifest_record TEXT,metadata_sha256 TEXT,updated_at TEXT NOT NULL)''')


def version(db,identifier):
    exists=db.execute("select 1 from sqlite_master where type='table' and name='auto_quality_dirty_v2'").fetchone()
    row=db.execute('select payload_version from auto_quality_dirty_v2 where id=?',(identifier,)).fetchone() if exists else None
    assert row is not None,'Exact payload journal is missing for '+identifier
    return row[0]


def atomic(path,blob):
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.qualified-index.tmp');tmp.write_bytes(blob);tmp.replace(path)


def require_source(record,original):
    assert record['category'] in ('scientific_diagram','poster'),'Outside requested categories'
    assert record['source_code_sha256']==original['code_sha256'] and record['source_image_sha256']==original['image_sha256'],'Qualified source hashes changed'
    assert all(record[key]==original[key] for key in ('category','source')),'Qualified source category or dataset changed'
    assert record['source_format']==original['format'],'Qualified source format changed'


def manifest_row(record,root=R):
    root=Path(root)
    assert record['id']==record['source_pair_sha256'],'Qualified manifest original ID changed'
    for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),
                       ('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:
        checked(root,record[key],record[digest])
    data=(json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode()
    digest=sha(data)
    directory=clean_path(root,record['code_file']).parent
    metadata=directory/('accepted_metadata.'+digest[:24]+'.json')
    if metadata.exists():
        assert sha(metadata.read_bytes())==digest,'Immutable accepted metadata was changed'
    else:atomic(metadata,data)
    fields=('id','source_pair_sha256','source','category','source_format','format',
            'code_file','code_sha256','image_file','image_sha256','original_reference','original_source_code',
            'source_code_sha256','source_image_sha256','conversion_method','model','model_configuration',
            'automatic_quality_policy','automatic_quality_audit','accepted_at_utc')
    result={key:record[key] for key in fields if key in record}
    result.update(status='qualified',schema_version=4,metadata_file=str(metadata.relative_to(root)),metadata_sha256=digest)
    return result,digest


def cache_publication(db,record,root=R):
    """Caller owns the job writer transaction; no independent commit here."""
    assert db.in_transaction
    initialize(db)
    assert record.get('automatic_quality_policy'),'Automatic qualification policy is required'
    source=db.execute('select input_record from jobs where id=?',(record['id'],)).fetchone()
    assert source is not None,'Missing original job'
    require_source(record,json.loads(source[0]))
    compact,digest=manifest_row(record,root)
    db.execute('insert or replace into '+TABLE+' values(?,?,?,?,?,?)',
               (record['id'],version(db,record['id']),1,json.dumps(compact,ensure_ascii=False),digest,now()))


def refresh(root=R):
    root=Path(root);work=root/'conversion'
    db=sqlite3.connect(work/'jobs.sqlite',timeout=2);begin(db);initialize(db);commit(db)
    db.execute('begin')
    rows=db.execute('''select j.id,j.output_record,j.input_record,coalesce(d.payload_version,0)
      from jobs j left join auto_quality_dirty_v2 d on d.id=j.id
      left join qualified_index_cache_v4 c on c.id=j.id
      where j.state='accepted' and (c.id is NULL or c.payload_version!=coalesce(d.payload_version,0))''').fetchall()
    db.rollback();changed=0
    for identifier,raw,input_raw,payload_version in rows:
        r=json.loads(raw);trusted=bool(r.get('automatic_quality_policy'));compact=None;digest=None
        if trusted:
            original=json.loads(input_raw)
            require_source(r,original)
            compact,digest=manifest_row(r,root)
        begin(db)
        state=db.execute('select state from jobs where id=?',(identifier,)).fetchone()
        if state==('accepted',) and version(db,identifier)==payload_version:
            db.execute('insert or replace into '+TABLE+' values(?,?,?,?,?,?)',
                       (identifier,payload_version,int(trusted),json.dumps(compact,ensure_ascii=False) if compact else None,digest,now()));changed+=1
        commit(db)
    db.close();return changed


def export(root=R):
    root=Path(root);work=root/'conversion';refreshed=refresh(root)
    db=sqlite3.connect(work/'jobs.sqlite',timeout=60);db.execute('begin')
    missing=db.execute('''select count(*) from jobs j left join auto_quality_dirty_v2 d on d.id=j.id
      left join qualified_index_cache_v4 c on c.id=j.id
      where j.state='accepted' and (c.id is NULL or c.payload_version!=coalesce(d.payload_version,0))''').fetchone()[0]
    assert missing==0,'Accepted metadata changed during qualified-index bootstrap; retry export'
    target=root/'release/qualified_drawio_manifest.inprogress.jsonl';tmp=target.with_suffix('.v4.tmp')
    count=0;digest=hashlib.sha256()
    with tmp.open('wb') as stream:
        for raw, in db.execute('''select c.manifest_record from qualified_index_cache_v4 c
          join jobs j on j.id=c.id join auto_quality_dirty_v2 d on d.id=c.id
          where j.state='accepted' and c.trusted=1 and c.payload_version=d.payload_version order by c.id'''):
            line=(raw+'\n').encode();stream.write(line);digest.update(line);count+=1
    legacy=db.execute('''select count(*) from qualified_index_cache_v4 c join jobs j on j.id=c.id
       where j.state='accepted' and c.trusted=0''').fetchone()[0]
    tmp.replace(target);db.rollback();db.close()
    result={'at':now(),'qualified_records':count,'legacy_unvalidated_excluded':legacy,'refreshed_full_records':refreshed,
            'manifest':str(target.relative_to(root)),'sha256':digest.hexdigest(),'inprogress':True,'goal_complete':False}
    atomic(work/'qualified_index_v4_status.json',(json.dumps(result,indent=2)+'\n').encode())
    return result
