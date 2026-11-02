"""Actual pool-constructor -> worker-contract check on two consumed originals.

Reads only canonical metadata; no cohort reservation, normal conversion or QA.
"""
import copy
import json
from pathlib import Path
import sqlite3

import compiler_mermaid_alpha_iteration_pool_v2 as pool
import compiler_mermaid_alpha_iteration_program_v2 as program


def main():
    directory=program.R/'release/compiler_iterations/controls/mermaid_alpha_source_contract_20261101_v3'
    directory.mkdir(parents=True,exist_ok=False)
    runtime=json.loads((program.R/'release/compiler_iterations/controls/mermaid_alpha_runtime_controls_20261101_v3/proof.json').read_bytes())
    compiler,_=program.case.bindings('mermaid');rows=[]
    with sqlite3.connect('file:'+str(program.W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as database:
        for item in runtime['cases']:
            identifier=item['id'];job=database.execute('select * from jobs where id=?',(identifier,)).fetchone()
            source=json.loads(job[4]);request=pool.request_from_job(job,source,compiler.UNITS['mermaid'])
            program.validate_source_requests([request])
            bad=copy.deepcopy(request)
            bad['source']={key:source[key]for key in ('category','format','source','code_sha256','image_sha256')}
            try:program.validate_source_requests([bad])
            except ValueError as error:
                if str(error)!='selected_worker_requires_complete_canonical_source_record':raise
            else:raise RuntimeError('minimal_scope_summary_would_be_dispatched')
            if database.execute('select * from jobs where id=?',(identifier,)).fetchone()!=job:raise RuntimeError('canonical_metadata_changed')
            rows.append({'id':identifier,'source_fields':len(source),'source_input_record_sha256':program.sha(job[4].encode()),
                         'request_sha256':pool.sha(pool.raw(request)),'full_canonical_source_passed':True,'five_field_summary_rejected':True,
                         'baseline_snapshot_verified':True,'canonical_metadata_unchanged':True})
    proof={'schema':'mermaid_alpha_actual_source_contract_v3','ok':True,'cases':rows,'reservations':0,'candidate_dispatches':0,'model_calls':0,
           'producers':{name:program.asset(path)for name,path in
                        [('preflight',Path(__file__).resolve()),('pool',Path(pool.__file__).resolve()),('program',Path(program.__file__).resolve()),
                         ('case',Path(program.case.__file__).resolve()),('controller',Path(program.controller.__file__).resolve())]},
           'frozen_frontend':compiler.configuration(),'goal_complete':False}
    target=directory/'proof.json';target.write_bytes(program.raw(proof))
    print(json.dumps({'proof':program.asset(target),'cases':rows,'candidate_dispatches':0},ensure_ascii=False))


if __name__=='__main__':main()
