import json,sqlite3,hashlib
from native_worker import W,R,now
from plantuml_style_repair import repair
from playwright.sync_api import sync_playwright
id='003ac6c589d230952350e02d172bc5eeb920e31be1efc738f87d272de9962337';db=sqlite3.connect(W/'jobs.sqlite',timeout=120);row=db.execute('select state,output_record from jobs where id=?',(id,)).fetchone();current=json.loads(row[1]);assert row[0] in ('rendered','needs_quality_repair');work=R/current['prior_version_audit'];old=json.loads((work/'before.json').read_text());old['code_file']=str((work/'before.drawio').relative_to(R));old['image_file']=str((work/'before.png').relative_to(R));newwork=work/'metadata_reaudit';newwork.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);result,proof=repair(b,old,newwork);b.close()
assert result,proof
updated,xml,png=result;assert updated['code_sha256']==current['code_sha256'],'Metadata re-audit unexpectedly changed XML';assert updated['image_sha256']==current['image_sha256'],'Metadata re-audit unexpectedly changed actual PNG'
current['svg_conversion']=updated['svg_conversion'];current['native_style_repair']['source_coverage']=proof['source_coverage'];current['native_style_repair']['metadata_reaudited_at']=now()
db.execute('begin immediate');assert db.execute('select state,output_record from jobs where id=?',(id,)).fetchone()==row
(R/current['code_file']).parent.joinpath('conversion.json').write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n');db.execute('update jobs set output_record=?,updated_at=? where id=?',(json.dumps(current,ensure_ascii=False),now(),id));db.commit();print(json.dumps({'id':id,'same_xml_and_native_png':True,'coverage':proof['source_coverage']}))
