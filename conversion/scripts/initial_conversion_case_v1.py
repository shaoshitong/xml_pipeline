"""One isolated offline initial-conversion case; never opens the jobs database.

Only cached TeX compilation or the existing PDF->native pure conversion chain.
It writes owned proposal artifacts. The supervising process owns admission,
process deadlines, publication CAS and any future clean metadata publication.
"""
import argparse
import collections
import datetime
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
OWNER='conversion/initial_conversion_supervisor_v1'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


class Deferred(RuntimeError):
    def __init__(self,reason,details=None):super().__init__(reason);self.reason=reason;self.details=details


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def entry(path):
    return {'file':str(path.relative_to(R)),'sha256':sha(path.read_bytes())}


def inputs(request,work):
    source=request['source'];manifest=request['manifest'];identifier=request['id']
    if (source['format']!='tikz' or manifest['source_format']!='tikz' or source['pair_sha256']!=identifier
            or manifest['id']!=identifier or any(source[key]!=manifest[key] for key in ['code_sha256','image_sha256'])):
        raise Deferred('authoritative_source_identity_mismatch')
    blobs=[]
    for field,digest in [('source_code','code_sha256'),('reference_image','image_sha256')]:
        path=(R/manifest[field]).resolve()
        if not path.is_relative_to(R.resolve()):raise Deferred('source_path_outside_registered_root')
        raw=path.read_bytes()
        if sha(raw)!=source[digest]:raise Deferred('source_file_hash_mismatch',field)
        blobs.append(raw)
    code,reference=blobs
    from PIL import Image
    image=Image.open(io.BytesIO(reference));size=image.size
    if list(size)!=[manifest['width'],manifest['height']]:raise Deferred('reference_header_dimensions_mismatch')
    (work/'source.tex').write_bytes(code);(work/'reference.bin').write_bytes(reference)
    return code,reference,size,image.format.lower()


def compile_case(request,work):
    code,reference,_,_=inputs(request,work);manifest=request['manifest']
    if manifest.get('panel_assets'):raise Deferred('asset_mapping_requires_larger_tier')
    # No tectonic_compile.fetch/compile_case: those can fetch shared dependencies.
    from sandbox_runner import command
    runtime=W/'runtime/tectonic';cache=runtime/'cache';env={'XDG_CACHE_HOME':str(cache),'TECTONIC_CACHE_DIR':str(cache)}
    argv=[str(runtime/'tectonic'),'--untrusted','--only-cached','--keep-logs','--keep-intermediates','/work/source.tex']
    cmd=command(work,argv,[(runtime,runtime)],env)
    # prlimit avoids a Python preexec_fn in any process importing threaded libs.
    prlimit=Path('/usr/bin/prlimit')
    if not prlimit.is_file():raise Deferred('missing_prlimit_runtime')
    cmd=[str(prlimit),'--cpu=90:100','--as='+str(8*1024**3),'--fsize='+str(512*1024**2),'--nofile=512:512','--']+cmd
    started=time.monotonic();completed=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=request['phase_timeout_seconds'])
    (work/'stdout.log').write_text(completed.stdout);(work/'stderr.log').write_text(completed.stderr)
    compile_record={'returncode':completed.returncode,'seconds':time.monotonic()-started,'cache_only':True,'dependency_fetch_allowed':False,'command':cmd}
    write_json(work/'compile.json',compile_record)
    if completed.returncode!=0:
        text=completed.stdout+'\n'+completed.stderr
        names=sorted(set(re.findall(r"File [`']([A-Za-z0-9_.-]+)' not found",text)))
        reason='missing_cached_dependencies' if names or 'not found' in text or 'not loadable' in text else 'cached_compiler_failure'
        raise Deferred(reason,{'returncode':completed.returncode,'missing_dependency_names':names[:100]})
    pdf=work/'source.pdf'
    if not pdf.is_file():raise Deferred('cached_compiler_missing_pdf')
    sys.path.append(str(W/'runtime/python_packages'));import pymupdf
    doc=pymupdf.open(pdf);captures=[]
    try:
        if not len(doc):raise Deferred('empty_compiled_pdf')
        for index,page in enumerate(doc):
            svg=work/('page'+str(index)+'.svg');svg.write_text(page.get_svg_image(text_as_path=False));text=page.get_text();paths=page.get_drawings()
            if not text.strip() and not paths:raise Deferred('blank_compiled_pdf_page')
            write_json(work/('page'+str(index)+'_text.json'),page.get_text('dict'))
            png=work/('page'+str(index)+'.png');page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).save(png)
            captures.append({'page':index,'width_pt':page.rect.width,'height_pt':page.rect.height,'text_characters':len(text),'drawing_paths':len(paths),
                'svg_file':str(svg.relative_to(R)),'svg_sha256':sha(svg.read_bytes()),'pdf_render_png':str(png.relative_to(R)),'pdf_render_png_sha256':sha(png.read_bytes())})
        result={'id':request['id'],'source':request['source']['source'],'source_code_sha256':sha(code),'source_image_sha256':sha(reference),
            'directory':str(work.relative_to(R)),'pdf_file':str(pdf.relative_to(R)),'pdf_sha256':sha(pdf.read_bytes()),'captures':captures,'pages':len(doc),
            'compile_returncode':0,'compile_attempts':[{'round':0,'returncode':0,'cache_only':True}],'compile_warnings':[line for line in completed.stderr.splitlines() if 'warning' in line.lower()],
            'native_drawio_conversion_complete':False,'captured_at_utc':now(),'sandbox':'existing bwrap command, unshare-all, only-cached, explicit read-only runtime; prlimit and independent whole-case supervisor',
            'dependency_fetch_allowed':False,'model':None}
    finally:doc.close()
    write_json(work/'preparation.json',result)
    return {'state':'compile_ready','record':result,'record_file':entry(work/'preparation.json'),'artifacts':{name:entry(work/name) for name in ['source.tex','reference.bin','source.pdf','compile.json','stdout.log','stderr.log']}}


def require_native_canvas(png,info,width,height):
    from PIL import Image
    returned=list(Image.open(io.BytesIO(png)).size);expected=[width,height]
    if returned!=expected or info.get('output_size')!=expected or info.get('selected_image')!='declared_first_page' or info.get('content_outside_declared_canvas') is not False:
        reason=('native_outside_reference_canvas_requires_registered_recovery' if info.get('content_outside_declared_canvas') or info.get('selected_image')=='complete_tight_graph' else 'native_dimensions_require_larger_renderer_tier')
        raise Deferred(reason,{'original_reference_page':expected,'native_png_page':returned,'native_output_size':info.get('output_size'),'selected_image':info.get('selected_image'),'content_outside_declared_canvas':info.get('content_outside_declared_canvas'),'returned_png_sha256':sha(png)})


def native_case(request,work):
    code,data,(width,height),ext=inputs(request,work);execution=request['execution']
    if max(width,height)>request['max_side']:raise Deferred('larger_canvas_tier_required',{'page':[width,height],'tier_max_side':request['max_side']})
    if execution.get('source_code_sha256')!=request['source']['code_sha256']:raise Deferred('compiled_source_identity_mismatch')
    if execution['pages']!=1:raise Deferred('multi_page_source_requires_recovery_tier',{'pages':execution['pages']})
    pdf=(R/execution['pdf_file']).resolve()
    if not pdf.is_relative_to(R.resolve()) or sha(pdf.read_bytes())!=execution['pdf_sha256']:raise Deferred('compiled_pdf_hash_mismatch')
    (work/'source.pdf').write_bytes(pdf.read_bytes());sys.path.append(str(W/'runtime/python_packages'));import pymupdf
    from pdf_to_native import source_svg,attach_fonts
    from svg_convert_v2 import build
    from tikz_connectivity import bind
    from native_worker import native
    from svg_batch import metric
    from playwright.sync_api import sync_playwright
    doc=pymupdf.open(stream=(work/'source.pdf').read_bytes(),filetype='pdf')
    try:
        if len(doc)!=1:raise Deferred('actual_multi_page_source_requires_recovery_tier',{'pages':len(doc)})
        svg,fonts,pdfstats=source_svg(doc,doc[0],work)
    finally:doc.close()
    (work/'source_render.svg').write_text(svg);blocked=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
        try:
            context=browser.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block')
            context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=context.new_page();page.set_default_timeout(60000)
            page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg)
            page.evaluate('([w,h])=>{const s=document.querySelector("svg");s.style.width=w+"px";s.style.height=h+"px";s.setAttribute("width",w);s.setAttribute("height",h);}',[width,height]);page.evaluate('document.fonts.ready')
            source_png=page.screenshot();(work/'source_render.png').write_bytes(source_png);dom=page.evaluate((W/'scripts/svg_dom_pdf.js').read_text())
        finally:browser.close()
    write_json(work/'source_dom.json',dom);xml,stats=build(dom,width,height);xml=attach_fonts(xml,fonts);xml,connectivity=bind(xml,dom,code.decode())
    cells=list(E.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1']
    if not vertices or not (stats['counts'].get('text',0) or stats['counts'].get('vector_shapes',0)):raise Deferred('no_editable_native_vector_or_text')
    normalize=lambda value:unicodedata.normalize('NFKC',html.unescape(value))
    text_equal=collections.Counter(normalize(o['text']) for o in dom['objects'] if o['type']=='text')==collections.Counter(normalize(c.get('value')) for c in cells if c.get('value'))
    if not text_equal:raise Deferred('native_text_counter_differs_from_pdf_svg')
    rendered=native.native_job(xml,width,height,min(120,request['phase_timeout_seconds']),W/'rendering_fonts/remote_render.py',request['max_side'],R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    if not rendered['ok']:raise Deferred('native_renderer_runtime_failure',{k:v for k,v in rendered.items() if k!='png'})
    png=rendered.pop('png');(work/'candidate.drawio').write_text(xml);(work/'candidate.png').write_bytes(png);write_json(work/'native_render.json',rendered['native_render'])
    require_native_canvas(png,rendered['native_render'],width,height)
    loaded={f['family'] for f in rendered['native_render'].get('loaded_fonts',[]) if f['status']=='loaded'};used={o['fontFamily'].strip('"\'') for o in dom['objects'] if o['type']=='text'}
    if not used<=loaded:raise Deferred('native_embedded_font_not_loaded')
    dest=Path(request['proposed_clean_directory']);version=request['artifact_version'];name=lambda stem,ext:stem+'.initial-v1.'+version+'.'+ext;font_records=[]
    for font in fonts.values():
        path=Path(font['file']);blob=path.read_bytes()
        if sha(blob)!=font['sha256']:raise Deferred('extracted_native_font_hash_mismatch')
        font_records.append({**{k:v for k,v in font.items() if k not in ['uri','glyph_advances','file']},'file':str(dest/'fonts'/'initial_v1'/version/path.name),'proposal_artifact':str(path.relative_to(R))})
    record={'id':request['id'],'source_pair_sha256':request['id'],'source':request['source']['source'],'category':request['source']['category'],'source_format':'tikz','source_record':request['source'],
        'source_image_sha256':sha(data),'source_code_sha256':sha(code),'original_reference':str(dest/name('original_image',ext)),'original_source_code':str(dest/name('original_source','tex')),
        'source_render_pdf':str(dest/name('source_render','pdf')),'source_render_pdf_sha256':execution['pdf_sha256'],'source_render_svg':str(dest/name('source_render','svg')),'source_render_svg_sha256':sha(svg.encode()),
        'image_file':str(dest/name('image','png')),'code_file':str(dest/name('diagram','drawio')),'image_sha256':sha(png),'code_sha256':sha(xml.encode()),'format':'drawio',
        'conversion_method':'sandbox_tikz_pdf_to_native_vectors_unicode_embedded_fonts_and_source_connections_v1','model':None,'vertices':len(vertices),'edges':len(edges),
        'bound_edges':sum(edge.get('source') in vertices and edge.get('target') in vertices for edge in edges),'pdf_conversion':pdfstats,'svg_conversion':stats,'connectivity':connectivity,'fonts':font_records,
        'native_text_counter_equal':text_equal,'blocked_source_resources':blocked,'render':rendered['native_render'],
        'metrics':{'original_reference_ssim_512':metric(data,png),'original_source_render_ssim_512':metric(data,source_png),'source_render_vs_drawio_ssim_512':metric(source_png,png)},
        'execution_audit':str(Path(execution['directory'])/'preparation.json'),'compile_warnings':execution.get('compile_warnings',[]),'quality_state':'pending_source_semantic_and_visual_validation','converted_at_utc':now()}
    issues=pdfstats['issues']+stats['issues']+connectivity['issues'];issues+=([{'reason':'native_content_outside_source_canvas'}] if record['render']['content_outside_declared_canvas'] else []);issues+=([{'reason':'source_or_native_fidelity_below_review_threshold'}] if min(record['metrics'].values())<.9 else []);record['unresolved_issues']=issues
    artifact_map={record['code_file']:entry(work/'candidate.drawio'),record['image_file']:entry(work/'candidate.png'),record['original_source_code']:entry(work/'source.tex'),record['original_reference']:entry(work/'reference.bin'),record['source_render_pdf']:entry(work/'source.pdf'),record['source_render_svg']:entry(work/'source_render.svg')}
    for font in font_records:artifact_map[font['file']]={'file':font.pop('proposal_artifact'),'sha256':font['sha256']}
    write_json(work/'candidate_record.json',record)
    return {'state':'native_ready','record':record,'record_file':entry(work/'candidate_record.json'),'publish_files':artifact_map,'requires_quality_repair':bool(issues or blocked or not connectivity['complete'] or record['bound_edges']!=len(edges)),
        'artifacts':{name:entry(work/name) for name in ['source.tex','reference.bin','source.pdf','source_render.svg','source_render.png','source_dom.json','candidate.drawio','candidate.png','native_render.json']}}


def main(request_path):
    request_path=Path(request_path).resolve();work=request_path.parent
    if not work.is_relative_to((R/OWNER).resolve()):raise ValueError('Case workspace outside its owned root')
    request=json.loads(request_path.read_text());started=time.monotonic()
    try:
        for path,digest in request['pins'].items():
            if sha(Path(path).read_bytes())!=digest:raise Deferred('pinned_implementation_changed')
        result=compile_case(request,work) if request['stage']=='compile' else native_case(request,work)
        for path,digest in request['pins'].items():
            if sha(Path(path).read_bytes())!=digest:raise Deferred('pinned_implementation_changed')
        result.update(ok=True)
    except Deferred as exc:result={'ok':False,'state':'deferred_recovery_tier','reason':exc.reason,'details':exc.details}
    except subprocess.TimeoutExpired:result={'ok':False,'state':'deferred_recovery_tier','reason':'phase_subprocess_deadline'}
    except Exception as exc:
        import traceback
        (work/'traceback.txt').write_text(traceback.format_exc());result={'ok':False,'state':'deferred_recovery_tier','reason':'typed_runtime_exception','error_type':type(exc).__name__,'error':str(exc)[:2500]}
    result.update(id=request['id'],stage=request['stage'],code_sha256=request['source']['code_sha256'],image_sha256=request['source']['image_sha256'],stage_input_hash=request['stage_input_hash'],seconds=time.monotonic()-started,model_calls=0,accepted=False)
    write_json(work/'result.json',result)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('request');args=parser.parse_args();main(args.request)
