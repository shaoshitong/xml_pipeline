"""Apply root review only to the exact, independently audited candidate; defer live workers."""
import json,sqlite3
from native_worker import R,W,now,sha
from durable_sqlite import begin,commit

NOTES={
'0b4d8f904638e102675cf373b09496594eab6c9bfd948e01a460c56fb405a785': 'Root compared full original/native images side by side. All nine source nodes retained, including four orange cylinders and five blue process rectangles; nine directed connections and all relationship labels retained. The dashed red impact branch, cylinder top ellipses, spacing, original colors, text and gray label backgrounds remain visible. Native arrowheads and antialiasing have small contour differences; no material missing content, wrong topology, displaced node or clipping observed.',
'0b8e6086486b77fdc223c81e902f2927af8f9a3be730f9f2133c68479b637fdb': 'Root compared full original/native images side by side. All twelve source nodes retained, including three green database cylinders and the three intentionally isolated top-row participants. All nine directed connectors, feedback loop, edge labels, source colors, text and gray label backgrounds retained. Native arrowheads and antialiasing have small contour differences; no material omitted participant, changed connection, displaced layout or clipping observed.'}
audit=json.loads((W/'mermaid_compound_node_release_audit.json').read_text());assert audit['ok'];D=sqlite3.connect(W/'jobs.sqlite',timeout=2);results=[]
for a in audit['results']:
 id=a['id'];assert id in NOTES and a['actual_render_after_harness_roundtrip_identical'] and a['source_coverage'] and a['all_payload_dependencies_clean'];assert a['endpoint_moves']==18 and a['source_edges']==9;assert a['source_nodes']==(9 if id.startswith('0b4') else 12)
 B=W/'compound_node_root_acceptance'/id/a['code_sha256'];B.mkdir(parents=True,exist_ok=True);review={'at':now(),'reviewer':'root','decision':'accepted_exact_reviewed_candidate','code_sha256':a['code_sha256'],'evidence':NOTES[id],'independent_audit':a,'case_specific':True,'exact_original_pixels':False};(B/'root_visual_review.json').write_text(json.dumps(review,indent=2))
 begin(D);state,raw=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();r=json.loads(raw);q=D.execute('select state from harness_queue_v3 where id=?',(id,)).fetchone()
 if state not in ['needs_quality_repair','harness_review_pending','rendered'] or (q and q[0]=='running'):
  D.rollback();results.append({'id':id,'accepted':False,'deferred_state':state,'review_preserved':str((B/'root_visual_review.json').relative_to(R))});continue
 if r['code_sha256']!=a['code_sha256']:
  D.rollback();results.append({'id':id,'accepted':False,'reason':'Current candidate changed since root review; new bytes require review','reviewed_code':a['code_sha256'],'current_code':r['code_sha256']});continue
 directory=(R/r['code_file']).parent
 assert sha((R/r['code_file']).read_bytes())==a['code_sha256'] and sha((R/r['image_file']).read_bytes())==r['image_sha256'];assert json.loads((directory/'conversion.json').read_text())==r
 (B/'before_record.json').write_text(raw);r.update(root_review=review,root_acceptance=str((B/'root_visual_review.json').relative_to(R)),accepted_at_utc=now(),validation_pending=[],quality_state='accepted_source_compound_geometry_fonts_and_root_visual_review')
 temp=directory/'conversion.json.compound-accept.tmp';temp.write_text(json.dumps(r,ensure_ascii=False,indent=2));temp.replace(directory/'conversion.json');D.execute('update jobs set state="accepted",output_record=?,error=NULL,worker_pid=NULL,updated_at=? where id=?',(json.dumps(r,ensure_ascii=False),now(),id));D.execute('update harness_queue_v3 set state="resolved_by_deterministic_acceptance",error=NULL,worker_pid=NULL where id=?',(id,));commit(D);results.append({'id':id,'accepted':True,'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256'],'payloads_unchanged':True})
out={'at':now(),'results':results,'goal_complete':False};(W/'compound_node_acceptance_result.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
