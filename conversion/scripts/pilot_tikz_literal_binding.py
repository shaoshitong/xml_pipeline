import hashlib,io,json,sqlite3,sys,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from tikz_literal_graph import parse_literal
from tikz_literal_connectivity import bind
from svg_batch import metric
from harness_source_provenance import validate_source_record
id=sys.argv[1] if len(sys.argv)>1 else '005ba1ad9f186a039a10a06e5f3a3737c28f5ac490463601cf482ccbdfdc1cea'
d=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);state,raw=d.execute('select state,output_record from jobs where id=?',(id,)).fetchone();r=json.loads(raw);validate_source_record(r);xml=(R/r['code_file']).read_text();reference=(R/r['original_reference']).read_bytes();oldpng=(R/r['image_file']).read_bytes();assert hashlib.sha256(xml.encode()).hexdigest()==r['code_sha256'] and hashlib.sha256(oldpng).hexdigest()==r['image_sha256'];code=(R/r['original_source_code']).read_text();source=parse_literal(code);width,height=Image.open(io.BytesIO(reference)).size
work=W/'tikz_literal_binding_pilot'/id/r['code_sha256'];work.mkdir(parents=True,exist_ok=True);(work/'baseline.drawio').write_text(xml);(work/'baseline_record.json').write_text(raw);(work/'source_graph.json').write_text(json.dumps(source,indent=2)+'\n');svg=(R/r['source_render_svg']).read_text();out={'id':id,'at':now(),'input_code_sha256':r['code_sha256'],'original_state':state,'work':str(work.relative_to(R)),'source_nodes':len(source['nodes']),'source_edges':len(source['edges']),'accepted':False}
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);ctx=b.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');blocked=[];ctx.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=ctx.new_page();page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg);page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready');dom=page.evaluate((W/'scripts/svg_dom_pdf.js').read_text());b.close()
assert not blocked
(work/'source_dom.json').write_text(json.dumps(dom));new,binding=bind(xml,dom,code);out['binding']=binding
if binding['complete']:
 (work/'candidate.drawio').write_text(new);res=native.native_job(new,width,height,150,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');out['render_ok']=res['ok']
 if res['ok']:
  png=res.pop('png');(work/'candidate.png').write_bytes(png);(work/'render.json').write_text(json.dumps(res['native_render'],indent=2));out.update(before_ssim=metric(reference,oldpng),after_ssim=metric(reference,png),prior_vs_candidate_ssim=metric(oldpng,png),output_code_sha256=hashlib.sha256(new.encode()).hexdigest(),output_image_sha256=hashlib.sha256(png).hexdigest())
 else:out['render_error']=res
(work/'report.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
