"""Finite source/native triangle rule replay on already-captured actual DOM."""
import sys,json,collections,sqlite3,datetime
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';P=W/'prototype/svg_source_profile_scope_v1/triangle_marker_cohort_v1';sys.path[:0]=[str(W/'prototype'),str(W/'scripts')]
import svg_native_triangle_marker_v1 as rule
import auto_quality_source_vector_v2 as prior
try:from auto_quality_common_v4 import registration_record
except ImportError:from auto_quality_common_v3 import registration_record
rows=json.loads((P/'cohort_report.json').read_text())['cohort'];D=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);results=[]
for row in rows:
 id=row['id'];out={'id':id,'input_code_sha256':row['code_sha256'],'input_image_sha256':row['image_sha256'],'source_code_sha256':row['source_code_sha256']}
 try:
  state,worker,raw=D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone();record=json.loads(raw);assert worker is None,'busy';assert record['code_sha256']==row['code_sha256'] and record['image_sha256']==row['image_sha256'],'revision changed';xml=prior._read_clean(record['code_file'],record['code_sha256']).decode();prior._identity(record,xml);dom=json.loads((P/id/'fresh_source_dom.json').read_text());assert dom['sceneCapture']['recordCodeSha256']==record['code_sha256'] and dom['sceneCapture']['sourceCodeSha256']==record['source_code_sha256'] and dom['sceneCapture']['sourceImageSha256']==record['source_image_sha256'],'capture revision mismatch';reference=prior._read_clean(record['original_reference'],record['source_image_sha256']);_,contract=registration_record(record,reference,xml);offset=contract['original_page_offset'] if contract else [0,0];proposal=rule.propose_from_scene(dom,xml,offset);out.update(ok=proposal['ok'],complete_source_marker_coverage=proposal.get('complete_source_marker_coverage'),marker_count=len(proposal['markers']),failures=proposal['failures']);(P/id/'triangle_rule_proposal.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+'\n')
  if proposal['ok']:(P/id/'triangle_candidate.drawio').write_text(proposal['candidate_xml']);out['replay']=rule.verify_candidate_from_scene(dom,xml,proposal['candidate_xml'],proposal,offset)
 except Exception as error:out['error']=repr(error)
 results.append(out)
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':rule.POLICY,'implementation_sha256':rule.sha(Path(rule.__file__).read_bytes()),'count':len(results),'candidate_records':sum(bool(r.get('ok')) for r in results),'complete_marker_records':sum(bool(r.get('complete_source_marker_coverage')) for r in results),'failure_reasons':dict(collections.Counter(f['reason'] for r in results for f in r.get('failures',[]))),'records':results,'scope':'Source-rule proposals/replay only, not native/render/ROI accepted or published.'};(P/'triangle_rule_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='records'}|{'candidate_ids':[r['id'] for r in results if r.get('ok')],'errors':dict(collections.Counter(r.get('error') for r in results)),'report':str(P/'triangle_rule_report.json')},ensure_ascii=False),flush=True)
