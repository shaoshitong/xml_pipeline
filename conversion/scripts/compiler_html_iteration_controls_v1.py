"""Publish and bind actual HTML source compiler controls before heldout use."""
import json
from pathlib import Path
import sqlite3

import compiler_html_iteration_case_v1 as case
import compiler_html_iteration_program_v1 as program

R=program.R
RECEIPT=R/'release/compiler_html_source_adapter_controls_v5/4b43fe1938124358baa91c8b67db028f/receipt.json'
RECEIPT_SHA='4e0ce6b6f3cde6e29a906e0ea7359fe24d06db47850f831bcb50234dd23f52a1'


def prepare():
    payload=RECEIPT.read_bytes()
    if program.sha(payload)!=RECEIPT_SHA:raise ValueError('HTML_adapter_control_receipt_changed')
    receipt=json.loads(payload)
    compiler,_=case.bindings('html')
    if receipt['configuration']!=compiler.configuration() or receipt['all_actual_controls_passed'] is not True:
        raise ValueError('HTML_adapter_controls_not_current_final_frontend')
    output=program.CONTROLS.parent
    output.mkdir(parents=True,exist_ok=False)
    positives=[];negatives=[];qualified=[]
    for role,items in [('positive',[receipt['positive']]),('negative',receipt['negative'])]:
        for item in items:
            _,blob=program.checked(item['record_file']);record=json.loads(blob)
            row={'id':item['id'],'name':item.get('kind','fresh_source_positive'),
                 'candidate':item['record_file'],'qa':item['quality_report'],
                 'fresh_png':item['fresh_png'],'source_code_sha256':record['source_code_sha256'],
                 'source_image_sha256':record['source_image_sha256'],
                 'regenerated_font_proof':item.get('complete_font_proof_regenerated_and_independently_passed',False)}
            program.check_control_case(row,role)
            (positives if role=='positive' else negatives).append(row)
            if role=='positive':
                _,qa_blob=program.checked(row['qa']);qa=json.loads(qa_blob)
                with sqlite3.connect('file:'+str(case.W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
                    source=json.loads(db.execute('select input_record from jobs where id=?',(item['id'],)).fetchone()[0])
                quality_directory=Path(row['qa']['file']).resolve().parent
                qualified.append(case.publish(record,source,qa,quality_directory))
    manifest=output/'qualified.jsonl'
    program.immutable(manifest,b''.join(program.raw(row) for row in qualified))
    proof={'schema':'compiler_html_iteration_controls_v1','producer':program.asset(Path(__file__).resolve()),
           'adapter_receipt':program.asset(RECEIPT),'frozen_frontend':compiler.configuration(),
           'positive_cases':positives,'negative_cases':negatives,
           'positives':[row['qa'] for row in positives],'negatives':[row['qa'] for row in negatives],
           'legacy_regression':receipt['legacy_regression'],'qualified_manifest':program.asset(manifest),
           'legacy_scope':'Existing HTMLV4 pair is preserved and reverified under its frozen policy; this does not claim it satisfies the new source-ink compiler.',
           'new_development_qualified':len(qualified),'heldout_consumed':0,'external_model_calls':0}
    program.immutable(program.CONTROLS,program.raw(proof))
    bundle=program.control_bundle(compiler)
    program.check_controls(bundle)
    return {'controls':str(program.CONTROLS),'proof_sha256':program.sha(program.CONTROLS.read_bytes()),
            'new_positive_pairs':len(qualified),'actual_negative_controls':len(negatives),
            'legacy_qualified_preserved':True,'heldout_selected':False,'model_calls':0}


if __name__=='__main__':print(json.dumps(prepare()))
