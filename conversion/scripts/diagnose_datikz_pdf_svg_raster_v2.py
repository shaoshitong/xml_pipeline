"""Localize the saved PDF/SVG replay difference without altering any source.

One saved-source SVG replay, not a normal conversion or candidate QA. Uses
only original PDF glyph boxes to separate text from non-text error. No fitted
coordinates, new reference image, threshold changes or qualification result.
"""
from pathlib import Path
import hashlib,io,json,math,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';S=W/'scripts';sys.path.insert(0,str(S));sys.path.append(str(W/'runtime/python_packages'))
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def main():
    import numpy as np,pymupdf
    from PIL import Image
    from playwright.sync_api import sync_playwright
    from compiler_language_capture_v1 import screenshot
    from auto_quality_common_v4 import image_quality
    folder=R/'clean/priority_datikz_source_viewport_v8/be/be12a33e5806b959b3018b090eee6774e4271652474e8654da4df34ad0d35c93/f63ab1913a0a446281652162c49acbee';record=json.loads((folder/'record.json').read_text());proof=record['compiler_tikz_source_viewport_v1'];files=proof['files']
    def checked(k):
        p=R/files[k]['file'];b=p.read_bytes();assert sha(b)==files[k]['sha256'];return b
    source=checked('source_svg');pdf=checked('source_pdf');png=checked('source_png');quality=json.loads(checked('actual_PDF_to_SVG_quality'));size=Image.open(io.BytesIO(png)).size;scale=proof['frame']['scale']
    root=W/'datikz_pdf_source_raster_diagnosis_v2'/uuid.uuid4().hex;root.mkdir(parents=True)
    with sync_playwright()as p:
        browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text']);context=browser.new_context(viewport=dict(width=size[0],height=size[1]),device_scale_factor=1,java_script_enabled=False,service_workers='block');context.route('**/*',lambda r:r.abort());page=context.new_page()
        try:
            page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+source.decode());page.evaluate('document.fonts.ready');fresh=screenshot(page)
        finally:context.close();browser.close()
    (root/'saved_source_SVG_replay.png').write_bytes(fresh);a=np.asarray(Image.open(io.BytesIO(png)).convert('RGB'),dtype=float);b=np.asarray(Image.open(io.BytesIO(fresh)).convert('RGB'),dtype=float);assert a.shape==b.shape
    mask=np.zeros(a.shape[:2],dtype=bool);fonts={};glyphs=[]
    with pymupdf.open(stream=pdf,filetype='pdf')as doc:
        for trace in doc[0].get_texttrace():
            if trace['type']!=0:continue
            fm=fonts.setdefault(trace['font'],np.zeros_like(mask))
            for unicode,gid,origin,box in trace['chars']:
                x0,y0,x1,y1=box;x0=max(0,math.floor(x0*scale)-1);y0=max(0,math.floor(y0*scale)-1);x1=min(size[0],math.ceil(x1*scale)+1);y1=min(size[1],math.ceil(y1*scale)+1)
                if x1>x0 and y1>y0:mask[y0:y1,x0:x1]=True;fm[y0:y1,x0:x1]=True
                glyphs.append(dict(text=chr(unicode),font=trace['font'],bbox=[x0,y0,x1,y1]))
    squared=np.mean((a-b)**2,axis=2);total=float(squared.sum());metrics={}
    for name,m in [('all_text',mask),('non_text',~mask),*fonts.items()]:
        metrics[name]=dict(pixels=int(m.sum()),squared_error=float(squared[m].sum()),share_of_total_squared_error=float(squared[m].sum()/total)if total else 0,reference_mean_darkness=float((1-a.mean(axis=2)[m]/255).mean()),SVG_mean_darkness=float((1-b.mean(axis=2)[m]/255).mean()))
    visual=image_quality(png,fresh,{},{});assert abs(visual['ssim_1024']-quality['ssim_1024'])<1e-10,'Saved-source raster mismatch no longer reproducible; preserve both observations'
    out=dict(root=str(root),original_source_SVG=files['source_svg'],original_PDF=files['source_pdf'],original_PNG=files['source_png'],saved_source_replay=asset(root/'saved_source_SVG_replay.png'),unchanged_source_raster_ssim=visual['ssim_1024'],required_ssim=.9,metrics=metrics,glyphs=len(glyphs),source_SVG_raster_probes=1,new_source_executions=0,new_normal_calls=0,new_QA_calls=0,new_models=0,source_unchanged=True,candidate_qualification_claimed=False,goal_complete=False)
    (root/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
if __name__=='__main__':main()
