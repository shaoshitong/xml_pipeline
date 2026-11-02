import hashlib,html,io,json,re,sqlite3,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from scipy.ndimage import label,find_objects
from native_worker import R,W,native,now
id='0005278c179cc15435717683c966700f047e3fb3633adee74122ac4006b19377';db=sqlite3.connect(W/'jobs.sqlite',timeout=60);out=json.loads(db.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);xml=(R/out['code_file']).read_text();data=(R/out['original_reference']).read_bytes();ref=Image.open(io.BytesIO(data)).convert('RGBA');bg=Image.new('RGBA',ref.size,'white');bg.alpha_composite(ref);rgb=np.array(bg.convert('RGB'));mask=np.all(rgb==[236,236,255],axis=2);labels,n=label(mask);boxes=[]
for slices in find_objects(labels):
 if slices is None:continue
 y,x=slices;area=(y.stop-y.start)*(x.stop-x.start)
 if area>200:boxes.append((x.start-1,y.start-1,x.stop-x.start+2,y.stop-y.start+2))
print('target_node_boxes',boxes,flush=True)
D=W/'case_repairs'/id/'root_visual_font_and_labels';D.mkdir(parents=True,exist_ok=True);(D/'before.drawio').write_text(xml);(D/'before_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));root=E.fromstring(xml)
for c in root.iter('mxCell'):
 st=c.get('style','');st=re.sub(r'fontFamily=[^;]*','fontFamily=Arial',st);c.set('style',st)
 # Keep all semantic nodes and adjust the border geometry from unambiguous source-color components.
 if c.get('id') in [str(x) for x in range(2,9)] and len(boxes)==7:
  boxes.sort(key=lambda b:(round(b[1]/5),b[0]));b=boxes[int(c.get('id'))-2];g=c.find('mxGeometry')
  for k,v in zip(('x','y','width','height'),b):g.set(k,str(v))
 # Native edge child labels move with their actual connector; avoid independent fake text boxes.
 if c.get('id') in [str(x) for x in range(16,23)]:
  edge=str(int(c.get('id'))-7);c.set('parent',edge);c.set('connectable','0');g=c.find('mxGeometry');g.set('relative','1');g.set('x','0');g.set('y','0');g.set('width','144');g.set('height','22');E.SubElement(g,'mxPoint',{'as':'offset','x':'-72','y':'-11'})
candidate=E.tostring(root,encoding='unicode');(D/'diagram.drawio').write_text(candidate);r=native.native_job(candidate,ref.width,ref.height,90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');
if r['ok']:(D/'image.png').write_bytes(r.pop('png'))
audit={'time':now(),'id':id,'root_review_before':{'pass':False,'issues':['Original sans-serif text changed to serif fallback.','Paired edge label backgrounds touch/merge and sit higher than in original.','Label boxes are detached vertices instead of edge children.']},'target_node_boxes':boxes,'render':r,'candidate_directory':str(D),'state':'pending_root_recheck'};(D/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');db.execute('update jobs set state="needs_quality_repair",error=?,updated_at=? where id=?',('Root review overrides critic pass: font fallback and detached/overlapping edge label boxes need correction; deterministic repair candidate pending recheck.',now(),id));db.commit();print(json.dumps(audit))
