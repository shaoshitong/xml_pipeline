"""Add actual prior source executions to global freshness exclusions; no outcomes used."""
from pathlib import Path
import hashlib,json,sqlite3
R=Path('/backup/shaoshitong/img2code_20261029')
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 chart=R/'clean/matplotlib_plot_pipeline_20261102_v1';inputs={r['id']:r for r in map(json.loads,(chart/'inputs.jsonl').read_text().splitlines())};seen={};evidence=[]
 for root in [chart,chart/'vector_backend_rollout_v6']:
  database=root/'once.sqlite'
  with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)as db:
   db.execute('begin');rows=db.execute("select id,record from cases where json_extract(record,'$.source_execution_completed')=1 order by id").fetchall()
  for identifier,body in rows:
   record=json.loads(body);assert record['id']==identifier and record['source_execution_completed']is True
   original=inputs[identifier];row=dict(id=identifier,source_code_sha256=original['payloads']['code']['expected_sha256'],source_image_sha256=original['payloads']['image']['expected_sha256'],reason='Previously executed actual chart source; exclude known source/provenance families from future unseen selection. No scores or failures used.')
   if identifier in seen:assert seen[identifier]==row
   seen[identifier]=row
  evidence.append(dict(database=str(database.relative_to(R)),actual_source_execution_rows=len(rows),database_sha256=sha(database.read_bytes())))
 p=R/'release/compiler_iterations/development_seen_v1/matplotlib_actual_execution_metadata_20261102_v1.jsonl';body=''.join(json.dumps(seen[k],sort_keys=True)+'\n'for k in sorted(seen))
 if p.exists():assert p.read_text()==body
 else:p.write_text(body);p.chmod(0o444)
 result=dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),rows=len(seen),evidence=evidence,source_or_image_payloads_read=False,candidate_or_quality_outcomes_used=False,new_source_executions=0,new_normal_calls=0,new_QA_calls=0,model_calls=0)
 print(json.dumps(result))
if __name__=='__main__':main()
