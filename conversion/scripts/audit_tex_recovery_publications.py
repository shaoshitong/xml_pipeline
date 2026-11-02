import hashlib,io,json,sqlite3,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from native_worker import R,W,native,now
d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True)
rows=d.execute('select id,state,input_record,output_record from jobs where id in (select id from tikz_dependency_repairs_v2 where state="requeued") and output_record is not NULL').fetchall()
checks=[];skipped=[];errors=[];fresh=[]
for id,state,src_raw,raw in rows:
    if state.endswith(('converting','rendering')) or 'repairing' in state or state=='repair_running':skipped.append({'id':id,'reason':'busy'});continue
    r=json.loads(raw);src=json.loads(src_raw)
    try:
        fields=[('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_svg','source_render_svg_sha256')]
        assert r['source_code_sha256']==src['code_sha256'] and r['source_image_sha256']==src['image_sha256']
        for key,hkey in fields:
            p=R/r[key];assert p.resolve().is_relative_to(R/'clean');assert hashlib.sha256(p.read_bytes()).hexdigest()==r[hkey],key
        for font in r.get('fonts',[]):
            p=R/font['file'];assert p.resolve().is_relative_to(R/'clean');assert hashlib.sha256(p.read_bytes()).hexdigest()==font['sha256']
        cells=list(E.fromstring((R/r['code_file']).read_text()).iter('mxCell'));assert any(c.get('vertex')=='1' for c in cells)
        if d.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]!=raw:skipped.append({'id':id,'reason':'revision_changed'});continue
        checks.append({'id':id,'state':state,'xml_sha256':r['code_sha256'],'png_sha256':r['image_sha256'],'source_bytes_preserved':True,'all_payloads_under_clean':True,'vertices':sum(c.get('vertex')=='1' for c in cells),'edges':sum(c.get('edge')=='1' for c in cells)})
    except Exception as e:
        if d.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]!=raw:skipped.append({'id':id,'reason':'revision_changed_during_check'});continue
        errors.append({'id':id,'error':str(e)})
for id in ('0002d1280db280c2d9227e7d2188cd20f0cbc446310f112772df3d9b62cca423','0029bf2032e526aa6fd09bbe5d8a324af2e677ae2652bef99909ee1b251330d7'):
    raw=d.execute('select output_record from jobs where id=?',(id,)).fetchone()[0];r=json.loads(raw);xml=(R/r['code_file']).read_bytes();png=(R/r['image_file']).read_bytes();assert hashlib.sha256(xml).hexdigest()==r['code_sha256'] and hashlib.sha256(png).hexdigest()==r['image_sha256']
    folder=W/'tex_recovery_native_audit'/id/r['code_sha256'];folder.mkdir(parents=True,exist_ok=True);(folder/'candidate.drawio').write_bytes(xml);(folder/'candidate.png').write_bytes(png)
    im=Image.open(io.BytesIO(png));render=native.native_job(xml.decode(),*im.size,120,W/'rendering_fonts/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    assert render['ok'],{k:v for k,v in render.items() if k!='png'}
    again=render.pop('png');(folder/'fresh_native.png').write_bytes(again);assert again==png,'Fresh native render differs'
    fresh.append({'id':id,'xml_sha256':r['code_sha256'],'png_sha256':r['image_sha256'],'fresh_png_byte_identical':True,'actual_native_renderer':render['native_render'],'quality_accepted':False})
out={'at':now(),'published_snapshot_rows':len(rows),'payload_checks':checks,'skipped':skipped,'errors':errors,'fresh_native_renders':fresh,'ok':not errors,'acceptance_count_change':0}
(W/'tex_recovery_publication_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out));assert out['ok']
