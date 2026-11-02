import json,sqlite3,copy,uuid,io,xml.etree.ElementTree as E
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np
from native_worker import R,W,native,now
from portable_native_fonts import ready_page
from mermaid_native_v2 import check_backgrounds
from svg_source_coverage_v2 import audit as coverage
from harness_context_v5 import build_context,compact_xml,hydrate
from strict_canvas_gate import require_declared_page
ID='02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce';D=sqlite3.connect(W/'jobs.sqlite',timeout=60);state,raw,source,inp=D.execute('select state,output_record,input_record,input_manifest from jobs where id=?',(ID,)).fetchone();r=json.loads(raw);assert r['conversion_method'].endswith('backgrounds_v4')
B=(R/r['native_source_geometry_repair']['audit']).parent;xml=(R/r['code_file']).read_text();stats=json.loads((B/'source_stats.json').read_text());dom=json.loads((B/'source_dom.json').read_text());bindings=stats['native_html_label_backgrounds'];assert len(bindings)==9;assert check_backgrounds(xml,bindings)['ok'];negatives=[]
for name in ['missing_background','unbound_background','transparent_background']:
 root=E.fromstring(xml);container=root.find('.//mxGraphModel/root');cell=next(c for c in root.iter('mxCell') if c.get('id')==bindings[0]['background'])
 if name=='missing_background':container.remove(cell)
 if name=='unbound_background':cell.set('parent','1')
 if name=='transparent_background':cell.set('style',cell.get('style')+'opacity=50;')
 try:check_backgrounds(E.tostring(root,encoding='unicode'),bindings)
 except AssertionError:negatives.append(name)
 else:raise AssertionError('Negative accepted '+name)
 if name=='missing_background':assert not coverage(dom,E.tostring(root,encoding='unicode'),stats)['ok']
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(b)
 boxes=page.evaluate('''async a=>{document.body.innerHTML='<div id="g"></div>';const g=new Graph(document.getElementById('g')),d=mxUtils.parseXml(a.xml);new mxCodec(d).decode(d.getElementsByTagName('mxGraphModel')[0],g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();const out=a.bindings.map(x=>{const s=g.view.getState(g.model.cells[x.background]);return {id:x.background,x:s.x,y:s.y,w:s.width,h:s.height}});g.destroy();return out}''',{'xml':xml,'bindings':bindings});b.close()
w,h=Image.open(R/r['original_reference']).size
probe_root=E.fromstring(xml)
for cell in probe_root.iter('mxCell'):
 if cell.get('value'):cell.set('value','')
def render_probe(root):
 result=native.native_job(E.tostring(root,encoding='unicode'),w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert result['ok'];return np.asarray(Image.open(io.BytesIO(result['png'])).convert('RGB'))
pixels=render_probe(probe_root);pixelchecks=[]
for box in boxes:
 x,y,bw,bh=[box[k] for k in ['x','y','w','h']];crop=pixels[int(np.ceil(y))+2:int(np.floor(y+bh))-2,int(np.ceil(x))+2:int(np.floor(x+bw))-2];assert crop.size
 # Text is hidden only in this diagnostic render to exclude legitimate LCD font color fringes.
 colored=np.max(crop,axis=2)-np.min(crop,axis=2);bad=int((colored>20).sum());# Retain observed failures; this diagnostic must not turn them into acceptance.
 pixelchecks.append({'background':box['id'],'colored_connector_pixels_inside':bad})
negative_root=copy.deepcopy(probe_root)
for cell in negative_root.iter('mxCell'):
 if cell.get('id') in {b['background'] for b in bindings}:cell.set('style',cell.get('style')+'opacity=50;')
negative_pixels=render_probe(negative_root);negative_ink=0
for box in boxes:
 x,y,wbox,hbox=[box[k] for k in ['x','y','w','h']];crop=negative_pixels[int(np.ceil(y))+2:int(np.floor(y+hbox))-2,int(np.ceil(x))+2:int(np.floor(x+wbox))-2];negative_ink+=int(((np.max(crop,axis=2)-np.min(crop,axis=2))>20).sum())
assert negative_ink>0,'Pixel diagnostic failed to detect transparent backgrounds'
work=W/'harness_sessions'/('backgrounds_preflight_'+uuid.uuid4().hex);work.mkdir();ctx=build_context(json.loads(source),json.loads(inp),r,work);compact=compact_xml(xml,ctx);roundtrip,used=hydrate(compact,ctx);w,h=Image.open(R/r['original_reference']).size;fresh=native.native_job(roundtrip,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==(R/r['image_file']).read_bytes();require_declared_page(fresh['native_render'],w,h)
out={'at':now(),'id':ID,'backgrounds':len(bindings),'negative_guards_rejected':negatives,'actual_pixel_checks':pixelchecks,'transparent_negative_connector_ink_pixels':negative_ink,'harness_context_source_provenance_valid':True,'harness_compact_hydrate_native_pixels_unchanged':True,'actual_background_label_moves':len(json.loads((B/'background_moves.json').read_text())),'ok':all(x['colored_connector_pixels_inside']==0 for x in pixelchecks),'accepted':False,'known_issue':'Native edge-owned background shapes can be overpainted by another later native edge; generic calibration refuses these cases pending a faithful editability-preserving solution.'};(W/'mermaid_html_background_tests.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
