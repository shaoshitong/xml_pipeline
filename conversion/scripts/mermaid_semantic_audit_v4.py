import collections,hashlib,json,os,sqlite3,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from mermaid_semantic_v4 import PARSE,check

def producers_live():
 for name,script in [("mermaid_geometry","mermaid_geometry_batch.py"),("text_batch","text_batch.py"),("harness_v2","harness_pool_v2.py"),("harness_v3","harness_pool_v3.py")]:
  try:
   o=json.loads((W/(name+"_owner.json")).read_text());p=Path("/proc")/str(o["pid"])/"cmdline"
   if p.exists() and script.encode() in p.read_bytes():return True
  except (OSError,ValueError):pass
 return False

def main():
 db=sqlite3.connect(W/'jobs.sqlite',timeout=60);db.execute('create table if not exists semantic_checks_v3 (id TEXT PRIMARY KEY,code_sha256 TEXT,method TEXT,status TEXT,details TEXT,updated_at TEXT)');db.commit();count=0;results=collections.Counter();version=json.loads((W/'runtime/mermaid/node_modules/mermaid/package.json').read_text())['version'];(W/'mermaid_semantic_v4_owner.json').write_text(json.dumps({'pid':os.getpid(),'started_at_utc':now(),'mermaid_version':version})+'\n')
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.add_script_tag(path=str(W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js'));page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:false}})")
  while True:
   items=db.execute('select j.id,j.input_manifest,j.output_record,c.code_sha256,c.method from jobs j left join semantic_checks_v3 c on c.id=j.id where j.format="mermaid" and j.output_record is not null and j.state not in ("repair_running","converting","mermaid_geometry_repairing")').fetchall();pending=[]
   for id,prep,raw,checked_hash,checked_method in items:
    out=json.loads(raw)
    if out['code_sha256']!=checked_hash or checked_method not in ('independent_official_mermaid_parser_groups_v3','independent_official_mermaid_parser_native_text_runs_v4') or (out.get('source_ast_file') and checked_method!='independent_official_mermaid_parser_native_text_runs_v4'):pending.append((id,json.loads(prep),out))
   pending.sort(key=lambda x:(not bool(x[2].get('source_ast_file')),x[0]))
   for id,prep,out in pending:
    try:
     code=(R/prep['source_code']).read_text();xml=(R/out['code_file']).read_text();assert hashlib.sha256(xml.encode()).hexdigest()==out['code_sha256'];ast=page.evaluate(PARSE,code);result=check(ast,xml)
    except Exception as e:result={'status':'reference_parse_or_audit_error','error':str(e)[:2000],'accepted':False}
    result['reference_parser_version']=version;db.execute('insert or replace into semantic_checks_v3 values (?,?,?,?,?,?)',(id,out['code_sha256'],'independent_official_mermaid_parser_native_text_runs_v4',result['status'],json.dumps(result,ensure_ascii=False),now()));db.commit();count+=1;results[result['status']]+=1
   progress={'updated_at_utc':now(),'new_checks_this_run':count,'statuses':dict(results),'scope':'Mermaid output candidates; no acceptance promotion','goal_complete':False};(W/'mermaid_semantic_v4_progress.json').write_text(json.dumps(progress,indent=2)+'\n')
   if not producers_live():break
   time.sleep(30)
  b.close()
 (W/'mermaid_semantic_v4_summary.json').write_text(json.dumps(progress,indent=2)+'\n')
if __name__=='__main__':main()
