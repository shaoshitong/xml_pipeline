#!/usr/bin/env python3
"""HKUST-only SVG -> derived image/code pairs, separate from provided-image pairs.
Targets VFIG-Data, VFIG-Bench, starvector/svg-diagrams; no dataset downloads.
Four bounded render subprocesses by default, 30 s timeout each. Resumable shards.
"""
import argparse, base64, collections, concurrent.futures, hashlib, html, importlib.util, io, json, math, os, re, signal, sqlite3, subprocess, sys, tempfile, time, urllib.parse, xml.etree.ElementTree as ET, zlib
from pathlib import Path

MAX_XML=20*1024*1024
NATIVE_RENDER_VERSION='official_offline_drawio_v1'


def first_native_page(native):
    """The selected code, not merely its SVG export, must generate the image."""
    tree=ET.fromstring(native['code'])
    pages=[n for n in tree if localtag(n)=='diagram'] if localtag(tree)=='mxfile' else []
    count=len(pages) if pages else 1
    if pages:
        for page in pages[1:]:tree.remove(page)
    return ET.tostring(tree,encoding='unicode'),count,(pages[0].get('name') if pages else None)


def native_pair_sha(svg_sha,code_sha):
    return hashlib.sha256((NATIVE_RENDER_VERSION+'|'+svg_sha+'|'+code_sha).encode()).hexdigest()


def renderer_path(root,explicit=None):
    candidates=[Path(explicit)] if explicit else [root/'remote/evaluation/remote_render.py',root/'evaluation/remote_render.py',Path(__file__).resolve().parent/'deepseek_cases/remote_render.py']
    return next((p.resolve() for p in candidates if p.is_file()),candidates[0])


def runtime_cache_path(root=None,renderer=None,explicit=None):
    if explicit:
        path=Path(explicit).resolve()
        if not path.is_file():raise ValueError('explicit_runtime_cache_manifest_missing')
        return path
    candidates=[]
    if root:candidates.append(Path(root)/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if renderer:
        candidates.extend(parent/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json' for parent in Path(renderer).resolve().parents)
    return next((path.resolve() for path in candidates if path.is_file()),None)


def cache_context(root,renderer,explicit=None):
    path=runtime_cache_path(root,renderer,explicit)
    if not path:return None,NATIVE_RENDER_VERSION+'|cache:none'
    from stencil_cache import load_cache
    bundle=Path(renderer).resolve().parent/'assets/viewer-static.min.js'
    if not bundle.is_file():raise ValueError('cached_official_drawio_viewer_missing')
    cache=load_cache(path,hashlib.sha256(bundle.read_bytes()).hexdigest())
    return path,NATIVE_RENDER_VERSION+'|cache:'+cache.cache_id


def should_skip_prior(prior,reviewed_key,rebuild_native,retry_failed,current_key,cache_available):
    if not prior:return False
    status,fmt=prior
    if status!='accepted':return not retry_failed
    if not rebuild_native:return True
    if fmt=='drawio':
        # Every valid v1 XML pair already renders the selected native code.
        return bool(reviewed_key and reviewed_key.startswith(NATIVE_RENDER_VERSION))
    if fmt=='svg':
        # Only tracked native-candidate fallbacks can benefit. Plain SVGs never
        # enter a migration merely because a new runtime cache was installed.
        return not (cache_available and reviewed_key and reviewed_key.startswith(NATIVE_RENDER_VERSION) and reviewed_key!=current_key)
    return True


def localtag(node):return node.tag.rsplit('}',1)[-1]


def number(value,default=0.):
    try:return float(value)
    except (TypeError,ValueError):return default


def source_svg(row):
    for key in ('svg','Svg','SVG','source_svg','code'):
        value=row.get(key)
        if isinstance(value,bytes):
            try:value=value.decode()
            except UnicodeError:continue
        if isinstance(value,str) and re.search(r'<svg(?:\s|>)',value):return value,key
    return None,None


def has_provided_image(row):
    for key in ('image','images','image_bytes','png_image','png'):
        value=row.get(key)
        if isinstance(value,dict):value=value.get('bytes') or value.get('path')
        if isinstance(value,(bytes,bytearray)) and value:return True
        if isinstance(value,list) and value:return True
        if isinstance(value,str) and value and (value.startswith('data:image/') or re.search(r'\.(png|jpe?g|webp)$',value,re.I)):return True
    return False


def parse_svg(svg):
    if len(svg.encode())>MAX_XML:raise ValueError('source_svg_over_20MB')
    if '<!ENTITY' in svg.upper():raise ValueError('xml_entity')
    for declaration in re.findall(r'<!DOCTYPE.*?>',svg,re.I|re.S):
        if '[' in declaration:raise ValueError('xml_internal_dtd')
    # Standard external SVG DOCTYPE declarations are inert here: ElementTree
    # does not fetch them and renderer resource fetches are independently blocked.
    root=ET.fromstring(svg)
    if localtag(root)!='svg':raise ValueError('not_svg_root')
    return root


def bounded_inflate(text):
    raw=base64.b64decode(text.strip());decoder=zlib.decompressobj(-15);data=decoder.decompress(raw,MAX_XML+1)
    if len(data)>MAX_XML or decoder.unconsumed_tail or not decoder.eof:raise ValueError('compressed_native_xml_invalid_or_over_20MB')
    decoded=urllib.parse.unquote(data.decode())
    if len(decoded.encode())>MAX_XML:raise ValueError('expanded_native_xml_over_20MB')
    if '<!DOCTYPE' in decoded.upper() or '<!ENTITY' in decoded.upper():raise ValueError('native_xml_dtd_or_entity')
    return ET.fromstring(decoded)


def extract_native(root):
    candidates=[]
    for node in root.iter():
        if localtag(node) in ('mxfile','mxGraphModel'):candidates.append(ET.tostring(node,encoding='unicode'))
        for key,value in node.attrib.items():
            if key.rsplit('}',1)[-1].lower() in ('content','data-mxgraph','mxfile','data-content'):candidates.append(value)
        if localtag(node) in ('metadata','desc') and node.text:candidates.append(node.text)
    for value in candidates:
        variants=[value]
        try:
            obj=json.loads(value)
            if isinstance(obj,dict):variants.extend(v for v in obj.values() if isinstance(v,str))
        except Exception:pass
        expanded_variants=[]
        for candidate in variants:
            # Try each escape depth separately: blindly unescaping an already valid
            # mxCell value such as "x &lt; y" would corrupt its XML attribute.
            for _ in range(4):
                expanded_variants.append(candidate);decoded=html.unescape(candidate)
                if '%3c' in decoded.lower():decoded=urllib.parse.unquote(decoded)
                if decoded==candidate:break
                candidate=decoded
        for candidate in expanded_variants:
            match=re.search(r'<(mxfile|mxGraphModel)\b.*?</\1>',candidate,re.S)
            if not match:continue
            original=match.group(0)
            if len(original.encode())>MAX_XML:raise ValueError('embedded_native_xml_over_20MB')
            if '<!DOCTYPE' in original.upper() or '<!ENTITY' in original.upper():raise ValueError('native_xml_dtd_or_entity')
            try:tree=ET.fromstring(original)
            except ET.ParseError:continue
            expanded=False
            for diagram in list(tree.iter()):
                if localtag(diagram)=='diagram' and not list(diagram) and (diagram.text or '').strip():
                    model=ET.fromstring(diagram.text) if diagram.text.lstrip().startswith('<mxGraphModel') else bounded_inflate(diagram.text)
                    diagram.text=None;diagram.append(model);expanded=True
            code=ET.tostring(tree,encoding='unicode')
            if len(code.encode())>MAX_XML:raise ValueError('normalized_native_xml_over_20MB')
            return {'code':code,'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'expanded_compressed_diagram':expanded,'tree':tree}
    return None


def native_asset_issue(native):
    if not native:return None
    for node in native['tree'].iter():
        markup=html.unescape(' '.join(node.attrib.values()))
        if re.search(r'<\s*(?:script|iframe|object|embed|video|audio|link|base)\b|\bon\w+\s*=|javascript\s*:',markup,re.I):return 'active_drawio_html_content'
        for reference in re.findall(r'(?:^|;)image=([^;]+)',node.get('style','')):
            reference=urllib.parse.unquote(reference)
            if reference and not reference.startswith(('data:','img/lib/','/img/lib/')):return 'external_drawio_image_dependency'
        for reference in re.findall(r'<img\b[^>]*\bsrc=[\'"]([^\'"]+)',node.get('value',''),re.I):
            if not reference.startswith('data:'):return 'external_drawio_html_image_dependency'
    return None


def canvas(root,max_side):
    viewbox=re.split(r'[ ,]+',root.get('viewBox','').strip());vw=vh=None
    if len(viewbox)==4:
        try:vw=float(viewbox[2]);vh=float(viewbox[3])
        except ValueError:pass
    units={'':1.,'px':1.,'pt':96/72,'pc':16.,'in':96.,'cm':96/2.54,'mm':96/25.4}
    def dim(value):
        m=re.fullmatch(r'\s*([+\-]?[0-9.eE]+)\s*([A-Za-z]*)\s*',value or '')
        if not m or m.group(2).lower() not in units:return None
        return number(m.group(1))*units[m.group(2).lower()]
    w=dim(root.get('width'));h=dim(root.get('height'))
    if not w:w=vw
    if not h:h=vh
    if not w or not h or not math.isfinite(w+h) or w<=0 or h<=0:raise ValueError('canvas_dimensions_unknown')
    scale=min(1.,max_side/max(w,h));return max(1,round(w*scale)),max(1,round(h*scale)),w,h


def asset_and_raster_check(root,width,height):
    counts=collections.Counter(localtag(n) for n in root.iter());raster=0;dominant=0
    for node in root.iter():
        tag=localtag(node)
        if tag in ('script','iframe','object','embed','audio','video'):raise ValueError('active_svg_content')
        for key,value in node.attrib.items():
            key=key.rsplit('}',1)[-1].lower()
            if key.startswith('on'):raise ValueError('svg_event_handler')
            if key in ('href','src') and tag not in ('a',) and value and not value.startswith(('#','data:')):raise ValueError('external_svg_asset')
            if key=='style' or tag=='style':
                for url in re.findall(r'url\(\s*[\'"]?([^\s)\'";]+)',value,re.I):
                    if not url.startswith(('#','data:')):raise ValueError('external_svg_css_asset')
        if tag=='style' and node.text:
            if '@import' in node.text:raise ValueError('external_svg_css_import')
            for url in re.findall(r'url\(\s*[\'"]?([^\s)\'";]+)',node.text,re.I):
                if not url.startswith(('#','data:')):raise ValueError('external_svg_css_asset')
        if tag=='image':
            href=next((v for k,v in node.attrib.items() if k.rsplit('}',1)[-1]=='href'),'')
            if re.match(r'data:image/(?:png|jpe?g|webp|gif|bmp)',href,re.I):
                raster+=1;area=number(node.get('width'))*number(node.get('height'))
                if width*height and area/(width*height)>.9:dominant+=1
    shapes=sum(counts[k] for k in ('path','rect','circle','ellipse','polygon','polyline','line'));native_text=counts['text']+counts['foreignObject']
    if raster and not shapes and not native_text:raise ValueError('raster_only_svg_wrapper')
    if dominant and shapes+native_text<=3:raise ValueError('dominant_raster_pseudo_svg')
    return counts,raster


def classify(row,rel,root,native,counts):
    path=str(rel).lower()
    if any(x in path for x in ('shapes-and-arrows','shapes_and_arrows')):return None,'shapes_and_arrows_subset',{}
    if native and re.search(r'mxgraph\.mockup|wireframe|landing.?page|login.?form|navigation.?bar|navbar|shopping.?cart|checkout',native['code'],re.I):
        return None,'web_ui_or_wireframe_domain',{}
    parts=[]
    for key in ('filename','Filename','caption','description','vlm_description','category','metadata','source'):
        value=row.get(key)
        if value is not None:parts.append(str(value))
    parts.extend(' '.join(n.itertext()) for n in root.iter() if localtag(n) in ('text','foreignObject','title','desc'))
    vertices=edges=labeled=0
    if native:
        parents={child:parent for parent in native['tree'].iter() for child in parent}
        for n in native['tree'].iter():
            if localtag(n)=='mxCell':
                vertices+=n.get('vertex')=='1';edges+=n.get('edge')=='1'
                wrapper=parents.get(n);value=n.get('value','') or (wrapper.get('label',wrapper.get('value','')) if wrapper is not None else '');value=html.unescape(value);value=re.sub('<[^>]+>',' ',value)
                if value.strip():labeled+=1;parts.append(value)
    text=html.unescape(' '.join(parts)).casefold();facts={'native_vertices':vertices,'native_edges':edges,'text_elements':counts['text'],'labeled_native_cells':labeled}
    chart=r'line chart|line plot|scatter|bar chart|bar plot|histogram|box ?plot|heatmap|data visual|time series|experimental results|performance curve|learning curve|roc curve|precision.recall|axis label|error bar|distribution plot'
    if re.search(chart,text):return 'chart','explicit_chart_semantics',facts
    ids=' '.join(n.get('id','') for n in root.iter()).lower()
    if re.search(r'xtick_|ytick_',ids) and counts['path']+counts['polyline']>2:return 'chart','plot_export_structure',facts
    # Plot subject matter does not exclude a chart. Reject standalone molecule,
    # circuit, geometry and icon diagrams only after chart structure is checked.
    if re.search(r'commutative|geometr(?:y|ic|ical)|euclidean|polyhedr|triangle|tetrahedr|knot diagram|graph theor|cayley|chemical|molecule|circuit|periodic table|(?:app|brand|social media) icon|company logo',text):return None,'excluded_math_chem_circuit_icon_domain',facts
    framework=r'flow.?chart|pipeline|workflow|architecture|neural network|convolutional|framework|data.?flow|block diagram|feature extraction|encoder|decoder|attention|transformer|embedding|classifier|preprocess|algorithm|training|prediction|activation|backprop|loss function|input|output|yes|start|process'
    matches=re.findall(framework,text)
    if native and edges>=2 and vertices>=3 and labeled>=3 and matches:return 'scientific_diagram','native_graph_and_framework_labels',facts
    if len(matches)>=2 and counts['text']+counts['foreignObject']>=3 and sum(counts[k] for k in ('path','line','polyline'))>=2:return 'scientific_diagram','framework_text_and_connectors',facts
    return None,'svg_domain_not_established',facts


def render_child(width,height,backend):
    svg=sys.stdin.buffer.read().decode()
    if backend=='cairosvg':
        import cairosvg
        def data_only_fetch(url,resource_type):
            if not str(url).startswith('data:'):raise ValueError('external/nested file or URL resource blocked')
            head,payload=str(url).split(',',1);data=base64.b64decode(payload) if ';base64' in head else urllib.parse.unquote_to_bytes(payload)
            if len(data)>MAX_XML:raise ValueError('embedded resource over 20MB')
            return data
        from cairosvg.surface import PNGSurface
        data=PNGSurface.convert(bytestring=svg.encode(),output_width=width,output_height=height,background_color='white',url_fetcher=data_only_fetch)
    else:
        from playwright.sync_api import sync_playwright
        installed=sorted(Path('/home/shaoshitong/.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
        opts={'headless':True,'args':['--disable-dev-shm-usage','--disable-gpu']}
        if installed:opts['executable_path']=str(installed[0])
        with sync_playwright() as p:
            browser=p.chromium.launch(**opts);page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1,java_script_enabled=False)
            page.route('**/*',lambda route:route.abort())
            # Scale an original-size viewport, rather than resizing a no-viewBox
            # SVG and accidentally cropping its right/bottom content.
            _,_,original_width,original_height=canvas(parse_svg(svg),max(width,height))
            style='html,body{margin:0;background:white}#source{width:'+str(original_width)+'px;height:'+str(original_height)+'px;transform:scale('+str(width/original_width)+','+str(height/original_height)+');transform-origin:0 0}#source>svg{display:block;width:100%!important;height:100%!important}'
            page.set_content('<html><head><style>'+style+'</style></head><body><div id="source">'+svg+'</div></body></html>',wait_until='load',timeout=20000)
            page.evaluate('document.fonts.ready');data=page.screenshot(type='png');browser.close()
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:im.verify()
    sys.stdout.buffer.write(data)


def job(svg,width,height,backend,timeout,_retried=False):
    started=time.monotonic();env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    process=None
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--render-only','--width',str(width),'--height',str(height),'--backend',backend],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,start_new_session=True)
        png,err=process.communicate(svg.encode(),timeout=timeout)
        if process.returncode:
            message=err.decode(errors='replace').strip()[-1500:] or 'nonzero exit without stderr'
            if backend=='chromium' and not _retried:
                result=job(svg,width,height,backend,timeout,True)
                result['seconds']=time.monotonic()-started
                result['browser_retry']=True;result['first_attempt_error']=message
                return result
            return {'ok':False,'reason':'render_failed_'+backend,'error':message,'returncode':process.returncode,'seconds':time.monotonic()-started}
        if not png.startswith(b'\x89PNG') or len(png)>64*1024*1024:return {'ok':False,'reason':'invalid_or_oversized_png','seconds':time.monotonic()-started}
        return {'ok':True,'png':png,'seconds':time.monotonic()-started}
    except subprocess.TimeoutExpired:
        if process:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.communicate()
        return {'ok':False,'reason':'render_timeout_30s','seconds':time.monotonic()-started}
    except Exception as e:return {'ok':False,'reason':'render_worker_exception','error':type(e).__name__+':'+str(e)[:200],'seconds':time.monotonic()-started}


def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));temp.replace(path)


def native_render_child(args):
    """Call the cached official renderer in an isolated, offline subprocess."""
    renderer=Path(args.drawio_renderer).resolve();bundle=renderer.parent/'assets/viewer-static.min.js'
    if not bundle.is_file() or bundle.stat().st_size<100000:raise ValueError('cached_official_drawio_viewer_missing')
    work=Path(args.render_directory);source=work/'selected.drawio';output=work/'render.png'
    code=sys.stdin.buffer.read(MAX_XML+1)
    if len(code)>MAX_XML:raise ValueError('selected_native_xml_over_20MB')
    source.write_bytes(code)
    spec=importlib.util.spec_from_file_location('img2code_official_remote_renderer',renderer)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # The existing renderer uses Browser.new_page. These guards apply before
    # any content is loaded; the bundle is injected from the cached local path.
    # No changes are made to the shared evaluation renderer or global proxies.
    from playwright.sync_api import Browser
    cache=None
    cache_manifest=runtime_cache_path(renderer=renderer,explicit=getattr(args,'runtime_cache',None))
    if cache_manifest:
        from stencil_cache import load_cache
        cache=load_cache(cache_manifest,hashlib.sha256(bundle.read_bytes()).hexdigest())
    original=Browser.new_page;blocked=[];served={};cache_errors=[]
    def offline_page(browser,*pos,**kw):
        page=original(browser,*pos,**kw);page.context.set_offline(True)
        def deny(route):
            if cache:
                try:
                    asset=cache.lookup(route.request.url)
                    if asset is not None:
                        evidence=asset['evidence'];served[evidence['url_path']]=evidence
                        route.fulfill(status=200,body=asset['body'],content_type=asset.get('content_type','application/xml'),headers={'Access-Control-Allow-Origin':'*','Cache-Control':'no-store'})
                        return
                except Exception as exc:
                    # Never expose request query values or silently use an
                    # unverified asset when a local-cache check fails.
                    cache_errors.append(type(exc).__name__)
            blocked.append(route.request.url.split(':',1)[0]);route.abort()
        page.route('**/*',deny)
        return page
    Browser.new_page=offline_page
    os.environ.pop('IMG2CODE_DRAWIO_BACKEND',None)
    try:info=module.drawio_png(source,output,args.width,args.height,'')
    finally:Browser.new_page=original
    if cache_errors:raise ValueError('native_drawio_runtime_cache_verification_failed')
    if blocked:raise ValueError('native_drawio_requires_blocked_resource')
    trace=info.get('browser_trace',[])
    if any(x.get('kind') in ('pageerror','requestfailed') or (x.get('kind')=='console' and x.get('type')=='error') for x in trace):raise ValueError('native_drawio_browser_error')
    if info.get('cells',0)<3 or info.get('svgCount',0)<1:raise ValueError('native_drawio_empty_graph')
    # A declared page may clip content. The official renderer also captures a
    # tight diagnostic with the same graph; use that complete render explicitly.
    tight=work/'render.tight.png';use_tight=bool(info.get('content_outside_declared_canvas'))
    if use_tight and not tight.is_file():raise ValueError('native_content_outside_canvas_without_complete_render')
    selected=tight if use_tight else output
    from PIL import Image,ImageChops
    with Image.open(selected) as image:
        image=image.convert('RGB')
        if ImageChops.difference(image,Image.new('RGB',image.size,'white')).getbbox() is None:raise ValueError('native_drawio_blank_render')
        scale=min(1.,args.max_side/max(image.size))
        if scale<1:image=image.resize((max(1,round(image.width*scale)),max(1,round(image.height*scale))),Image.Resampling.LANCZOS)
        image.save(output,format='PNG');width,height=image.size
    info.pop('browser_trace',None)
    # Temporary paths are not durable locators; retain only renderer evidence.
    for key in ('svg_export','tight_diagnostic'):info.pop(key,None)
    info.update({'network_and_file_resources_blocked':True,'blocked_resource_requests':len(blocked),'selected_image':'complete_tight_graph' if use_tight else 'declared_first_page','output_size':[width,height],'render_version':NATIVE_RENDER_VERSION,'runtime_cache_id':cache.cache_id if cache else None,'runtime_cache_manifest_sha256':hashlib.sha256(cache_manifest.read_bytes()).hexdigest() if cache_manifest else None,'runtime_cache_provenance':{key:cache.metadata.get(key) for key in ('version','commit','viewer_release_commit','archive_sha256','archive_role','stencil_source_kind','viewer_bundle_sha256')} if cache else None,'served_local_dependencies':list(served.values()),'runtime_resource_policy':'network/file requests blocked; only exact allowlisted pinned stencil XML may be fulfilled from SHA-verified task-local bytes'})
    atomic_json(work/'native_render.json',info)


def native_job(code,width,height,timeout,renderer,max_side,runtime_cache=None):
    started=time.monotonic();process=None
    try:
        with tempfile.TemporaryDirectory(prefix='img2code-native-') as directory:
            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');env.pop('IMG2CODE_DRAWIO_BACKEND',None)
            command=[sys.executable,str(Path(__file__).resolve()),'--render-native-only','--drawio-renderer',str(renderer),'--render-directory',directory,'--width',str(width),'--height',str(height),'--max-side',str(max_side)]
            cache_manifest=runtime_cache_path(renderer=renderer,explicit=runtime_cache)
            if cache_manifest:command.extend(['--runtime-cache',str(cache_manifest)])
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,start_new_session=True)
            _,err=process.communicate(code.encode(),timeout=timeout)
            if process.returncode:return {'ok':False,'reason':'native_drawio_render_failed','error':err.decode(errors='replace').strip()[-1500:],'seconds':time.monotonic()-started}
            png=(Path(directory)/'render.png').read_bytes();info=json.loads((Path(directory)/'native_render.json').read_text())
            if not png.startswith(b'\x89PNG') or len(png)>64*1024*1024:raise ValueError('invalid_or_oversized_native_png')
            return {'ok':True,'png':png,'native_selected':True,'native_render':info,'seconds':time.monotonic()-started}
    except subprocess.TimeoutExpired:
        if process:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.communicate()
        return {'ok':False,'reason':'native_drawio_render_timeout','seconds':time.monotonic()-started}
    except Exception as exc:return {'ok':False,'reason':'native_drawio_worker_exception','error':type(exc).__name__+':'+str(exc)[:300],'seconds':time.monotonic()-started}


def selected_job(svg,native_code,width,height,backend,timeout,renderer,max_side,runtime_cache=None,preserve_existing_svg=False):
    started=time.monotonic();native=None
    if native_code:
        native=native_job(native_code,width,height,timeout,renderer,max_side,runtime_cache)
        if native['ok']:return native
        if preserve_existing_svg:return native
    result=job(svg,width,height,backend,timeout);result['native_selected']=False
    if native:result.update({'native_fallback_reason':native['reason'],'native_fallback_error':native.get('error'),'seconds':time.monotonic()-started})
    return result


def reconcile_shards(db,out,source,root,manifest,pq):
    shards=sorted(out.glob('pairs-*.parquet'));rows=sum(pq.ParquetFile(p).metadata.num_rows for p in shards)
    ledger=db.execute('SELECT COUNT(*) FROM items WHERE source=? AND status="accepted"',(source,)).fetchone()[0]
    manifest_rows=0;manifest_valid=True
    if manifest.is_file():
        with manifest.open() as stream:
            for line in stream:
                try:json.loads(line);manifest_rows+=1
                except Exception:manifest_valid=False
    restore_ledger=ledger<rows;restore_manifest=not manifest_valid or manifest_rows!=rows
    if not restore_ledger and not restore_manifest:return
    columns=['source_repo','source_file','source_row','source_filename','source_svg_sha256','code_sha256','image_sha256','code_format','category','image_provenance','code_provenance','render_backend','width','height','semantic_basis']
    temp=manifest.with_suffix('.recovered.jsonl');output=temp.open('w') if restore_manifest else None
    preexisting_review_ids={row[0] for row in db.execute('SELECT item_id FROM render_versions')}
    try:
        for shard in shards:
            optional=['pairing','render_version','render_review_key','code_execution_checked','render_validation_scope','native_render_json','native_fallback_reason','native_original_page_count','native_selected_page']
            available=set(pq.ParquetFile(shard).schema_arrow.names)
            for index,row in enumerate(pq.read_table(shard,columns=columns+[key for key in optional if key in available]).to_pylist()):
                raw_key=row['source_repo']+'|'+row['source_file']+'|'+str(row['source_row']);item_id=hashlib.sha256((raw_key+'|'+row['source_svg_sha256']).encode()).hexdigest();pair_sha=native_pair_sha(row['source_svg_sha256'],row['code_sha256']) if row.get('render_version')==NATIVE_RENDER_VERSION else hashlib.sha256((row['source_svg_sha256']+row['code_sha256']).encode()).hexdigest()
                if restore_ledger:
                    db.execute('INSERT OR IGNORE INTO pairs VALUES (?)',(pair_sha,));db.execute('INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)',(item_id,source,'accepted',None,row['code_format'],row['category']))
                    if row.get('render_version') and item_id not in preexisting_review_ids:db.execute('INSERT OR REPLACE INTO render_versions VALUES (?,?)',(item_id,row.get('render_review_key') or row['render_version']))
                if output:
                    record={**row,'source':source,'format':row['code_format'],'gold_code_provenance':row['code_provenance'],'image_key':'image','code_key':'code','pairing':row.get('pairing','derived_from_source_svg'),'structurally_complete':True,'code_execution_checked':bool(row.get('code_execution_checked',False)),'native_xml_selected_as_code':row['code_format']=='drawio','clean_file':str(shard.relative_to(root)),'clean_row':index,'derived_file':str(shard.relative_to(root)),'derived_row':index,'manifest_recovered_from_committed_shard':True}
                    if row.get('native_render_json'):
                        try:record['native_render']=json.loads(row['native_render_json'])
                        except (ValueError,TypeError):pass
                    output.write(json.dumps(record,ensure_ascii=False)+'\n')
        db.commit()
    finally:
        if output:output.close()
    if restore_manifest:temp.replace(manifest)
    print(json.dumps({'event':'derived_state_reconciled','source':source,'committed_rows':rows,'ledger_restored':restore_ledger,'manifest_restored':restore_manifest}),flush=True)


def main_run(args):
    import pyarrow as pa,pyarrow.parquet as pq
    root=args.root.resolve();derived=root/'derived';manifests=root/'manifests';reports=root/'reports'
    for p in (derived,manifests,reports):p.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(manifests/'derived_state.sqlite');db.execute('CREATE TABLE IF NOT EXISTS items(item_id TEXT PRIMARY KEY,source TEXT,status TEXT,reason TEXT,format TEXT,category TEXT)');db.execute('CREATE TABLE IF NOT EXISTS pairs(pair_sha TEXT PRIMARY KEY)');db.execute('CREATE TABLE IF NOT EXISTS render_versions(item_id TEXT PRIMARY KEY,version TEXT)');db.commit()
    schema=pa.schema([('source_repo',pa.string()),('source_file',pa.string()),('source_row',pa.int64()),('source_filename',pa.string()),('category',pa.string()),('image',pa.struct([('bytes',pa.binary()),('path',pa.string())])),('source_svg',pa.large_string()),('source_svg_sha256',pa.string()),('code',pa.large_string()),('code_format',pa.string()),('native_drawio',pa.large_string()),('image_provenance',pa.string()),('code_provenance',pa.string()),('pairing',pa.string()),('render_backend',pa.string()),('width',pa.int32()),('height',pa.int32()),('semantic_basis',pa.string()),('code_sha256',pa.string()),('image_sha256',pa.string()),('render_version',pa.string()),('render_review_key',pa.string()),('code_execution_checked',pa.bool_()),('render_validation_scope',pa.string()),('native_render_json',pa.large_string()),('native_fallback_reason',pa.string()),('native_original_page_count',pa.int32()),('native_selected_page',pa.int32())])
    summary={'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'workers':args.workers,'per_image_timeout_seconds':args.timeout,'sources':{},'derived_pairs':0,'provided_image_pairs':0,'native_render_version':NATIVE_RENDER_VERSION,'note':'Derived images are rendered from the selected SVG or selected first-page native drawio code. Embedded XML exporter authorship is unverified; it is not original-author gold. Legacy mixed SVG-image/native-code rows must be excluded from the canonical catalog. code_execution_checked means only offline rendering of the selected code. Counts remain separate from provided-image/code pairs.'}
    drawio_renderer=renderer_path(root,args.drawio_renderer)
    runtime_cache,current_review_key=cache_context(root,drawio_renderer,getattr(args,'runtime_cache',None))
    summary.update({'runtime_cache_available':runtime_cache is not None,'native_review_key':current_review_key})
    selected=[]
    for source in sorted((root/'raw').iterdir()):
        if not source.is_dir():continue
        if args.only:
            if not any(x.lower() in source.name.lower() for x in args.only):continue
        elif not any(x in source.name.lower() for x in ('qijiahe--vfig-data','qijiahe--vfig-bench','starvector--svg-diagrams')):continue
        selected.append(source)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for source in selected:
            out=derived/source.name;out.mkdir(parents=True,exist_ok=True);manifest=manifests/('derived.'+source.name+'.jsonl');rejected=manifests/('derived.'+source.name+'.rejected.jsonl');buffer=[];buffer_bytes=0;pending_pairs=set();pending={};next_part=max([int(re.search(r'pairs-(\d+)\.parquet',p.name).group(1)) for p in out.glob('pairs-*.parquet')]+[-1])+1
            reconcile_shards(db,out,source.name,root,manifest,pq)
            processed_this_run=0;upgrade_stats=collections.Counter()
            def keep_existing_svg(item_id,record,reason,error=None):
                # The previous SVG/image pair remains valid even if native
                # extraction, eligibility, rendering or de-duplication fails.
                db.execute('INSERT OR REPLACE INTO render_versions VALUES (?,?)',(item_id,current_review_key))
                upgrade_stats['retained_existing_svg']+=1;upgrade_stats['retained_'+reason]+=1
                rf.write(json.dumps({**record,'event':'native_upgrade_retained_existing_svg','reason':reason,'render_review_key':current_review_key,**({'error':error} if error else {})},ensure_ascii=False)+'\n')
            def reject(item_id,record,reason,error=None):
                record['reason']=reason
                if error:record['error']=error
                rf.write(json.dumps(record,ensure_ascii=False)+'\n');db.execute('INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)',(item_id,source.name,'rejected',reason,None,None))
            def flush():
                nonlocal next_part,buffer_bytes
                if not buffer:return
                target=out/f'pairs-{next_part:05d}.parquet';temp=target.with_suffix('.parquet.tmp');pq.write_table(pa.Table.from_pylist([x['row'] for x in buffer],schema=schema),temp,compression='zstd');temp.replace(target)
                for index,item in enumerate(buffer):
                    record=item['manifest'];record.update({'derived_file':str(target.relative_to(root)),'derived_row':index,'clean_file':str(target.relative_to(root)),'clean_row':index});mf.write(json.dumps(record,ensure_ascii=False)+'\n');db.execute('INSERT OR IGNORE INTO pairs VALUES (?)',(item['pair_sha'],));db.execute('INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?)',(item['item_id'],source.name,'accepted',None,item['row']['code_format'],item['row']['category']))
                    if item['row'].get('render_version'):db.execute('INSERT OR REPLACE INTO render_versions VALUES (?,?)',(item['item_id'],item['row'].get('render_review_key') or item['row']['render_version']))
                mf.flush();os.fsync(mf.fileno());db.commit();pending_pairs.difference_update(item['pair_sha'] for item in buffer);buffer.clear();buffer_bytes=0;next_part+=1
            def collect(done):
                nonlocal buffer_bytes,processed_this_run
                for future in done:
                    meta=pending.pop(future);result=future.result();processed_this_run+=1
                    if meta.get('preserve_existing_svg') and (not result['ok'] or not result.get('native_selected')):
                        pending_pairs.discard(meta['pair_sha']);keep_existing_svg(meta['item_id'],meta['manifest'],result.get('reason') or result.get('native_fallback_reason') or 'native_upgrade_returned_svg',result.get('error') or result.get('native_fallback_error'));continue
                    if not result['ok']:
                        pending_pairs.discard(meta['pair_sha']);reject(meta['item_id'],meta['manifest'],result['reason'],result.get('error'));continue
                    png=result['png'];row=meta['row'];record=meta['manifest']
                    if result.get('native_selected'):
                        if meta.get('preserve_existing_svg'):upgrade_stats['upgraded_to_native']+=1
                        info=result['native_render'];row.update({'image_provenance':'rendered_from_selected_native_drawio','pairing':'derived_from_native_drawio','render_backend':'official_offline_drawio','code_execution_checked':True,'render_validation_scope':'selected_first_page_render_only_network_and_file_resources_blocked','native_render_json':json.dumps(info,ensure_ascii=False),'width':info['output_size'][0],'height':info['output_size'][1]})
                        record.update({'native_xml_selected_as_code':True,'native_render':info,'code_execution_checked':True,'render_validation_scope':row['render_validation_scope']})
                    elif meta['native_candidate']:
                        # Never pair the source SVG image with unrendered native XML.
                        row.update({'code':row['source_svg'],'code_format':'svg','code_provenance':'dataset_svg','code_sha256':row['source_svg_sha256'],'native_fallback_reason':result.get('native_fallback_reason'),'code_execution_checked':True,'render_validation_scope':'source_svg_render_only_network_and_file_resources_blocked'})
                        pending_pairs.discard(meta['pair_sha']);meta['pair_sha']=native_pair_sha(row['source_svg_sha256'],row['code_sha256'])
                        if meta['pair_sha'] in pending_pairs or db.execute('SELECT 1 FROM pairs WHERE pair_sha=?',(meta['pair_sha'],)).fetchone():
                            reject(meta['item_id'],record,'duplicate_derived_source_and_code_after_svg_fallback');continue
                        pending_pairs.add(meta['pair_sha']);record.update({'native_xml_selected_as_code':False,'native_xml_fallback_reason':result.get('native_fallback_reason'),'native_xml_fallback_error':result.get('native_fallback_error')})
                    row['image']={'bytes':png,'path':meta['item_id']+'.png'};row['image_sha256']=hashlib.sha256(png).hexdigest()
                    record.update({k:row.get(k) for k in ('code_format','code_provenance','image_provenance','pairing','render_backend','width','height','code_sha256','image_sha256','render_version','render_review_key','code_execution_checked','render_validation_scope')});record.update({'format':row['code_format'],'gold_code_provenance':row['code_provenance'],'render_seconds':result['seconds']})
                    buffer.append({'item_id':meta['item_id'],'pair_sha':meta['pair_sha'],'row':row,'manifest':record});buffer_bytes+=len(png)+len(row['source_svg'].encode())+len(row['code'].encode())
                    if len(buffer)>=args.shard_rows or buffer_bytes>=32*1024*1024:flush()
                    if processed_this_run%50==0:print(json.dumps({'event':'derived_progress','source':source.name,'renders_finished_this_run':processed_this_run,'buffered_pairs':len(buffer),'pending':len(pending),'next_shard':next_part}),flush=True)
            with manifest.open('a') as mf,rejected.open('a') as rf:
                for file in sorted(source.rglob('*.parquet')):
                    rel=str(file.relative_to(source));row_index=0
                    try:reader=pq.ParquetFile(file)
                    except Exception as e:
                        rf.write(json.dumps({'source_repo':source.name,'source_file':rel,'reason':'unreadable_parquet','error':type(e).__name__})+'\n');continue
                    for batch in reader.iter_batches(batch_size=16):
                        for row in batch.to_pylist():
                            index=row_index;row_index+=1;svg,key=source_svg(row)
                            raw_key=source.name+'|'+rel+'|'+str(index);svg_sha=hashlib.sha256((svg or '').encode()).hexdigest();item_id=hashlib.sha256((raw_key+'|'+svg_sha).encode()).hexdigest();prior=db.execute('SELECT status,format FROM items WHERE item_id=?',(item_id,)).fetchone()
                            version_row=db.execute('SELECT version FROM render_versions WHERE item_id=?',(item_id,)).fetchone();reviewed_key=version_row[0] if version_row else None
                            if should_skip_prior(prior,reviewed_key,args.rebuild_native,args.retry_failed,current_review_key,runtime_cache is not None):continue
                            preserve_existing_svg=bool(prior and prior[0]=='accepted' and prior[1]=='svg')
                            if preserve_existing_svg:upgrade_stats['reviewed_existing_svg']+=1
                            record={'source':source.name,'source_repo':source.name,'source_file':rel,'source_row':index,'source_svg_sha256':svg_sha,'image_provenance':'rendered_from_source_svg','pairing':'derived_from_source_svg'}
                            try:
                                if has_provided_image(row):raise ValueError('provided_image_record_not_source_only')
                                if not svg:raise ValueError('no_source_svg')
                                tree=parse_svg(svg);w,h,ow,oh=canvas(tree,args.max_side);counts,raster=asset_and_raster_check(tree,ow,oh);native=extract_native(tree);category,basis,facts=classify(row,rel,tree,native,counts)
                                if category is None:raise ValueError(basis)
                                if prior and prior[0]=='accepted' and not native:
                                    if preserve_existing_svg:keep_existing_svg(item_id,record,'native_document_no_longer_extractable')
                                    continue
                                native_issue=native_asset_issue(native);use_native=bool(native and not native_issue);selected_code,page_count,page_name=first_native_page(native) if use_native else (None,None,None);code=selected_code if use_native else svg;fmt='drawio' if use_native else 'svg';code_sha=hashlib.sha256(code.encode()).hexdigest();pair_sha=native_pair_sha(svg_sha,code_sha) if native else hashlib.sha256((svg_sha+code_sha).encode()).hexdigest()
                                if preserve_existing_svg and not use_native:
                                    keep_existing_svg(item_id,record,native_issue or 'native_not_eligible');continue
                                if pair_sha in pending_pairs or db.execute('SELECT 1 FROM pairs WHERE pair_sha=?',(pair_sha,)).fetchone():
                                    if preserve_existing_svg:
                                        keep_existing_svg(item_id,record,'duplicate_native_source_and_code');continue
                                    raise ValueError('duplicate_derived_source_and_code')
                                pending_pairs.add(pair_sha);backend='chromium' if counts['foreignObject'] else 'cairosvg';provenance='embedded_exporter_drawio_author_unverified' if use_native else 'dataset_svg';record.update({'category':category,'code_format':fmt,'format':fmt,'code_provenance':provenance,'gold_code_provenance':provenance,'image_key':'image','code_key':'code','structurally_complete':True,'code_execution_checked':False,'code_sha256':code_sha,'render_backend':backend,'width':w,'height':h,'semantic_basis':basis,'raster_image_elements':raster,'native_xml_selected_as_code':use_native,'native_xml_auxiliary_issue':native_issue,'native_xml_decompressed':native['expanded_compressed_diagram'] if native else False,'embedded_xml_sha256':native['original_sha256'] if native else None,'structure':facts,'native_original_page_count':page_count,'native_selected_page':0 if use_native else None,'native_selected_page_name':page_name,'render_version':NATIVE_RENDER_VERSION if native else None,'render_review_key':current_review_key if native else None})
                                output_row={'source_repo':source.name,'source_file':rel,'source_row':index,'source_filename':str(row.get('filename',row.get('Filename',''))),'category':category,'source_svg':svg,'source_svg_sha256':svg_sha,'code':code,'code_format':fmt,'native_drawio':native['code'] if native else None,'image_provenance':'rendered_from_source_svg','code_provenance':provenance,'pairing':'derived_from_source_svg','render_backend':backend,'width':w,'height':h,'semantic_basis':basis,'code_sha256':code_sha,'render_version':NATIVE_RENDER_VERSION if native else None,'render_review_key':current_review_key if native else None,'code_execution_checked':True,'render_validation_scope':'source_svg_render_only_network_and_file_resources_blocked','native_original_page_count':page_count,'native_selected_page':0 if use_native else None}
                                future=pool.submit(selected_job,svg,selected_code,w,h,backend,args.timeout,drawio_renderer,args.max_side,runtime_cache,preserve_existing_svg);pending[future]={'item_id':item_id,'pair_sha':pair_sha,'manifest':record,'row':output_row,'native_candidate':use_native,'preserve_existing_svg':preserve_existing_svg}
                            except Exception as e:
                                reason=str(e)[:180] if isinstance(e,ValueError) else type(e).__name__
                                if preserve_existing_svg:keep_existing_svg(item_id,record,reason)
                                else:reject(item_id,record,reason,None)
                            if len(pending)>=args.workers*2:
                                done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED);collect(done)
                        db.commit()
                    print(json.dumps({'event':'derived_source_file_scanned','source':source.name,'file':rel,'rows':row_index,'rendered_this_run':processed_this_run,'pending':len(pending)}),flush=True)
                while pending:
                    done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED);collect(done)
                flush();db.commit()
            statuses=dict(db.execute('SELECT status,COUNT(*) FROM items WHERE source=? GROUP BY status',(source.name,)).fetchall());reasons=dict(db.execute('SELECT reason,COUNT(*) FROM items WHERE source=? AND status="rejected" GROUP BY reason',(source.name,)).fetchall());formats=dict(db.execute('SELECT format,COUNT(*) FROM items WHERE source=? AND status="accepted" GROUP BY format',(source.name,)).fetchall());categories=dict(db.execute('SELECT category,COUNT(*) FROM items WHERE source=? AND status="accepted" GROUP BY category',(source.name,)).fetchall())
            summary['sources'][source.name]={'derived_pairs':statuses.get('accepted',0),'rejected':statuses.get('rejected',0),'reasons':reasons,'formats':formats,'categories':categories,'shards':len(list(out.glob('pairs-*.parquet'))),'manifest':str(manifest.relative_to(root)),'native_upgrade':dict(upgrade_stats)};summary['derived_pairs']=sum(x['derived_pairs'] for x in summary['sources'].values());atomic_json(reports/'derived_summary.json',summary);print(json.dumps({'event':'derived_source_complete','source':source.name,**summary['sources'][source.name]}),flush=True)
    summary['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());atomic_json(reports/'derived_summary.json',summary);db.close()


def self_test():
    # Real control-flow/ledger tests with fake Arrow, not a browser rendering claim.
    import contextlib,importlib.util,pickle,types
    class Table:
        def __init__(self,rows):self.rows=rows
        def to_pylist(self):return self.rows
        @classmethod
        def from_pylist(cls,rows,schema=None):return cls(rows)
    class PF:
        def __init__(self,path):
            self.rows=pickle.loads(Path(path).read_bytes());self.metadata=types.SimpleNamespace(num_rows=len(self.rows));self.schema_arrow=types.SimpleNamespace(names=list(self.rows[0]) if self.rows else [])
        def iter_batches(self,batch_size=16):yield Table(self.rows)
    pa=types.ModuleType('pyarrow');pq=types.ModuleType('pyarrow.parquet')
    for key in ('string','large_string','int64','int32','binary','bool_'):setattr(pa,key,lambda:None)
    pa.struct=lambda *x:None;pa.schema=lambda *x:None;pa.Table=Table;pa.parquet=pq
    pq.ParquetFile=PF;pq.read_table=lambda path,columns=None:Table([{k:r.get(k) for k in columns} for r in pickle.loads(Path(path).read_bytes())] if columns else pickle.loads(Path(path).read_bytes()));pq.write_table=lambda table,path,**kw:Path(path).write_bytes(pickle.dumps(table.rows))
    old_pa=sys.modules.get('pyarrow');old_pq=sys.modules.get('pyarrow.parquet');sys.modules['pyarrow']=pa;sys.modules['pyarrow.parquet']=pq
    baseline_path=Path(__file__).resolve().with_name('curate_derived.py');spec=importlib.util.spec_from_file_location('stencil_baseline_fixture',baseline_path);baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    old_context=globals()['cache_context'];old_selected=globals()['selected_job']
    def mark(code):return next((name for name in ('GOOD_NATIVE','UPGRADE_OK','ASSET_ISSUE','FAIL_NATIVE','FALLBACK_DUP') if name in (code or '')),'PLAIN')
    def successful(svg,code):return {'ok':True,'native_selected':True,'png':b'\x89PNGnative'+hashlib.sha256(code.encode()).digest(),'seconds':0,'native_render':{'output_size':[600,400],'renderer':'official test stub','network_and_file_resources_blocked':True,'blocked_resource_requests':0}}
    def baseline_selected(svg,code,*args):
        if code and mark(code)=='GOOD_NATIVE':return successful(svg,code)
        return {'ok':True,'native_selected':False,'png':b'\x89PNGsvg'+hashlib.sha256(svg.encode()).digest(),'seconds':0,**({'native_fallback_reason':'native_drawio_render_failed'} if code else {})}
    baseline.selected_job=baseline_selected
    model='<mxGraphModel pageWidth="600" pageHeight="400"><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" value="Input" vertex="1"/><mxCell id="3" value="Encoder {mark}" vertex="1" {style}/><mxCell id="4" value="Output" vertex="1"/><mxCell id="5" edge="1"/><mxCell id="6" edge="1"/></root></mxGraphModel>'
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" id="{mark}" {content}><text>Input</text><text>Encoder</text><text>Output</text><path d="M0,0 L100,100"/><path d="M100,100 L200,200"/></svg>'
    rows=[]
    for name in ('PLAIN','GOOD_NATIVE','UPGRADE_OK','ASSET_ISSUE','FAIL_NATIVE','FALLBACK_DUP'):
        native='<mxfile><diagram name="first">'+model.format(mark=name,style='style="image=https://example.invalid/dep.png"' if name=='ASSET_ISSUE' else '')+'</diagram></mxfile>'
        rows.append({'filename':name+'.svg','svg':svg.format(mark=name,content='' if name=='PLAIN' else 'content="'+html.escape(native,quote=True)+'"')})
    try:
        with tempfile.TemporaryDirectory(prefix='stencil-migration-fixture-') as directory:
            root=Path(directory);raw=root/'raw/starvector--svg-diagrams';raw.mkdir(parents=True);(raw/'data.parquet').write_bytes(pickle.dumps(rows))
            args=argparse.Namespace(root=root,only=None,workers=1,timeout=1,max_side=1000,shard_rows=2,retry_failed=False,rebuild_native=False,drawio_renderer=Path('/unused/renderer.py'),runtime_cache=None)
            with contextlib.redirect_stdout(io.StringIO()):baseline.main_run(args)
            dbpath=root/'manifests/derived_state.sqlite';out=root/'derived/starvector--svg-diagrams'
            def states():
                with sqlite3.connect(dbpath) as db:return dict(db.execute('SELECT status,COUNT(*) FROM items GROUP BY status').fetchall())
            assert states()=={'accepted':6}
            calls=[]
            def upgraded(svg,code,*args):
                label=mark(code);calls.append(label)
                if label=='UPGRADE_OK':return successful(svg,code)
                if label=='FALLBACK_DUP':return {'ok':True,'native_selected':False,'png':b'\x89PNGduplicate','seconds':0,'native_fallback_reason':'blocked'}
                return {'ok':False,'reason':'native_drawio_render_failed','error':'fixture blocked'}
            globals()['selected_job']=upgraded;args.rebuild_native=True
            globals()['cache_context']=lambda *args:(None,NATIVE_RENDER_VERSION+'|cache:none')
            before=len(list(out.glob('pairs-*.parquet')))
            with contextlib.redirect_stdout(io.StringIO()):main_run(args)
            assert not calls and len(list(out.glob('pairs-*.parquet')))==before and states()=={'accepted':6}
            cache_path=root/'manifest-cache.json';cache_path.write_text('{}');key=NATIVE_RENDER_VERSION+'|cache:fixture-cache-A'
            globals()['cache_context']=lambda *args:(cache_path,key)
            with contextlib.redirect_stdout(io.StringIO()):main_run(args)
            assert sorted(calls)==['FAIL_NATIVE','FALLBACK_DUP','UPGRADE_OK'],calls
            assert states()=={'accepted':6} and len(list(out.glob('pairs-*.parquet')))==before+1
            with sqlite3.connect(dbpath) as db:
                assert dict(db.execute('SELECT format,COUNT(*) FROM items WHERE status="accepted" GROUP BY format'))=={'drawio':2,'svg':4}
                assert db.execute('SELECT COUNT(*) FROM render_versions WHERE version=?',(key,)).fetchone()[0]==4
            previous_calls=list(calls)
            with contextlib.redirect_stdout(io.StringIO()):main_run(args)
            assert calls==previous_calls and states()=={'accepted':6}
            with sqlite3.connect(dbpath) as db:assert db.execute('SELECT COUNT(*) FROM render_versions WHERE version=?',(key,)).fetchone()[0]==4
            # A new cache may reconsider previously failed candidates, while the
            # successful native pairs and ordinary SVG stay untouched.
            key=NATIVE_RENDER_VERSION+'|cache:fixture-cache-B'
            with contextlib.redirect_stdout(io.StringIO()):main_run(args)
            assert calls[len(previous_calls):]==['FAIL_NATIVE','FALLBACK_DUP'],calls
            assert states()=={'accepted':6}
            assert should_skip_prior(('accepted','svg'),None,True,True,key,True)
            assert should_skip_prior(('accepted','drawio'),NATIVE_RENDER_VERSION,True,True,key,True)
            assert not should_skip_prior(('accepted','drawio'),None,True,True,key,False)
    finally:
        globals()['cache_context']=old_context;globals()['selected_job']=old_selected
        if old_pa is None:sys.modules.pop('pyarrow',None)
        else:sys.modules['pyarrow']=old_pa
        if old_pq is None:sys.modules.pop('pyarrow.parquet',None)
        else:sys.modules['pyarrow.parquet']=old_pq
    print(json.dumps({'self_test':'passed','fixtures':['no cache preserves existing SVG/native','ordinary SVG never retried','valid v1 XML never retried','native fallback upgrades exactly once','failed upgrade keeps existing accepted SVG','no-use-native keeps accepted SVG','duplicate SVG fallback keeps accepted SVG','reconcile preserves cache review stamp','new cache permits bounded reconsideration','legacy XML remains eligible for rebuild']}),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path);p.add_argument('--self-test',action='store_true');p.add_argument('--only',nargs='*');p.add_argument('--workers',type=int,default=4);p.add_argument('--timeout',type=int,default=30);p.add_argument('--max-side',type=int,default=3072);p.add_argument('--shard-rows',type=int,default=512);p.add_argument('--retry-failed',action='store_true');p.add_argument('--rebuild-native',action='store_true',help='Re-render accepted legacy embedded-native rows once with the selected-code renderer');p.add_argument('--drawio-renderer',type=Path);p.add_argument('--runtime-cache',type=Path,help='Pinned task-local stencil cache manifest; default auto-detects v32.6.1');p.add_argument('--render-native-only',action='store_true');p.add_argument('--render-directory',type=Path);p.add_argument('--render-only',action='store_true');p.add_argument('--width',type=int);p.add_argument('--height',type=int);p.add_argument('--backend',choices=['cairosvg','chromium'],default='cairosvg');a=p.parse_args()
    if a.self_test:self_test()
    elif a.render_native_only:native_render_child(a)
    elif a.render_only:render_child(a.width,a.height,a.backend)
    elif a.root:main_run(a)
    else:p.error('--root required')

if __name__=='__main__':main()
