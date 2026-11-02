"""Restore verified provenance fields lost by legacy Harness and count actual XML cells."""
import json,hashlib,sqlite3
from native_worker import R,W,now
from durable_sqlite import begin,commit
from harness_context_v4 import structure
from source_svg_snapshot import auxiliary_hashes
sha=lambda b:hashlib.sha256(b).hexdigest();D=sqlite3.connect(W/'jobs.sqlite',timeout=2);results=[]
for id in ['0426a77f5545d5e8ba52986113529ee94b2dbd7ac28a9656c8c9cc55ef36c6f4','00c975522ec4d80ed17b33637be20d9adc5271a1207763bc5073c591bfcd1ed2']:
 state,raw=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert state in ('accepted','needs_quality_repair');r=json.loads(raw);proof=r['native_source_marker_repair'];assert proof['output_code_sha256']==r['code_sha256'];xml=(R/r['code_file']).read_text();assert sha(xml.encode())==r['code_sha256'];assert sha((R/r['image_file']).read_bytes())==r['image_sha256'];struct=structure(xml,{});assert struct['ok'];changes={}
 for key in ('vertices','edges','bound_edges'):
  if r.get(key)!=struct[key]:changes[key]={'before':r.get(key),'after':struct[key]};r[key]=struct[key]
 if r.get('source_font_recovery_archive'):
  folder=(R/r['source_font_recovery_archive']).resolve();assert folder.is_relative_to(R/'conversion/harness_sessions');v=json.loads((folder/'conversion.json').read_text());assert all(r[k]==v[k] for k in ('id','source_image_sha256','source_code_sha256'));assert sha((folder/'diagram.drawio').read_bytes())==v['code_sha256'];assert auxiliary_hashes(v)==v['native_source_font_repair']['source_auxiliary_hashes']
  for key in ('source_render_svg','source_render_svg_sha256','source_render_dot','original_source_data','source_data_sha256','source_data_locator'):
   if v.get(key):
    if r.get(key):assert r[key]==v[key],key
    else:r[key]=v[key];changes[key]={'restored_from':r['source_font_recovery_archive']}
 assert auxiliary_hashes(r)==r['native_source_font_repair']['source_auxiliary_hashes'];B=W/'source_vee_record_metadata'/id;B.mkdir(parents=True,exist_ok=True);(B/'before_record.json').write_text(raw);audit={'at':now(),'id':id,'unchanged_code_sha256':r['code_sha256'],'unchanged_image_sha256':r['image_sha256'],'changes':changes,'all_restored_clean_source_payload_hashes_verified':True};(B/'report.json').write_text(json.dumps(audit,indent=2));r['native_source_marker_repair']['metadata_audit']=str((B/'report.json').relative_to(R));begin(D);assert D.execute('select state,output_record from jobs where id=?',(id,)).fetchone()==(state,raw);p=(R/r['code_file']).parent/'conversion.json';t=p.with_suffix('.metadata.tmp');t.write_text(json.dumps(r,ensure_ascii=False,indent=2));t.replace(p);D.execute('update jobs set output_record=?,updated_at=? where id=?',(json.dumps(r,ensure_ascii=False),now(),id));commit(D);results.append(audit)
print(json.dumps(results))
