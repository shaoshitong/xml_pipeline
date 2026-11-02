import copy,json,sqlite3,xml.etree.ElementTree as E
from native_worker import R,W,now
from mermaid_semantic_v3 import check
D=sqlite3.connect(W/'jobs.sqlite');inspected=json.loads((W/'mermaid_group_inspection.json').read_text());results=[]
from playwright.sync_api import sync_playwright
from mermaid_semantic_v3 import PARSE
results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.add_script_tag(path=str(W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js'));page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:false}})")
 for i in inspected:
  raw,prep=D.execute('select output_record,input_manifest from jobs where id=?',(i['id'],)).fetchone();r=json.loads(raw);source=(R/json.loads(prep)['source_code']).read_text();xml=(R/r['code_file']).read_text();ast=page.evaluate(PARSE,source);result=check(ast,xml);row={'id':i['id'],'check':result};results.append(row)
  if i['id'].startswith('1de9'):
   assert result['status']=='node_edge_text_match' and result['matched_groups']==9
   broken=E.fromstring(xml);cell=next(c for c in broken.iter('mxCell') if c.get('vertex')=='1' and c.get('parent') not in ['0','1']);cell.set('parent','1');negative=check(ast,E.tostring(broken,encoding='unicode'));assert negative['status']=='source_content_mismatch' and negative['group_errors'];row['negative_detached_member']=negative['group_errors']
   broken=E.fromstring(xml);wrapper=next(c for c in broken.iter() if c.get('label')=='Top Military Officials');wrapper.set('label','Changed Title');negative=check(ast,E.tostring(broken,encoding='unicode'));assert negative['status']=='source_content_mismatch';row['negative_changed_group_title_detected']=True
   broken=E.fromstring(xml);edge=next(c for c in broken.iter('mxCell') if c.get('edge')=='1');edge.set('target',edge.get('source'));negative=check(ast,E.tostring(broken,encoding='unicode'));assert negative['status']=='source_content_mismatch' and negative['missing_or_changed_edges'];row['negative_wrong_connection_detected']=True
  if i['id'].startswith('4c85'):assert result['status']=='node_edge_text_match' and result['matched_groups']==4
  if i['id'].startswith('2f10'):assert result['status']=='source_content_mismatch' and any(m['node']=='Key' for m in result['node_text_mismatches'])
 b.close()
(W/'mermaid_groups_v3_tests.json').write_text(json.dumps({'checked_at_utc':now(),'results':results,'ok':True},indent=2)+'\n');print(json.dumps({'ok':True,'results':[{'id':r['id'],'status':r['check']['status'],'groups':r['check']['matched_groups'],'group_errors':r['check']['group_errors']} for r in results]}))
