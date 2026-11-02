import json,sqlite3,hashlib
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';D=sqlite3.connect(W/'jobs.sqlite',timeout=60);rows=D.execute("select id,state,output_record from jobs where json_extract(output_record,'$.conversion_method')='remote_deepseek_harness_verified_fonts_and_native_arrow_gate_v4'").fetchall();out=[]
for id,state,raw in rows:
 r=json.loads(raw);v={'id':id,'state':state,'code_sha256':r['code_sha256'],'font_gate_applicable':r.get('source_fullname_face_validation',{}).get('applicable'),'source_editability_applicable':r.get('source_editability',{}).get('applicable'),'recovery_archive':r.get('source_font_recovery_archive'),'previous_archive':r.get('previous_candidate_archive')};p=R/r['previous_candidate_archive']/'conversion.json' if r.get('previous_candidate_archive') else None
 if p and p.exists():
  a=json.loads(p.read_text());v['baseline_has_source_font_proof']=bool(a.get('native_source_font_repair'));v['baseline_recovery_archive']=a.get('source_font_recovery_archive');v['lost_source_locators']=[k for k in ('source_render_svg','source_render_svg_sha256','source_render_dot') if a.get(k) and not r.get(k)];v['missing_next_iteration_font_proof']=bool(v['baseline_has_source_font_proof'] and not r.get('native_source_font_repair') and not r.get('source_font_recovery_archive'))
 out.append(v)
result={'v4_published':len(out),'records':out,'affected':[x for x in out if x.get('missing_next_iteration_font_proof') or x.get('lost_source_locators')]};(W/'harness_provenance_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
