import json,sqlite3,xml.etree.ElementTree as E
from native_worker import W
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);out=[]
for id,raw in D.execute("select id,record from plantuml_geometry_repairs where state='failed' limit 6"):
 p=W/'plantuml_geometry_repair'/id/'source.svg';item={'id':id,'error':json.loads(raw)['error'][:800]}
 if p.exists():
  root=E.parse(p).getroot();item.update(type=root.get('data-diagram-type'),groups=[e.attrib for e in root.iter() if e.tag.endswith('}g')][:8],tags=list({e.tag.rsplit('}',1)[-1] for e in root.iter()}))
 out.append(item)
print(json.dumps(out))
