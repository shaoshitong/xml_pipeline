import hashlib,json,sqlite3
from native_worker import R,W,native,now
from harness_canvas_contract import validate,require_render,require_xml_page,RENDERER
from harness_source_provenance import validate_frozen,validate_source_record
sha=lambda b:hashlib.sha256(b).hexdigest();d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);results=[]
for id,raw in d.execute('select id,output_record from jobs where state="harness_review_pending" and json_extract(output_record,"$.conversion_method")="remote_deepseek_harness_verified_canvas_v6" order by id'):
 r=json.loads(raw);xml=(R/r['code_file']).read_bytes();png=(R/r['image_file']).read_bytes();assert sha(xml)==r['code_sha256'] and sha(png)==r['image_sha256'];assert json.loads(((R/r['code_file']).parent/'conversion.json').read_text())==r;source_checks=validate_source_record(r);validate_frozen(r['source_provenance']);contract=validate(r,(R/r['original_reference']).read_bytes());require_xml_page(xml.decode(),contract)
 for f in r.get('fonts',[]):
  p=(R/f['file']).resolve();assert p.is_relative_to(R/'clean') and sha(p.read_bytes())==f['sha256']
 fresh=native.native_job(xml.decode(),*contract['output_page'],150,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'];require_render(fresh['native_render'],contract);assert fresh['png']==png,'Fresh native PNG differs from model-published pair'
 work=W/'harness_v6_publication_audit'/id/r['code_sha256'];work.mkdir(parents=True,exist_ok=True);(work/'fresh_native.png').write_bytes(fresh['png']);results.append({'id':id,'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256'],'source_hash_checks':source_checks,'canvas_contract_revalidated':True,'fresh_native_png_byte_identical':True,'bound_edges':r['bound_edges'],'edges':r['edges'],'reference_ssim':r['metrics']['original_reference_ssim_512'],'critic_score':r['critic'].get('score'),'accepted':False})
out={'at':now(),'ok':bool(results),'results':results,'scope':'Publication/source/font/canvas integrity and repeatable native rendering only. Model judgments do not establish final source semantics or visual acceptance.','new_acceptances':0};(W/'harness_v6_publication_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
