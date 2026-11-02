"""Read-only source/PDF/candidate relation probe for the real execution pilot."""
import hashlib,io,json,sqlite3,sys
from pathlib import Path
from PIL import Image
from native_worker import R,W,now
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
ID='6a09ccf14db3f3ac3d016e3eff21daed7c468f7e9a7ea1a5fef3a853f6fe36a6'
sha=lambda b:hashlib.sha256(b).hexdigest()
db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);state,raw=db.execute('select state,output_record from jobs where id=?',(ID,)).fetchone();db.close();r=json.loads(raw)
pilot=json.loads((W/'tikz_execution_graph_real_pilot.json').read_text());proof=Path(next(x['proof'] for x in pilot['results'] if x['id']==ID and x['ok']));s=json.loads(proof.read_text())
assert r['source_code_sha256']==s['source_sha256'];assert sha((R/r['original_source_code']).read_bytes())==s['source_sha256']
pdf=R/r['source_render_pdf'];assert sha(pdf.read_bytes())==r['source_render_pdf_sha256']
with pymupdf.open(pdf) as current,pymupdf.open(proof.parent/'baseline/source.pdf') as baseline:
 relation=[]
 for i,(a,b) in enumerate(zip(current,baseline)):
  x=a.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);y=b.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
  relation.append({'page':i,'same_rect':a.rect==b.rect,'rect':list(a.rect),'pixel_identical':(x.width,x.height,x.samples)==(y.width,y.height,y.samples),'current_pdf_pixel_sha256':sha(x.samples),'baseline_pdf_pixel_sha256':sha(y.samples)})
 assert len(current)==len(baseline)
out={'at':now(),'id':ID,'state':state,'conversion_method':r.get('conversion_method'),'code_sha256':r['code_sha256'],'source_sha256':s['source_sha256'],'current_source_pdf':r['source_render_pdf'],'current_source_svg':r['source_render_svg'],'current_pdf_sha256':r['source_render_pdf_sha256'],'baseline_pdf_sha256':s['runs']['baseline']['pdf_sha256'],'reference_size':Image.open(R/r['original_reference']).size,'candidate_size':Image.open(R/r['image_file']).size,'native_page_padding':r.get('native_page_padding'),'native_canvas_contract':r.get('native_canvas_contract'),'source_pdf_relation':relation,'executed_edges':s['graph']['edges'],'executed_node_count':len(s['graph']['nodes']),'annotation_count':len(s['graph']['decorative_nodes']),'sidecar_file':str(proof.relative_to(R)),'record_keys':list(r)}
(W/'tikz_execution_binding_probe.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
