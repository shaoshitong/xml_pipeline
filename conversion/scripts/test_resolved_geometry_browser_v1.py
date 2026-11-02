"""Actual browser controls for CSS geometry, local transforms and rejection."""
from pathlib import Path
import hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def main():
    from playwright.sync_api import sync_playwright
    from svg_source_endpoint_bridge_v5 import capture
    helper=(S/'svg_resolved_geometry_v1.js').read_text();checks={}
    cases=[
        ('css_overrides_attributes','<style>rect{width:30px;height:40px;x:5px;y:7px}</style><rect width="1" height="2"/>',dict(x=5,y=7,width=30,height=40)),
        ('missing_dimensions','<style>.box{width:30px;height:30px}</style><rect class="box"/>',dict(width=30,height=30)),
        ('circle_css_radius','<style>circle{r:15px;cx:30px;cy:40px}</style><circle r="1" cx="1" cy="1"/>',dict(cx=30,cy=40,r=15)),
        ('ellipse_css_radii','<style>ellipse{rx:20px;ry:10px;cx:30px;cy:40px}</style><ellipse rx="1" ry="1"/>',dict(cx=30,cy=40,rx=20,ry=10)),
        ('percent_rect','<rect x="10" y="20" width="50%" height="25%"/>',dict(x=10,y=20,width=100,height=50)),
        ('local_geometry_under_transform','<g transform="translate(30,10) scale(2)"><rect x="5" y="7" style="width:20px;height:10px"/></g>',dict(x=5,y=7,width=20,height=10)),
        ('absolute_css_corners','<rect style="width:30px;height:20px;rx:5px;ry:3px"/>',dict(width=30,height=20,rx=5,ry=3)),
        ('ordinary_attributes','<rect x="5" y="7" width="30" height="40" rx="2"/>',dict(x=5,y=7,width=30,height=40,rx=2,ry=2))]
    with sync_playwright()as p:
        browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu']);context=browser.new_context(viewport=dict(width=200,height=200),java_script_enabled=False,service_workers='block');context.route('**/*',lambda r:r.abort());page=context.new_page()
        try:
            for name,body,wanted in cases:
                page.set_content('<style>html,body{margin:0;padding:0}svg{display:block}</style><svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'+body+'</svg>')
                html=page.content();before=page.screenshot();dom=capture(page);after=page.screenshot();assert html==page.content()and before==after,name
                obj=next(o for o in dom['objects']if o['type']=='shape')
                assert all(abs(obj['attrs'][k]-v)<.00001 for k,v in wanted.items()),(name,obj['attrs'],wanted)
                assert obj['sourceResolvedGeometry']['source_attributes_unchanged'];checks[name]=dict(passed=True,attrs=obj['attrs'],pixels_unchanged=True,source_attributes_unchanged=True)
            page.set_content('<svg width="200" height="200"><rect width="30" height="20" style="rx:10%"/></svg>')
            dom=capture(page);assert any(i['reason']=='source_resolved_geometry_unsupported'for i in dom['issues']);checks['percentage_radius_rejected_without_guessing']=True
        finally:context.close();browser.close()
    root=R/'conversion/source_resolved_geometry_browser_controls_v1'/uuid.uuid4().hex;root.mkdir(parents=True);result=dict(root=str(root),controls=checks,passed=True,normal_calls=0,QA_calls=0,model_calls=0)
    (root/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
