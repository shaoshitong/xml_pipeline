import json,sqlite3,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native
from svg_convert_v3 import unpack,pack
from svg_batch import metric
from strict_canvas_gate import require_declared_page
ID='02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce';D=sqlite3.connect(W/'jobs.sqlite',timeout=60);r=json.loads(D.execute('select output_record from jobs where id=?',(ID,)).fetchone()[0]);B=W/'mermaid_label_background_pilot'/ID;B.mkdir(parents=True,exist_ok=True);root=E.fromstring((R/r['code_file']).read_text());container=root.find('.//mxGraphModel/root');cells={c.get('id'):c for c in root.iter('mxCell')};bindings=r['svg_conversion']['native_html_label_backgrounds']
for x in bindings:
 bg=cells[x['background']];text=cells[x['label']];s=unpack(text.get('style'));s['labelBackgroundColor']=x['source_css_color'];text.set('style',pack(s));container.remove(bg)
xml=E.tostring(root,encoding='unicode');(B/'candidate.drawio').write_text(xml);w,h=Image.open(R/r['original_reference']).size;result=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert result['ok'];require_declared_page(result['native_render'],w,h);(B/'candidate.png').write_bytes(result['png']);(B/'native_render.json').write_text(json.dumps(result['native_render'],indent=2));out={'id':ID,'native_reference_ssim':metric((R/r['original_reference']).read_bytes(),result['png']),'before':r['metrics']['original_reference_ssim_512'],'accepted':False,'published':False};(B/'report.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
