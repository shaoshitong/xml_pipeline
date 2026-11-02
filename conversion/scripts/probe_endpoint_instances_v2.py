"""Source-only endpoint regression probe; no conversions or QA qualifications."""
import hashlib,io,json,sqlite3,sys,uuid
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
import compiler_svg_scene_frontend_v8 as frontend
import svg_source_endpoint_bridge_v1 as old
import svg_source_endpoint_bridge_v2 as new
R=frontend.R

def main():
    root=R/'conversion/source_endpoint_instance_probe_v2'/uuid.uuid4().hex
    root.mkdir(parents=True)
    out=[]
    with sync_playwright()as p:
        browser=p.chromium.launch(executable_path=frontend.CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
        try:
            for identifier in ['0dc3f8bb2a134a79aba055dc8cc6686f7d097b187bd08267a5bdc4f8d8bd633e','2a6f2b074d5050fc30f67a12a516aca7ab0ec7764a747b07a0846c020ded0251']:
                with sqlite3.connect((frontend.W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as d:
                    d.row_factory=sqlite3.Row;job=dict(d.execute('select*from jobs where id=?',(identifier,)).fetchone())
                _,source,reference=frontend._inputs(job);size=Image.open(io.BytesIO(reference)).size
                context=browser.new_context(viewport=dict(width=size[0],height=size[1]),device_scale_factor=1,java_script_enabled=False,service_workers='block')
                context.route('**/*',lambda route:route.abort());page=context.new_page()
                page.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+source.decode('utf-8-sig'))
                page.evaluate('([w,h])=>{let s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h)}',list(size))
                page.evaluate('()=>document.fonts.ready');before=page.screenshot()
                prior=old.capture(page);after=new.capture(page);legacy=new.capture(page,legacy=True)
                assert page.screenshot()==before,'source_observation_changed_pixels'
                assert [(o['id'],o['type'],o.get('tag'),o.get('text'))for o in after['objects']]==[(o['id'],o['type'],o.get('tag'),o.get('text'))for o in legacy['objects']],'legacy_general_identity_disagrees'
                missing=lambda value:[v for v in value['issues']if v.get('reason')=='marker_expansion_failed' and 'endpoint_facts' in v.get('error','')]
                assert not missing(after),after['issues']
                if identifier.startswith('0dc3'):assert missing(prior)and after['sourceEndpointDirection']['instances']>0
                for name,value in [('old',prior),('new',after),('new_legacy',legacy)]:
                    (root/(identifier+'_'+name+'.json')).write_text(json.dumps(value))
                out.append(dict(id=identifier,old_missing_endpoint_issues=len(missing(prior)),new_missing_endpoint_issues=len(missing(after)),new_issues=after['issues'],endpoint_evidence=after['sourceEndpointDirection'],pixels_unchanged=True,legacy_general_object_identity_equal=True,source_sha256=hashlib.sha256(source).hexdigest(),new_normal_conversions=0,full_QA_claimed=False))
                context.close()
        finally:browser.close()
    summary=dict(cases=out,root=str(root),new_normal_conversions=0,source_only=True)
    (root/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
