import hashlib,json,sqlite3
from native_worker import R,W,native,now
from strict_canvas_gate import require_declared_page
from harness_source_provenance import validate_source_record,archive_record
d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);results=[]
for id,oldhash,rawproof in d.execute('select id,input_hash,record from native_page_padding_repairs where state="published"'):
    state,raw=d.execute('select state,output_record from jobs where id=?',(id,)).fetchone();r=json.loads(raw);p=json.loads(rawproof)
    if r['code_sha256']!=p['new_code_sha256']:continue
    xml=(R/r['code_file']).read_bytes();png=(R/r['image_file']).read_bytes();assert hashlib.sha256(xml).hexdigest()==r['code_sha256'] and hashlib.sha256(png).hexdigest()==r['image_sha256'];assert json.loads(((R/r['code_file']).parent/'conversion.json').read_text())==r
    checks=validate_source_record(r);old,oldxml,oldraw,folder=archive_record(r['previous_candidate_archive'],r);assert old['code_sha256']==oldhash
    assert r['render']['renderer_profile']=='native_page_padding_strict_v1';renderer=W/'rendering_canvas_padding_proof/remote_render.py';assert hashlib.sha256(renderer.read_bytes()).hexdigest()==r['render']['renderer_module_sha256']
    width,height=p['geometry']['new_page'];fresh=native.native_job(xml.decode(),width,height,150,renderer,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'];require_declared_page(fresh['native_render'],width,height);assert fresh['png']==png,'Fresh actual native PNG differs'
    dest=W/'native_page_padding_audit'/id/r['code_sha256'];dest.mkdir(parents=True,exist_ok=True);(dest/'fresh_native.png').write_bytes(fresh['png'])
    results.append({'id':id,'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256'],'state_at_audit':state,'fresh_actual_native_png_byte_identical':True,'source_hash_checks':checks,'previous_archive_source_identity_valid':True,'renderer_profile_verified':True,'outside_nonwhite_pixels':fresh['native_render']['outside_page_pixel_audit']['nonwhite_outside_pixels'],'reference_ssim_before':p['reference_ssim_before'],'reference_ssim_after':p['reference_ssim_after'],'accepted':False})
out={'at':now(),'ok':bool(results),'results':results,'root_visual_review':{'id':'03299a3c21789a81926f027324ec2c78cc9134ff3fc0e46e271f1699b3202c19','code_sha256':'bd98f30f586d2d4e3395896c25a189392dc2263ea49940d5aaca7d23fbbb76f5','notes':'Original/new native compared side by side at full width. Original vertical whitespace restored; named boxes, diamond and multi-arrow/return paths remain visible in matching arrangement. Small text metrics differ from reference and semantic edge binding remains unresolved. Not accepted.'},'new_acceptances':0};(W/'native_page_padding_publication_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out));assert out['ok']
