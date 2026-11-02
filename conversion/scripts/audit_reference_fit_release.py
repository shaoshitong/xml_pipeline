import json,sqlite3,hashlib
from native_worker import R,W,now
from harness_source_provenance import validate_frozen
ID='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641';D=sqlite3.connect(W/'jobs.sqlite',timeout=60);state,raw=D.execute('select state,output_record from jobs where id=?',(ID,)).fetchone();r=json.loads(raw);assert state=='accepted'
rows=[json.loads(s) for s in (R/'release/drawio_manifest.inprogress.jsonl').open()];matches=[x for x in rows if x['id']==ID];assert len(matches)==1 and matches[0]==r
checks=[]
for k,hk in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('source_render_svg','source_render_svg_sha256')]:
 p=R/r[k];assert p.resolve().is_relative_to(R/'clean') and hashlib.sha256(p.read_bytes()).hexdigest()==r[hk];checks.append(k)
for x in r['native_source_geometry_repair']['files'].values():
 p=R/x['file'];assert p.resolve().is_relative_to(R/'clean') and hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
for f in (list(r['native_embedded_fonts'].values()) if isinstance(r['native_embedded_fonts'],dict) else r['native_embedded_fonts']):
 for k,hk in [('file','sha256'),('original_file','original_sha256')]:
  p=R/f[k];assert p.resolve().is_relative_to(R/'clean') and hashlib.sha256(p.read_bytes()).hexdigest()==f[hk]
old=json.loads((W/'mermaid_reference_fit'/ID/'before_record.json').read_text());validate_frozen(old['source_provenance'])
result={'at':now(),'id':ID,'accepted_manifest_records':len(rows),'db_and_index_record_equal':True,'current_payload_hashes_and_clean_only_dependencies_valid':True,'previous_frozen_source_provenance_still_valid':True,'fields_checked':checks,'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256'],'ok':True}
(W/'mermaid_reference_fit_release_audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
