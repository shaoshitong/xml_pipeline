import io,json,re,sqlite3,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from scipy.ndimage import label,find_objects
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
id='0005278c179cc15435717683c966700f047e3fb3633adee74122ac4006b19377';db=sqlite3.connect(W/'jobs.sqlite');out=json.loads(db.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);D=W/'case_repairs'/id/'root_visual_font_and_labels';data=(R/out['original_reference']).read_bytes();ref=Image.open(io.BytesIO(data)).convert('RGBA');bg=Image.new('RGBA',ref.size,'white');bg.alpha_composite(ref);rgb=np.array(bg.convert('RGB'));mask=(rgb[:,:,0]==rgb[:,:,1])&(rgb[:,:,1]==rgb[:,:,2])&(rgb[:,:,0]>=210)&(rgb[:,:,0]<=250);labels,n=label(mask);boxes=[]
for slices in find_objects(labels):
 if slices is None:continue
 y,x=slices;w=x.stop-x.start;h=y.stop-y.start
 if w>100 and h>10:boxes.append((x.start,y.start,w,h))
boxes.sort(key=lambda b:(round(b[1]/5),b[0]));print('label_boxes',boxes,flush=True);assert len(boxes)==7
root=E.fromstring((D/'diagram.drawio').read_text());cells={c.get('id'):c for c in root.iter('mxCell')}
for n,b in enumerate(boxes,16):
 c=cells[str(n)];g=c.find('mxGeometry');g.set('width',str(b[2]));g.set('height',str(b[3]));x,y,w,h=b;gray=int(np.median(rgb[y:y+h,x:x+w,0][mask[y:y+h,x:x+w]]));c.set('style',re.sub(r'fillColor=[^;]*','fillColor=#'+format(gray,'02x')*3,c.get('style')))
for n in (10,11,12,13):
 c=cells[str(n)];st=c.get('style');st=st.replace('exitX=0.2;','exitX=0.23;').replace('exitX=0.8;','exitX=0.77;').replace('entryX=0.2;','entryX=0.23;').replace('entryX=0.8;','entryX=0.77;');c.set('style',st)
xml=E.tostring(root,encoding='unicode')
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome');page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<div id="graph"></div>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(native.renderer_path(R).parent/'assets/viewer-static.min.js'));states=page.evaluate('''xml=>{const g=new Graph(document.getElementById('graph'));const d=mxUtils.parseXml(xml);new mxCodec(d).decode(d.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();return Object.fromEntries(Object.entries(g.model.cells).filter(([id,c])=>+id>=16).map(([id,c])=>{const s=g.view.getState(c);return [id,{x:s.x,y:s.y}]}));}''',xml);b.close()
for n,box in enumerate(boxes,16):
 g=cells[str(n)].find('mxGeometry');offset=g.find('mxPoint');state=states[str(n)];offset.set('x',str(float(offset.get('x'))+box[0]-state['x']));offset.set('y',str(float(offset.get('y'))+box[1]-state['y']))
xml=E.tostring(root,encoding='unicode');(D/'diagram.drawio').write_text(xml);r=native.native_job(xml,ref.width,ref.height,90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert r['ok'];png=r.pop('png');(D/'image.png').write_bytes(png);audit=json.loads((D/'audit.json').read_text());audit.update(label_boxes=boxes,label_binding='Each text chip is an actual child vertex of its semantic edge, with relative geometry and offset to original source pixel bounds.',render=r);(D/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps({'ok':True,'label_boxes':boxes,'states_before':states}))
