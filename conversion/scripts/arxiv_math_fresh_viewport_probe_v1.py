"""One previously unvalidated author source, no PDF import or old output changes."""
from pathlib import Path
import json,sqlite3,sys,xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';sys.path.insert(0,str(R/'conversion/scripts'))
import arxiv_math_source_repair_v1 as repair
from arxiv_math_uniform_viewport_renderer_v1 import MathSynced,POLICY
D=P/'math_uniform_viewport_probe_v1';D.mkdir(exist_ok=True)
if (D/'selection.json').exists():
 row=json.loads((D/'selection.json').read_text());case=D/'cases'/row['id']
 if (case/'record.json').exists():print((case/'record.json').read_text());raise SystemExit()
else:
 with sqlite3.connect((P/'math_source_replay_v1/once.sqlite').as_uri()+'?mode=ro',uri=True) as c:known={x[0] for x in c.execute('select id from cases')}
 choices=[]
 with sqlite3.connect((P/'recent_ai_source_expansion_v2/once.sqlite').as_uri()+'?mode=ro',uri=True) as c:
  for raw, in c.execute("select record from pdfs where status='technical_failure_review'"):
   row=json.loads(raw)
   if row['id'] in known or not row.get('author_xml_recovered') or 'MathJaxRender' not in row.get('reason',''):continue
   code=R/row['author_xml_file']
   if not code.exists() or not row['paper'][:2].isdigit() or int(row['paper'][:2])<23:continue
   facts=repair.facts(code.read_text())
   if facts['edges']<15:continue
   choices.append((code.stat().st_size,row))
 assert choices,'no_fresh_probe_available'
 row=sorted(choices,key=lambda a:a[0])[0][1];row['original_once_database']='clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/once.sqlite';(D/'selection.json').write_text(json.dumps(row,indent=2))
case=D/'cases'/row['id'];case.mkdir(parents=True,exist_ok=True);file=case/'input.json';file.write_text(json.dumps(row))
repair.D=D;repair.MathSynced=MathSynced;repair.POLICY=POLICY
result=repair.work(file)
print(json.dumps(dict(id=row['id'],paper=row['paper'],status=result['status'],reason=result.get('reason'),no_prior_math_validation=True,new_PDF_import_calls=0)))
