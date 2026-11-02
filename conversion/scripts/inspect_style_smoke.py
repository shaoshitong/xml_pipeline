import sys,json,sqlite3,traceback
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sys.path.insert(0,str(W/'scripts'))
d=sqlite3.connect(W/'jobs.sqlite')
for id,state,record in d.execute('select id,state,record from plantuml_style_repairs'):
 r=json.loads(record);print(id,state,'changes',[(x['kind'],x.get('object',x.get('native_edge'))) for x in r.get('changes',[])],'rejected',r.get('unresolved_mappings'),r.get('error'))
from plantuml_style_repair import repair
from playwright.sync_api import sync_playwright
id='e647ce1486f91f14571889932f1ac166004219b8bba528ac469587f6107d0e6e';out=json.loads(d.execute('select output_record from jobs where id=?',(id,)).fetchone()[0]);w=W/'plantuml_style_debug';w.mkdir(exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
 try:repair(b,out,w)
 except:traceback.print_exc()
 b.close()
