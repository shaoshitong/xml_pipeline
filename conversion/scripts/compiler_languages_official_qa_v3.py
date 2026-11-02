import pathlib,sys,json,uuid
R=pathlib.Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_languages_source_layout_v3 as c
from deterministic_candidate_quality_ro_v1 import verify
report=W/c.VERSION/'development/4b4ba8956dbc433e99ba30c80016fb2b/report.json';x=json.loads(report.read_text());rows=[];dest=report.parent/'official_QA.json'
for row in x['results']:
 if not row['ok']:continue
 work=W/'prototype/candidate_quality_ro_v1'/('mermaid_cli_v3_'+row['id'][:12]+'_'+uuid.uuid4().hex)
 q=verify(row['id'],row['record_file'],R,pathlib.Path(c.__file__),work);z={'id':row['id'],'record_file':row['record_file'],'ok':q['ok'],'failures':q['failures'],'evidence_file':q['evidence_file']};rows.append(z);dest.write_text(json.dumps({'official_qa':'deterministic_candidate_quality_ro_v1.verify','results':rows,'unseen_consumed':0,'canonical_mutations':0,'model_calls':0},indent=2));print(json.dumps(z),flush=True)
print(json.dumps({'report':str(dest),'passed':sum(r['ok'] for r in rows),'total':len(rows),'unseen_consumed':0,'release_publication':False}),flush=True)
