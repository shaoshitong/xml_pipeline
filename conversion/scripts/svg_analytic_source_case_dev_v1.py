from pathlib import Path
import sys,json,sqlite3,hashlib
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
import compiler_svg_scene_frontend_v7 as front
import compiler_svg_scene_backend_v6 as backend
identifier=sys.argv[1];work=Path(sys.argv[2]);cfg=front.configuration()
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:job=db.execute('select * from jobs where id=?',(identifier,)).fetchone()
source=json.loads(job[4]);manifest=json.loads(job[11]);record=dict(id=identifier,source_pair_sha256=identifier,source_format='svg',category=source['category'],source=source['source'],source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],original_source_code=manifest['source_code'],original_reference=manifest['reference_image'])
try:
 prepared=front.prepare_source(record,job,work)
 captures=prepared['capture'];dom=captures['dom'];markers=dom['sceneMetadata']['markerContexts'];objects={o['id']:o for o in dom['objects']};checks=[]
 for key,ctx in markers.items():
  heads=[o for o in dom['objects']if key in o.get('sceneMarkerContexts',[])];row=dict(context=key,owner=ctx['owner'],side=ctx['side'])
  try:geometry=backend._triangle(heads[0],objects[ctx['owner']],ctx['side']);row.update(ok=True,maximum_source_vertex_error_px=geometry['maximum_source_vertex_error_px'])
  except Exception as error:row.update(ok=False,reason=str(error))
  checks.append(row)
 result=dict(id=identifier,source_ok=prepared['ok'],sourceproof=prepared['sourceproof'],source_endpoint_direction=dom['sourceEndpointDirection'],markers=checks,normal_conversion_calls=0,target_pixels_used_for_endpoint_rules=False,configuration=cfg)
except Exception as error:
 result=dict(id=identifier,ok=False,error_type=type(error).__name__,reason=str(error),normal_conversion_calls=0)
 if not work.exists():work.mkdir(parents=True)
(work/'analytic_summary.json').write_text(json.dumps(result,indent=2))
with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True)as db:assert db.execute('select * from jobs where id=?',(identifier,)).fetchone()==job
print(json.dumps({k:v for k,v in result.items()if k not in ('configuration','sourceproof')},ensure_ascii=False))
