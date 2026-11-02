"""Actual pool-constructor -> worker-contract check on two consumed originals.

Reads only canonical metadata; no cohort reservation, normal conversion or QA.
"""
import copy
import json
from pathlib import Path
import sqlite3

import compiler_mermaid_alpha_iteration_pool_v3 as pool
import compiler_mermaid_alpha_iteration_program_v2 as program


def main():
    directory=program.R/'release/compiler_iterations/controls/mermaid_alpha_source_contract_20261101_v5'
    directory.mkdir(parents=True,exist_ok=False)
    runtime=json.loads((program.R/'release/compiler_iterations/controls/mermaid_alpha_runtime_controls_20261101_v3/proof.json').read_bytes())
    compiler,_=program.case.bindings('mermaid');rows=[]
    with sqlite3.connect('file:'+str(program.W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as database:
        for item in runtime['cases']:
            identifier=item['id'];job=database.execute('select * from jobs where id=?',(identifier,)).fetchone()
            source=json.loads(job[4]);request=pool.request_from_job(job,source,compiler.UNITS['mermaid'])
            program.validate_source_requests([request])
            legacy_support=compiler.static_support(job)
            support=pool.static_support_from_job(compiler,job)
            if support.get('supported')is not True or support.get('unit')!=compiler.UNITS['mermaid']:
                raise RuntimeError('real_source_pool_static_support_contract_failed:'+str(support))
            if legacy_support.get('supported')is not False or not any("tuple"in reason for reason in legacy_support.get('reasons',[])):
                raise RuntimeError('legacy_positional_job_failure_not_reproduced')
            bad=copy.deepcopy(request)
            bad['source']={key:source[key]for key in ('category','format','source','code_sha256','image_sha256')}
            try:program.validate_source_requests([bad])
            except ValueError as error:
                if str(error)!='selected_worker_requires_complete_canonical_source_record':raise
            else:raise RuntimeError('minimal_scope_summary_would_be_dispatched')
            if database.execute('select * from jobs where id=?',(identifier,)).fetchone()!=job:raise RuntimeError('canonical_metadata_changed')
            rows.append({'id':identifier,'source_fields':len(source),'source_input_record_sha256':program.sha(job[4].encode()),
                         'request_sha256':pool.sha(pool.raw(request)),'full_canonical_source_passed':True,'five_field_summary_rejected':True,
                         'baseline_snapshot_verified':True,'canonical_metadata_unchanged':True,
                         'actual_source_pool_static_supported':True,'legacy_tuple_interface_failure_reproduced':True,
                         'source_support':support,'legacy_tuple_failure':legacy_support['reasons']})
    proof={'schema':'mermaid_alpha_actual_source_contract_v5','ok':True,'cases':rows,'reservations':0,'candidate_dispatches':0,'model_calls':0,
           'producers':{name:program.asset(path)for name,path in
                        [('preflight',Path(__file__).resolve()),('pool',Path(pool.__file__).resolve()),('program',Path(program.__file__).resolve()),
                         ('case',Path(program.case.__file__).resolve()),('controller',Path(program.controller.__file__).resolve())]},
           'frozen_frontend':compiler.configuration(),'goal_complete':False}
    target=directory/'proof.json';target.write_bytes(program.raw(proof))
    print(json.dumps({'proof':program.asset(target),'cases':rows,'candidate_dispatches':0},ensure_ascii=False))


if __name__=='__main__':main()
