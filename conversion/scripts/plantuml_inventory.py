import json,sqlite3,collections,re
from PIL import Image
from native_worker import R,W,now
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);counts=collections.Counter();sources=collections.Counter();bad=[]
for id,raw,source in D.execute("select id,input_manifest,json_extract(input_record,'$.source') from jobs where format='plantuml'"):
 try:
  inp=json.loads(raw);im=Image.open(R/inp['reference_image']);metadata=str(im.info.get('plantuml',''));versions=re.findall(r'PlantUML version ([^\s(]+)',metadata);counts[','.join(sorted(set(versions))) if versions else 'missing_version_metadata']+=1;sources[source]+=1
 except Exception as e:bad.append({'id':id,'error':repr(e)})
out={'at':now(),'count':sum(counts.values()),'versions':dict(counts),'sources':dict(sources),'errors':bad};(W/'plantuml_version_inventory.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
