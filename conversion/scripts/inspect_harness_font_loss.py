import json,sqlite3,xml.etree.ElementTree as E
from pathlib import Path
W=Path('/backup/shaoshitong/img2code_20261029/conversion');R=W.parent;D=sqlite3.connect(W/'jobs.sqlite');out=[]
for id,raw in D.execute("select id,output_record from jobs where state='harness_review_pending' and json_extract(output_record,'$.conversion_method')='remote_deepseek_harness_source_assets_data_and_independent_critic_v3'"):
 r=json.loads(raw);a=r.get('previous_candidate_archive')
 if not a:continue
 p=R/a/'conversion.json'
 if not p.exists():continue
 old=json.loads(p.read_text());fs=old.get('native_embedded_fonts',[])
 if not fs:continue
 model=E.fromstring((R/r['code_file']).read_text()).find('.//mxGraphModel');fonts={s.split('^',1)[0] for s in model.get('extFonts','').split('|') if s};missing=[f['family'] for f in fs if f['family'] not in fonts];out.append({'id':id,'missing_prior_fonts':missing,'previous_count':len(fs),'candidate_origin':r['candidate_origin'],'before_ssim':old.get('metrics',{}),'after_ssim':r.get('metrics',{}),'archive':a})
report={'affected':sum(bool(r['missing_prior_fonts']) for r in out),'inspected_with_prior_native_fonts':len(out),'cases':out};(W/'harness_v3_font_loss_inventory.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
