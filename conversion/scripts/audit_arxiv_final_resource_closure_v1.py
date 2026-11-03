"""Check current standalone editable-resource closure for all frozen additions."""
from pathlib import Path
import datetime,hashlib,json,zipfile
from arxiv_author_native_assets_v1 import dependencies
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/goal500_final_delivery_v1'
def main():
 rows=[json.loads(x) for x in (D/'accepted_new_pairs.jsonl').read_text().splitlines()];errors=[];assets=0
 with zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war') as war:
  for row in rows:
   try:
    code=R/row['code_file'];blob=code.read_bytes();assert hashlib.sha256(blob).hexdigest()==row['code_sha256'];dep=dependencies(blob,code,code,war);assets+=len(dep['assets'])
    if dep['issues']:errors.append(dict(id=row['id'],issues=dep['issues']))
   except Exception as error:errors.append(dict(id=row['id'],error=type(error).__name__+':'+str(error)))
 result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),ok=not errors,pairs_checked=len(rows),dependency_records_checked=assets,no_original_PDF_or_original_directory_fallback=True,errors=errors,CPU_host='HKUST3',new_PDF_import_calls=0,new_model_calls=0)
 (D/'resource_closure_final.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);return not result['ok']
if __name__=='__main__':raise SystemExit(main())
