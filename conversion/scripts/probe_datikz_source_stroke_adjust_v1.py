"""One diagnostic stroke-raster hypothesis; never a qualified reference.

Poppler's SplashOutputDev enables stroke adjustment, unlike ordinary SVG paint.
crispEdges is only a diagnostic approximation here, not an implementation of
Poppler's algorithm. Original PDF/SVG bytes and all candidate/QA files stay put.
"""
from pathlib import Path
import hashlib,io,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
PRIMARY='https://skia.googlesource.com/third_party/poppler/+/315ab3006fb24bf47b595343e6a3e90995f2a588/poppler/SplashOutputDev.cc'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    from PIL import Image
    from playwright.sync_api import sync_playwright
    from compiler_language_capture_v1 import screenshot
    from auto_quality_common_v4 import image_quality
    p=R/'clean/priority_datikz_source_viewport_v8/be/be12a33e5806b959b3018b090eee6774e4271652474e8654da4df34ad0d35c93/f63ab1913a0a446281652162c49acbee';record=json.loads((p/'record.json').read_text());source=(p/'source_svg.svg').read_bytes();reference=(p/'source_png.png').read_bytes();assert sha(source)==record['source_render_svg_sha256'];assert sha(reference)==record['source_render_png_sha256'];size=Image.open(io.BytesIO(reference)).size
    root=R/'conversion/datikz_source_stroke_adjust_diagnostic_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    with sync_playwright()as pw:
        browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text']);context=browser.new_context(viewport=dict(width=size[0],height=size[1]),device_scale_factor=1,java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:route.abort());page=context.new_page()
        try:
            page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+source.decode());page.evaluate('document.fonts.ready')
            before=page.evaluate('()=>[...document.querySelectorAll("svg path,svg text")].map(e=>e.outerHTML)')
            page.evaluate('()=>{const s=document.createElement("style");s.textContent="svg path{shape-rendering:crispEdges}";document.head.appendChild(s)}');probe=screenshot(page)
            after=page.evaluate('()=>[...document.querySelectorAll("svg path,svg text")].map(e=>e.outerHTML)');assert before==after
        finally:context.close();browser.close()
    (root/'diagnostic_only_crisp_edges.png').write_bytes(probe);q=image_quality(reference,probe,{},{});out=dict(root=str(root),primary_source=PRIMARY,hypothesis='Differences in stroke adjustment explain a large non-text component of the saved PDF/SVG error.',diagnostic_approximation='SVG shape-rendering:crispEdges on paths only; no coordinates, text or font changes.',source_path_and_text_DOM_unchanged=True,source_SVG_sha256=sha(source),original_PNG_sha256=sha(reference),probe_PNG_sha256=sha(probe),quality_diagnostic=q,baseline_source_SSIM=.8893715647115513,thresholds_unchanged=True,new_normal_calls=0,new_QA_calls=0,source_SVG_raster_probes=1,new_source_executions=0,canonical_reference_changed=False,Poppler_stroke_adjust_equivalence_claimed=False,candidate_qualification_claimed=False,goal_complete=False)
    (root/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
if __name__=='__main__':main()
