"""Independent replay/QA of an existing development candidate; no generation."""
from pathlib import Path
import datetime, hashlib, json, sqlite3, sys, uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import html_source_flex_paragraph_frontend_v1 as frontend
import compiler_html_source_flex_paragraph_quality_ro_v1 as quality
sha=lambda b:hashlib.sha256(b).hexdigest()
ident=sys.argv[1];key=sys.argv[2];d=R/'clean/html_flex_paragraph_development_v1'/key/ident
previous=json.loads((d/'result.json').read_text());assert previous['generation_ok']
claim=(d/'normal_once_claim.json').read_bytes();cfg=frontend.configuration();assert json.loads(claim)['configuration']==cfg
p=Path(previous['candidate_record_file']);record=p.read_bytes()
with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:job=db.execute('select * from jobs where id=?',(ident,)).fetchone()
work=W/'prototype/candidate_quality_ro_v1'/('HTML_flex_'+ident[:12]+'_'+uuid.uuid4().hex)
out=quality.verify(ident,p,R,Path(frontend.__file__),work)
assert p.read_bytes()==record and (d/'normal_once_claim.json').read_bytes()==claim and frontend.configuration()==cfg
with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True) as db:assert db.execute('select * from jobs where id=?',(ident,)).fetchone()==job
report={'id':ident,'source_core_key':key,'quality_ok':out.get('ok'),'quality_failures':out.get('failures'),'checks':list(out.get('checks',{})),'quality_policy':out.get('quality_policy'),'quality_report':str(work/'report.json'),'existing_candidate_unchanged':True,'generation_calls':0,'original_generation_claim_preserved':True,'model_calls':0,'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
with (d/'independent_QA_summary.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report,ensure_ascii=False),flush=True)
