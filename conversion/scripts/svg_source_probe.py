import collections,json,sqlite3,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');d=sqlite3.connect(R/'conversion/jobs.sqlite');n=collections.Counter();examples={}
for id,s,m in d.execute('select id,source,input_manifest from jobs where format="svg"'):
 text=(R/json.loads(m)['source_code']).read_text();root=E.fromstring(text)
 for test,ok in [('embedded_native',any(k in root.attrib for k in ['content','data-mxgraph'])),('graphviz',any(x.get('class')=='edge' for x in root.iter())),('marker',any(x.tag.endswith('}marker') or x.tag=='marker' for x in root.iter()))]:
  if ok:n[test]+=1;examples.setdefault(test,{'id':id,'source':s,'attributes':list(root.attrib)})
print(json.dumps({'counts':n,'examples':examples}))
