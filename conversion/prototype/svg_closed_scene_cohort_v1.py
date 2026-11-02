"""Read-only current-revision SVG profile cohort; all proof artifacts stay remote."""
import sys,json,sqlite3,collections,hashlib,datetime,time
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';P=W/'prototype/svg_source_profile_scope_v1';sys.path[:0]=[str(W/'prototype'),str(W/'scripts')]
import auto_quality_svg_closed_scene_v1 as profile
import auto_quality_source_vector_v2 as prior
from svg_source_scene_dom_v1 import close_worker_runtime
from auto_quality_common import resource_checks
try:from auto_quality_common_v4 import registration_record
except ImportError:from auto_quality_common_v3 import registration_record
sha=lambda b:hashlib.sha256(b).hexdigest()
S=json.loads((P/'static_source_scan.json').read_text())['records'];selected=[]
for kind,group,limit,label in [('closed_source_paint_no_declared_relation_or_marker','generic_or_connector_path_profile_missing',100,'closed_current_generic'),('closed_source_paint_no_declared_relation_or_marker',None,30,'closed_other'),('use_expansion_requires_fresh_DOM','generic_or_connector_path_profile_missing',30,'use_current_generic'),('source_marker_owners_without_declared_graph_nodes','generic_or_connector_path_profile_missing',6,'marker_negative_cohort'),('untyped_open_source_paint_requires_relation_or_plot_evidence','generic_or_connector_path_profile_missing',10,'open_negative_cohort')]:
 items=[row for row in S if row['kind']==kind and (row['qa3_group']==group if group else row['qa3_group']!='generic_or_connector_path_profile_missing')][:limit]
 selected.extend((label,row) for row in items)
D=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);out=P/'closed_scene_cohort_v1';out.mkdir(exist_ok=True);results=[];started=time.time()
try:
 for i,(label,snapshot) in enumerate(selected,1):
  id=snapshot['id'];item={'id':id,'cohort':label,'static_kind':snapshot['kind'],'captured_QA3_group':snapshot['qa3_group']}
  try:
   current=D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone();assert current,'missing job';state,worker,raw=current;record=json.loads(raw);item['state']=state;assert not worker,'busy current revision';assert record['code_sha256']==snapshot['input_code_sha256'] and record['image_sha256']==snapshot['input_image_sha256'],'snapshot revision changed';xml=prior._read_clean(record['code_file'],record['code_sha256']).decode();prior._identity(record,xml);reference=prior._read_clean(record['original_reference'],record['source_image_sha256']);_,contract=registration_record(record,reference,xml);offset=contract['original_page_offset'] if contract else [0,0];dom=profile.capture_closed_scene(record);result=profile.check_scene_coverage(dom,xml,offset)
   if result['supported']:
    try:result['evidence']['original_asset_resources']=resource_checks(R,record,xml,reference)
    except Exception as error:result['ok']=False;result['failures'].append({'reason':'original_asset_resource_gate_error','error':repr(error)})
   after=D.execute('select worker_pid,output_record from jobs where id=?',(id,)).fetchone();assert not after[0] and json.loads(after[1])['code_sha256']==record['code_sha256'] and json.loads(after[1])['image_sha256']==record['image_sha256'],'revision changed during proof';prior._identity(record,xml)
   item.update(input_code_sha256=record['code_sha256'],input_image_sha256=record['image_sha256'],source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],supported=result['supported'],ok=result['ok'],failures=result['failures'],source_objects=len(dom['objects']),source_issues=dom.get('issues',[]),reference_offset=offset)
   # Old generic guard vs exact converted-paint checks are diagnostic only.
   try:item['old_guard_ok']=prior._decorative_profile(dom)['ok'];item['old_paint_ok']=prior._paint_coverage(dom,xml)['ok'];item['old_inventory_ok']=prior._graphviz_coverage(dom,xml,{})['ok']
   except Exception as error:item['old_diagnostic_error']=repr(error)
   case=out/id;case.mkdir(exist_ok=True);(case/'fresh_source_dom.json').write_text(json.dumps(dom,ensure_ascii=False));(case/'proof.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');item['proof']=str(case/'proof.json')
  except Exception as error:item.update(skipped=True,error=repr(error))
  results.append(item)
  if i%10==0:print(json.dumps({'progress':i,'total':len(selected),'supported':sum(bool(r.get('supported')) for r in results),'ok':sum(bool(r.get('ok')) for r in results)}),flush=True)
finally:close_worker_runtime()
groups={}
for row in results:
 g=groups.setdefault(row['cohort'],{'count':0,'supported':0,'ok':0,'skipped':0,'failure_reasons':collections.Counter(),'ok_ids':[]});g['count']+=1;g['supported']+=bool(row.get('supported'));g['ok']+=bool(row.get('ok'));g['skipped']+=bool(row.get('skipped'));g['failure_reasons'].update(set(f.get('reason',str(f)) if isinstance(f,dict) else str(f) for f in row.get('failures',[])))
 if row.get('ok'):g['ok_ids'].append(row['id'])
for g in groups.values():g['failure_reasons']=dict(g['failure_reasons'])
report={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':profile.POLICY,'implementation_sha256':sha(Path(profile.__file__).read_bytes()),'elapsed_seconds':time.time()-started,'groups':groups,'records':results,'scope':'Fresh offline actual source DOM plus current immutable XML/source/ref identities. No canonical/DB/queue/model changes or accepted outcome. Native renderer/font/editing and original image gates remain required.'};(out/'cohort_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='records'}|{'report':str(out/'cohort_report.json')},ensure_ascii=False),flush=True)
