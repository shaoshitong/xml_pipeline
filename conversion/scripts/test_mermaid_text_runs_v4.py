import json,sqlite3,xml.etree.ElementTree as E
from native_worker import R,W,now
from mermaid_semantic_v4 import check
D=sqlite3.connect(W/'jobs.sqlite');ids=['ab692a4bc019ce00ed3be2f5838f2285c5789c6ddcb59fc94a6d2ba16c9ff9dd','2806c6a330ea68e1080a8109be7f7dbef25f67f81b6bb4885ff430f39dc9258b','5dcb061796f21db463da1ac6e53b6505fcabe5b93b2e15c4f58e19a8368b5ba9'];results=[]
for id in ids:
 r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);xml=(R/r['code_file']).read_text();ast=json.loads((R/r['source_ast_file']).read_text());result=check(ast,xml);assert result['status']=='node_edge_text_match',result;assert result['reconstructed_native_text_runs'];negative=[]
 for kind in ['missing_node_text','missing_edge_text','wrong_terminal','duplicate_source_tag']:
  root=E.fromstring(xml);cells=list(root.iter('mxCell'))
  if kind=='missing_node_text':
   c=next(c for c in cells if c.get('value') and c.get('parent','').startswith('node_'));c.set('value','DELETED')
  elif kind=='missing_edge_text':
   edges={c.get('id') for c in cells if c.get('edge')=='1'};options=[c for c in cells if c.get('value') and c.get('parent') in edges]
   if not options:continue
   options[0].set('value','DELETED')
  elif kind=='wrong_terminal':
   c=next(c for c in cells if c.get('edge')=='1');c.set('target',c.get('source'))
  else:
   c=[c for c in cells if c.get('mermaidId')];c[1].set('mermaidId',c[0].get('mermaidId'))
  assert check(ast,E.tostring(root,encoding='unicode'))['status']=='source_content_mismatch',kind;negative.append(kind)
 results.append({'id':id,'check':result,'negative_rejected':negative})
(W/'mermaid_text_runs_v4_tests.json').write_text(json.dumps({'at':now(),'results':results,'ok':True},indent=2));print(json.dumps({'ok':True,'cases':len(results),'negative_checks':sum(len(x['negative_rejected']) for x in results)}))
