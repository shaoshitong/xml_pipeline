import datetime,json,shutil,sqlite3,time
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite',timeout=60);now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat();report={'started_at_utc':now(),'reason':'Unavailable CSS first font caused serif fallback. v3 obtains actual Chromium platform fonts.','requeued':[]};n=db.execute('update jobs set state="queued_html_v3",updated_at=? where state="queued" and format="html"',(now(),)).rowcount;db.commit();report['pending_migrated']=n
for id,state,raw in db.execute('select id,state,output_record from jobs where format="html" and state in ("rendered","needs_quality_repair") and output_record is not null').fetchall():
 o=json.loads(raw)
 if o.get('conversion_method')!='offline_html_dom_native_shapes_text_original_image_assets_v2':continue
 dest=W/'version_archive'/id/'html_v2';dest.mkdir(parents=True,exist_ok=True)
 for key in ['code_file','image_file']:
  src=R/o[key];shutil.copy2(src,dest/src.name)
 (dest/'conversion.json').write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n');n=db.execute('update jobs set state="queued_html_v3",error=?,updated_at=? where id=? and state=? and output_record=?',('Requeued to preserve actual rendered source fonts; prior candidate archived.',now(),id,state,raw)).rowcount;db.commit()
 if n:report['requeued'].append(id)
report['finished_at_utc']=now();path=W/('html_v3_migration_'+str(int(time.time()))+'.json');path.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({**report,'requeued':len(report['requeued'])}))
