"""Preserve real existing H9 development normals before the unattended release."""
import json,sqlite3
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
BASE=R/'release/compiler_iterations/source_core_attempts/manual_catalog_20261101_v4_tikz_node_paint.json'
BASE_SHA='643501535d705a7ac847681cc00ba436def8efbdd50ed6eb91fc39d2adc2f37d'
OUTPUT=R/'release/compiler_iterations/source_core_attempts/manual_catalog_20261101_v5_html_paragraph.json'
RECEIPT=OUTPUT.with_name('html_paragraph_development_normals_20261101_v9.json')
DEV=W/'html_source_paragraph_frontend_v9_development/dea41ca976e54da3ad440d8083ca16a9'
PLAN=[DEV/'0bc37fc196e3f7ea12094ff9fe36f687bf2ff2c17308c27c7435ba5677ed4d20.json',DEV/'2a019af6eb56e0ce6c4b8a4f19f990090a8e6ae9f4fa1403e5f521db53cbd2e2.json',W/'html_paragraph_final_qualified_regressions_v9/525da3198f544bc182d2606edd5b27d5/conversion.json']

def run():
 import compiler_types_program_v1 as common
 import html_source_paragraph_frontend_v9 as frontend
 import compiler_source_core_attempts_v3 as history
 configuration=frontend.configuration();identity=history.core_identity(configuration);base=json.loads(BASE.read_bytes())
 if common.sha(BASE.read_bytes())!=BASE_SHA or len(base['entries'])!=9 or base['schema']!='source_core_manual_attempt_catalog_v3':raise ValueError('frozen_TikZ_plus_previous_manual_history_changed')
 rows=[];entries=list(base['entries']);before=[]
 for path in PLAN:
  attempt=json.loads(path.read_bytes());record=attempt.get('record');assert attempt.get('ok')is True and isinstance(record,dict),'real_prior_frontend_normal_result_missing';identifier=record['id']
  with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as database:job=database.execute('select*from jobs where id=?',(identifier,)).fetchone()
  before.append(job);source=json.loads(job[4]);manifest=json.loads(job[11]);assert(source['pair_sha256'],source['format'],source['code_sha256'],source['image_sha256'])==(identifier,'html',record['source_code_sha256'],record['source_image_sha256'])
  assert common.sha((R/manifest['source_code']).read_bytes())==source['code_sha256']and common.sha((R/manifest['reference_image']).read_bytes())==source['image_sha256']
  assert common.sha((R/record['code_file']).read_bytes())==record['code_sha256']and common.sha((R/record['image_file']).read_bytes())==record['image_sha256']
  index=len(rows);rows.append(dict(id=identifier,normal_conversion_receipt_count=1,frontend=common.asset(path),source=source,actual_candidate_XML=common.asset(R/record['code_file']),actual_candidate_PNG=common.asset(R/record['image_file']),conservative_same_SOURCE_core_budget_preserved=True,earlier_development_QA_only_revisions_do_not_reset_budget=True))
  entries.append(dict(id=identifier,source_core_key=identity['key'],source=source,receipt={},rows_key='normal_history',row_index=index,normal_count_key='normal_conversion_receipt_count',frontend=common.asset(path),requires_unchanged_canonical=False))
 with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as database:after=[database.execute('select*from jobs where id=?',(row['id'],)).fetchone()for row in rows]
 assert before==after and frontend.configuration()==configuration
 receipt=dict(schema='HTML_paragraph_existing_real_development_normal_history_v9',source_core=identity,configuration=configuration,normal_history=rows,producer=common.asset(Path(__file__)),base_catalog=common.asset(BASE),canonical_SHA_before=common.sha(common.raw(before)),canonical_SHA_after=common.sha(common.raw(after)),canonical_original_unchanged_during_history_publication=True,normal_calls_in_this_publication=0,new_heldout=0,models=0,conservative_budget_mapping='Historical SOURCE executions are preserved even when later QA-only or view-restoration repairs change frozen configuration; no normal Source call can be recovered by wrapper/QA version changes.')
 common.immutable(RECEIPT,common.raw(receipt));reference=common.asset(RECEIPT)
 for entry in entries[9:]:entry['receipt']=reference
 common.immutable(OUTPUT,common.raw(dict(schema='source_core_manual_attempt_catalog_v3',entries=entries,base_catalog=common.asset(BASE),additional_source_normal_history=reference,producer=common.asset(Path(__file__)),shared_default_catalog_unchanged=True)))
 events=history.collect(configuration,root=R,catalog=str(OUTPUT.relative_to(R)));history.validate(events,configuration,root=R)
 assert {row['id']for row in events}=={row['id']for row in rows}and len(events)==3
 for row in rows:assert history.guard(row['id'],row['source'],configuration,root=R,catalog=str(OUTPUT.relative_to(R)))['already_attempted']is True
 OUTPUT.chmod(0o444);RECEIPT.chmod(0o444);return dict(catalog=common.asset(OUTPUT),receipt=reference,core=identity,normal_distinct_HTML_ids=len(events),all_entries=len(entries),all_actual_normals_preserved=True)
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
