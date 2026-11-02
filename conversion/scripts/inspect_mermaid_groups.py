import json,sqlite3,xml.etree.ElementTree as E
from playwright.sync_api import sync_playwright
from native_worker import R,W
from mermaid_semantic_audit import PARSE
D=sqlite3.connect(W/'jobs.sqlite');ids=['1de9d01cf0831c9382c965366832b19591f6c3c97ea17b9bcb46cdbf5fff2bfe','4c85f70fd86d5ee3e2444eb4768bde0d089e987e9a5788cf04be6cac9268c100','2f1083fcf9ae2cfa6116746def55ab7f03ecffe755d2460b85a4ca5eb9edc909'];out=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.add_script_tag(path=str(W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js'));page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:false}})")
 for id in ids:
  raw,prep=D.execute('select output_record,input_manifest from jobs where id=?',(id,)).fetchone();r=json.loads(raw);inp=json.loads(prep);ast=page.evaluate(PARSE,(R/inp['source_code']).read_text());xml=E.fromstring((R/r['code_file']).read_text());cells=[]
  for c in xml.findall('.//mxGraphModel/root/*'):
   m=c if c.tag=='mxCell' else c.find('mxCell');cells.append({'wrapper':c.attrib if c.tag!='mxCell' else {},'cell':m.attrib})
  out.append({'id':id,'groups':ast['groups'],'vertices':ast['vertices'],'cells':cells})
 b.close()
(W/'mermaid_group_inspection.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
