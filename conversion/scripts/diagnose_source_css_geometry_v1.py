"""Read actual source CSS dimensions and compare the failed native geometry."""
from pathlib import Path
import hashlib,io,json,sqlite3,sys,uuid,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def asset(p):return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
    run=R/'release/compiler_iterations/runs/svg_complex_compound_linear_cached_unseen_20261102_v10_C'
    with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as db:r=json.loads(db.execute("select result from samples where id like '332ef%'").fetchone()[0])
    attempt=json.loads((R/r['evidence_directory']/'frontend_result.json').read_bytes());record=attempt['record'];source=R/record['original_source_code'];xml=R/record['code_file']
    assert asset(source)['sha256']==record['source_code_sha256']and asset(xml)['sha256']==record['code_sha256']
    cells={c.get('id'):c for c in ET.fromstring(xml.read_bytes()).iter('mxCell')}
    from PIL import Image
    from playwright.sync_api import sync_playwright
    size=Image.open(R/record['original_reference']).size
    with sync_playwright()as p:
        browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu']);context=browser.new_context(viewport=dict(width=size[0],height=size[1]),java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:route.abort());page=context.new_page()
        try:
            page.set_content('<style>html,body{margin:0;padding:0}svg{display:block}</style>'+source.read_text())
            observations=page.evaluate('''()=>[...document.querySelectorAll('svg rect')].map(e=>{const cs=getComputedStyle(e),b=e.getBoundingClientRect(),g=e.getBBox();return {attributes:Object.fromEntries(['x','y','width','height','class','style'].map(k=>[k,e.getAttribute(k)])),computed:{x:cs.x,y:cs.y,width:cs.width,height:cs.height},local_bbox:{x:g.x,y:g.y,w:g.width,h:g.height},screen_bbox:{x:b.x,y:b.y,w:b.width,h:b.height}}}).filter(r=>r.screen_bbox.x>=949&&r.screen_bbox.x<=951&&r.screen_bbox.w>=29&&r.screen_bbox.w<=31)''')
        finally:context.close();browser.close()
    native=[dict(id=key,geometry=cells[key].find('mxGeometry').attrib,parent=cells[key].get('parent'))for key in ['v197','v206']]
    assert observations and all(float(r['geometry']['width'])==.01 for r in native)
    root=R/'conversion/source_css_geometry_diagnosis_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    result=dict(root=str(root),source=asset(source),candidate=asset(xml),quality_report=asset(R/r['quality_report']),actual_source_rectangles=observations,native_rectangles=native,diagnosis='Rendered source CSS supplies nonzero rectangle dimensions that the source attribute-only observer stored as zero; native stencil emitter used the zero attributes.',normal_calls=0,QA_calls=0,model_calls=0,qualification_claimed=False)
    (root/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
