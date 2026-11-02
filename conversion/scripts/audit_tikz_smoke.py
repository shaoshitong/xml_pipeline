import hashlib,json,sqlite3
from pathlib import Path
from native_worker import R,W,now
D=sqlite3.connect(W/'jobs.sqlite');results=[]
for id in json.loads((W/'tikz_native_smoke_ids.json').read_text()):
 state,raw,error=D.execute('select state,output_record,error from jobs where id=?',(id,)).fetchone();r=json.loads(raw) if raw else None;out={'id':id,'state':state,'error':error}
 if r:
  paths={k:r[k] for k in ['original_reference','original_source_code','source_render_pdf','source_render_svg','image_file','code_file']};assert all(p.startswith('clean/') and (R/p).is_file() for p in paths.values());pairs=[('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_svg','source_render_svg_sha256'),('image_file','image_sha256'),('code_file','code_sha256')]
  for f,h in pairs:assert hashlib.sha256((R/r[f]).read_bytes()).hexdigest()==r[h]
  for f in r['fonts']:assert f['file'].startswith('clean/') and hashlib.sha256((R/f['file']).read_bytes()).hexdigest()==f['sha256']
  out.update(source=r['source'],vertices=r['vertices'],edges=r['edges'],bound_edges=r['bound_edges'],metrics=r['metrics'],pdf_issues=r['pdf_conversion']['issues'],svg_issue_count=len(r['svg_conversion']['issues']),connectivity_complete=r['connectivity']['complete'],connectivity_issues=r['connectivity']['issues'],loaded_fonts=len(r['render']['loaded_fonts']),native_text_counter_equal=r['native_text_counter_equal'],content_outside_canvas=r['render']['content_outside_declared_canvas'],source_hashes_and_clean_paths_ok=True)
 results.append(out)
report={'checked_at_utc':now(),'results':results,'outputs':sum(r.get('source_hashes_and_clean_paths_ok',False) for r in results),'total':len(results),'goal_complete':False};(W/'tikz_smoke_audit.json').write_text(json.dumps(report,indent=2,default=lambda x:list(x))+'\n');print(json.dumps(report,default=lambda x:list(x)))
