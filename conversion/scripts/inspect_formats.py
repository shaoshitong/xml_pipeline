import collections,json,sqlite3,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';db=sqlite3.connect(W/'jobs.sqlite');tags=collections.Counter();flags=collections.Counter();sources=collections.Counter();examples=[]
for id,source,m in db.execute('select id,source,input_manifest from jobs where format="svg" order by id'):
 p=json.loads(m);code=(R/p['source_code']).read_text();sources[source]+=1
 try:
  root=E.fromstring(code);t=collections.Counter(x.tag.rsplit('}',1)[-1] for x in root.iter());tags.update(t)
  for name in ['text','image','foreignObject','clipPath','mask','linearGradient','radialGradient','use','filter','style','marker']:
   if t[name]:flags[name]+=1
  if len(examples)<8:examples.append({'id':id,'source':source,'tags':t,'code_excerpt':code[:4500]})
 except Exception:flags['parse_error']+=1
print(json.dumps({'svg_sources':sources,'svg_element_counts':tags,'svg_samples_with':flags,'examples':examples},ensure_ascii=False))
print('TEXT_STATS')
for fmt in ['mermaid','plantuml']:
 rows=[json.loads(x[0]) for x in db.execute('select output_record from jobs where format=? and state="rendered" and output_record is not null',(fmt,))];scores=sorted(x['metrics']['original_reference_ssim_512'] for x in rows)
 print(json.dumps({'format':fmt,'count':len(rows),'ssim_quantiles':[scores[int((len(scores)-1)*p)] for p in [0,.1,.5,.9,1]] if scores else []}))
print('EXAMPLE_TEXT')
for fmt in ['mermaid','plantuml']:
 x=db.execute('select id,input_manifest,output_record from jobs where format=? and state="rendered" order by id limit 1',(fmt,)).fetchone();p=json.loads(x[1]);print(json.dumps({'id':x[0],'format':fmt,'source':(R/p['source_code']).read_text(),'output':json.loads(x[2])},ensure_ascii=False))
