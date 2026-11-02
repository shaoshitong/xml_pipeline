import json,copy,sqlite3,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,now
from portable_native_fonts import ready_page
from native_label_paint_order import inspect_order,reorder,pixel_audit
from mermaid_native_v2 import check_backgrounds

ID='02d454e72a49e3f65cf7c091283da5edea4ae0ee55057eb5845d9086bf7208ce'
D=sqlite3.connect(W/'jobs.sqlite',timeout=60);r=json.loads(D.execute('select output_record from jobs where id=?',(ID,)).fetchone()[0]);assert r['conversion_method'].endswith('label_paint_order_v6')
B=W/'mermaid_label_order_pilot'/ID;old=R/r['previous_candidate_archive'];xml=(old/'diagram.drawio').read_text();candidate=(R/r['code_file']).read_text();bindings=r['svg_conversion']['native_html_label_backgrounds'];w,h=Image.open(R/r['original_reference']).size
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);order=inspect_order(b,xml,bindings);new=reorder(xml,order);assert new==candidate;afterorder=inspect_order(b,candidate,bindings);assert reorder(candidate,afterorder)==candidate;b.close()
before=pixel_audit(xml,order['boxes'],w,h);after=pixel_audit(candidate,afterorder['boxes'],w,h);assert before['bad_pixels']>0 and after['ok'];neg=[]
bad=copy.deepcopy(order);bad['cyclic']=[bad['ordered'][0],bad['ordered'][1]]
try:reorder(xml,bad)
except AssertionError:neg.append('cyclic_constraints')
else:raise AssertionError('Cycle accepted')
bad=copy.deepcopy(order);bad['ordered'][1]=bad['ordered'][0]
try:reorder(xml,bad)
except AssertionError:neg.append('duplicate_edge_order')
else:raise AssertionError('Duplicate accepted')
root=E.fromstring(candidate)
for c in root.iter('mxCell'):
 if c.get('id')==bindings[0]['background']:c.set('parent','1')
try:check_backgrounds(E.tostring(root,encoding='unicode'),bindings)
except AssertionError:neg.append('detached_background')
else:raise AssertionError('Detached background accepted')
root=E.fromstring(candidate)
for c in root.iter('mxCell'):
 if c.get('id') in {x['background'] for x in bindings}:c.set('style',c.get('style')+'opacity=50;')
negative=pixel_audit(E.tostring(root,encoding='unicode'),afterorder['boxes'],w,h);assert not negative['ok'];neg.append('transparent_background_actual_pixels')
result={'at':now(),'id':ID,'before':before,'after':after,'negative_checks':neg,'idempotent':True,'all_cells_unchanged':True,'transparent_negative_bad_pixels':negative['bad_pixels'],'ok':True,'quality_acceptance':False};(W/'native_label_paint_order_tests.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
