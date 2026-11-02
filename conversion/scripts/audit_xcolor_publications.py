import hashlib,io,json,sqlite3
from pathlib import Path
from PIL import Image
from native_worker import R,W,native,now
from tex_xcolor_forwarding import plan
from harness_source_provenance import validate_source_record
d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);results=[]
for id in json.loads((W/'xcolor_smoke_ids.json').read_text()):
    raw=d.execute('select output_record from jobs where id=?',(id,)).fetchone()[0];r=json.loads(raw);support=r['source_preparation'];data=(R/r['original_source_code']).read_bytes();p=plan(data)
    assert p['original_code_sha256']==r['source_code_sha256']==support['original_code_sha256'];assert p['wrapper_sha256']==support['wrapper_sha256'];assert (R/support['wrapper_file']).read_text()==p['wrapper'];assert (R/support['original_source_file']).read_bytes()==data
    checks=validate_source_record(r)
    for key in ('wrapper_file','original_source_file','proof_file'):assert (R/support[key]).resolve().is_relative_to(R/'clean')
    assert json.loads((R/support['proof_file']).read_text())['wrapper_sha256']==p['wrapper_sha256']
    xml=(R/r['code_file']).read_bytes();png=(R/r['image_file']).read_bytes();assert hashlib.sha256(xml).hexdigest()==r['code_sha256'] and hashlib.sha256(png).hexdigest()==r['image_sha256']
    folder=W/'xcolor_native_audit'/id/r['code_sha256'];folder.mkdir(parents=True,exist_ok=True);(folder/'candidate.drawio').write_bytes(xml);(folder/'candidate.png').write_bytes(png);(folder/'record.json').write_text(raw)
    width,height=Image.open(R/r['original_reference']).size
    fresh=native.native_job(xml.decode(),width,height,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'];again=fresh.pop('png');assert again==png,'Fresh native differs';(folder/'fresh_native.png').write_bytes(again)
    result={'id':id,'source_hash_checks':checks,'code_sha256':r['code_sha256'],'image_sha256':r['image_sha256'],'source_wrapper_and_original_preserved':True,'fresh_native_png_byte_identical':True,'original_size':[width,height],'native_size':list(Image.open(io.BytesIO(png)).size),'metrics':r['metrics'],'unresolved_issues':r.get('unresolved_issues'),'quality_accepted':False}
    if id.startswith('03299'):
        strict=native.native_job(xml.decode(),width,height,120,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert strict['ok'];spng=strict.pop('png');(folder/'strict_canvas_probe.png').write_bytes(spng);s=strict['native_render'];result['strict_canvas_probe']={key:s.get(key) for key in ('selected_image','output_size','outside_page_pixel_audit','content_outside_declared_canvas')}
        result['root_visual_review']='Original/native side-by-side: named boxes, decision diamond, text and path arrangement visible. Native tight crop removes source vertical whitespace. Legacy native overflow proof records 29 nonwhite pixels beyond the declared page; retain pending canvas and semantic edge-binding repair.'
    (folder/'audit.json').write_text(json.dumps(result,indent=2)+'\n');results.append(result)
out={'at':now(),'ok':True,'results':results,'new_acceptances':0};(W/'xcolor_publication_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
