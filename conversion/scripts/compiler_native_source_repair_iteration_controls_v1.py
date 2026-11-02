"""Bind actual native-source controls to the fixed native compiler program."""
import datetime
import json
from pathlib import Path
import sqlite3
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
ADAPTER=R/'release/compiler_native_source_repair_v1/controls/physical_runs_20261101_v2/receipt.json'
DEFAULT=R/'release/compiler_iterations/controls/native_source_font_runs_controls_20261101_v1'


def main(output=DEFAULT):
 import compiler_native_source_repair_frontend_v1 as frontend
 import compiler_native_source_repair_iteration_case_v1 as case
 import compiler_native_source_repair_iteration_program_v1 as program
 import compiler_types_program_v1 as common
 from qualified_index_v4 import manifest_row,require_source
 output=Path(output).resolve();adapter=json.loads(ADAPTER.read_bytes());configuration=frontend.configuration()
 if not adapter['ok']or adapter['configuration']!=configuration:raise ValueError('native_source_actual_controls_or_pins_changed')
 positive=[];negative=[];accepted={}
 for role in ('positive','negative'):
  for row in adapter[role]:
   value={**row};program.check_control_case(value,role,configuration)
   if role=='positive':
    _,payload=common.checked(row['candidate']);record=json.loads(payload);_,payload=common.checked(row['qa']);qa=json.loads(payload)
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:source=json.loads(db.execute('select input_record from jobs where id=?',(row['id'],)).fetchone()[0])
    require_source(record,source);out={**record,'quality_state':'accepted_original_native_complete_text_node_fonts_v1','automatic_quality_policy':qa['quality_policy'],'automatic_quality_audit':str(Path(row['qa']['file']).relative_to(R)),'accepted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_configuration':dict(external_model_calls=0,deterministic_compiler=True)}
    accepted[row['id']]=manifest_row(out,R)[0];positive.append(value)
   else:negative.append(value)
 output.mkdir(parents=True,exist_ok=False);common.immutable(output/'qualified.jsonl',b''.join(common.raw(accepted[i])for i in sorted(accepted)))
 proof=dict(schema='compiler_native_source_repair_iteration_controls_v1',frozen_frontend=configuration,producer=common.asset(Path(__file__)),adapter_receipt=common.asset(ADAPTER),positive_cases=positive,negative_cases=negative,actual_endpoint_editing_reports=[row['qa']for row in positive],qualified_manifest=common.asset(output/'qualified.jsonl'),new_heldout_consumed=0,model_calls=0,canonical_mutations=0)
 common.immutable(output/'proof.json',common.raw(proof));program.check_controls({**proof,'definition':common.asset(output/'proof.json')});return common.asset(output/'proof.json')
