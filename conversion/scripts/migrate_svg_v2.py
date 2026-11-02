import datetime,json,shutil,sqlite3,time
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite',timeout=60);now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat();report={'started_at_utc':now(),'reason':'v1 inserts Graphviz groups before source background, hiding group children. v2 preserves source group paint order.','requeued':[]}
db.execute('begin immediate');n=db.execute('update jobs set route="svg_v2",updated_at=? where state="queued" and route="svg"',(now(),)).rowcount;db.commit();report['queued_route_migrated']=n
# This lets original workers drain their current job, without killing running renders.
for id,state,raw in db.execute('select id,state,output_record from jobs where format="svg" and state in ("rendered","needs_quality_repair") and output_record is not null').fetchall():
 record=json.loads(raw)
 if record.get('conversion_method')!='svg_element_native_stencils_editable_text_and_connectors_v1' or not record.get('svg_conversion',{}).get('counts',{}).get('node_groups'):continue
 dest=W/'version_archive'/id/'svg_v1';dest.mkdir(parents=True,exist_ok=True)
 for key in ('code_file','image_file'):
  src=R/record[key];shutil.copy2(src,dest/src.name)
 (dest/'conversion.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 changed=db.execute('update jobs set state="queued",route="svg_v2",error=?,updated_at=? where id=? and state=? and output_record=?',('Requeued to repair verified background/group paint-order defect; previous candidate archived.',now(),id,state,raw)).rowcount;db.commit()
 if changed:report['requeued'].append(id)
report['finished_at_utc']=now();path=W/('svg_v2_migration_'+str(int(time.time()))+'.json');path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({**report,'requeued':len(report['requeued']),'audit':str(path)}))
