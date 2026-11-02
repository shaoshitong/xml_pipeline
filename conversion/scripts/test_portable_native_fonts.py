import json,sqlite3,hashlib,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from portable_native_fonts import ready_page,capture,embed
B=W/'font_portability_probe';B.mkdir(exist_ok=True);root=E.Element('mxfile');m=E.SubElement(E.SubElement(root,'diagram'), 'mxGraphModel',page='1',pageWidth='680',pageHeight='240');r=E.SubElement(m,'root');E.SubElement(r,'mxCell',id='0');E.SubElement(r,'mxCell',id='1',parent='0')
for i in range(4):
 c=E.SubElement(r,'mxCell',id='t'+str(i),parent='1',vertex='1',value='Editable fonts: Alpha 123 Ω ≥',style=f'shape=text;html=1;fontFamily=Liberation Sans;fontStyle={i};fontSize=24;align=left;verticalAlign=middle;spacing=0;strokeColor=none;fillColor=none;');E.SubElement(c,'mxGeometry',x='20',y=str(20+50*i),width='600',height='40',**{'as':'geometry'})
fixture=E.tostring(root,encoding='unicode');D=sqlite3.connect(W/'jobs.sqlite');ids=['ab692a4bc019ce00ed3be2f5838f2285c5789c6ddcb59fc94a6d2ba16c9ff9dd','2806c6a330ea68e1080a8109be7f7dbef25f67f81b6bb4885ff430f39dc9258b'];cases=[('fixture',fixture,680,240,None)]
for id in ids:
 out=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);xml=(R/out['code_file']).read_text();w,h=Image.open(R/out['image_file']).size;cases.append((id,xml,w,h,out))
results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);pg=ready_page(b)
 for id,xml,w,h,out in cases:
  path=B/id;path.mkdir(exist_ok=True)
  try:
   before=native.native_job(xml,w,h,90,W/'rendering_fontproof/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert before['ok'];observed=capture(pg,xml);new,fonts,report=embed(xml,observed,path/'fonts');(path/'before.drawio').write_text(xml);(path/'candidate.drawio').write_text(new);(path/'before.png').write_bytes(before['png']);(path/'observations.json').write_text(json.dumps(observed,indent=2));assert not report['issues'],report['issues'];assert report['changes'];after=native.native_job(new,w,h,90,W/'rendering_fontproof/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert after['ok'];(path/'candidate.png').write_bytes(after['png']);usage={x['cell']:x['fonts'] for x in after['native_render']['actual_platform_font_usage']};custom=all(usage.get(x['cell']) and all(f['isCustomFont'] for f in usage[x['cell']] if f['glyphCount']) for x in report['changes']);same=before['png']==after['png'];result={'id':id,'pixel_identical':same,'every_changed_text_uses_custom_embedded_font':custom,'report':report,'fonts':[{k:v for k,v in f.items() if k!='uri'} for f in fonts.values()],'before_native_render':before['native_render'],'after_native_render':after['native_render']};(path/'report.json').write_text(json.dumps(result,indent=2));assert same and custom,result;results.append({'id':id,'ok':True,'fonts':len(fonts),'changed_text_cells':len(report['changes'])});print(json.dumps(results[-1]),flush=True)
  except Exception as e:results.append({'id':id,'ok':False,'error':repr(e)});print(json.dumps(results[-1]),flush=True)
 b.close()
(B/'test_report.json').write_text(json.dumps({'at':now(),'results':results},indent=2));assert all(r['ok'] for r in results)
