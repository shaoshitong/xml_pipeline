"""Real isolated controller: ordinary source rejection, then existing positive QA.

The positive is a consumed control candidate, never another normal conversion.
No unseen ID is consumed and no canonical job is modified.
"""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import compiler_mermaid_alpha_iteration_batch_v2 as controller
import compiler_mermaid_alpha_iteration_case_v2 as case
import compiler_mermaid_alpha_iteration_program_v2 as program

R,W,raw,sha=controller.R,controller.W,controller.base.raw,controller.base.sha
DIRECTORY=R/'release/compiler_iterations/controls/mermaid_alpha_runtime_controls_20261101_v2'
RUN='mermaid_alpha_runtime_preflight_20261101_v2'
REJECTION='88b8cc887c9ad3406a764c4757f4d7e99bd0fb90a337e1a64b94c4db53776192'


def main():
    DIRECTORY.mkdir(parents=True,exist_ok=False)
    compiler,quality=case.bindings('mermaid');config=compiler.configuration()
    controls=program.control_bundle(compiler);program.check_controls(controls)
    positive=controls['positive_cases'][0]
    manifest=[];snapshots={}
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30)as db:
        for seq,identifier in enumerate((REJECTION,positive['id']),1):
            job=db.execute('select * from jobs where id=?',(identifier,)).fetchone();snapshots[identifier]=job
            source=json.loads(job[4]);old=json.loads(job[9])if job[9]else{}
            row=dict(seq=seq,id=identifier,source=source,compiler_unit=compiler.UNITS['mermaid'],cluster='consumed_runtime_control',
                     source_record_sha256=sha((job[9]or'').encode()),baseline_code_sha256=old.get('code_sha256'),baseline_image_sha256=old.get('image_sha256'),
                     evaluation_phase='candidate'if seq==1 else'control_positive')
            if seq==2:row['existing_development_candidate']=str(R/positive['candidate']['file'])
            manifest.append(row)
    manifest_path=DIRECTORY/'input.jsonl';manifest_path.write_bytes(b''.join(raw(row)for row in manifest))
    pins={**controller.base.pins(),**config['pins']}
    for module in (controller,case,program,quality):
        path=Path(module.__file__).resolve();pins[str(path)]=sha(path.read_bytes())
    for name in ('initial_conversion_process_v1.py','compiler_typed_runtime_failure_v1.py','compiler_mermaid_alpha_iteration_overlap_v1.py','compiler_mermaid_alpha_qualifications_v2.py'):
        path=W/'scripts'/name;pins[str(path)]=sha(path.read_bytes())
    freeze=dict(pins=pins,input_sha256=sha(manifest_path.read_bytes()),
                qa_policy_sha256=sha(raw({'scope':'consumed_runtime_entrypoint_control','source_policy':config['policy'],'quality':quality.VERSION})),
                predicate_hashes={compiler.UNITS['mermaid']:sha(raw({'source_policy':config['policy']}))})
    freeze.update(implementation_identity=controller.implementation_identity(freeze),implementation_identity_sha256=controller.implementation_digest(freeze))
    freeze_path=DIRECTORY/'freeze.json';freeze_path.write_bytes(raw(freeze))
    run=controller.FLOOR/RUN;controller.create(run,manifest_path,freeze_path,'development')
    with(DIRECTORY/'controller.log').open('xb')as log:
        result=subprocess.run([sys.executable,'-B',str(Path(controller.__file__).resolve()),'run','--run-id',RUN,'--workers','1','--case-timeout','900'],stdin=subprocess.DEVNULL,stdout=log,stderr=log)
    if result.returncode:raise RuntimeError('real_alpha_controller_failed:'+str(result.returncode))
    rows=[]
    with sqlite3.connect('file:'+str(run/'status.sqlite')+'?mode=ro',uri=True)as db:
        for identifier,status,attempts,payload in db.execute('select id,status,attempts,result from samples order by seq'):
            value=json.loads(payload)
            rows.append(dict(id=identifier,status=status,attempts=attempts,reason=value.get('reason'),infrastructure_failure=value.get('infrastructure_failure')is True,
                             quality_report=value.get('quality_report'),evidence_directory=value.get('evidence_directory')))
    if len(rows)!=2 or rows[0]['status']!='abandoned'or rows[0]['reason']!='source_cli_intrinsic_canvas_mismatch'or rows[0]['infrastructure_failure']or rows[1]['status']!='qualified'or any(row['attempts']!=1 for row in rows):raise RuntimeError('real_controller_failure_continue_positive_contract_not_met:'+json.dumps(rows))
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:
        if any(db.execute('select * from jobs where id=?',(identifier,)).fetchone()!=job for identifier,job in snapshots.items()):raise RuntimeError('canonical_jobs_changed')
    proof=dict(schema='compiler_mermaid_alpha_runtime_controls_v2',ok=True,frozen_frontend=config,
               producer=program.asset(Path(__file__).resolve()),run=str(run),cases=rows,
               consumed_source_rejection_normal_attempts=1,positive_normal_reconversions=0,unseen_consumed=0,canonical_jobs_unchanged=True,
               typed_failure_continues_to_next_sample=True,model_calls=0,goal_complete=False)
    (DIRECTORY/'proof.json').write_bytes(raw(proof))
    print(json.dumps({'proof':program.asset(DIRECTORY/'proof.json'),'cases':rows,'goal_complete':False},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
