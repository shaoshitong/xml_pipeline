"""Re-read saved prototype artifacts and independently verify hashes/pixel proofs."""
import hashlib,json,sys
from pathlib import Path
from native_worker import W,now
from tikz_execution_graph import graph_from_events,parse_events
sys.path.append(str(W/'runtime/python_packages'))
import pymupdf
sha=lambda b:hashlib.sha256(b).hexdigest()
roots=[]
for name in ('tikz_execution_graph_smoke.json','tikz_execution_graph_real_pilot.json'):
 report=json.loads((W/name).read_text());roots.extend(Path(r.get('proof_file') or r.get('proof')) for r in report['results'])
results=[]
for file in roots:
 result=json.loads(file.read_text());folder=file.parent;checks=[]
 assert sha(Path(result['engine_file']).read_bytes())==result['engine_sha256']
 for source in result['pgf_core_files'].values():assert sha(Path(source['file']).read_bytes())==source['sha256']
 for kind,run in result['runs'].items():
  work=folder/kind
  assert sha((work/'original_source.tex').read_bytes())==result['source_sha256']
  assert sha((work/'source.tex').read_bytes())==run['wrapper_sha256']
  assert sha((work/'source.pdf').read_bytes())==run['pdf_sha256']
 assert sha((folder/'instrumented/tikz_execution_graph_hooks.tex').read_bytes())==result['hook_sha256']
 trace=(folder/'instrumented/source.iic').read_bytes();assert sha(trace)==result['execution_trace_sha256']
 graph=graph_from_events(parse_events(trace.decode()));assert graph==result['graph']
 with pymupdf.open(folder/'baseline/source.pdf') as a,pymupdf.open(folder/'instrumented/source.pdf') as b:
  assert len(a)==len(b)==len(result['instrumentation_pdf_pixel_equivalence'])
  for i,(original,instrumented) in enumerate(zip(a,b)):
   x=original.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);y=instrumented.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
   assert (x.width,x.height,x.samples)==(y.width,y.height,y.samples)
   assert sha(x.samples)==result['instrumentation_pdf_pixel_equivalence'][i]['baseline_pixel_sha256']==result['instrumentation_pdf_pixel_equivalence'][i]['instrumented_pixel_sha256']
 results.append({'proof':str(file),'all_current_artifact_hashes_verified':True,'fresh_pdf_pixels_identical':True,'fresh_graph_trace_parse_identical':True,'graph_ok':graph['ok'],'named_nodes':len(graph['nodes']),'annotations':len(graph['decorative_nodes']),'edges':len(graph['edges'])})
out={'at':now(),'ok':True,'verified_proofs':len(results),'positive_graphs':sum(r['graph_ok'] for r in results),'negative_graphs':sum(not r['graph_ok'] for r in results),'results':results,'jobs_or_canonical_modified':False}
(W/'tikz_execution_graph_verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
