import collections,json,sqlite3
from native_worker import R,W,now
from tikz_literal_graph import parse_literal
d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);counts=collections.Counter();failures=collections.Counter();eligible=[]
for id,raw in d.execute('select id,output_record from jobs where format="tikz" and output_record is not null and state in ("rendered","needs_quality_repair") and worker_pid is NULL and coalesce(json_extract(output_record,"$.edges"),0)=0'):
 r=json.loads(raw);counts['unbound_idle_tikz']+=1
 try:s=parse_literal((R/r['original_source_code']).read_text())
 except Exception as exc:failures[str(exc).split(':')[0]]+=1;continue
 counts['complete_explicit_graph_parse']+=1
 if r.get('native_page_padding') or r.get('native_canvas_contract'):counts['needs_padded_geometry_bridge']+=1;continue
 eligible.append({'id':id,'input_hash':r['code_sha256'],'nodes':len(s['nodes']),'edges':len(s['edges']),'reference_ssim':r.get('metrics',{}).get('original_reference_ssim_512')})
counts['current_original_geometry_candidates']=len(eligible);out={'at':now(),'counts':counts,'unsupported_source_reasons':dict(failures),'candidates':eligible,'goal_complete':False,'note':'Current deterministic parser cohort only. Other inputs remain in full-scope conversion/Harness queues; no quality acceptance implied.'};(W/'tikz_literal_inventory.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='candidates'}))
