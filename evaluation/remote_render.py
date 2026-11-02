#!/usr/bin/env python3
"""HKUST-only rendering and image comparison for the controlled harness cases."""
import argparse
import ast
import base64
import io
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import unquote_to_bytes
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


def drawio_embed_png(source, output, width, proxy):
    """Use the actual diagrams.net embed renderer, never a cell approximation."""
    from playwright.sync_api import sync_playwright
    xml = source.read_text()
    root = ET.fromstring(xml)
    if root.tag not in ('mxfile', 'mxGraphModel'):
        raise ValueError('drawio requires mxfile or mxGraphModel root')
    if re.search(r'data:image|https?://[^;"\s]+\.(?:png|jpe?g|webp)', xml, re.I):
        raise ValueError('embedded raster or external raster reference is disallowed')
    opts = dict(headless=True, args=['--disable-dev-shm-usage'])
    installed = sorted(Path('/home/shaoshitong/.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),
                       key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
    if installed:
        opts['executable_path'] = str(installed[0])
    if proxy:
        opts['proxy'] = {'server': proxy}
    with sync_playwright() as p:
        browser = p.chromium.launch(**opts)
        page = browser.new_page(viewport={'width': 1600, 'height': 1200})
        page.set_default_timeout(120000)
        page.set_content('''<!doctype html><html><body><script>
        window.protocol=[];
        window.addEventListener('message', e => {
          if (e.origin !== 'https://embed.diagrams.net') return;
          try {window.protocol.push(JSON.parse(e.data));} catch (_) {}
        });
        </script><iframe id="editor" style="width:1500px;height:1100px"
        src="https://embed.diagrams.net/?embed=1&proto=json&spin=1&ui=min&dark=0&noSaveBtn=1&noExitBtn=1"></iframe>
        </body></html>''')
        page.wait_for_function("window.protocol.some(x=>x.event==='init')", timeout=150000)
        page.evaluate('''xml=>document.querySelector('#editor').contentWindow.postMessage(
          JSON.stringify({action:'load',xml,autosave:0,title:'controlled-evaluation',
          background:'#ffffff',dark:0}), 'https://embed.diagrams.net')''', xml)
        page.wait_for_function("window.protocol.some(x=>x.event==='load')", timeout=120000)
        page.evaluate('''w=>document.querySelector('#editor').contentWindow.postMessage(
          JSON.stringify({action:'export',format:'png',scale:1,width:w,border:0,
          size:'page',background:'#ffffff',transparent:false,grid:false}),
          'https://embed.diagrams.net')''', width)
        page.wait_for_function("window.protocol.some(x=>x.event==='export')", timeout=120000)
        result = page.evaluate("window.protocol.filter(x=>x.event==='export').at(-1)")
        browser.close()
    if result.get('error'):
        raise RuntimeError(str(result['error']))
    data = result.get('data', '')
    if not data.startswith('data:image/png'):
        raise RuntimeError('embed export did not return PNG data')
    head, payload = data.split(',', 1)
    output.write_bytes(base64.b64decode(payload) if ';base64' in head else unquote_to_bytes(payload))
    return {'renderer': 'embed.diagrams.net JSON load/export in Chromium',
            'vertices': sum(c.get('vertex') == '1' for c in root.iter('mxCell')),
            'edges': sum(c.get('edge') == '1' for c in root.iter('mxCell')),
            'protocol_source': 'https://www.drawio.com/docs/reference/embed-mode/'}


def drawio_png(source, output, width, height, proxy):
    """Render with the real official static GraphViewer, cached on HKUST.

    No full editor, iframe init or network fetch is needed in the browser for
    ordinary shapes. The page canvas is captured without moving model objects.
    A second tight image records all diagram content if the source extends
    outside its declared page; it never silently replaces the page render.
    """
    if os.environ.get('IMG2CODE_DRAWIO_BACKEND')=='embed':
        return drawio_embed_png(source,output,width,proxy)
    from playwright.sync_api import sync_playwright
    xml=source.read_text();root=ET.fromstring(xml)
    if root.tag not in ('mxfile','mxGraphModel'):
        raise ValueError('drawio requires mxfile or mxGraphModel root')
    if re.search(r'data:image|https?://[^;"\s]+\.(?:png|jpe?g|webp)',xml,re.I):
        raise ValueError('embedded raster or external raster reference is disallowed')
    assets=Path(__file__).resolve().parent/'assets';assets.mkdir(exist_ok=True)
    bundle=assets/'viewer-static.min.js'
    url='https://raw.githubusercontent.com/jgraph/drawio/dev/src/main/webapp/js/viewer-static.min.js'
    if not bundle.exists():
        import requests
        response=requests.get(url,timeout=60,
            proxies={'http':proxy,'https':proxy} if proxy else None)
        response.raise_for_status();data=response.content
        if len(data)<100000 or b'GraphViewer' not in data:
            raise ValueError('official viewer bundle download did not return expected JavaScript')
        temporary=bundle.with_name(bundle.name+'.tmp.'+str(os.getpid()))
        temporary.write_bytes(data);temporary.replace(bundle)
        (assets/'viewer-provenance.json').write_text(json.dumps({
            'url':url,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
            'downloaded_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'documentation':'https://www.drawio.com/docs/reference/diagram-generation/',
            'upstream':'https://github.com/jgraph/drawio'},indent=2))
    model=root if root.tag=='mxGraphModel' else root.find('.//mxGraphModel')
    def dimension(key,default):
        try:return max(1,math.ceil(float(model.get(key,default)))) if model is not None else default
        except (ValueError,TypeError):return default
    canvas_w=dimension('pageWidth',width);canvas_h=dimension('pageHeight',height)
    if max(canvas_w,canvas_h)>8192 or canvas_w*canvas_h>64000000:
        raise ValueError('source canvas exceeds rendering limits')
    installed=sorted(Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),
        key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
    opts={'headless':True,'args':['--disable-dev-shm-usage']}
    if installed:opts['executable_path']=str(installed[0])
    if proxy:opts['proxy']={'server':proxy}
    trace=[]
    with sync_playwright()as p:
        browser=p.chromium.launch(**opts)
        page=browser.new_page(viewport={'width':max(canvas_w,640),'height':max(canvas_h,480)},
                              device_scale_factor=1)
        page.set_default_timeout(30000)
        page.on('pageerror',lambda error:trace.append({'kind':'pageerror','text':str(error)[:2000]}))
        page.on('requestfailed',lambda req:trace.append({'kind':'requestfailed','url':req.url,'error':req.failure}))
        page.on('console',lambda msg:trace.append({'kind':'console','type':msg.type,'text':msg.text[:1200]})
                if msg.type in ('error','warning') else None)
        page.set_content('<!doctype html><html><head><style>html,body{margin:0;padding:0;background:white;}'+
            '#graph{position:relative;margin:0;padding:0;border:0;overflow:hidden;background:white;'+
            f'width:{canvas_w}px;height:{canvas_h}px;'+
            '}</style></head><body><div id="graph"></div></body></html>')
        page.evaluate('''()=>{window.onDrawioViewerLoad=()=>{window.viewerBundleReady=true};
            window.mxLoadResources=false;window.mxLoadStylesheets=false;}''')
        page.add_script_tag(path=str(bundle))
        page.wait_for_function("typeof GraphViewer==='function'")
        page.evaluate('''xml=>{
            const d=document.getElementById('graph');
            d.setAttribute('data-mxgraph',JSON.stringify({xml,nav:false,resize:false,
              responsive:false,'auto-fit':false,'auto-origin':false,'browser-translate':false,
              'allow-zoom-in':false,'allow-zoom-out':false,center:false,border:0,zoom:1,
              lightbox:false,editable:false,'dark-mode':'light','show-note-icons':false}));
            GraphViewer.createViewerForElement(d,v=>{window.evalViewer=v});
        }''',xml)
        page.wait_for_function('window.evalViewer && window.evalViewer.graph && window.evalViewer.graph.view')
        info=page.evaluate('''dims=>{
            const v=window.evalViewer,g=v.graph,d=document.getElementById('graph');
            g.sizeDidChange=function(){};
            g.view.scaleAndTranslate(1,0,0);g.view.validate();
            d.style.width=dims[0]+'px';d.style.height=dims[1]+'px';
            d.style.border='0';d.style.padding='0';d.style.overflow='hidden';
            d.scrollLeft=0;d.scrollTop=0;
            const b=g.getGraphBounds(),t=g.view.translate;
            return {graphBounds:{x:b.x,y:b.y,width:b.width,height:b.height},
              scale:g.view.scale,translate:{x:t.x,y:t.y},
              cells:Object.keys(g.model.cells).length,
              svgCount:d.querySelectorAll('svg').length,
              foreignObjectCount:d.querySelectorAll('foreignObject').length,
              version:typeof EditorUi==='undefined'?null:EditorUi.VERSION};
        }''',[canvas_w,canvas_h])
        page.evaluate('document.fonts.ready')
        page.locator('#graph').screenshot(path=str(output),animations='disabled',timeout=20000)
        # Independent native SVG export gives a second editable render artifact.
        try:
            svg=page.evaluate('''()=>new XMLSerializer().serializeToString(
                window.evalViewer.graph.getSvg('#ffffff',1,0))''')
            (source.parent/'render.svg').write_text(svg)
            info['svg_export']=str(source.parent/'render.svg')
        except Exception as exc:info['svg_export_error']=str(exc)[:1000]
        b=info['graphBounds']
        outside=(b['x']<0 or b['y']<0 or b['x']+b['width']>canvas_w or b['y']+b['height']>canvas_h)
        info['content_outside_declared_canvas']=outside
        # Capture all native graph content as a separate diagnostic when needed.
        if outside and max(b['width'],b['height'])<8192 and b['width']*b['height']<64000000:
            tight_w=math.ceil(b['width']+4);tight_h=math.ceil(b['height']+4)
            page.evaluate('''args=>{
              const g=window.evalViewer.graph,d=document.getElementById('graph');
              g.view.scaleAndTranslate(1,2-args[0],2-args[1]);g.view.validate();
              d.style.width=args[2]+'px';d.style.height=args[3]+'px';
              d.scrollLeft=0;d.scrollTop=0;
            }''',[b['x'],b['y'],tight_w,tight_h])
            page.set_viewport_size({'width':max(tight_w,640),'height':max(tight_h,480)})
            tight=source.parent/'render.tight.png'
            page.locator('#graph').screenshot(path=str(tight),animations='disabled')
            info['tight_diagnostic']=str(tight)
        browser.close()
    (source.parent/'viewer.trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2))
    return {'renderer':'official draw.io viewer-static.min.js GraphViewer in local Chromium',
      'viewer_bundle_sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),
      'viewer_bundle_url':url,'canvas':[canvas_w,canvas_h],**info,
      'vertices':sum(c.get('vertex')=='1'for c in root.iter('mxCell')),
      'edges':sum(c.get('edge')=='1'for c in root.iter('mxCell')),
      'browser_trace':trace,
      'renderer_note':'Actual upstream Graph renders geometry/styles/text. No custom mxCell approximation; model coordinates preserved on declared page.'}


def svg_png(source, output, width, height):
    import cairosvg
    root = ET.fromstring(source.read_text())
    if root.tag.rsplit('}', 1)[-1] != 'svg':
        raise ValueError('SVG root required')
    for e in root.iter():
        tag = e.tag.rsplit('}', 1)[-1]
        if tag in ('image', 'script', 'foreignObject'):
            raise ValueError('SVG must use native vector/text elements; found ' + tag)
        for k,v in e.attrib.items():
            if k.rsplit('}',1)[-1] == 'href' and not v.startswith('#'):
                raise ValueError('external SVG asset is disallowed')
    cairosvg.svg2png(url=str(source), write_to=str(output),
                    output_width=width, output_height=height)
    return {'renderer': 'CairoSVG',
            'vector_elements': len(list(root.iter())),
            'text_elements': sum(e.tag.rsplit('}',1)[-1]=='text' for e in root.iter())}


def chart_png(source, output):
    tree = ast.parse(source.read_text())
    allowed = {'matplotlib', 'numpy', 'math', 'random', 'scipy', 'seaborn', 'pandas'}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [x.name for x in n.names] if isinstance(n, ast.Import) else [n.module or '']
            if any(name.split('.')[0] not in allowed for name in names):
                raise ValueError('chart import outside plotting allowlist: ' + ','.join(names))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {
                'exec','eval','compile','open','__import__','input','breakpoint'}:
            raise ValueError('disallowed chart runtime operation: ' + n.func.id)
        if isinstance(n, ast.Attribute) and n.attr.startswith('__'):
            raise ValueError('dunder attribute is disallowed in chart source')
    env = dict(os.environ, MPLBACKEND='Agg', MPLCONFIGDIR=str(output.parent/'mplconfig'),
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_FSIZE, (50*1024**2, 50*1024**2))
    run = subprocess.run([sys.executable, str(source)], cwd=source.parent,
                         env=env, capture_output=True, timeout=90, preexec_fn=limits)
    (source.parent/'render.stdout.txt').write_bytes(run.stdout)
    (source.parent/'render.stderr.txt').write_bytes(run.stderr)
    if run.returncode:
        raise RuntimeError('chart exited %s: %s' % (run.returncode, run.stderr.decode(errors='replace')[-4000:]))
    if not output.exists():
        raise RuntimeError('chart must save render.png in its current working directory')
    return {'renderer': 'matplotlib Agg', 'returncode': run.returncode}


def validate_poster_html(text):
    class PosterParser(HTMLParser):
        def handle_starttag(self,tag,attrs):
            if tag in {'script','iframe','frame','frameset','object','embed','img','image',
                       'link','base','video','audio','source'}:
                raise ValueError('HTML poster disallows resource/executable element: '+tag)
            for key,value in attrs:
                value=value or ''
                if key.lower().startswith('on'):
                    raise ValueError('HTML poster disallows event-handler attributes')
                if key.lower() in {'src','srcset','poster','action','formaction'}:
                    raise ValueError('HTML poster must not load network or file resources')
                if key.lower() in {'href','xlink:href'}and not value.startswith('#'):
                    raise ValueError('HTML poster may only reference local fragment IDs')
                if tag=='meta'and key.lower()=='http-equiv':
                    raise ValueError('HTML poster disallows http-equiv redirects or headers')
        handle_startendtag=handle_starttag
    PosterParser().feed(text)
    if re.search(r'@import\b|javascript\s*:|data\s*:image',text,re.I):
        raise ValueError('HTML poster disallows imported resources or embedded raster data')
    for resource in re.findall(r'url\s*\((.*?)\)',text,re.I|re.S):
        if not resource.strip().strip('\"\'').startswith('#'):
            raise ValueError('CSS URL must reference an inline fragment ID')


def html_png(source,output,width,height):
    """Render a native academic poster in a fixed, offline browser viewport."""
    from playwright.sync_api import sync_playwright
    text=source.read_text();validate_poster_html(text)
    installed=sorted(Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),
        key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
    options={'headless':True,'args':['--disable-dev-shm-usage']}
    if installed:options['executable_path']=str(installed[0])
    blocked=[]
    with sync_playwright()as p:
        browser=p.chromium.launch(**options)
        context=browser.new_context(viewport={'width':width,'height':height},
            device_scale_factor=1,service_workers='block',java_script_enabled=False)
        context.set_offline(True)
        def deny_resource(route):
            blocked.append(route.request.url);route.abort()
        context.route('**/*',deny_resource)
        page=context.new_page();page.set_default_timeout(30000)
        page.set_content(text,wait_until='domcontentloaded')
        page.evaluate('document.fonts.ready')
        document=page.evaluate('''()=>({
          documentWidth:document.documentElement.scrollWidth,
          documentHeight:document.documentElement.scrollHeight,
          htmlTextElements:Array.from(document.querySelectorAll('body *')).filter(e=>
            e.namespaceURI==='http://www.w3.org/1999/xhtml'&&e.childElementCount===0&&
            e.tagName!=='STYLE'&&e.textContent.trim().length>0).length,
          svgTextElements:document.querySelectorAll('svg text').length,
          svgVectorElements:document.querySelectorAll('svg path,svg rect,svg circle,svg ellipse,svg line,svg polyline,svg polygon').length,
          unreadableMarkers:(document.body.innerText.match(/\\[unreadable\\]/g)||[]).length
        })''')
        page.screenshot(path=str(output),full_page=False,animations='disabled')
        browser.close()
    return {'renderer':'offline headless Chromium HTML/CSS/inline SVG',
        'viewport':[width,height],'network_and_file_resources_blocked':True,
        'blocked_resource_requests':blocked,'native_editable_elements':document,
        'content_outside_viewport':document['documentWidth']>width or document['documentHeight']>height}


def metrics(reference, output):
    from PIL import Image
    import numpy as np
    from skimage.metrics import structural_similarity
    target = Image.open(reference).convert('RGB')
    raw = Image.open(output).convert('RGBA')
    white = Image.new('RGBA', raw.size, 'white'); white.alpha_composite(raw)
    rendered = white.convert('RGB')
    original_dims = rendered.size
    rendered = rendered.resize(target.size, Image.Resampling.LANCZOS)
    a,b = np.asarray(target), np.asarray(rendered)
    mask_a = np.min(a,axis=-1)<240
    mask_b = np.min(b,axis=-1)<240
    union = (mask_a|mask_b).sum()
    return {'reference_size': list(target.size), 'render_size': list(original_dims),
            'ssim_resized': float(structural_similarity(a,b,channel_axis=2,data_range=255)),
            'mae_resized_0_1': float(np.abs(a.astype(float)-b.astype(float)).mean()/255),
            'foreground_iou_resized': float((mask_a&mask_b).sum()/union) if union else 1.0,
            'comparison_note': 'Whole render resized to target; SSIM/background IoU are diagnostics, not semantic correctness.'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--kind',choices=['drawio','svg','python','html'],required=True)
    ap.add_argument('--source',required=True)
    ap.add_argument('--reference')
    ap.add_argument('--width',type=int,required=True)
    ap.add_argument('--height',type=int,required=True)
    ap.add_argument('--proxy',default=os.environ.get('IMG2CODE_DRAWIO_PROXY',''))
    args=ap.parse_args()
    source=Path(args.source).resolve(); output=source.parent/'render.png'
    result={'ok':False,'kind':args.kind,'source':str(source),'output':str(output)}
    started=time.monotonic()
    try:
        if args.kind=='drawio': result.update(drawio_png(source,output,args.width,args.height,args.proxy))
        elif args.kind=='svg': result.update(svg_png(source,output,args.width,args.height))
        elif args.kind=='html': result.update(html_png(source,output,args.width,args.height))
        else: result.update(chart_png(source,output))
        from PIL import Image
        with Image.open(output) as im:
            im.verify()
        result['ok']=True
        if args.reference:result['metrics']=metrics(args.reference,output)
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)[-5000:]
    result['seconds']=round(time.monotonic()-started,3)
    (source.parent/'render.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0 if result['ok'] else 1


if __name__=='__main__':sys.exit(main())
