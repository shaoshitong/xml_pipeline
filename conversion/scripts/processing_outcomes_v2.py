"""Full-scope accounting: qualified + explicitly abandoned + pending = inputs."""
import argparse
import datetime
import json
import sqlite3
from pathlib import Path

ROOT=Path('/backup/shaoshitong/img2code_20261029')
EXPECTED={'scientific_diagram':107161,'poster':24743}
TOTAL=sum(EXPECTED.values())
TABLE='processing_outcomes_v2'


def utcnow():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sync(db,expected=EXPECTED):
    expected_total=sum(expected.values())
    db.execute('begin immediate')
    try:
        categories=dict(db.execute('select category,count(*) from jobs group by category'))
        assert categories==expected,'Authoritative input scope changed'
        db.execute('''create table if not exists processing_outcomes_v2(
          id TEXT PRIMARY KEY,category TEXT NOT NULL,format TEXT NOT NULL,
          source_code_hash TEXT NOT NULL,source_image_hash TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status in ('pending','qualified','abandoned')),
          reason TEXT,record TEXT,updated_at TEXT NOT NULL,
          CHECK(status!='abandoned' or (reason is NOT NULL and length(trim(reason))>0)),
          CHECK(status!='qualified' or record is NOT NULL))''')
        stamp=utcnow()
        # Existing identities are never overwritten by a new pipeline version.
        db.execute('''insert into processing_outcomes_v2
          select j.id,j.category,j.format,json_extract(j.input_record,'$.code_sha256'),
          json_extract(j.input_record,'$.image_sha256'),'pending',NULL,NULL,?
          from jobs j where not exists(select 1 from processing_outcomes_v2 o where o.id=j.id)''',(stamp,))
        count=db.execute('select count(*) from '+TABLE).fetchone()[0]
        assert count==expected_total,'Outcome registry does not cover exact original input IDs'
        assert not db.execute('''select 1 from processing_outcomes_v2 o join jobs j on j.id=o.id
          where o.category!=j.category or o.format!=j.format or
          o.source_code_hash!=json_extract(j.input_record,'$.code_sha256') or
          o.source_image_hash!=json_extract(j.input_record,'$.image_sha256') limit 1''').fetchone(),'Original outcome identity changed'
        qualified=0
        for identifier,raw in db.execute('''select id,output_record from jobs where state='accepted'
          and json_extract(output_record,'$.automatic_quality_policy') is not NULL''').fetchall():
            r=json.loads(raw)
            original=db.execute('select source_code_hash,source_image_hash from '+TABLE+' where id=?',(identifier,)).fetchone()
            assert r['id']==r['source_pair_sha256']==identifier
            assert original==(r['source_code_sha256'],r['source_image_sha256'])
            assert all(r[key].startswith('clean/') for key in ('code_file','image_file','original_reference','original_source_code'))
            record={key:r[key] for key in ('id','source_code_sha256','source_image_sha256','code_file','code_sha256',
                    'image_file','image_sha256','original_reference','original_source_code','automatic_quality_policy','automatic_quality_audit')}
            payload=json.dumps(record,sort_keys=True)
            qualified+=db.execute('''update processing_outcomes_v2 set status='qualified',reason=NULL,record=?,updated_at=?
              where id=? and (status!='qualified' or record IS NOT ?)''',(payload,stamp,identifier,payload)).rowcount
        # A superseded/corrupt qualification is pending again, never silently kept.
        db.execute('''update processing_outcomes_v2 set status='pending',reason='qualification_revision_changed',updated_at=?
          where status='qualified' and not exists(select 1 from jobs j where j.id=processing_outcomes_v2.id
          and j.state='accepted' and json_extract(j.output_record,'$.automatic_quality_policy') is not NULL
          and json_extract(j.output_record,'$.code_sha256')=json_extract(processing_outcomes_v2.record,'$.code_sha256')
          and json_extract(j.output_record,'$.image_sha256')=json_extract(processing_outcomes_v2.record,'$.image_sha256'))''',(stamp,))
        db.execute('''update processing_outcomes_v2 set status='pending',reason='abandoned_revision_changed_waiting_program_qa',updated_at=?
          where status='abandoned' and json_extract(record,'$.code_sha256') is not NULL
          and exists(select 1 from jobs j where j.id=processing_outcomes_v2.id and j.output_record is not NULL
          and (json_extract(j.output_record,'$.code_sha256')!=json_extract(processing_outcomes_v2.record,'$.code_sha256')
          or json_extract(j.output_record,'$.image_sha256')!=json_extract(processing_outcomes_v2.record,'$.image_sha256')))''',(stamp,))
        states=dict(db.execute('select status,count(*) from '+TABLE+' group by status'))
        assert sum(states.values())==expected_total
        db.commit()
    except BaseException:
        db.rollback();raise
    return {'at':stamp,'input_total':expected_total,'categories':categories,'outcomes':states,
            'qualified_revisions_updated':qualified,'all_inputs_have_exact_identity_record':True,
            'completion_rule':'qualified + abandoned = inputs, pending = 0',
            'completion_proven':False,'goal_complete':False,
            'history_budget_status':'Historical usage ledger import is required before any new model call. Unknown history is not zero.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args();work=args.root/'conversion'
    db=sqlite3.connect(work/'jobs.sqlite',timeout=60)
    result=sync(db)
    (work/'processing_outcomes_v2_status.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
