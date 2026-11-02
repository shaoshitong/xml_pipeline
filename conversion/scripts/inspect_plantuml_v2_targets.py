import json,sqlite3,xml.etree.ElementTree as E,collections
from native_worker import W,R
D=sqlite3.connect(W/'jobs.sqlite');out=[]
for id,raw in D.execute("select id,record from plantuml_geometry_repairs where state='failed' limit 12"):
 work=W/'plantuml_geometry_repair'/id;p=work/'source.svg'
 if not p.exists():continue
 root=E.parse(p).getroot();types=collections.Counter(e.tag.rsplit('}',1)[-1] for e in root.iter());groups=[e for e in root.iter() if e.tag.endswith('}g')];item={'id':id,'type':root.get('data-diagram-type'),'groups':len(groups),'link_groups':sum(g.get('class')=='link' for g in groups),'tags':dict(types),'error':json.loads(raw)['error'][:2500]}
 if item['type']=='STATE':item['circles']=[e.attrib for e in root.iter() if e.tag.endswith('}ellipse') or e.tag.endswith('}circle')];item['last_children']=[{'tag':e.tag.rsplit('}',1)[-1],**e.attrib} for e in list(list(root)[-1])[-8:]]
 out.append(item)
print(json.dumps(out))
