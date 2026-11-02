import hashlib,html,io,json,sqlite3,time,xml.etree.ElementTree as E
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity
from native_worker import R,W,native,normalize,now

def run():
 d=sqlite3.connect(W/'jobs.sqlite',timeout=60);results=[]
 for id,raw,prep in d.execute('select id,input_record,input_manifest from jobs where format="svg" and state="queued"').fetchall():
  inp=json.loads(prep);source=json.loads(raw);code=(R/inp['source_code']).read_text();root=E.fromstring(code);content=root.get('content')
  if not content:continue
  try:
   if not content.lstrip().startswith('<'):content=html.unescape(content)
   xml,pages,model=normalize(content);cells=list(model.iter('mxCell'));parents={child:parent for parent in model.iter() for child in parent};cid=lambda c:c.get('id') or parents.get(c,E.Element('none')).get('id');vertices={cid(c) for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1'];assert vertices
   # Claim only queued rows; no duplicate worker touches this route yet.
   cursor=d.execute('update jobs set state="native_svg_running", attempts=attempts+1,updated_at=? where id=? and state="queued"',(now(),id));d.commit()
   if not cursor.rowcount:continue
   data=(R/inp['reference_image']).read_bytes();assert hashlib.sha256(code.encode()).hexdigest()==source['code_sha256'];assert hashlib.sha256(data).hexdigest()==source['image_sha256']
   render=native.native_job(xml,inp['width'],inp['height'],90,native.renderer_path(R),8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert render['ok'],json.dumps(render)
   png=render.pop('png');ref=Image.open(io.BytesIO(data)).convert('RGBA');bg=Image.new('RGBA',ref.size,'white');bg.alpha_composite(ref);ref=bg.convert('RGB');pred=Image.open(io.BytesIO(png)).convert('RGB');directory=R/'clean/drawio_unified'/id[:2]/id;out={'id':id,'source_pair_sha256':id,'source':source['source'],'category':source['category'],'source_format':'svg','source_record':source,'source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],'format':'drawio','conversion_method':'embedded_native_xml_recovery_from_svg','source_page_count':pages,'code_file':str((directory/'diagram.drawio').relative_to(R)),'image_file':str((directory/'image.png').relative_to(R)),'code_sha256':hashlib.sha256(xml.encode()).hexdigest(),'image_sha256':hashlib.sha256(png).hexdigest(),'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),'render':render['native_render'],'metrics':{'exact_reference_pixels':ref.size==pred.size and bool(np.array_equal(ref,pred)),'original_reference_ssim_512':float(structural_similarity(np.array(ref.resize((512,512))),np.array(pred.resize((512,512))),channel_axis=2,data_range=255))},'quality_state':'pending_source_and_visual_validation','converted_at_utc':now()};directory.mkdir(parents=True,exist_ok=True);(directory/'diagram.drawio').write_text(xml);(directory/'image.png').write_bytes(png);(directory/'conversion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');d.execute('update jobs set state="rendered",output_record=?,error=NULL,updated_at=? where id=?',(json.dumps(out,ensure_ascii=False),now(),id));d.commit();results.append({'id':id,'state':'rendered','metrics':out['metrics']})
  except Exception as e:
   error=type(e).__name__+': '+str(e)[:1800];d.execute('update jobs set state="needs_fallback",error=?,updated_at=? where id=?',(error,now(),id));d.commit();results.append({'id':id,'state':'needs_fallback','error':error})
  print(json.dumps(results[-1]),flush=True)
 (W/'native_svg_recovery.json').write_text(json.dumps({'finished_at_utc':now(),'results':results},indent=2)+'\n')
if __name__=='__main__':run()
