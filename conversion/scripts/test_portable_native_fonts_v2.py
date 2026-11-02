import json,sqlite3,hashlib,collections,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from portable_native_fonts_v2 import ready_page,capture,embed
from native_font_embedding_batch import canonical
B=W/'font_portability_probe_v2';B.mkdir(exist_ok=True)
root=E.Element('mxfile');m=E.SubElement(E.SubElement(root,'diagram'),'mxGraphModel',page='1',pageWidth='720',pageHeight='260');r=E.SubElement(m,'root');E.SubElement(r,'mxCell',id='0');E.SubElement(r,'mxCell',id='1',parent='0')
for i in range(4):
 c=E.SubElement(r,'mxCell',id='t'+str(i),parent='1',vertex='1',value='Editable math ∀ ∂ ℝ ≥ 中文',style=f'shape=text;html=1;fontFamily=Arial;fontStyle={i};fontSize=24;align=left;verticalAlign=middle;spacing=0;strokeColor=none;fillColor=none;');E.SubElement(c,'mxGeometry',x='20',y=str(20+55*i),width='680',height='45',**{'as':'geometry'})
cases=[('fixture',E.tostring(root,encoding='unicode'),720,260,None)]
D=sqlite3.connect(W/'jobs.sqlite')
for prefix in ['0024a3897c4d','001d1bc71772','0018d2b26757','0001c7fc6c8a']:
 row=D.execute("select id,output_record from jobs where id like ?",(prefix+'%',)).fetchone()
 if row:
  id,raw=row;out=json.loads(raw);xml=(R/out['code_file']).read_text();w,h=Image.open(R/out['image_file']).size
  if 'extFonts=' not in xml:cases.append((id,xml,w,h,out))
def counts(render):
 return {row['cell']:dict(collections.Counter({f['postScriptName']:f['glyphCount'] for f in row['fonts'] if f['glyphCount']})) for row in render['actual_platform_font_usage']}
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser)
 for id,xml,w,h,out in cases:
  path=B/id;path.mkdir(exist_ok=True);result={'id':id}
  try:
   (path/'before.drawio').write_text(xml);observed=capture(page,xml);(path/'observations.json').write_text(json.dumps(observed,indent=2));new,fonts,details=embed(xml,observed,path/'fonts',page);(path/'details.json').write_text(json.dumps(details,indent=2));(path/'candidate.drawio').write_text(new);result.update(issues=details['issues'],mixed_text_cells=details['mixed_text_cells'],fonts=len(fonts),text_cells=len(details['changes']));assert not details['issues'],str(details['issues'])[:600]
   changed={x['cell'] for x in details['changes']};normalized=E.fromstring(new);originals={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
   for c in normalized.iter('mxCell'):
    if any(x['cell']==c.get('id') and x['mixed_runs'] for x in details['changes']):c.set('value',originals[c.get('id')].get('value',''))
   assert canonical(xml,changed)==canonical(E.tostring(normalized,encoding='unicode'),changed),'Nonfont graph changed'
   before=native.native_job(xml,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert before['ok'];after=native.native_job(new,w,h,120,W/'rendering_fontproof_v2/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert after['ok'];(path/'before.png').write_bytes(before['png']);(path/'candidate.png').write_bytes(after['png']);(path/'render_before.json').write_text(json.dumps(before['native_render'],indent=2));(path/'render_after.json').write_text(json.dumps(after['native_render'],indent=2))
   bc,ac=counts(before['native_render']),counts(after['native_render']);usage={x['cell']:x['fonts'] for x in after['native_render']['actual_platform_font_usage']};same=before['png']==after['png'];custom=all(usage.get(cid) and all(f['isCustomFont'] for f in usage[cid] if f['glyphCount']) for cid in changed);samecounts=all(bc.get(cid)==ac.get(cid) for cid in changed);result.update(pixel_identical=same,custom=custom,physical_font_counts_preserved=samecounts,font_count_differences={cid:[bc.get(cid),ac.get(cid)] for cid in changed if bc.get(cid)!=ac.get(cid)});assert same and custom and samecounts,str(result)
   result['ok']=True
  except Exception as e:result.update(ok=False,error=repr(e)[:1200])
  (path/'report.json').write_text(json.dumps(result,indent=2));results.append(result);print(json.dumps(result),flush=True)
 browser.close()
(B/'test_report.json').write_text(json.dumps({'at':now(),'results':results},indent=2));assert all(r['ok'] for r in results)
