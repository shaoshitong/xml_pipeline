import collections,json,sqlite3
from native_worker import R,W
D=sqlite3.connect(W/'jobs.sqlite');rows=D.execute('select s.id,s.details,j.input_manifest,j.output_record from semantic_checks s join jobs j on j.id=s.id where s.status="source_content_mismatch" and s.code_sha256=json_extract(j.output_record,"$.code_sha256")').fetchall();patterns=collections.Counter();samples={}
for id,raw,prep,out in rows:
 d=json.loads(raw);key=tuple(bool(d.get(k)) for k in ['node_text_mismatches','extra_nodes','missing_or_changed_edges','extra_or_changed_edges','unmapped_bound_nodes']);patterns[str(key)]+=1
 if str(key) not in samples:samples[str(key)]={'id':id,'details':d,'source':(R/json.loads(prep)['source_code']).read_text()[:4500]}
print(json.dumps({'total':len(rows),'patterns':patterns,'samples':list(samples.values())},ensure_ascii=False))
