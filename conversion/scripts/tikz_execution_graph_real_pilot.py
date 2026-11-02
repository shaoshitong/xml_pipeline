"""Read-only candidate selection plus isolated macro/loop compile pilot."""
import hashlib,json,re,sqlite3,uuid
from pathlib import Path
from native_worker import R,W,now
from tikz_execution_graph import compile_execution_graph

db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True)
selected=[]
for id,raw in db.execute("select id,output_record from jobs where format='tikz' and output_record is not null order by coalesce(json_extract(output_record,'$.metrics.original_reference_ssim_512'),0) desc"):
 record=json.loads(raw)
 if not record.get('original_source_code'):continue
 path=(R/record['original_source_code']).resolve()
 if not path.is_relative_to(R/'clean') or not path.is_file():continue
 data=path.read_bytes()
 if len(data)>12000 or hashlib.sha256(data).hexdigest()!=record['source_code_sha256']:continue
 code=data.decode()
 if r'\foreach' not in code or r'\node' not in code or r'\draw' not in code:continue
 if any(t in code for t in (r'\begin{axis}',r'\addplot',r'\includegraphics',r'\input{',r'\include{')):continue
 # Selection heuristics choose a small graph, never assert its true topology.
 if not re.search(r'\\draw(?:\[[^\]]*\])?\s*\([A-Za-z]',code):continue
 selected.append({'id':id,'source':record['source'],'source_file':str(path.relative_to(R)),'source_sha256':record['source_code_sha256'],'bytes':len(data),'foreach_statements':code.count(r'\foreach'),'draw_statements':code.count(r'\draw'),'node_statements':code.count(r'\node'),'reference_ssim':record.get('metrics',{}).get('original_reference_ssim_512')})
 if len(selected)>=12:break
db.close()
selected.sort(key=lambda r:(r['draw_statements']+r['node_statements'],r['bytes']))
root=W/'tikz_execution_graph_prototype'/('real_'+uuid.uuid4().hex[:12]);root.mkdir(parents=True)
(root/'selection.json').write_text(json.dumps({'at':now(),'selection_heuristic_only':True,'candidates':selected},indent=2)+'\n')
results=[]
for candidate in selected[:3]:
 data=(R/candidate['source_file']).read_bytes()
 result=compile_execution_graph(data,root/candidate['id']);graph=result.get('graph',{})
 report={'id':candidate['id'],'source':candidate['source'],'source_sha256':candidate['source_sha256'],'ok':result['ok'],'error':result.get('error'),'source_nodes':len(graph.get('nodes',[])),'source_edges':len(graph.get('edges',[])),'graph_failures':graph.get('failures'),'pdf_pixel_equivalence':result.get('instrumentation_pdf_pixel_equivalence'),'proof':str(root/candidate['id']/'execution_graph.json')}
 results.append(report);print(json.dumps(report),flush=True)
 if result['ok']:break
out={'at':now(),'selected_candidates':len(selected),'results':results,'successful_real_cases':sum(r['ok'] for r in results),'published':False,'root':str(root)}
(W/'tikz_execution_graph_real_pilot.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True)
