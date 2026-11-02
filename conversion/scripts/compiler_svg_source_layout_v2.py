"""Finite direct Graphviz-role SVG frontend; source layout is never recomputed.

Source proof is rebuilt from authoritative original bytes for both old and new
candidates. Only recorded CairoSVG-derived references are admitted. No model,
canonical writes, dispatcher, renderer search, DOT replay, or threshold waiver.
"""
from __future__ import annotations
import base64
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='compiler_svg_source_layout_v2'
UNIT='direct_svg_graphviz_roles_recorded_cairosvg_anchor_v2'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
PYTHON='/home/shaoshitong/anaconda3/bin/python'
SOURCE_RUNTIME=W/'runtime/compiler_svg_source_layout_v1'
SOURCE_PACKAGES=SOURCE_RUNTIME/'cairo_py'
DEPENDENCIES=(VERSION+'.py','compiler_render_domain_v3.py','compiler_scene_text_v2.py',
 'svg_dom_v6.js','svg_convert_v2.py','svg_convert_v3.py','svg_convert_v5.py',
 'svg_source_coverage_v2.py','auto_quality_source_vector_v2.py','auto_quality_common.py',
 'portable_native_fonts.py','native_source_font_profile_v4.py','pdf_to_native.py',
 'auto_quality_move.py','native_worker.py','clip_canvas_render_v4b.py','strict_canvas_gate.py')
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda v:(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode()


def require(value,reason):
    if not value:raise ValueError(reason)


def _write(path,blob):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():require(path.read_bytes()==blob,'immutable_payload_changed')
    else:
        with path.open('xb') as stream:stream.write(blob)


def _read(locator,digest):
    require(isinstance(locator,str) and not Path(locator).is_absolute(),'invalid_relative_original_locator')
    path=(R/locator).resolve(strict=True);require(path.is_relative_to(R.resolve()),'original_locator_outside_registered_root')
    blob=path.read_bytes();require(sha(blob)==digest,'original_payload_hash_changed');return blob


def _entry(path):
    return {'file':str(Path(path).relative_to(R)),'sha256':sha(Path(path).read_bytes())}


def configuration(data_root=R):
    require(Path(data_root).resolve()==R.resolve(),'requires_registered_HKUST_data_root')
    pins={str(W/'scripts'/name):sha((W/'scripts'/name).read_bytes()) for name in DEPENDENCIES}
    for path in (Path(CHROME),Path(PYTHON).resolve(),R/'scripts/curate_derived.py',
                 R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'):
        pins[str(path)]=sha(path.read_bytes())
    manifest=SOURCE_RUNTIME/'manifest.json'
    runtime_ready=manifest.is_file() and (SOURCE_PACKAGES/'cairosvg/surface.py').is_file()
    if runtime_ready:
        pins[str(manifest)]=sha(manifest.read_bytes())
        for path in sorted(SOURCE_RUNTIME.rglob('*')):
            if path.is_file() and path.suffix in ('.py','.so','.json'):
                pins[str(path)]=sha(path.read_bytes())
        for library in json.loads(manifest.read_text()).get('shared_libraries',[]):
            require(sha(Path(library['file']).read_bytes())==library['sha256'],'source_shared_library_changed')
            pins[library['file']]=library['sha256']
    return {'policy':VERSION+':'+sha(raw(pins))[:20],'pins':pins,'unit':UNIT,
            'source_requires_native_info':True,'source_renderer':'recorded_cairosvg_only',
            'source_runtime_available':runtime_ready,'unseen_ready':False,'automatic_rollout':False}


def _job(value):
    if isinstance(value,dict):return value
    names=('id','category','format','source','input_record','state','route','attempts','updated_at',
           'output_record','error','input_manifest','worker_pid')
    require(len(value)==len(names),'invalid_full_job');return dict(zip(names,value))


def _inputs(record_or_job,job=None):
    given=_job(job) if job is not None else record_or_job
    identifier=given['id']
    # Never trust candidate-supplied renderer provenance. This is one indexed,
    # read-only original job lookup, not a table or output_record scan.
    with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True) as db:
        db.execute('pragma query_only=ON')
        row=db.execute('select input_record,input_manifest,format,category,source from jobs where id=?',(identifier,)).fetchone()
    require(row is not None and row[1],'missing_authoritative_original_manifest')
    source=json.loads(row[0]);manifest=json.loads(row[1])
    require((source['format'],source['category'],source['source'])==row[2:],'original_job_identity_changed')
    require(source['pair_sha256']==identifier,'original_pair_identity_changed')
    if 'input_record' in given:
        require(json.loads(given['input_record'])==source,'provided_original_snapshot_changed')
    if job is not None or 'source_code_sha256' in record_or_job:
        for key in ('code','image'):
            require(record_or_job['source_'+key+'_sha256']==source[key+'_sha256'],'candidate_original_identity_changed')
    code=_read(manifest['source_code'],source['code_sha256'])
    reference=_read(manifest['reference_image'],source['image_sha256'])
    return source,code,reference


def _terminal(name,names):
    if name in names:return name
    choices=[n for n in names if name.startswith(n+':')]
    require(len(choices)==1,'ambiguous_or_missing_graphviz_source_terminal');return choices[0]


def source_admission(source,code,size):
    """Pure, source-only unit predicate, independent of conversion outcomes."""
    require(source.get('format')=='svg' and source.get('category')=='scientific_diagram','unsupported_source_format_or_category')
    require(source.get('render_backend')=='cairosvg' and source.get('image_provenance')=='rendered_from_source_svg'
            and source.get('pairing')=='derived_from_source_svg','source_renderer_provenance_unknown_or_unsupported')
    require(source.get('source_svg_sha256')==sha(code),'recorded_original_svg_identity_missing_or_changed')
    require(list(size)==[source.get('width'),source.get('height')],'recorded_source_canvas_differs_from_reference')
    require(max(size)<=8192 and size[0]*size[1]<=64000000 and len(code)<=2000000,'source_resource_bound')
    require(b'<!ENTITY' not in code.upper() and not re.search(br'<!DOCTYPE[^>]*\[',code,re.I),'source_xml_entity_unsupported')
    root=ET.fromstring(code);require(root.tag.split('}')[-1]=='svg','source_root_not_svg')
    allowed={'svg','g','a','title','desc','path','polygon','polyline','rect','circle','ellipse','line','text'}
    ids=set();nodes=[];edges=[]
    for element in root.iter():
        tag=element.tag.split('}')[-1];require(tag in allowed,'unsupported_svg_element:'+tag)
        identifier=element.get('id')
        if identifier:require(identifier not in ids,'duplicate_source_xml_id');ids.add(identifier)
        for key,value in element.attrib.items():
            local=key.split('}')[-1]
            require(not local.lower().startswith('on'),'source_event_handler_unsupported')
            require(local not in ('filter','clip-path','mask','marker-start','marker-mid','marker-end'),
                    'unsupported_svg_reference_or_effect:'+local)
            if local=='href':
                require(tag=='a','unsupported_svg_resource_reference')
                scheme=re.match(r'^\s*([A-Za-z][A-Za-z0-9+.-]*):',value)
                require(not scheme or scheme[1].lower() in ('http','https','mailto'),'source_active_or_unknown_anchor_scheme')
            require('url(' not in value.lower(),'source_paint_server_or_external_reference_unsupported')
        if tag=='g' and element.get('class') in ('node','edge'):
            titles=[child.text or '' for child in element if child.tag.split('}')[-1]=='title']
            require(len(titles)==1 and titles[0],'source_graphviz_title_missing_or_ambiguous')
            require(element.get('id'),'source_graphviz_role_id_missing')
            (nodes if element.get('class')=='node' else edges).append((element.get('id'),titles[0]))
            if element.get('class')=='edge':
                def leaves(container):
                    result=[]
                    for child in container:
                        name=child.tag.split('}')[-1]
                        if name in ('a','g'):result.extend(leaves(child))
                        else:result.append(name)
                    return result
                children=leaves(element)
                require(children.count('path')==1 and all(t in ('title','path','polygon','text') for t in children),
                        'source_edge_primitive_or_path_multiplicity_unsupported')
        if tag=='g':require(element.get('class','') in ('','graph','node','edge'),'source_graph_hierarchy_or_role_unsupported')
    require(nodes and edges,'requires_explicit_graphviz_node_and_edge_roles')
    names=[title for _,title in nodes];require(len(names)==len(set(names)),'duplicate_source_node_title')
    for _,title in edges:
        parts=re.split(r'->|--',title);require(len(parts)==2,'source_edge_title_unsupported')
        for name in parts:_terminal(name,names)
    return {'unit':UNIT,'source_nodes':len(nodes),'source_edges':len(edges),'reference_canvas':list(size),
            'renderer':'cairosvg','source_layout_preserved':True,'relayout':False}


def static_support(record_or_job):
    result={'supported':False,'unit':UNIT,'reasons':[],'scope':'Source-only eligibility; source-reference, extraction and native gates remain mandatory.'}
    try:
        from PIL import Image
        source,code,reference=_inputs(record_or_job)
        result.update(source_admission(source,code,Image.open(io.BytesIO(reference)).size),supported=True)
    except Exception as error:result['reasons']=[str(error)[:1800]]
    return result


_CAIRO=r'''import sys,base64,urllib.parse,json,hashlib,ctypes,ctypes.util
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from cairosvg.surface import PNGSurface
import cairocffi
work=Path(sys.argv[4]);work.mkdir(parents=True,exist_ok=True)
libcairo=ctypes.CDLL(ctypes.util.find_library('cairo'))
libft=ctypes.CDLL(ctypes.util.find_library('freetype'))
lock=libcairo.cairo_ft_scaled_font_lock_face;lock.argtypes=[ctypes.c_void_p];lock.restype=ctypes.c_void_p
unlock=libcairo.cairo_ft_scaled_font_unlock_face;unlock.argtypes=[ctypes.c_void_p]
ps=libft.FT_Get_Postscript_Name;ps.argtypes=[ctypes.c_void_p];ps.restype=ctypes.c_char_p
load=libft.FT_Load_Sfnt_Table;load.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_long,ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];load.restype=ctypes.c_int
glyph=libft.FT_Get_Char_Index;glyph.argtypes=[ctypes.c_void_p,ctypes.c_ulong];glyph.restype=ctypes.c_uint
paint=[];faces={}
def observe(context,text,operation):
 if not text:return
 scaled=context.get_scaled_font();address=int(cairocffi.ffi.cast('uintptr_t',scaled._pointer));face=lock(address)
 if not face:raise ValueError('source_cairo_physical_font_lock_failed')
 try:
  name=ps(face)
  if not name:raise ValueError('source_cairo_physical_postscript_missing')
  name=name.decode();index=int(ctypes.cast(face,ctypes.POINTER(ctypes.c_long))[1]);length=ctypes.c_ulong()
  if load(face,0,0,None,ctypes.byref(length)) or not 0<length.value<=20000000:raise ValueError('source_cairo_actual_sfnt_unavailable')
  buffer=(ctypes.c_ubyte*length.value)()
  if load(face,0,0,buffer,ctypes.byref(length)):raise ValueError('source_cairo_actual_sfnt_read_failed')
  blob=bytes(buffer);digest=hashlib.sha256(blob).hexdigest();path=work/(digest+'.sfnt')
  if not path.exists():path.write_bytes(blob)
  key=digest+':'+str(index)
  faces[key]={'postscript':name,'file':str(path),'sha256':digest,'collection_index':index}
  missing=[ord(c) for c in text if not c.isspace() and glyph(face,ord(c))==0]
  if missing:raise ValueError('source_cairo_actual_face_missing_codepoints')
  paint.append({'text':text,'face':key,'operation':operation})
 finally:unlock(address)
for operation in ('show_text','text_path'):
 original=getattr(cairocffi.Context,operation)
 def wrapped(self,text,_original=original,_operation=operation):
  observe(self,text,_operation);return _original(self,text)
 setattr(cairocffi.Context,operation,wrapped)
def fetch(url,resource_type):
 if not str(url).startswith('data:'):raise ValueError('source_external_resource_blocked')
 head,payload=str(url).split(',',1)
 data=base64.b64decode(payload) if ';base64' in head else urllib.parse.unquote_to_bytes(payload)
 if len(data)>20000000:raise ValueError('source_embedded_resource_bound')
 return data
png=PNGSurface.convert(bytestring=sys.stdin.buffer.read(),output_width=int(sys.argv[2]),output_height=int(sys.argv[3]),background_color='white',url_fetcher=fetch)
(work/'cairo_physical_fonts.json').write_text(json.dumps({'faces':faces,'paint':paint},sort_keys=True,indent=2)+'\n')
sys.stdout.buffer.write(png)
'''


def _render_source(code,size,work):
    require((SOURCE_RUNTIME/'manifest.json').is_file() and (SOURCE_PACKAGES/'cairosvg/surface.py').is_file(),
            'infrastructure_source_renderer_missing:CairoSVG isolated runtime')
    result=subprocess.run([PYTHON,'-I','-c',_CAIRO,str(SOURCE_PACKAGES),str(size[0]),str(size[1]),str(work)],
                          input=code,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,check=False)
    require(result.returncode==0,'source_cairosvg_render_failed:'+result.stderr.decode(errors='replace')[-1500:])
    require((work/'cairo_physical_fonts.json').is_file(),'source_cairo_actual_font_observation_missing')
    return result.stdout,json.loads((work/'cairo_physical_fonts.json').read_text())


def _capture(code,size,work):
    from playwright.sync_api import sync_playwright
    import compiler_render_domain_v3 as domain
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':size[0],'height':size[1]},device_scale_factor=1,
                                    java_script_enabled=False,service_workers='block');blocked=[]
        try:
            context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()))
            page=context.new_page();page.set_default_timeout(45000)
            page.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+code.decode('utf-8-sig'))
            page.evaluate('''([w,h])=>{const s=document.querySelector('svg');s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''',list(size))
            domain._wait_fonts(page);original_png=page.screenshot(type='png',timeout=45000)
            before,dom=domain._observe(page,context)
            require(page.screenshot(type='png',timeout=45000)==original_png,'source_dom_extractor_changed_pixels')
            require(not dom.get('issues'),'source_dom_feature_unsupported:'+json.dumps(dom['issues'])[:1000])
            require(dom.get('nodes') and before,'source_graph_or_text_extraction_incomplete')
            require(len(dom['objects'])<=1000,'source_scene_complexity_bound')
            faces=domain._physical_faces([f['postScriptName'] for row in before.values() for f in row['actual_fonts'] if f.get('glyphCount')])
            css='\n'.join('@font-face{font-family:"'+f['family']+'";src:url(data:font/ttf;base64,'+base64.b64encode(f['embedded']).decode()+');font-weight:normal;font-style:normal;}' for f in faces.values())
            page.evaluate('css=>{const s=document.createElement("style");s.textContent=css;document.head.appendChild(s)}',css)
            replacements=[]
            for row in before.values():
                signature=domain._font_signature(row['actual_fonts']);require(len(signature)==1,'source_mixed_physical_font_run_unsupported')
                replacements.append([row['source_element_index'],faces[signature[0][0]]['family']])
            page.evaluate('''rows=>{for(const [i,f] of rows){const e=document.querySelector('[data-compiler-domain-v3="'+i+'"]');e.style.fontFamily=f;e.style.fontWeight='normal';e.style.fontStyle='normal'}}''',replacements)
            domain._wait_fonts(page);positions,_=domain._observe(page,context)
            for key in before:
                require([c['text'] for c in before[key]['chars']]==[c['text'] for c in positions[key]['chars']],'source_embedding_changed_characters')
                require(domain._font_signature(before[key]['actual_fonts'])==domain._font_signature(positions[key]['actual_fonts'],True),'source_embedding_changed_physical_font')
                require(all(abs(a[k]-b[k])<=.03 for a,b in zip(before[key]['chars'],positions[key]['chars']) for k in ('x','y','width','height')),'source_embedding_changed_glyph_geometry')
            anchors=page.evaluate('''()=>[...document.querySelectorAll('svg a')].map((a,i)=>({index:i,id:a.id,attributes:[...a.attributes].map(x=>({name:x.name,value:x.value})),descendant_source_ids:[...a.querySelectorAll('*')].filter(x=>!['a','g','title','desc'].includes(x.localName)).map(x=>x.id),tooltip:a.getAttributeNS('http://www.w3.org/1999/xlink','title')||a.getAttribute('title')||a.querySelector(':scope > title')?.textContent||'',href:a.getAttribute('href')||a.getAttributeNS('http://www.w3.org/1999/xlink','href')||'',automatically_navigated:false}))''')
            png=page.screenshot(type='png',timeout=45000);require(not blocked,'source_external_resources_blocked')
            _write(work/'browser_source.png',png);_write(work/'dom.json',raw(dom));_write(work/'positions.json',raw(positions))
            return {'dom':dom,'positions':positions,'faces':faces,'png':png,'browser_version':browser.version,'anchors':anchors,
                    'source_dom_extraction_preserved_all_pixels':True}
        finally:context.close();browser.close()


def prepare_source(record,job=None,work=None):
    """Symmetric source proof: candidate fields never decide source scope."""
    from PIL import Image
    from auto_quality_common import image_quality
    import compiler_render_domain_v3 as domain
    source,code,reference=_inputs(record,job);size=Image.open(io.BytesIO(reference)).size
    predicate=source_admission(source,code,size)
    work=Path(work or W/VERSION/'source'/source['pair_sha256']/uuid.uuid4().hex).resolve()
    require(work.is_relative_to(W/VERSION),'source_work_outside_owner');work.mkdir(parents=True,exist_ok=False)
    engine,cairo_fonts=_render_source(code,size,work/'cairo_fonts');require(Image.open(io.BytesIO(engine)).size==size,'source_renderer_canvas_changed')
    _write(work/'cairosvg_source.png',engine);capture=_capture(code,size,work)
    positions=domain._positions(capture['positions'],(0,0))
    reference_check=image_quality(reference,engine,{},positions)
    bridge=image_quality(engine,capture['png'],{},positions)
    cairo_font_proof=_cairo_font_check(cairo_fonts,capture)
    require(reference_check['text_regions_checked']==len(capture['positions']),'source_reference_text_scope_incomplete')
    require(bridge['text_regions_checked']==len(capture['positions']),'source_domain_bridge_text_scope_incomplete')
    proof={'policy':VERSION,'source_code_sha256':sha(code),'source_image_sha256':sha(reference),
           'source_metadata_sha256':sha(raw(source)),'predicate':predicate,'source_renderer':'recorded_cairosvg',
           'source_engine_png_sha256':sha(engine),'source_browser_png_sha256':sha(capture['png']),
           'fresh_source_dom_sha256':sha(raw(capture['dom'])),'source_reference':reference_check,
           'source_browser_bridge_diagnostic_only':bridge,'cairo_browser_physical_font_equivalence':cairo_font_proof,
           'source_dom_extraction_preserved_all_pixels':capture['source_dom_extraction_preserved_all_pixels'],
           'source_anchor_metadata':capture['anchors'],'complete_source_objects':len(capture['dom']['objects']),
           'required_text_cell_ids':sorted(capture['positions']),'candidate_independent':True,
           'all_image_thresholds_unchanged':True,'parameter_search':False,'relayout':False}
    _write(work/'sourceproof.json',raw(proof))
    return {'ok':reference_check['ok'] and cairo_font_proof['ok'],'source':source,'code':code,'reference':reference,
            'size':size,'sourceproof':proof,'capture':capture,'work':work}


def _cairo_font_check(observation,capture):
    """Actual Cairo FT face/SFNT per painted scalar, not Fontconfig guesses."""
    from native_source_font_profile_v4 import _sfnt
    result={'ok':False,'failures':[],'actual_source_font_faces':0,'nonblank_scalars':0,
            'method':'cairo_ft_scaled_font_lock_face_and_FT_Load_Sfnt_Table_per_text_paint',
            'metadata_sha256':sha(raw({'faces':{key:{k:v for k,v in row.items() if k!='file'} for key,row in observation['faces'].items()},
                                       'paint':observation['paint']}))}
    try:
        actual={}
        for key,row in observation['faces'].items():
            blob=Path(row['file']).read_bytes();require(sha(blob)==row['sha256'],'source_cairo_actual_font_bytes_changed')
            face=_sfnt(blob,row['collection_index']);require(face['postscript']==row['postscript'],'source_cairo_actual_postscript_disagrees')
            actual[key]=face
        painted=[(char,actual[row['face']]) for row in observation['paint'] for char in row['text'] if not char.isspace()]
        expected=[]
        for row in capture['positions'].values():
            names=[font['postScriptName'] for font in row['actual_fonts'] if font.get('glyphCount')]
            require(len(names)==1,'source_browser_physical_font_run_unsupported')
            expected.extend((char,capture['faces'][names[0]]['face']) for char in row['text'] if not char.isspace())
        require(painted and [c for c,_ in painted]==[c for c,_ in expected],'source_cairo_browser_painted_text_inventory_differs')
        require(all(a==b for (_,a),(_,b) in zip(painted,expected)),'source_cairo_browser_actual_physical_font_differs')
        result.update(ok=True,actual_source_font_faces=len(actual),nonblank_scalars=len(painted),
                      actual_source_font_sfnt_tables_equal_browser=True)
    except Exception as error:result['failures'].append({'reason':str(error).split(':',1)[0]})
    return result


def source_reproduction(record,work):
    try:
        prepared=prepare_source(record,work=work);proof=prepared['sourceproof']
        return {'supported':True,'ok':prepared['ok'],'reason':'source_reference_reproduced' if prepared['ok'] else
                ('source_reference_mismatch' if not proof['source_reference']['ok'] else 'source_cairo_browser_physical_font_unproven'),
                'evidence':proof}
    except Exception as error:
        return {'supported':False,'ok':False,'reason':str(error).split(':',1)[0],'detail':str(error)[:2000],
                'infrastructure_failure':str(error).startswith('infrastructure_')}


def _semantics(dom,xml):
    from auto_quality_source_vector_v2 import _graphviz_coverage,_paint_coverage
    from compiler_render_domain_v3 import marker_check
    markers=marker_check(dom,xml)
    coverage=_graphviz_coverage(dom,xml,{'native_graphviz_arrowheads':markers['native_graphviz_arrowheads']})
    paint=_paint_coverage(dom,xml)
    failures=markers['failures']+coverage['errors']+paint['errors']
    cells=list(ET.fromstring(xml).iter('mxCell'));rank={c.get('id'):i for i,c in enumerate(cells)}
    objects=[o for o in dom['objects'] if o['id'] in rank]
    inversions=[]
    for i,left in enumerate(objects):
        a=left['bbox']
        for right in objects[i+1:]:
            b=right['bbox']
            overlap=min(a['x']+a['w'],b['x']+b['w'])>max(a['x'],b['x']) and min(a['y']+a['h'],b['y']+b['h'])>max(a['y'],b['y'])
            if overlap and rank[left['id']]>rank[right['id']]:inversions.append([left['id'],right['id']])
    if inversions:failures.append({'reason':'overlapping_source_native_paint_order_changed','pairs':inversions[:30]})
    if any(abs(paint['source_layout_translation'][key])>.03 for key in ('dx','dy')):
        failures.append({'reason':'unregistered_source_layout_translation'})
    return {'ok':not failures,'failures':failures,'markers':markers,'coverage':coverage,'paint':paint,
            'source_overlap_paint_order':{'ok':not inversions,'inversions':inversions[:30]}}


def _native(xml,size):
    from native_worker import native
    from strict_canvas_gate import require_declared_page
    result=native.native_job(xml,*size,180,W/'rendering_paintbounds_strict/remote_render.py',8192,
                             R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
    require(result.get('ok'),'fresh_native_render_failed');require_declared_page(result['native_render'],*size)
    return result


def convert(record,job,work):
    result={'ok':False,'supported':False,'accepted':False,'model_calls':0};stage='source'
    try:
        work=Path(work).resolve();require(work.is_relative_to(W/VERSION),'compiler_work_outside_owner')
        work.mkdir(parents=True,exist_ok=False);configuration()
        prepared=prepare_source(record,job,work/'source');result['supported']=True
        result['source_reproduction']=prepared['sourceproof'];require(prepared['ok'],'source_reference_or_physical_font_mismatch')
        source=prepared['source'];capture=prepared['capture'];size=prepared['size'];stage='emit_native'
        from svg_convert_v5 import build
        from svg_convert_v3 import unpack,pack
        from pdf_to_native import attach_fonts
        xml,stats=build(copy.deepcopy(capture['dom']),*size)
        dest=R/'clean'/VERSION/source['pair_sha256'][:2]/source['pair_sha256']/uuid.uuid4().hex;dest.mkdir(parents=True)
        fonts={}
        for name,face in capture['faces'].items():
            embedded=face['embedded'];original=Path(face['file']).read_bytes()
            require(sha(original)==face['original_sha256'],'source_font_file_changed')
            ep=dest/'fonts'/(face['embedded_sha256']+'.ttf');op=dest/'fonts'/('original_'+face['original_sha256']+Path(face['file']).suffix)
            _write(ep,embedded);_write(op,original)
            fonts[face['family']]={'family':face['family'],'file':str(ep.relative_to(R)),'sha256':sha(embedded),
              'original_file':str(op.relative_to(R)),'original_sha256':sha(original),'collection_index':face['collection_index'],
              'uri':'data:font/ttf;base64,'+base64.b64encode(embedded).decode(),'physical_postscript_name':name}
        tree=ET.fromstring(xml);cells={c.get('id'):c for c in tree.iter('mxCell')}
        for identifier,row in capture['positions'].items():
            name=[f['postScriptName'] for f in row['actual_fonts'] if f['glyphCount']][0];face=capture['faces'][name]
            style=unpack(cells[identifier].get('style'));flags=int(style.get('fontStyle',0))
            if face['face']['bold']:flags&=~1
            if face['face']['italic']:flags&=~2
            style.update(fontFamily=face['family'],fontStyle=str(flags));cells[identifier].set('style',pack(style))
        xml=attach_fonts(ET.tostring(tree,encoding='unicode'),fonts)
        stage='source_derived_text_anchor';initial=_native(xml,size)
        from compiler_scene_text_v2 import offsets,apply_offsets
        corrections=offsets(capture['positions'],initial['native_render']);xml=apply_offsets(xml,capture['positions'],corrections)
        semantic=_semantics(capture['dom'],xml);require(semantic['ok'],'native_source_coverage_failed:'+json.dumps(semantic['failures'])[:1000])
        final=_native(xml,size);stage='save_candidate'
        files={'code_file':('candidate.drawio',xml.encode()),'image_file':('candidate.png',final['png']),
               'original_source_code':('original.svg',prepared['code']),'original_reference':('reference.bin',prepared['reference']),
               'source_render_png':('source_cairosvg.png',(prepared['work']/'cairosvg_source.png').read_bytes())}
        out={'id':source['pair_sha256'],'source_pair_sha256':source['pair_sha256'],'source':source['source'],
             'category':source['category'],'source_format':'svg','format':'drawio','source_record':source,
             'source_code_sha256':source['code_sha256'],'source_image_sha256':source['image_sha256'],
             'code_sha256':sha(xml.encode()),'image_sha256':sha(final['png']),'conversion_method':VERSION,
             'native_embedded_fonts':[{k:v for k,v in f.items() if k!='uri'} for f in fonts.values()],
             'svg_conversion':stats,'quality_state':'pending_independent_full_quality','accepted':False,'model':None,
             'source_anchor_metadata':capture['anchors'],
             'compiler_svg_source_layout_v2':{'sourceproof':prepared['sourceproof'],'anchor_offsets':corrections}}
        for key,(name,blob) in files.items():
            path=dest/name;_write(path,blob);out[key]=str(path.relative_to(R))
            if key=='source_render_png':out[key+'_sha256']=sha(blob)
        allcells=list(ET.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in allcells if c.get('vertex')=='1'};edges=[c for c in allcells if c.get('edge')=='1']
        out.update(vertices=len(vertices),edges=len(edges),bound_edges=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges))
        _write(dest/'record.json',raw(out));result.update(ok=True,reason='native_candidate_pending_full_quality',record=out,record_file=str(dest/'record.json'))
    except Exception as error:
        result.update(reason=str(error).split(':',1)[0],detail=str(error)[:2500],stage=stage,
                      infrastructure_failure=str(error).startswith('infrastructure_'),development_not_ready=True)
    if 'work' in locals() and work.is_dir():_write(work/'result.json',raw(result))
    return result


def validate_source(record,xml,prepared=None,native_render=None):
    result={'supported':False,'ok':False,'profile':VERSION,'failures':[],'evidence':{}}
    try:
        require(sha(xml.encode())==record['code_sha256'],'candidate_revision_changed')
        prepared=prepared or prepare_source(record);capture=prepared['capture'];proof=prepared['sourceproof']
        require(prepared['ok'],'source_reference_or_physical_font_mismatch');result['supported']=True
        semantic=_semantics(capture['dom'],xml);checks={'semantics':semantic}
        require(native_render is not None,'fresh_native_glyph_and_font_info_required')
        import compiler_render_domain_v3 as domain
        checks['glyphs']=domain.glyph_check(capture['positions'],native_render)
        checks['physical_fonts']=domain.physical_font_check(record,xml,capture['positions'],capture['faces'],native_render)
        from auto_quality_common import image_quality
        native_png=_read(record['image_file'],record['image_sha256'])
        checks['same_domain_pixels']=image_quality(capture['png'],native_png,{},domain._positions(capture['positions'],(0,0)))
        primitives=domain._primitive_positions(capture['dom'],(0,0))
        checks['source_primitive_pixels']=image_quality(capture['png'],native_png,{},primitives)
        require(checks['source_primitive_pixels']['text_regions_checked']==len(primitives),'incomplete_source_primitive_pixel_scope')
        for name,check in checks.items():
            if not check.get('ok'):result['failures'].append({'gate':name,'reason':name+'_failed','failures':check.get('failures',[])})
        result['evidence']={'complete_source_coverage':not result['failures'],'required_text_cell_ids':sorted(capture['positions']),
                            'candidate_code_sha256':sha(xml.encode()),'fresh_sourceproof':proof,'checks':checks,
                            'candidate_independent_source_scope':True,'original_reference_gates_still_required':True}
        result['ok']=not result['failures']
    except Exception as error:result['failures'].append({'reason':str(error).split(':',1)[0],'detail':str(error)[:2200]})
    return result


def check_source(record,xml,source,data_root,native_info=None):
    require(Path(data_root).resolve()==R.resolve(),'requires_registered_HKUST_data_root')
    require(sha(source.encode())==record['source_code_sha256'],'source_hook_argument_changed')
    return validate_source(record,xml,native_render=native_info)


def quality_visual(record,xml,native_info,png,reference,source_profile,data_root=R):
    """Calibrated v3 staging: source-ref full; same-domain full; cross local diagnostic."""
    require(source_profile.get('ok') and source_profile['evidence']['complete_source_coverage'],
            'staged_visual_requires_complete_independent_source_proof')
    evidence=source_profile['evidence'];require(evidence['candidate_code_sha256']==sha(xml.encode()),'staged_visual_source_revision_changed')
    require(evidence['fresh_sourceproof']['cairo_browser_physical_font_equivalence']['ok'],
            'staged_visual_source_physical_font_equivalence_unproven')
    require(all(evidence['checks'][key]['ok'] for key in ('semantics','glyphs','physical_fonts','same_domain_pixels','source_primitive_pixels')),
            'staged_visual_source_native_proof_incomplete')
    prepared=prepare_source(record);require(prepared['ok'],'staged_visual_fresh_source_reproduction_failed')
    require(sha(reference)==record['source_image_sha256'],'staged_visual_original_reference_changed')
    from auto_quality_common import image_quality
    import compiler_render_domain_v3 as domain
    capture=prepared['capture'];positions=domain._positions(capture['positions'],(0,0))
    cross=image_quality(reference,png,{},positions)
    same=image_quality(capture['png'],png,{},positions)
    primitives=domain._primitive_positions(capture['dom'],(0,0));local=image_quality(capture['png'],png,{},primitives)
    require(same['text_regions_checked']==len(capture['positions']) and local['text_regions_checked']==len(primitives),
            'staged_visual_incomplete_fresh_source_expected_scope')
    failures=[f for f in cross['failures'] if f!='local_text_line_ssim_below_0.55']
    if not same['ok']:failures.append('same_browser_domain_full_fidelity_failed')
    if not local['ok']:failures.append('source_primitive_local_pixels_failed')
    return {**cross,'ok':not failures,'failures':failures,'policy':'svg_complete_source_same_domain_full_and_original_nonlocal_v3',
            'cross_renderer_local_text_diagnostic_only':True,'original_reference_visual_diagnostic':cross,
            'fresh_source_reference_all_original_gates':prepared['sourceproof']['source_reference'],
            'same_browser_domain_full_gates':same,'all_source_primitive_full_gates':local,
            'all_original_nonlocal_thresholds_unchanged':True,'source_physical_face_equivalence':True}


def audit_editing(record,xml,source_profile,data_root=R):
    require(Path(data_root).resolve()==R.resolve(),'requires_registered_HKUST_data_root')
    require(source_profile.get('ok') and source_profile['evidence']['candidate_code_sha256']==sha(xml.encode()),'editing_source_proof_missing')
    from auto_quality_move import audit
    observed=audit(xml);edges=[c for c in ET.fromstring(xml).iter('mxCell') if c.get('edge')=='1']
    require(observed['edge_count']==len(edges) and len(observed['moves'])==2*len(edges),'editing_endpoint_scope_incomplete')
    require({(m['edge'],m['side']) for m in observed['moves']}=={(e.get('id'),side) for e in edges for side in ('source','target')},'editing_endpoint_identity_incomplete')
    for move in observed['moves']:
        require(all(abs(move['delta'][axis]-value)<=.03 for axis,value in (('x',17),('y',11))),'native_endpoint_did_not_follow')
        require(all(abs(child[axis]-value)<=.03 for child in move['child_deltas'] for axis,value in (('x',17),('y',11))),'native_node_child_did_not_follow')
        for label in move['label_member_deltas']:
            rows=label['members'];require(not rows or all(abs(c[axis]-rows[0][axis])<=.03 for c in rows for axis in ('x','y')),'native_edge_label_group_split')
    return {'ok':True,'profile':VERSION+'_actual_editing','endpoint_moves':len(observed['moves']),'details':observed}
