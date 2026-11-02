import collections,hashlib,html,json,os,re,sqlite3,time,xml.etree.ElementTree as E
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,s):self.parts.append(s)
 def handle_starttag(self,t,a):
  if t=='br':self.parts.append(' ')
def text(s):
 p=Text();p.feed(html.unescape(s or ''));return re.sub(r'\s+',' ',''.join(p.parts)).strip()
PARSE='''async code=>{const d=await mermaid.mermaidAPI.getDiagramFromText(code);const v=d.db.getVertices?.(),e=d.db.getEdges?.();return {type:d.type,vertices:v instanceof Map?[...v.entries()]:v,edges:e,groups:d.db.getSubGraphs?.()};}'''
def check(ast,xml):
 if not ast.get('vertices') or ast.get('edges') is None:return {'status':'unsupported_diagram_type','type':ast['type']}
 vertices=dict(ast['vertices']) if isinstance(ast['vertices'],list) else ast['vertices'];expected_nodes={id:text(v.get('text') or id) for id,v in vertices.items()};root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p};actual_nodes={};id_map={};edges=[];unmapped=[]
 for c in root.iter('mxCell'):
  p=parents.get(c);cid=c.get('id') or (p.get('id') if p is not None else None);mid=c.get('mermaidId') or (p.get('mermaidId') if p is not None else None);label=c.get('value') if c.get('value') is not None else p.get('label','') if p is not None else ''
  if c.get('vertex')=='1' and mid and mid.startswith('n:'):id_map[cid]=mid[2:];actual_nodes[mid[2:]]=text(label)
  if c.get('edge')=='1':edges.append((c,label))
 expected_edges=collections.Counter((e['start'],e['end'],text(e.get('text',''))) for e in ast['edges']);actual_edges=collections.Counter()
 # Model-generated XML may not retain converter-specific mermaidId annotations.
 # Only infer an id from a unique exact source label and a unique candidate vertex.
 label_sources=collections.defaultdict(list);label_cells=collections.defaultdict(list)
 for sid,label in expected_nodes.items():label_sources[label].append(sid)
 for c in root.iter('mxCell'):
  if c.get('vertex')!='1':continue
  p=parents.get(c);cid=c.get('id') or (p.get('id') if p is not None else None);label=c.get('value') if c.get('value') is not None else p.get('label','') if p is not None else '';label_cells[text(label)].append(cid)
 for label,sids in label_sources.items():
  candidates=label_cells.get(label,[])
  if len(sids)==1 and len(candidates)==1 and sids[0] not in actual_nodes:id_map[candidates[0]]=sids[0];actual_nodes[sids[0]]=label
 for c,label in edges:
  if not text(label):
   p=parents.get(c);cid=c.get('id') or (p.get('id') if p is not None else None);children=[text(x.get('value','')) for x in root.iter('mxCell') if x.get('parent')==cid and x.get('vertex')=='1' and x.get('value')]
   if len(children)==1:label=children[0]
  src=id_map.get(c.get('source'));tgt=id_map.get(c.get('target'))
  if src is None or tgt is None:unmapped.append({'cell':c.get('id'),'source':c.get('source'),'target':c.get('target'),'label':label})
  actual_edges[(src,tgt,text(label))]+=1
 mismatched=[{'node':id,'expected':v,'actual':actual_nodes.get(id)} for id,v in expected_nodes.items() if actual_nodes.get(id)!=v];extra_nodes=sorted(set(actual_nodes)-set(expected_nodes));missing_edges=list((expected_edges-actual_edges).elements());extra_edges=list((actual_edges-expected_edges).elements());ok=not mismatched and not extra_nodes and not missing_edges and not extra_edges and not unmapped
 return {'status':'node_edge_text_match' if ok else 'source_content_mismatch','type':ast['type'],'expected_nodes':len(expected_nodes),'expected_edges':sum(expected_edges.values()),'actual_nodes':len(actual_nodes),'actual_edges':len(edges),'node_text_mismatches':mismatched,'extra_nodes':extra_nodes,'missing_or_changed_edges':missing_edges,'extra_or_changed_edges':extra_edges,'unmapped_bound_nodes':unmapped,'subgraphs_pending_hierarchy_check':len(ast.get('groups') or []),'limitations':['Shape/style/layout and visual fidelity are separate gates.','Subgraph hierarchy and non-flowchart diagram types require additional checks.'],'accepted':False}
def main():
 db=sqlite3.connect(W/'jobs.sqlite',timeout=60);db.execute('create table if not exists semantic_checks (id TEXT PRIMARY KEY,code_sha256 TEXT,method TEXT,status TEXT,details TEXT,updated_at TEXT)');db.commit();count=0;results=collections.Counter();version=json.loads((W/'runtime/mermaid/node_modules/mermaid/package.json').read_text())['version'];(W/'mermaid_semantic_owner.json').write_text(json.dumps({'pid':os.getpid(),'started_at_utc':now(),'mermaid_version':version})+'\n')
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.route('**/*',lambda r:r.abort());page.set_content('<html></html>');page.add_script_tag(path=str(W/'runtime/mermaid/node_modules/mermaid/dist/mermaid.min.js'));page.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:false}})")
  while True:
   items=db.execute('select j.id,j.input_manifest,j.output_record,c.code_sha256,c.method from jobs j left join semantic_checks c on c.id=j.id where j.format="mermaid" and j.output_record is not null and j.state not in ("repair_running","converting")').fetchall();pending=[]
   for id,prep,raw,checked_hash,checked_method in items:
    out=json.loads(raw)
    if out['code_sha256']!=checked_hash or checked_method!='independent_official_mermaid_parser_v2':pending.append((id,json.loads(prep),out))
   for id,prep,out in pending:
    try:
     code=(R/prep['source_code']).read_text();xml=(R/out['code_file']).read_text();assert hashlib.sha256(xml.encode()).hexdigest()==out['code_sha256'];ast=page.evaluate(PARSE,code);result=check(ast,xml)
    except Exception as e:result={'status':'reference_parse_or_audit_error','error':str(e)[:2000],'accepted':False}
    result['reference_parser_version']=version;db.execute('insert or replace into semantic_checks values (?,?,?,?,?,?)',(id,out['code_sha256'],'independent_official_mermaid_parser_v2',result['status'],json.dumps(result,ensure_ascii=False),now()));db.commit();count+=1;results[result['status']]+=1
   progress={'updated_at_utc':now(),'new_checks_this_run':count,'statuses':dict(results),'scope':'Mermaid output candidates; no acceptance promotion','goal_complete':False};(W/'mermaid_semantic_progress.json').write_text(json.dumps(progress,indent=2)+'\n')
   queued=db.execute('select count(*) from jobs where format="mermaid" and state in ("queued","converting","repair_running")').fetchone()[0]
   if not queued:break
   owner=json.loads((W/'text_batch_owner.json').read_text());pid=owner['pid'];proc=__import__('pathlib').Path('/proc')/str(pid)/'cmdline'
   if not proc.exists() or 'text_batch.py' not in proc.read_bytes().replace(b'\0',b' ').decode():break
   time.sleep(30)
  b.close()
 (W/'mermaid_semantic_summary.json').write_text(json.dumps(progress,indent=2)+'\n')
if __name__=='__main__':main()
