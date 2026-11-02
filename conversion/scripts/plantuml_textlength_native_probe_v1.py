import sys,json,uuid,html,statistics,xml.etree.ElementTree as E
from pathlib import Path
sys.path.insert(0,'/backup/shaoshitong/img2code_20261029/conversion/scripts')
from native_worker import R,W,native
from strict_canvas_gate import require_declared_page
base=W/'plantuml_textlength_native_probe_v1'/uuid.uuid4().hex;base.mkdir(parents=True)
rows=json.loads((W/'plantuml_textlength_probe_v1/aa083cf632924d7086d8fc57ab4c3f47/report.json').read_text())['rows']
rec=json.loads((R/'clean/compiler_plantuml_natural_candidate_v8/05/05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798/e576d9b4928c49fb9fe992cc0ad1870c/record.json').read_text());root=E.fromstring((R/rec['code_file']).read_text());cells={c.get('id'):c for c in root.iter('mxCell')};plans={}
for cid,r in zip(('v5t0','v10t0','v15t0','v20t0'),rows):
 chars=r['adjusted'][0]['chars'];text=r['text'];spacing=(float(r['attrs']['textLength'])-r['natural'][0]['whole']['width'])/(len(chars)-1);last=chars[-1]['text'];prefix=text[:-len(last)];cells[cid].set('value','<span data-plantuml-spacing-v1="'+cid+'" style="letter-spacing:'+format(spacing,'.9f')+'px;">'+html.escape(prefix)+'<span style="letter-spacing:0px;">'+html.escape(last)+'</span></span>');plans[cid]={'source':r,'spacing':spacing}
xml=E.tostring(root,encoding='unicode');render=native.native_job(xml,322,275,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'],render
(base/'diagram.drawio').write_text(xml);(base/'fresh_native.png').write_bytes(render['png']);(base/'native_render.json').write_text(json.dumps(render['native_render'],indent=2));obs={r['cell']:[c for run in r['runs'] for c in run['chars']] for r in render['native_render']['actual_text_positions']};out=[]
for cid,p in plans.items():
 a=p['source']['adjusted'][0]['chars'];b=obs[cid];dx=statistics.median(x['x']-y['x'] for x,y in zip(a,b));dy=statistics.median(x['y']-y['y'] for x,y in zip(a,b));out.append({'cell':cid,'spacing':p['spacing'],'dx':dx,'dy':dy,'maxx':max(abs(x['x']-y['x']-dx) for x,y in zip(a,b)),'sizes':[(round(x['width']-y['width'],6),round(x['height']-y['height'],6)) for x,y in zip(a,b)],'chars':b[:3]})
report={'report':str(base/'report.json'),'details':out};(base/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
