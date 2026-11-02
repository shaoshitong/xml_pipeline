import json,sqlite3,uuid
from pathlib import Path
from native_worker import R,W
from harness_context import build_context,compact_xml,hydrate,structure
D=sqlite3.connect(W/'jobs.sqlite');cases=[]
queries=[('poster_assets','format="html" and state="needs_quality_repair"'),('python_data','format="python" and source="allenai--CoSyn-400K" and state="needs_quality_repair" and json_extract(output_record,"$.conversion_method") not like "%v2"'),('svg_panels','format="svg" and json_array_length(json_extract(input_manifest,"$.panel_assets"))>0 and state="needs_quality_repair"'),('tikz_graph','format="tikz" and state="needs_quality_repair"'),('mermaid_semantics','format="mermaid" and state="rendered" and id in (select id from semantic_checks where status="source_content_mismatch")'),('plantuml','format="plantuml" and state="needs_fallback"')]
for label,where in queries:
 row=D.execute('select id,input_record,input_manifest,output_record from jobs where '+where+' order by id limit 1').fetchone()
 if not row:cases.append({'kind':label,'missing':True});continue
 id,raw,prep,prev=row;work=W/'harness_context_preflight'/id;work.mkdir(parents=True,exist_ok=True)
 try:
  previous=json.loads(prev) if prev else None;ctx=build_context(json.loads(raw),json.loads(prep),previous,work);report={'kind':label,'id':id,'assets':len(ctx['assets']),'vectors':len(ctx['vector_assets']),'fonts':len(ctx['fonts']),'source_data_provided':ctx['auxiliary'] is not None,'source_prompt_characters':len(ctx['source_for_prompt'])}
  if previous:
   xml=(R/previous['code_file']).read_text();compact=compact_xml(xml,ctx);restored,used=hydrate(compact,ctx);(work/'roundtrip.drawio').write_text(restored);report.update(candidate_prompt_characters=len(compact),candidate_resource_cells=len(used),structure=structure(restored,ctx))
  report['ok']=True
 except Exception as e:report={'kind':label,'id':id,'ok':False,'error':type(e).__name__+': '+str(e)}
 cases.append(report)
(W/'harness_context_preflight.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n');print(json.dumps(cases,ensure_ascii=False))
