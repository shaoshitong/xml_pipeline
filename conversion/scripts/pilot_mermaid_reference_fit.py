import json,sqlite3,hashlib,io,math,shutil
from pathlib import Path
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from mermaid_semantic_v4 import PARSE,check as semantic
from mermaid_native_v1 import build
from mermaid_geometry_coverage import check as geometry
from svg_source_coverage_v2 import audit as coverage
from svg_batch import metric
from portable_native_fonts import ready_page,capture,embed
from strict_canvas_gate import require_declared_page
from native_move_audit import audit as move_audit
id='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641';D=sqlite3.connect(W/'jobs.sqlite',timeout=60);r=json.loads(D.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);B=W/'mermaid_reference_fit'/id;B.mkdir(parents=True,exist_ok=True);(B/'before_record.json').write_text(json.dumps(r,indent=2));ref=(R/r['original_reference']).read_bytes();w,h=Image.open(io.BytesIO(ref)).size;target=np.asarray(Image.open(io.BytesIO(ref)).convert('RGB')).astype(float);code=(R/r['original_source_code']).read_text();base=W/'mermaid_variant_source_probe'/id;svg=(base/'10.9.1_html.svg').read_text();fit=json.loads((base/'reference_scale_fit.json').read_text());assert len(fit['pairs'])==7 and max(f['max_abs_residual'] for f in fit['fits'].values())<1;initial=[w*fit['fits']['x']['scale'],h*fit['fits']['y']['scale'],fit['fits']['x']['offset'],fit['fits']['y']['offset']];scores=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);ctx=browser.new_context(viewport={'width':w,'height':h},service_workers='block');page=ctx.new_page();page.route('**/*',lambda route:route.abort());page.set_content('<html></html>');page.add_script_tag(path=str(W/'runtime/mermaid_versions/10.9.1/mermaid.min.js'));page.evaluate("async code=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',flowchart:{htmlLabels:true}});await mermaid.render('register',code)}",code);ast=page.evaluate(PARSE,code);page.set_content('<style>html,body{margin:0;background:white;overflow:hidden}</style>'+svg)
 def render(params):
  page.evaluate('''p=>{const s=document.querySelector('svg');s.style.maxWidth='none';s.style.width=p[0]+'px';s.style.height=p[1]+'px';s.style.position='absolute';s.style.left=p[2]+'px';s.style.top=p[3]+'px';s.setAttribute('preserveAspectRatio','none');}''',params);page.evaluate('document.fonts.ready');png=page.screenshot();a=np.asarray(Image.open(io.BytesIO(png)).convert('RGB')).astype(float);mse=float(np.mean((target-a)**2));scores.append({'parameters':params,'mse':mse});return mse,png
 best=(*render(initial),initial)
 for params in [[1552.,396.,0.,0.],[round(initial[0]),round(initial[1]),0.,0.]]:
  error,png=render(params)
  if error<best[0]:best=(error,png,params)
 # Small global-only coordinate fit; no per-node edits, labels, content or source topology changes.
 for step in [1.,.25]:
  for axis in range(4):
   current=list(best[2])
   for delta in [-step,step]:
    q=current.copy();q[axis]+=delta;error,png=render(q)
    if error<best[0]:best=(error,png,q)
 render(best[2]);(B/'source_fit.png').write_bytes(best[1]);fitted_svg=page.locator('svg').evaluate('(s)=>s.outerHTML');(B/'source_fit.svg').write_text(fitted_svg);md=page.evaluate((W/'scripts/mermaid_dom_adapter_v1.js').read_text(),ast);dom=page.evaluate((W/'scripts/svg_dom_mermaid_v1.js').read_text());xml,stats,processed=build(dom,w,h,md);cov=coverage(processed,xml,stats);geo=geometry(ast,xml,md);sem=semantic(ast,xml);assert cov['ok'] and geo['ok'] and sem['status']=='node_edge_text_match';(B/'source_dom.json').write_text(json.dumps(dom,indent=2));(B/'source_ast.json').write_text(json.dumps(ast,indent=2));(B/'source_geometry.json').write_text(json.dumps(md,indent=2));(B/'source_stats.json').write_text(json.dumps(stats,indent=2));(B/'unembedded.drawio').write_text(xml)
 pagefont=ready_page(browser);observations=capture(pagefont,xml);new,fonts,fontproof=embed(xml,observations,B/'fonts');assert not fontproof['issues'],fontproof;pagefont.close();ctx.close();browser.close()
 (B/'candidate.drawio').write_text(new);(B/'font_proof.json').write_text(json.dumps(fontproof,indent=2));(B/'fonts.json').write_text(json.dumps(fonts,indent=2));before=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');after=native.native_job(new,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert before['ok'] and after['ok'] and before['png']==after['png'],'Font embedding changed actual pixels';require_declared_page(after['native_render'],w,h);(B/'candidate.png').write_bytes(after['png']);(B/'native_render.json').write_text(json.dumps(after['native_render'],indent=2));moves=move_audit(new);assert len(moves['moves'])==20
 for m in moves['moves']:
  assert abs(m['delta']['x']-17)<.0001 and abs(m['delta']['y']-11)<.0001
  for c in m['child_deltas']:assert abs(c['x']-17)<.0001 and abs(c['y']-11)<.0001
 (B/'moves.json').write_text(json.dumps(moves,indent=2))
out={'at':now(),'id':id,'initial_parameters':initial,'parameters':best[2],'anchor_fit':fit,'optimization':scores,'source_reference_ssim':metric(ref,best[1]),'native_reference_ssim':metric(ref,after['png']),'source_native_ssim':metric(best[1],after['png']),'prior_ssim':r['metrics']['original_reference_ssim_512'],'font_pixels_unchanged':True,'physical_fonts':[f['physical_postscript_name'] for f in fonts.values()],'semantic':sem,'source_object_coverage':cov,'geometry':geo,'actual_endpoint_moves':len(moves['moves']),'source_dom_issues':dom['issues'],'accepted':False};(B/'report.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
