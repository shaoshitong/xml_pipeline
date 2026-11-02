"""Full RO using an existing consumed candidate and explicit private stale fixture."""
from pathlib import Path
import json,sqlite3,os
import compiler_svg_source_viewport_iteration_case_v1 as case
import compiler_svg_source_viewport_frontend_v1 as compiler
import compiler_svg_source_viewport_quality_ro_v1 as quality
from compiler_types_program_v1 import R,W,asset,immutable,raw,sha

def main():
 id='2e7a3239abab0f76415a23602e1e611e7c9f6b4fedf265ef1a7739fffc7007e6';record_file=R/'clean/compiler_svg_source_viewport_graphviz_v1/2e'/id/'49ae45a7b0d14915b2e2bb8d1fec9bb6/record.json';directory=R/'release/compiler_iterations/controls/svg_source_surface_controls_20261101_v1';work=W/'svg_source_surface_stale_lease_control_v1';work.mkdir(exist_ok=False)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as d:
  real=d.execute('select * from jobs where id=?',(id,)).fetchone();schema=d.execute("select sql from sqlite_master where name='jobs'").fetchone()[0]
 fixture=list(real);fixture[12]=99999999
 if case.canonical_owner_evidence(fixture[12])['decision']!='definite_dead_ENOENT':raise ValueError('private_stale_fixture_not_definitely_dead')
 fixture_db=work/'explicit_PRIVATE_fixture.sqlite'
 with sqlite3.connect(fixture_db)as d:d.execute(schema);d.execute('insert into jobs values ('+','.join('?'for _ in fixture)+')',fixture)
 fixture=tuple(fixture);qa_db,owner,owner_file=case.quality_database(fixture,work,database=fixture_db);record=json.loads(record_file.read_bytes());record['canonical_owner_guard']=owner;proposal=work/'candidate_record.json';immutable(proposal,raw(record));qa_work=W/'prototype/candidate_quality_ro_v1/svg_source_surface_explicit_PRIVATE_stale_lease_v1';q=quality.verify(id,proposal,R,Path(compiler.__file__),qa_work,database=qa_db);case.full_quality(q,record)
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as d:after=d.execute('select * from jobs where id=?',(id,)).fetchone()
 with sqlite3.connect('file:'+str(fixture_db)+'?mode=ro',uri=True)as d:fixture_after=d.execute('select * from jobs where id=?',(id,)).fetchone()
 if after!=real or fixture_after!=fixture:raise RuntimeError('real_or_private_fixture_authority_was_mutated')
 proof={'schema':'svg_source_surface_explicit_PRIVATE_stale_lease_full_RO_control_v1','ok':True,'id':id,'existing_candidate_only_no_new_normal_conversion':True,'private_fixture_not_real_canonical_lease':True,'real_original_worker_pid':real[12],'fixture_worker_pid':fixture[12],'real_canonical_raw13_sha256_before':sha(raw(list(real))),'real_canonical_raw13_sha256_after':sha(raw(list(after))),'real_canonical_raw13_unchanged':True,'private_fixture_raw13_unchanged':True,'owner_guard':owner,'owner_guard_audit':asset(owner_file),'record':asset(proposal),'quality':asset(qa_work/'report.json'),'all8_full_QA_passed':True,'frozen_frontend':compiler.configuration(),'case_module':asset(case.__file__),'model_calls':0,'new_heldout':0,'normal_frontend_attempts':0}
 immutable(directory/'private_stale_lease_full_ro_v1.json',raw(proof));print(json.dumps({'proof':asset(directory/'private_stale_lease_full_ro_v1.json'),'all8_full_QA_passed':True,'real_canonical_unchanged':True,'case_module':asset(case.__file__)}),flush=True)
if __name__=='__main__':main()
