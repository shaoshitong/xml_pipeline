import json
from playwright.sync_api import sync_playwright
from native_worker import W,now
svg='''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100"><circle cx="25" cy="25" r="10" fill="#222"/><circle cx="25" cy="65" r="10" fill="#222"/><g class="entity" data-entity="Dest" id="Dest"><rect x="100" y="10" width="50" height="40"/><text x="105" y="35">Dest</text></g><g class="link" id="link" data-entity-1=".start." data-entity-2="Dest"><path d="M25 45 L94 25" fill="none" stroke="black"/></g></svg>'''
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=b.new_page();page.set_content(svg);md=page.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text());assert len(md['links'])==0;assert any(x['reason']=='plantuml_link_metadata_unresolved' for x in md['issues']);b.close()
out={'at':now(),'test':'equidistant initial circles must remain unresolved','ok':True,'metadata':md};(W/'plantuml_v2_negative.json').write_text(json.dumps(out,indent=2));print(json.dumps({'ok':True,'test':out['test']}))
