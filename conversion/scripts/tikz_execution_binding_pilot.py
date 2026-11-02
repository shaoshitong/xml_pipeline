"""Non-publishing real-candidate execution binding and native runtime proof."""
import argparse,collections,hashlib,io,json,shutil,sqlite3,sys,time,uuid,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now,native
from tikz_execution_graph import parse_events,graph_from_events
from tikz_execution_binding import bind_execution
from harness_source_provenance import validate_source_record
from svg_batch import metric
sys.path.append(str(W/'runtime/python_packages'));import pymupdf
sha=lambda b:hashlib.sha256(b).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--id',default='6a09ccf14db3f3ac3d016e3eff21daed7c468f7e9a7ea1a5fef3a853f6fe36a6');parser.add_argument('--proof');a=parser.parse_args();id=a.id
db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);state,raw=db.execute('select state,output_record from jobs where id=?',(id,)).fetchone();r=json.loads(raw);db.close();validate_source_record(r)
xml=(R/r['code_file']).read_text();assert sha(xml.encode())==r['code_sha256'];baseline_png=(R/r['image_file']).read_bytes();assert sha(baseline_png)==r['image_sha256']
if a.proof:
 proof=Path(a.proof).resolve();assert proof.is_relative_to(W/'tikz_execution_graph_prototype')
else:
 pilot=json.loads((W/'tikz_execution_graph_real_pilot.json').read_text());proof=Path(next(x['proof'] for x in pilot['results'] if x['id']==id and x['ok']))
sidecar=json.loads(proof.read_text());assert sidecar['source_sha256']==r['source_code_sha256']
assert sha(Path(sidecar['engine_file']).read_bytes())==sidecar['engine_sha256']
for source in sidecar['pgf_core_files'].values():assert sha(Path(source['file']).read_bytes())==source['sha256']
for mode,run in sidecar['runs'].items():
 work=proof.parent/mode;assert sha((work/'original_source.tex').read_bytes())==r['source_code_sha256'];assert sha((work/'source.tex').read_bytes())==run['wrapper_sha256'];assert sha((work/'source.pdf').read_bytes())==run['pdf_sha256']
trace=(proof.parent/'instrumented/source.iic').read_bytes();assert sha(trace)==sidecar['execution_trace_sha256'];events=parse_events(trace.decode());assert graph_from_events(events)==sidecar['graph']
relations=[]
with pymupdf.open(R/r['source_render_pdf']) as current,pymupdf.open(proof.parent/'baseline/source.pdf') as baseline:
 assert len(current)==len(baseline)==1,'Prototype currently requires one source PDF page'
 for i,(p,q) in enumerate(zip(current,baseline)):
  x=p.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);y=q.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
  assert (x.width,x.height,x.samples)==(y.width,y.height,y.samples),'Current candidate PDF differs from execution baseline PDF'
  relations.append({'page':i,'rect':list(p.rect),'current_pdf_sha256':r['source_render_pdf_sha256'],'execution_pdf_sha256':sidecar['runs']['baseline']['pdf_sha256'],'actual_pixels_identical':True,'pixel_sha256':sha(x.samples)})
work=W/'tikz_execution_binding_pilot'/id/(r['code_sha256']+'_'+uuid.uuid4().hex[:8]);work.mkdir(parents=True);(work/'baseline.drawio').write_text(xml);(work/'baseline_record.json').write_text(raw);(work/'baseline.png').write_bytes(baseline_png)
reference=(R/r['original_reference']).read_bytes();width,height=Image.open(io.BytesIO(reference)).size;svg=(R/r['source_render_svg']).read_text();blocked=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=context.new_page();page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');dom=page.evaluate((W/'scripts/svg_dom_pdf_v2.js').read_text());matrix=page.evaluate('()=>{const m=document.querySelector("svg").getScreenCTM();return [m.a,m.b,m.c,m.d,m.e,m.f]}');browser.close()
assert not blocked;(work/'source_dom.json').write_text(json.dumps(dom));(work/'sidecar_locator.json').write_text(json.dumps({'proof':str(proof),'sha256':sha(proof.read_bytes()),'trace_sha256':sha(trace),'svg_root_screen_ctm':matrix},indent=2)+'\n')
candidate,binding=bind_execution(xml,dom,sidecar,events,matrix)
out={'at':now(),'id':id,'ok':False,'published':False,'input_code_sha256':r['code_sha256'],'source_sha256':r['source_code_sha256'],'source_pdf_relation':relations,'work':str(work.relative_to(R)),'binding':binding}
if binding['complete']:
 (work/'candidate.drawio').write_text(candidate);fresh=native.native_job(candidate,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');out['render_ok']=fresh['ok']
 if fresh['ok']:
  png=fresh.pop('png');(work/'candidate.png').write_bytes(png);(work/'native_render.json').write_text(json.dumps(fresh['native_render'],indent=2)+'\n');out.update(output_code_sha256=sha(candidate.encode()),output_image_sha256=sha(png),reference_ssim_before=metric(reference,baseline_png),reference_ssim_after=metric(reference,png))
  from auto_quality_move import audit
  moves=audit(candidate);assert len(moves['moves'])==2*binding['source_edges']
  for move in moves['moves']:
   assert abs(move['delta']['x']-17)<.05 and abs(move['delta']['y']-11)<.05
   assert all(abs(c['x']-17)<.05 and abs(c['y']-11)<.05 for c in move.get('child_deltas',[]))
   for group in move.get('label_member_deltas',[]):
    members=group['members'];assert members
    assert all(abs(c['x']-members[0]['x'])<.05 and abs(c['y']-members[0]['y'])<.05 for c in members)
  (work/'native_moves.json').write_text(json.dumps(moves,indent=2)+'\n');out['actual_endpoint_moves']=len(moves['moves']);out['whole_edge_label_groups_verified']=len(binding['binding']['edge_child_labels'])
  normalize=lambda text:collections.Counter(c.get('value','') for c in E.fromstring(text).iter('mxCell') if c.get('value'))
  assert normalize(xml)==normalize(candidate);out['all_original_text_fragments_preserved']=True
  before={c.get('id') for c in E.fromstring(xml).iter('mxCell')};after={c.get('id') for c in E.fromstring(candidate).iter('mxCell')};assert before-after=={m['source_object'] for m in binding['binding']['native_arrowheads']};out['only_source_matched_arrow_polygons_replaced']=True
  assert sha((R/r['code_file']).read_bytes())==r['code_sha256'] and sha((R/r['image_file']).read_bytes())==r['image_sha256'];out['input_revision_unchanged']=True;out['ok']=True
(work/'report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(W/'tikz_execution_binding_pilot.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='binding'}));print(json.dumps({'binding_complete':binding['complete'],'issues':binding['issues'],'mapping':binding.get('coordinate_mapping'),'source_nodes':binding.get('source_nodes'),'source_edges':binding.get('source_edges'),'owned_annotations':binding.get('owned_executed_annotations'),'retained_annotations':binding.get('retained_free_annotation_serials')}))
