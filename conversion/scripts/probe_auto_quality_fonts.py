import concurrent.futures,json,sqlite3,hashlib,time
from pathlib import Path
from native_worker import R,W,native

def probe(row):
 id,raw=row;r=json.loads(raw);xml=(R/r['code_file']).read_text();assert hashlib.sha256(xml.encode()).hexdigest()==r['code_sha256'];w,h=r['render']['canvas'];z=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');info=z.get('native_render',{});x={'id':id,'code_sha256':r['code_sha256'],'format':r['source_format'],'method':r['conversion_method'],'ok':z['ok'],'non_custom':[row for row in info.get('actual_platform_font_usage',[]) if any(f.get('glyphCount') and not f['isCustomFont'] for f in row['fonts'])],'font_registry':r.get('native_embedded_fonts'),'source_font_validation':r.get('native_font_validation'),'text_positions_count':len(info.get('actual_text_positions',[]))};folder=W/'auto_quality_font_probe'/id/r['code_sha256'];folder.mkdir(parents=True,exist_ok=True);(folder/'native_render.json').write_text(json.dumps(info,indent=2)+'\n');(folder/'probe.json').write_text(json.dumps(x,indent=2)+'\n');return x
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);rows=D.execute("select distinct j.id,j.output_record from auto_quality_exceptions_v1 q join jobs j on j.id=q.id where q.route='deterministic_font_embedding' and j.worker_pid is NULL and j.state!='accepted' and q.code_hash=json_extract(j.output_record,'$.code_sha256') limit 16").fetchall()
with concurrent.futures.ProcessPoolExecutor(max_workers=4) as p:out=list(p.map(probe,rows))
r={'at':time.time(),'rows':out};(W/'auto_quality_font_probe.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
