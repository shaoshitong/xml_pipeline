import json,sqlite3
from playwright.sync_api import sync_playwright
from native_worker import W,now
from mermaid_reference_fit_v1 import convert_variant
ID='0f3c4920498befd11cc4f1db52ebe2f323539403c43fbfb94c919c18998ed641';D=sqlite3.connect(W/'jobs.sqlite',timeout=60);raw=D.execute('select output_record from jobs where id=?',(ID,)).fetchone()[0];r=json.loads(raw)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);report=convert_variant(b,r,W/'mermaid_reference_fit_grid_regression'/ID);b.close()
assert report['native_reference_ssim']>=r['metrics']['original_reference_ssim_512']-.00001
assert D.execute('select output_record from jobs where id=?',(ID,)).fetchone()[0]==raw
out={'at':now(),'id':ID,'parameters':report['parameters'],'native_reference_ssim':report['native_reference_ssim'],'already_accepted_sample_unchanged':True,'ok':True};(W/'mermaid_reference_fit_grid_regression.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
