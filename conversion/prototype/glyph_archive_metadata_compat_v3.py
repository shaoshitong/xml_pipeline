"""CAS-only repair of the independent glyph archive locator.

The immutable Range proof, current XML/PNG/source, queue state and all visual
results are unchanged. Harness's historical source archive link is restored
from the hashed previous record; the new prior-pair archive has its own key.
"""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from durable_sqlite import begin,commit

R=Path('/backup/shaoshitong/img2code_20261029');FIELD='html_actual_text_alignment';OWNER='conversion/auto_quality_glyph_alignment_v3'
COLUMNS='state,output_record,worker_pid,error,updated_at,input_record,input_manifest'
IDLE=('rendered','needs_quality_repair','harness_review_pending')
sha=lambda blob:hashlib.sha256(blob).hexdigest()


def _owned(root,relative,digest):
    path=(root/relative).resolve();assert path.is_relative_to((root/OWNER).resolve()),'Unowned glyph proof';blob=path.read_bytes();assert sha(blob)==digest,'Glyph proof hash changed';return blob


def proposed_record(old,root=R):
    root=Path(root);link=old[FIELD];bad=old.get('previous_candidate_archive')
    assert bad and (root/bad).resolve().is_relative_to((root/OWNER).resolve()),'No misplaced glyph archive locator'
    assert old['code_sha256']==link['output_code_sha256'] and old['image_sha256']==link['output_image_sha256'],'Stale glyph revision'
    proof=json.loads(_owned(root,link['proof'],link['proof_sha256']));previous=json.loads(_owned(root,link['previous_record'],link['previous_record_sha256']))
    assert all(previous[key]==old[key] for key in ('id','source_code_sha256','source_image_sha256'))
    assert proof['files']['previous_record']=={'file':link['previous_record'],'sha256':link['previous_record_sha256']}
    previous_link=previous.get('previous_candidate_archive')
    assert not previous_link or (root/previous_link).resolve().is_relative_to((root/'conversion/harness_sessions').resolve()),'Previous Harness archive locator is also invalid'
    for pathkey,hashkey in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:
        path=(root/old[pathkey]).resolve();assert path.is_relative_to((root/'clean').resolve());assert sha(path.read_bytes())==old[hashkey],'Payload changed during metadata-only migration'
    new=copy.deepcopy(old);new['glyph_alignment_prior_pair_archive']=bad
    if previous_link:new['previous_candidate_archive']=previous_link
    else:new.pop('previous_candidate_archive',None)
    a,b=copy.deepcopy(old),copy.deepcopy(new)
    for key in ('previous_candidate_archive','glyph_alignment_prior_pair_archive'):a.pop(key,None);b.pop(key,None)
    assert a==b,'Metadata migration changed a non-archive field'
    return new


def model_running(db,id):
    present=db.execute('select 1 from sqlite_master where type="table" and name="harness_queue_v3"').fetchone()
    return bool(present and db.execute('select 1 from harness_queue_v3 where id=? and state="running"',(id,)).fetchone())


def repair_one(db,id,root=R,resolver=None):
    root=Path(root);begin(db);pointer=None;prior_pointer=None;replacement=None;committed=False
    try:
        prior=db.execute('select '+COLUMNS+' from jobs where id=?',(id,)).fetchone()
        if not prior or prior[0] not in IDLE or prior[2] is not None or model_running(db,id):db.rollback();return {'id':id,'state':'skipped_busy_or_nonidle'}
        old=json.loads(prior[1]);bad=old.get('previous_candidate_archive') or ''
        if not old.get(FIELD) or not (root/bad).resolve().is_relative_to((root/OWNER).resolve()):db.rollback();return {'id':id,'state':'no_migration_needed'}
        new=proposed_record(old,root)
        if resolver is None:
            from harness_source_provenance import resolve
            resolver=resolve
        resolver(new)
        pointer=(root/old['code_file']).parent/'conversion.json';prior_pointer=pointer.read_bytes();assert json.loads(prior_pointer)==old,'Canonical pointer differs from the complete job revision'
        assert db.execute('select '+COLUMNS+' from jobs where id=?',(id,)).fetchone()==prior and not model_running(db,id),'Metadata CAS ownership changed'
        replacement=(json.dumps(new,ensure_ascii=False,indent=2)+'\n').encode();work=root/'conversion/glyph_archive_metadata_compat_v3'/id/sha(prior[1].encode());work.mkdir(parents=True,exist_ok=True)
        (work/'before_record.json').write_text(prior[1]);(work/'after_record.json').write_bytes(replacement)
        temporary=pointer.with_name(pointer.name+'.glyph-archive-'+uuid.uuid4().hex+'.tmp');temporary.write_bytes(replacement);temporary.replace(pointer)
        db.execute('update jobs set output_record=? where id=?',(json.dumps(new,ensure_ascii=False),id));commit(db);committed=True
        result={'id':id,'state':'repaired_archive_metadata_only','old_record_sha256':sha(prior[1].encode()),'new_record_sha256':sha(json.dumps(new,ensure_ascii=False).encode()),'code_sha256':old['code_sha256'],'image_sha256':old['image_sha256'],'previous_candidate_archive':new.get('previous_candidate_archive'),'glyph_alignment_prior_pair_archive':new['glyph_alignment_prior_pair_archive'],'source_and_glyph_proof_unchanged':True,'queue_unchanged':True,'audit':str(work.relative_to(root))}
        try:(work/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
        except OSError:pass  # The committed canonical/SQL metadata remains authoritative.
        return result
    except Exception:
        if not committed and pointer is not None and prior_pointer is not None and replacement is not None and pointer.exists() and pointer.read_bytes()==replacement:
            temporary=pointer.with_name(pointer.name+'.glyph-archive-rollback.tmp');temporary.write_bytes(prior_pointer);temporary.replace(pointer)
        db.rollback();raise
