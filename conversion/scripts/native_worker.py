import argparse,base64,concurrent.futures,datetime,hashlib,importlib.util,io,json,os,sqlite3,sys,time,urllib.parse,xml.etree.ElementTree as ET,zlib
from pathlib import Path
import pyarrow.parquet as pq
from PIL import Image
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(R/'scripts'))
import curate_pairs as core
import curate_derived as native
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def pair(row):
 if row.get('clean_file'):
  pf=pq.ParquetFile(R/row['clean_file']);offset=row['clean_row'];group=0
  while offset>=pf.metadata.row_group(group).num_rows:offset-=pf.metadata.row_group(group).num_rows;group+=1
  columns=sorted({row['image_key'],row['code_key']});x=pf.read_row_group(group,columns=columns).slice(offset,1).to_pylist()[0]
  data=core.image_bytes(x[row['image_key']],R/'clean'/row['source']/'source_files');code=core.code_value(x)[0] if row['code_key'] in ('messages','conversations','conversation') else core.text_content(x[row['code_key']])
  if row.get('profile'):code=core.unwrap_code(code)
 else:data=(R/(row.get('reference_image') or row['image_file'])).read_bytes();code=(R/row['code_file']).read_text()
 assert sha(data)==row['image_sha256'] and sha(code.encode())==row['code_sha256']
 return data,code

def normalize(code):
 root=ET.fromstring(code);pages=list(root.findall('diagram')) if root.tag=='mxfile' else []
 if root.tag=='mxGraphModel':model=root
 elif pages:
  p=pages[0];model=p.find('mxGraphModel')
  if model is None:
   text=(p.text or '').strip()
   if text.startswith('<'):model=ET.fromstring(text)
   else:model=ET.fromstring(urllib.parse.unquote(zlib.decompress(base64.b64decode(text),-15).decode()))
 else:raise ValueError('no mxGraphModel')
 assert model.tag=='mxGraphModel'
 # Preserve graph and page geometry exactly, but use a single canonical uncompressed page.
 out=ET.Element('mxfile',{'host':'app.diagrams.net','type':'device'});diagram=ET.SubElement(out,'diagram',{'id':'page-1','name':pages[0].get('name','Page-1') if pages else 'Page-1'});diagram.append(model)
 return ET.tostring(out,encoding='unicode'),max(1,len(pages)),model

def run(item):
 id,raw=item;row=json.loads(raw);started=time.monotonic();directory=R/'clean/drawio_unified'/id[:2]/id
 try:
  data,code=pair(row);xml,pages,model=normalize(code);cells=list(model.iter('mxCell'));vertices=[c for c in cells if c.get('vertex')=='1'];edges=[c for c in cells if c.get('edge')=='1']
  if not vertices:raise ValueError('empty vertex set')
  if all('shape=image' in c.get('style','') for c in vertices):raise ValueError('raster-only diagram wrapper')
  image=Image.open(io.BytesIO(data));width,height=image.size
  result=native.native_job(xml,width,height,90,native.renderer_path(R),max_side=8192,runtime_cache=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
  if not result['ok']:raise ValueError(json.dumps({k:v for k,v in result.items() if k!='png'}))
  directory.mkdir(parents=True,exist_ok=True);(directory/'diagram.drawio').write_text(xml);(directory/'image.png').write_bytes(result['png'])
  metrics={}
  try:
   import numpy as np
   from skimage.metrics import structural_similarity
   ref=image.convert('RGBA');background=Image.new('RGBA',ref.size,'white');background.alpha_composite(ref);ref=background.convert('RGB');pred=Image.open(io.BytesIO(result['png'])).convert('RGB');before=np.array(ref.resize((512,512)));after=np.array(pred.resize((512,512)))
   metrics={'exact_reference_pixels':ref.size==pred.size and bool(np.array_equal(np.array(ref),np.array(pred))),'original_reference_ssim_512':float(structural_similarity(before,after,channel_axis=2,data_range=255)),'interpretation':'Diagnostic only. Material original-reference mismatch requires repair even when the output matches its XML. Alpha is composited on white for comparison.'}
  except Exception as e:metrics={'error_type':type(e).__name__}
  output={'id':id,'source_pair_sha256':id,'source':row['source'],'category':row['category'],'source_format':row['format'],'source_image_sha256':row['image_sha256'],'source_code_sha256':row['code_sha256'],'code_file':str((directory/'diagram.drawio').relative_to(R)),'image_file':str((directory/'image.png').relative_to(R)),'code_sha256':sha(xml.encode()),'image_sha256':sha(result['png']),'format':'drawio','conversion_method':'native_xml_normalization','source_page_count':pages,'selected_source_page':0,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(bool(c.get('source') and c.get('target')) for c in edges),'render':result['native_render'],'metrics':metrics,'converted_at_utc':now(),'seconds':round(time.monotonic()-started,3),'quality_state':'pending_visual_acceptance','source_record':row}
  (directory/'conversion.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');return id,'rendered',output,None
 except Exception as e:return id,'needs_fallback',None,type(e).__name__+': '+str(e)[:1800]

def main(args):
 db=sqlite3.connect(W/'jobs.sqlite');db.execute('PRAGMA busy_timeout=30000')
 items=db.execute('SELECT id,input_record FROM jobs WHERE route="native" AND state="queued" ORDER BY source,id LIMIT ?',(args.limit,)).fetchall()
 if args.pilot:
  selected=[];seen=set()
  for item in items:
   source=json.loads(item[1])['source']
   if source not in seen:selected.append(item);seen.add(source)
  items=selected
 for id,_ in items:db.execute('UPDATE jobs SET state="running",attempts=attempts+1,updated_at=? WHERE id=?',(now(),id))
 db.commit();counts={};log=W/'native_events.jsonl'
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool,log.open('a') as f:
  for id,state,output,error in pool.map(run,items):
   db.execute('UPDATE jobs SET state=?,updated_at=?,output_record=?,error=? WHERE id=?',(state,now(),json.dumps(output,ensure_ascii=False) if output else None,error,id));db.commit();counts[state]=counts.get(state,0)+1;event={'time':now(),'id':id,'state':state,'error':error};f.write(json.dumps(event)+'\n');f.flush();print(json.dumps(event),flush=True)
 summary={'finished_at_utc':now(),'selected':len(items),'counts':counts,'all_state_counts':dict(db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state').fetchall()),'goal_complete':False};(W/('native_pilot.json' if args.pilot else 'native_batch.json')).write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);p.add_argument('--limit',type=int,default=2000);p.add_argument('--pilot',action='store_true');main(p.parse_args())
