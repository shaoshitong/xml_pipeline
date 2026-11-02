"""Finite per-ID deterministic adapters. No canonical SQL writes, queues or models.

The caller supplies a private SQLite database containing exactly this job and an
owned work directory, and enforces a whole-process timeout. Existing candidates
are returned unchanged for the caller's full quality gate. Newly generated
payloads are stored in a fresh, immutable clean attempt directory.
"""
from contextlib import contextmanager
from pathlib import Path
import datetime
import hashlib
import io
import json
import mimetypes
import shutil
import sqlite3
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as ET

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
FORMATS = ('drawio', 'svg', 'html', 'python', 'plantuml', 'mermaid')
JOB_COLUMNS = ('id','category','format','source','input_record','state','route',
               'attempts','updated_at','output_record','error','input_manifest','worker_pid')
INITIAL_STATES = frozenset(('queued','queued_html_v3','python_source_rendered',
                          'source_rendered','svg_source_rendered',
                          'mermaid_source_rendered','plantuml_source_rendered'))
CHROME = '/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'


class AdapterFailure(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _job(value):
    if isinstance(value, dict):
        if not set(JOB_COLUMNS) <= set(value):
            raise AdapterFailure('invalid_full_job_snapshot')
        return {key:value[key] for key in JOB_COLUMNS}
    if len(value) != len(JOB_COLUMNS):
        raise AdapterFailure('invalid_full_job_snapshot')
    return dict(zip(JOB_COLUMNS,value))


def _check_private(database, identifier):
    database = Path(database).resolve(strict=True)
    if database == (W/'jobs.sqlite').resolve():
        raise AdapterFailure('canonical_database_is_not_private')
    with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True,timeout=10) as db:
        db.execute('pragma query_only=ON')
        if db.execute('select id from jobs').fetchall() != [(identifier,)]:
            raise AdapterFailure('private_database_must_contain_only_requested_id')


def _read(locator, digest):
    if not isinstance(locator,str) or not locator or Path(locator).is_absolute():
        raise AdapterFailure('invalid_relative_input_locator')
    path = (R/locator).resolve(strict=True)
    if not path.is_relative_to(R.resolve()):
        raise AdapterFailure('input_locator_outside_dataset')
    raw = path.read_bytes()
    if sha(raw) != digest:
        raise AdapterFailure('authoritative_input_hash_changed')
    return raw


def _write(path, raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    # Never overwrite an accepted or historical candidate.
    with path.open('xb') as stream:
        stream.write(raw)


@contextmanager
def _browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=CHROME,
                                             args=['--disable-dev-shm-usage'])
        try:
            yield browser
        finally:
            browser.close()


def _svg(browser, svg, width, height, dom_script='svg_dom.js'):
    context = browser.new_context(java_script_enabled=False,
                                  viewport={'width':width,'height':height},
                                  service_workers='block')
    blocked=[]
    try:
        context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()))
        page=context.new_page();page.set_default_timeout(45000)
        page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode())
        page.evaluate('''([w,h])=>{const s=document.querySelector('svg');if(!s)throw Error('missing_svg');
          if(!s.viewBox.baseVal.width)s.setAttribute('viewBox',`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);
          s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''',[width,height])
        page.evaluate('document.fonts.ready')
        source_png=page.screenshot()
        dom=page.evaluate((W/'scripts'/dom_script).read_text())
        return dom,source_png,blocked
    finally:
        context.close()


def _render(xml,width,height):
    from native_worker import native
    result=native.native_job(xml,width,height,120,W/'rendering_fonts/remote_render.py',
                             8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not result.get('ok'):
        raise AdapterFailure('native_render_failed:'+json.dumps({k:v for k,v in result.items() if k!='png'})[:1800])
    return result['png'],result['native_render']


def _html(browser,code,manifest,width,height):
    from html_batch_v3 import convert
    from rendered_fonts import resolve_fonts
    assets=manifest.get('asset_root')
    asset_root=(R/assets).resolve(strict=True) if assets else None
    if asset_root and not asset_root.is_relative_to(R.resolve()):
        raise AdapterFailure('html_asset_root_outside_dataset')
    served={};blocked=[]
    context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block')
    try:
        def route(request):
            parsed=urllib.parse.urlparse(request.request.url)
            if parsed.hostname!='source.invalid':
                blocked.append(request.request.url);request.abort();return
            relative=urllib.parse.unquote(parsed.path.lstrip('/'))
            if relative=='index.html':request.fulfill(body=code,content_type='text/html');return
            target=(asset_root/relative).resolve() if asset_root else None
            if target is None or not target.is_relative_to(asset_root) or not target.is_file():
                blocked.append(request.request.url);request.abort();return
            served[request.request.url]=target
            request.fulfill(body=target.read_bytes(),content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
        context.route('**/*',route);page=context.new_page();page.set_default_timeout(45000)
        page.goto('http://source.invalid/index.html',wait_until='networkidle')
        page.evaluate('document.fonts.ready');source_png=page.screenshot()
        dom=page.evaluate((W/'scripts/html_dom_v3.js').read_text())
        fonts=resolve_fonts(page,dom);xml,assets=convert(dom,served,width,height)
        return xml,{'unsupported_features':dom['unsupported'],'blocked_source_resources':blocked,
                    'source_assets':assets,'rendered_font_mapping':fonts,
                    'original_asset_root':manifest.get('asset_root')},source_png
    finally:
        context.close()


def _python(job,source,manifest,code,work,private_db):
    # A previous successful source capture can be consumed without re-executing.
    execution=None
    if job['state']=='python_source_rendered':
        with sqlite3.connect('file:'+str(Path(private_db).resolve())+'?mode=ro',uri=True) as db:
            row=db.execute('select record from python_renders where id=? and state=?',
                           (job['id'],'python_source_rendered')).fetchone()
        if row and row[0]:execution=json.loads(row[0])
    if execution is None:
        from sandbox_runner import run,PYTHON
        if manifest.get('panel_assets'):
            raise AdapterFailure('python_asset_manifest_not_supported_by_fixed_adapter')
        capture=work/'python_capture';capture.mkdir(exist_ok=False)
        _write(capture/'source.py',code)
        _write(capture/'capture.py',(W/'scripts/python_capture.py').read_bytes())
        if manifest.get('source_data'):
            _write(capture/'data.json',_read(manifest['source_data'],manifest['source_data_sha256']))
        extra=[(p,p) for p in [W/'runtime/graphviz',W/'runtime/python_packages'] if p.exists()]
        process=run(capture,[PYTHON,'-I','/work/capture.py'],timeout=150,extra_ro=extra)
        _write(capture/'stdout.log',process.stdout.encode());_write(capture/'stderr.log',process.stderr.encode())
        meta=json.loads((capture/'execution.json').read_text()) if (capture/'execution.json').exists() else {}
        if process.returncode or not meta.get('ok'):
            raise AdapterFailure('python_source_execution_failed:'+str(meta or process.stderr[-2000:]))
        captures=[]
        for entry in meta.get('captures',[]):
            path=(capture/entry['svg']).resolve(strict=True)
            if not path.is_relative_to(capture.resolve()):raise AdapterFailure('python_capture_path_escape')
            captures.append({**entry,'svg_file':str(path.relative_to(R)), 'svg_sha256':sha(path.read_bytes())})
        execution={'id':job['id'],'source_code_sha256':source['code_sha256'],
                   'captures':captures,'figures':len(captures),'execution':meta}
    if execution.get('id')!=job['id'] or execution.get('source_code_sha256')!=source['code_sha256']:
        raise AdapterFailure('python_capture_source_identity_mismatch')
    if execution.get('figures')!=1 or len(execution.get('captures',[]))!=1:
        raise AdapterFailure('multiple_or_missing_python_figures')
    entry=execution['captures'][0]
    return _read(entry['svg_file'],entry['svg_sha256']),execution,entry


def _plantuml(browser,code,work,width,height):
    from plantuml_runtime import run,JAR_SHA
    from plantuml_fonts import resolve
    from plantuml_native import build
    from svg_source_coverage_v2 import audit
    svg=run(work,code,'svg');source_png=run(work,code,'png')
    context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block')
    blocked=[]
    try:
        context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()))
        page=context.new_page();page.set_default_timeout(45000)
        page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode())
        page.evaluate('''([w,h])=>{let s=document.querySelector('svg');s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''',[width,height])
        fonts=resolve(page,work);page.evaluate('document.fonts.ready')
        metadata=page.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text())
        dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text())
        if not metadata.get('groups'):raise AdapterFailure('plantuml_entity_graph_not_supported')
        xml,stats=build(dom,width,height,metadata);stats['source_coverage']=audit(dom,xml,stats)
        stats['physical_font_resolution']=fonts
        return xml,svg,source_png,{'svg_conversion':stats,'blocked_source_resources':blocked,
            'plantuml_runtime':{'version':'1.2025.7','jar_sha256':JAR_SHA,'network_disabled':True,
                                'security_profile':'SANDBOX','font_resolution':fonts}}
    finally:
        context.close()


def _mermaid(browser,code,width,height):
    # Keep one fixed, uniform full-viewBox projection. The historical helper
    # stretches axes independently and can turn a supported arrow into an
    # unsupported contour before the source marker audit even runs.
    from mermaid_geometry_batch import BUNDLE,BUNDLE_SHA
    from mermaid_semantic_audit import PARSE
    from mermaid_native_v2 import build
    from mermaid_geometry_coverage import check
    from svg_source_coverage_v2 import audit
    if sha(BUNDLE.read_bytes())!=BUNDLE_SHA:raise AdapterFailure('mermaid_bundle_changed')
    context=browser.new_context(viewport={'width':width,'height':height},service_workers='block')
    blocked=[]
    try:
        context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()))
        page=context.new_page();page.set_default_timeout(45000)
        page.set_content('<html><body></body></html>');page.add_script_tag(path=str(BUNDLE))
        svg=page.evaluate('''async code=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:2000000,flowchart:{htmlLabels:true}});return (await mermaid.render('diagram',code)).svg;}''',code.decode())
        ast=page.evaluate(PARSE,code.decode())
        page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg)
        page.evaluate('''([w,h])=>{const s=document.querySelector('svg');s.style.maxWidth='none';s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);s.setAttribute('preserveAspectRatio','xMidYMid meet');}''',[width,height])
        page.evaluate('document.fonts.ready');source_png=page.screenshot()
        metadata=page.evaluate((W/'scripts/mermaid_dom_adapter_v1.js').read_text(),ast)
        dom=page.evaluate((W/'scripts/svg_dom_mermaid_v2.js').read_text())
        xml,stats,processed=build(dom,width,height,metadata)
        coverage=audit(processed,xml,stats);semantics=check(ast,xml,metadata)
        if not coverage['ok'] or not semantics['ok']:
            raise AdapterFailure('mermaid_source_coverage_failed:'+json.dumps({'coverage':coverage,'semantics':semantics})[:2000])
        stats['source_coverage']=coverage;stats['source_ast_validation']=semantics
        renderer={'version':'10.9.1','bundle_sha256':BUNDLE_SHA,'font_override':None,
                  'projection':'fixed_full_viewbox_xMidYMid_meet_v1'}
        stats['source_renderer']=renderer
        svg=page.locator('svg').evaluate('s=>s.outerHTML').encode()
        return xml,svg,source_png,{'svg_conversion':stats,'source_renderer':renderer,
            'blocked_source_resources':blocked,'_source_ast':ast}
    finally:
        context.close()


def _generate(job,source,manifest,code,reference,width,height,work,private_db,dest):
    fmt=job['format'];extra={};source_svg=None;source_png=None
    if fmt=='drawio':
        from native_worker import normalize
        xml,pages,_=normalize(code.decode());extra.update(source_page_count=pages,selected_source_page=0)
    else:
        with _browser() as browser:
            if fmt=='html':
                prepared={**manifest,'asset_root':manifest.get('asset_root') or source.get('asset_root')}
                xml,extra,source_png=_html(browser,code,prepared,width,height)
            elif fmt=='mermaid':
                xml,source_svg,source_png,extra=_mermaid(browser,code,width,height)
                ast=extra.pop('_source_ast')
                _write(dest/'source_ast.json',(json.dumps(ast,ensure_ascii=False,indent=2)+'\n').encode())
                extra['source_ast_file']=str((dest/'source_ast.json').relative_to(R))
            elif fmt=='plantuml':
                xml,source_svg,source_png,extra=_plantuml(browser,code,work,width,height)
            else:
                if fmt=='python':
                    source_svg,execution,entry=_python(job,source,manifest,code,work,private_db)
                    extra.update(execution=execution,execution_success=execution['execution']['ok'],capture_count=1)
                    if manifest.get('source_data'):
                        aux=_read(manifest['source_data'],manifest['source_data_sha256'])
                        _write(dest/'original_data.json',aux)
                        extra.update(original_source_data=str((dest/'original_data.json').relative_to(R)),
                                     source_data_sha256=sha(aux),source_data_locator=manifest.get('source_data_locator'))
                    if entry.get('dot'):
                        original=(R/entry['svg_file']).parent/entry['dot']
                        if original.is_file():
                            _write(dest/'source_render.dot',original.read_bytes())
                            extra['source_render_dot']=str((dest/'source_render.dot').relative_to(R))
                else:source_svg=code
                from svg_convert_v2 import build
                dom,source_png,blocked=_svg(browser,source_svg,width,height)
                xml,stats=build(dom,width,height)
                extra.update(svg_conversion=stats,blocked_source_resources=blocked)
    png,render=_render(xml,width,height)
    files={'code_file':('diagram.drawio',xml.encode()),'image_file':('image.png',png),
           'original_source_code':('original_source.'+fmt,code),
           'original_reference':('original_image.bin',reference)}
    if source_svg is not None:files['source_render_svg']=('source_render.svg',source_svg)
    if source_png is not None:files['source_render_png']=('source_render.png',source_png)
    cells=list(ET.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'}
    edges=[c for c in cells if c.get('edge')=='1']
    if not vertices:raise AdapterFailure('no_editable_vertices')
    record={'id':job['id'],'source_pair_sha256':job['id'],'source':source['source'],
        'category':source['category'],'source_format':fmt,'source_record':source,
        'source_image_sha256':source['image_sha256'],'source_code_sha256':source['code_sha256'],
        'format':'drawio','conversion_method':'fixed_finite_'+fmt+'_native_candidate_v1',
        'model':None,'vertices':len(vertices),'edges':len(edges),
        'bound_edges':sum(c.get('source') in vertices and c.get('target') in vertices for c in edges),
        'render':render,'quality_state':'pending_full_program_quality_validation',
        'converted_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**extra}
    for field,(name,raw) in files.items():
        _write(dest/name,raw);record[field]=str((dest/name).relative_to(R))
        if field=='code_file':record['code_sha256']=sha(raw)
        elif field=='image_file':record['image_sha256']=sha(raw)
        elif field.startswith('source_render_'):record[field+'_sha256']=sha(raw)
    return record


def convert(job_tuple,private_db_path,work):
    """Return an existing/new candidate or a typed finite failure; never accept it."""
    started=time.monotonic();job=None
    try:
        job=_job(job_tuple)
        if job['format'] not in FORMATS:raise AdapterFailure('unsupported_adapter_format')
        _check_private(private_db_path,job['id'])
        source=json.loads(job['input_record'])
        if source.get('format')!=job['format'] or source.get('category')!=job['category'] or source.get('source')!=job['source']:
            raise AdapterFailure('job_source_identity_mismatch')
        if job['output_record']:
            record=json.loads(job['output_record'])
            if (record.get('id'),record.get('source_pair_sha256'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(job['id'],job['id'],source['code_sha256'],source['image_sha256']):
                raise AdapterFailure('existing_candidate_identity_mismatch')
            return {'ok':True,'record':record,'existing_candidate':True,'model_calls':0}
        if job['state'] not in INITIAL_STATES:raise AdapterFailure('historical_failure_requires_recorded_skip')
        if job['worker_pid'] is not None:raise AdapterFailure('job_is_owned_by_another_worker')
        if not job['input_manifest']:raise AdapterFailure('missing_prepared_input_manifest')
        manifest=json.loads(job['input_manifest']);code=_read(manifest['source_code'],source['code_sha256'])
        reference=_read(manifest['reference_image'],source['image_sha256'])
        if (manifest.get('code_sha256'),manifest.get('image_sha256'))!=(source['code_sha256'],source['image_sha256']):
            raise AdapterFailure('prepared_manifest_identity_mismatch')
        from PIL import Image
        width,height=Image.open(io.BytesIO(reference)).size
        if max(width,height)>8192 or width*height>64000000:raise AdapterFailure('reference_canvas_exceeds_fixed_limits')
        work=Path(work).resolve(strict=True)
        if not work.is_relative_to(W.resolve()):raise AdapterFailure('attempt_work_outside_owned_conversion_root')
        # A random attempt component prevents concurrent or restarted writes to
        # this ID from overwriting an older payload, even when a child times out.
        dest=R/'clean/fixed_batch_candidates_v1'/job['id'][:2]/job['id']/uuid.uuid4().hex
        dest.mkdir(parents=True,exist_ok=False)
        record=_generate(job,source,manifest,code,reference,width,height,work,private_db_path,dest)
        _write(dest/'conversion.json',(json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode())
        return {'ok':True,'record':record,'existing_candidate':False,'model_calls':0,
                'seconds':time.monotonic()-started,'candidate_directory':str(dest.relative_to(R))}
    except Exception as error:
        return {'ok':False,'id':job.get('id') if job else None,
                'reason':str(error).split(':',1)[0] if isinstance(error,AdapterFailure) else 'adapter_runtime_failure',
                'error_type':type(error).__name__,'error':str(error)[:3000],
                'model_calls':0,'seconds':time.monotonic()-started}
