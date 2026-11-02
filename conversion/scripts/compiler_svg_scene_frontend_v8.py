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
# Reuse frozen research helpers without shadowing the production common modules.
if str(W/'prototype') not in sys.path:sys.path.append(str(W/'prototype'))
VERSION='compiler_svg_scene_frontend_v8'
UNIT='general_svg_source_scene_analytic_endpoints_native_curve_nested_groups_v8'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
PYTHON='/home/shaoshitong/anaconda3/bin/python'
SOURCE_RUNTIME=W/'runtime/compiler_svg_source_layout_v1'
SOURCE_PACKAGES=SOURCE_RUNTIME/'cairo_py'
DEPENDENCIES=(VERSION+'.py','svg_source_group_nesting_v1.py','compiler_svg_scene_backend_v6.py','svg_native_bezier_ir_v1.py','svg_source_endpoint_bridge_v1.py','svg_source_endpoint_direction_v1.py','svg_source_endpoint_descriptors_v1.js','svg_dom_v7.js','compiler_render_domain_v3.py','compiler_scene_text_v2.py',
 'svg_dom_v6.js','svg_convert_v2.py','svg_convert_v3.py','svg_convert_v5.py',
 'svg_source_coverage_v2.py','auto_quality_source_vector_v2.py','auto_quality_common.py',
 'portable_native_fonts.py','native_source_font_profile_v4.py','pdf_to_native.py',
 'auto_quality_move.py','native_worker.py','clip_canvas_render_v4b.py','strict_canvas_gate.py',
 'compiler_svg_scene_backend_v7.py','compiler_svg_explicit_coordinates_v2.py','compiler_svg_explicit_coordinates_v2.js','native_free_edges_v4.py','native_marker_geometry_explicit_v3.py','native_svg_screen_offset_v1.py','native_marker_geometry_exact_v1.py','auto_quality_svg_closed_scene_v1.py','tikz_execution_binding_v2.py','tikz_execution_marker_quality.py','svg_source_scene_dom_v2.py','svg_dom_source_scene_v2.js','svg_native_triangle_marker_v1.py','svg_native_marker_edit_probe_v2.py')
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
    pins={}
    for name in DEPENDENCIES:
        path=W/'scripts'/name
        if not path.is_file():path=W/'prototype'/name
        pins[str(path)]=sha(path.read_bytes())
    for path in (Path(CHROME),Path(PYTHON).resolve(),R/'scripts/curate_derived.py',
                 R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'):
        pins[str(path)]=sha(path.read_bytes())
    import importlib
    for name in ('fontTools.svgLib.path','fontTools.svgLib.path.parser','fontTools.svgLib.path.arc',
                 'fontTools.pens.recordingPen','fontTools.pens.basePen','fontTools.pens.transformPen',
                 'fontTools.misc.bezierTools','fontTools.misc.transform'):
        path=Path(importlib.import_module(name).__file__).resolve();pins[str(path)]=sha(path.read_bytes())
    calibration=_validate_exact_marker_calibration()
    for path in calibration['pinned_files']:pins[str(path)]=sha(Path(path).read_bytes())
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


def _validate_exact_marker_calibration():
    import itertools
    import native_marker_geometry_exact_v1 as rule
    owner=W/'native_marker_exact_grid_calibration_v1';pp=owner/'preregistered_plan.json';rp=owner/'report.json'
    require(pp.is_file() and rp.is_file(),'infrastructure_exact_marker_calibration_missing')
    plan=json.loads(pp.read_text());report=json.loads(rp.read_text())
    require(plan['geometry_epsilon_px']==rule.EXACT_EPSILON_PX and plan['exact_geometry_only_boundary_px']==rule.EXACT_GRID_BOUNDARY_PX and plan['nonexact_boundary_px']==1,'exact_marker_calibration_policy_changed')
    require(report['plan_sha256']==sha(pp.read_bytes()) and report['policy']==rule.POLICY,'exact_marker_calibration_identity_changed')
    require(plan['rule_sha256']==sha(Path(rule.__file__).read_bytes()),'exact_marker_calibration_rule_changed')
    script=W/'scripts/compiler_marker_alias_calibration_v1.py';require(plan['script_sha256']==sha(script.read_bytes()),'exact_marker_calibration_program_changed')
    expected=set();negative_expected=set()
    for li,depth in enumerate(plan['depths']):
        for ki,kind in enumerate(plan['ratios']):
            for si,stroke in enumerate(plan['stroke_widths']):
                for ai,angle in enumerate(plan['angles']):
                    for pi,phase in enumerate(plan['phases']):
                        key=(depth,kind,stroke,angle,tuple(phase));expected.add(key)
                        if pi==(li+ki+si+ai)%2:
                            for name in plan['negative_variants']:negative_expected.add((*key,name))
    observed=set()
    for row in report['positive_results']:
        key=(row['depth'],row['kind'],row['stroke'],row['angle'],tuple(row['phase']));require(key not in observed,'duplicate_exact_marker_calibration_case');observed.add(key)
        exact=row['maximum_vertex_error_px']<=rule.EXACT_EPSILON_PX;require(row['exact_geometry']==exact,'calibration_exact_geometry_claim_wrong')
        check=rule.contour_decision(row['boundary_distance_px'],row['ink_area_ratio'],{'exact_geometry':exact,'source_fill_and_absent_stroke_match':True},source_viewport_containment=True,actual_editing=True)
        require(all(row[k]==check[k] for k in ('ok','old_rule_passed','exact_geometry_alias_eligible','alias_used')),'exact_marker_calibration_decision_changed')
    require(observed==expected and len(observed)==192,'exact_marker_calibration_positive_scope_incomplete')
    negatives=set()
    for row in report['negative_results']:
        key=(row['depth'],row['kind'],row['stroke'],row['angle'],tuple(row['phase']),row['mutation']);require(key not in negatives,'duplicate_exact_marker_calibration_negative');negatives.add(key)
        require(not row['alias_eligible'] and not row['alias_would_accept'],'exact_marker_calibration_negative_falsely_accepted')
    require(negatives==negative_expected and len(negatives)==384,'exact_marker_calibration_negative_scope_incomplete')
    require(report['passed'] and report['negative_alias_acceptances']==0 and sum(r['alias_used'] for r in report['positive_results'])==10,'exact_marker_calibration_not_passed')
    return {'pinned_files':[pp,rp,script], 'positive_cases':192,'negative_cases':384,'alias_only_positive_cases':10,'actual_data_editing_still_separately_mandatory':True}


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
    require(source.get('format')=='svg' and source.get('category')=='scientific_diagram','unsupported_source_format_or_category')
    require(source.get('render_backend')=='cairosvg' and source.get('image_provenance')=='rendered_from_source_svg'
            and source.get('pairing')=='derived_from_source_svg','source_renderer_provenance_unknown_or_unsupported')
    require(source.get('source_svg_sha256')==sha(code),'recorded_original_svg_identity_missing_or_changed')
    require(list(size)==[source.get('width'),source.get('height')],'recorded_source_canvas_differs_from_reference')
    require(max(size)<=8192 and size[0]*size[1]<=64000000 and len(code)<=2000000,'source_resource_bound')
    require(b'<!ENTITY' not in code.upper() and not re.search(br'<!DOCTYPE[^>]*\[',code,re.I),'source_xml_entity_unsupported')
    root=ET.fromstring(code);require(root.tag.split('}')[-1]=='svg','source_root_not_svg')
    allowed={'svg','g','a','title','desc','metadata','defs','marker','symbol','use','style','path','polygon','polyline','rect','circle','ellipse','line','text','tspan'}
    ids=set();markers=0
    for element in root.iter():
        tag=element.tag.split('}')[-1];require(tag in allowed,'unsupported_svg_element:'+tag)
        if tag=='g':require(not any(c in ('node','edge','cluster') for c in element.get('class','').split()),'general_scene_path_requires_no_graphviz_roles')
        if tag=='marker':markers+=1
        identifier=element.get('id')
        if identifier:require(identifier not in ids,'duplicate_source_xml_id');ids.add(identifier)
        for key,value in element.attrib.items():
            local=key.split('}')[-1]
            require(not local.lower().startswith('on'),'source_event_handler_unsupported')
            require(local not in ('filter','clip-path','mask','marker-mid'),'source_effect_or_middle_marker_requires_another_frontend')
            if local=='href':require(value.startswith('#') or tag=='a' and re.match(r'^(?:https?://|mailto:)',value),'source_external_resource_not_supported')
            if 'url(' in value.lower():require(not re.search(r'url\(\s*[\"\']?(?!#)[^\s\"\')]',value,re.I),'source_external_paint_resource_not_supported')
    require(markers,'general_svg_scene_requires_explicit_source_markers')
    return {'unit':UNIT,'reference_canvas':list(size),'source_explicit_marker_definitions':markers,'renderer':'cairosvg','source_layout_preserved':True,'relayout':False}


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


def _screenshot(page):
    """Viewport capture; retry a compositor-only failure through CDP view capture.

    The fallback changes no source DOM, viewport, scale, fonts, or pixels. It is
    bounded to the exact Chromium infrastructure error, never quality results.
    """
    try:
        return page.screenshot(type='png',timeout=45000)
    except Exception as error:
        if 'Unable to capture screenshot' not in str(error):raise
        session=page.context.new_cdp_session(page)
        try:
            answer=session.send('Page.captureScreenshot',{'format':'png','fromSurface':False,'captureBeyondViewport':False})
            blob=base64.b64decode(answer['data'],validate=True)
            from PIL import Image
            require(list(Image.open(io.BytesIO(blob)).size)==[page.viewport_size['width'],page.viewport_size['height']],
                    'infrastructure_source_capture_canvas_changed')
            return blob
        except Exception as fallback:
            raise ValueError('infrastructure_source_capture_failed:'+str(fallback)[:1200]) from fallback
        finally:session.detach()


def _bind_actual_cairo_faces(page,observation,domain):
    """Translate the renderer's actual font selection into the SVG browser view.

    CairoSVG's toy font selection can treat a CSS family list differently from
    Chromium. Read the actual Cairo FT faces and logical paint sequence, then
    embed those same physical faces. No reference pixels or candidate are read.
    """
    rows=page.evaluate(_RUN_ROWS_JS)
    painted=[(char,item['face']) for item in observation['paint'] if item['operation']=='show_text'
             for char in item['text'] if not char.isspace()]
    wanted=[char for row in rows for char in row['text'] if not char.isspace()]
    require([char for char,_ in painted]==wanted,'source_cairo_browser_logical_paint_inventory_differs')
    postscript={key:item['postscript'] for key,item in observation['faces'].items()}
    faces=domain._physical_faces(postscript.values());replacements=[];offset=0
    for row in rows:
        length=sum(not char.isspace() for char in row['text']);keys={key for _,key in painted[offset:offset+length]};offset+=length
        require(len(keys)==1,'source_cairo_multi_face_run_requires_separate_frontend')
        key=next(iter(keys));face=faces[postscript[key]]
        replacements.append([row['source_selector'],face['family']])
    css='\n'.join('@font-face{font-family:"'+f['family']+'";src:url(data:font/ttf;base64,'+base64.b64encode(f['embedded']).decode()+');font-weight:normal;font-style:normal;}' for f in faces.values())
    page.evaluate('css=>{const s=document.createElement("style");s.textContent=css;document.head.appendChild(s)}',css)
    page.evaluate('''rows=>{for(const [selector,f] of rows){const e=document.querySelector(selector);e.style.setProperty('font-family',f,'important');e.style.setProperty('font-weight','normal','important');e.style.setProperty('font-style','normal','important')}}''',replacements)
    domain._wait_fonts(page)


def _preserve_source_whitespace(cells,positions):
    """Keep source whitespace inside neutral HTML so mxGraph cannot trim it."""
    import html
    for identifier,row in positions.items():
        text=row['text']
        if text!=text.strip():
            cells[identifier].set('value','<span data-compiler-source-whitespace-scene-v5="true">'+html.escape(text)+'</span>')


def _apply_offsets(xml,positions,corrections):
    """Only the compiler's own neutral whitespace wrapper may be replaced."""
    from compiler_scene_text_v2 import wrap
    from auto_quality_source_vector_v2 import _plain
    tree=ET.fromstring(xml);cells={cell.get('id'):cell for cell in tree.iter('mxCell')}
    require(set(corrections)==set(positions),'text_correction_mapping_incomplete')
    for identifier,correction in corrections.items():
        cell=cells[identifier];value=cell.get('value','');text=positions[identifier]['text']
        require(_plain(value)==text,'baseline_source_text_changed')
        if correction['applied']:
            require(not ('<span' in value.lower() or '<font' in value.lower()) or
                    value.startswith('<span data-compiler-source-whitespace-scene-v5="true">'),
                    'rich_native_font_runs_require_separate_layout_compiler')
            cell.set('value',wrap(text,identifier,correction))
    return ET.tostring(tree,encoding='unicode')


def _normalize_paint_alpha(dom):
    """Preserve CSS RGBA paint alpha in native color/opacity fields.

    The legacy SVG color helper kept only RGB and accidentally painted fully
    transparent Graphviz page-outline strokes. This normalization is derived
    solely from fresh computed source CSS, and used symmetrically for emission
    and independent source coverage. It does not remove any visible source ink.
    """
    dom=copy.deepcopy(dom)
    for obj in dom.get('objects',[]):
        style=obj.get('style',{})
        for paint in ('fill','stroke'):
            value=style.get(paint,'none')
            match=re.fullmatch(r'rgba\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)',value)
            if not match:continue
            red,green,blue,alpha=map(float,match.groups())
            require(0<=alpha<=1 and all(0<=v<=255 for v in (red,green,blue)),'invalid_source_css_rgba')
            obj.setdefault('source_computed_paint_alpha',{})[paint]={'css':value,'alpha':alpha}
            style[paint]='none' if alpha==0 else 'rgb('+','.join(str(round(v)) for v in (red,green,blue))+')'
            style[paint+'Opacity']=float(style.get(paint+'Opacity',1))*alpha
    return dom


_RUN_ROWS_JS=r'''()=>{const rows=[];const painted=n=>{const p=n.parentElement;if(!p||p.closest('defs,marker,symbol,pattern,clipPath,mask')||getComputedStyle(p).visibility!=='visible')return false;for(let a=p;a;a=a.parentElement){const c=getComputedStyle(a);if(c.display==='none'||+c.opacity===0)return false;}return true;};for(const [index,e] of [...document.querySelectorAll('svg text')].entries()){const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=walker.nextNode()){if(!n.textContent.trim()||!painted(n))continue;const all=document.createRange();all.selectNodeContents(n);const whole=all.getBoundingClientRect();if(!whole.width||!whole.height)continue;const chars=[];for(const {segment,index:i} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const range=document.createRange();range.setStart(n,i);range.setEnd(n,i+segment.length);const b=range.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}const key=n.parentElement.getAttribute('data-compiler-scene-run-v2');if(key===null)throw Error('source_run_wrapper_missing');rows.push({source_element_index:index,source_selector:'[data-compiler-scene-run-v2="'+key+'"]',text:n.textContent,chars});}}return rows;}'''


def _wrap_source_runs(page):
    before=_screenshot(page)
    page.evaluate('''()=>{const painted=n=>{const p=n.parentElement;if(!p||p.closest('defs,marker,symbol,pattern,clipPath,mask')||getComputedStyle(p).visibility!=='visible')return false;for(let a=p;a;a=a.parentElement){const c=getComputedStyle(a);if(c.display==='none'||+c.opacity===0)return false;}return true;};let serial=0;for(const text of document.querySelectorAll('svg text')){const walker=document.createTreeWalker(text,NodeFilter.SHOW_TEXT),nodes=[];let n;while(n=walker.nextNode())if(n.textContent.trim()&&painted(n)){const range=document.createRange();range.selectNodeContents(n);const b=range.getBoundingClientRect();if(b.width&&b.height)nodes.push(n);}for(const node of nodes){let parent=node.parentElement;const isolated=parent.childNodes.length===1&&(parent.localName==='tspan'||parent===text);if(!isolated){const span=document.createElementNS('http://www.w3.org/2000/svg','tspan');parent.insertBefore(span,node);span.appendChild(node);parent=span;}parent.setAttribute('data-compiler-scene-run-v2',String(serial++));}}}''')
    require(_screenshot(page)==before,'source_run_wrapper_changed_visible_source_pixels')


def _observe_runs(page,context,domain):
    from svg_source_endpoint_bridge_v1 import capture
    dom=capture(page,legacy=True);rows=page.evaluate(_RUN_ROWS_JS);objects=[o for o in dom['objects'] if o['type']=='text']
    require(len(objects)==len(rows) and objects,'fresh_source_run_scope_invalid');positions={};session=context.new_cdp_session(page)
    try:
        session.send('DOM.enable',{'includeWhitespace':'all'});session.send('CSS.enable');document=session.send('DOM.getDocument',{'depth':1})['root']['nodeId']
        for obj,row in zip(objects,rows):
            require(obj['text']==row['text'],'source_run_order_changed')
            node=session.send('DOM.querySelector',{'nodeId':document,'selector':row['source_selector']})['nodeId']
            children=session.send('DOM.describeNode',{'nodeId':node,'depth':1})['node'].get('children',[])
            require(len(children)==1 and children[0].get('nodeType')==3 and children[0].get('nodeValue')==row['text'],'painted_source_run_parent_must_isolate_exact_original_Text_node')
            fonts=session.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
            positions[obj['id']]={**row,'bbox':obj['bbox'],'actual_fonts':fonts,'physical_font_scope':'one_verified_original_Text_node_only'}
        return positions,dom
    finally:session.detach()


def _observe_general(page,context,domain):
    positions,legacy=_observe_runs(page,context,domain)
    from svg_source_scene_dom_v2 import EXTRACTOR
    from svg_source_endpoint_bridge_v1 import capture
    dom=capture(page)
    identity=lambda value:[(o['id'],o['type'],o.get('tag'),o.get('text')) for o in value['objects']]
    require(identity(dom)==identity(legacy),'general_scene_source_object_identity_changed')
    from svg_source_scene_dom_v2 import enrich_scene
    return positions,enrich_scene(dom)


def _capture_issue_gate(dom):
    # These marker viewport claims are discharged by fresh whole-head source
    # containment and actual native marker contour/edit probes, never waived.
    deferred={'scene_marker_viewport_clip_unproven'}
    unresolved=[issue for issue in dom.get('issues',[]) if issue.get('reason') not in deferred]
    require(not unresolved,'source_scene_feature_unsupported:'+json.dumps(unresolved)[:1800])


def _capture(code,size,work,cairo_fonts=None):
    from playwright.sync_api import sync_playwright
    import compiler_render_domain_v3 as domain
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
        context=browser.new_context(viewport={'width':size[0],'height':size[1]},device_scale_factor=1,
                                    java_script_enabled=False,service_workers='block');blocked=[]
        try:
            context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()))
            page=context.new_page();page.set_default_timeout(45000)
            page.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+code.decode('utf-8-sig'))
            page.evaluate('''([w,h])=>{const s=document.querySelector('svg');s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''',list(size))
            domain._wait_fonts(page)
            _wrap_source_runs(page)
            if cairo_fonts is not None:_bind_actual_cairo_faces(page,cairo_fonts,domain)
            original_png=_screenshot(page)
            before,dom=_observe_general(page,context,domain)
            require(_screenshot(page)==original_png,'source_dom_extractor_changed_pixels')
            _capture_issue_gate(dom)
            dom=_normalize_paint_alpha(dom)
            require(before,'source_text_extraction_incomplete')
            require(len(dom['objects'])<=1000,'source_scene_complexity_bound')
            for obj in dom['objects']:
                if obj['type']=='text':
                    require(obj['style'].get('fill') not in ('none','transparent') and obj['style'].get('fillOpacity',1)==1
                            and (obj['style'].get('stroke')=='none' or obj['style'].get('strokeWidth',0)==0),
                            'source_cairo_nonfill_or_stroked_text_physical_paint_profile_unsupported')
            faces=domain._physical_faces([f['postScriptName'] for row in before.values() for f in row['actual_fonts'] if f.get('glyphCount')])
            css='\n'.join('@font-face{font-family:"'+f['family']+'";src:url(data:font/ttf;base64,'+base64.b64encode(f['embedded']).decode()+');font-weight:normal;font-style:normal;}' for f in faces.values())
            page.evaluate('css=>{const s=document.createElement("style");s.textContent=css;document.head.appendChild(s)}',css)
            replacements=[]
            for row in before.values():
                signature=domain._font_signature(row['actual_fonts']);require(len(signature)==1,'source_mixed_physical_font_run_unsupported')
                replacements.append([row['source_selector'],faces[signature[0][0]]['family']])
            page.evaluate('''rows=>{for(const [selector,f] of rows){const e=document.querySelector(selector);e.style.setProperty('font-family',f,'important');e.style.setProperty('font-weight','normal','important');e.style.setProperty('font-style','normal','important')}}''',replacements)
            domain._wait_fonts(page);positions,_=_observe_general(page,context,domain)
            for key in before:
                require([c['text'] for c in before[key]['chars']]==[c['text'] for c in positions[key]['chars']],'source_embedding_changed_characters')
                require(domain._font_signature(before[key]['actual_fonts'])==domain._font_signature(positions[key]['actual_fonts'],True),'source_embedding_changed_physical_font')
                require(all(abs(a[k]-b[k])<=.03 for a,b in zip(before[key]['chars'],positions[key]['chars']) for k in ('x','y','width','height')),'source_embedding_changed_glyph_geometry')
            anchors=page.evaluate('''()=>[...document.querySelectorAll('svg a')].map((a,i)=>({index:i,id:a.id,attributes:[...a.attributes].map(x=>({name:x.name,value:x.value})),descendant_source_ids:[...a.querySelectorAll('*')].filter(x=>!['a','g','title','desc'].includes(x.localName)).map(x=>x.id),tooltip:a.getAttributeNS('http://www.w3.org/1999/xlink','title')||a.getAttribute('title')||a.querySelector(':scope > title')?.textContent||'',href:a.getAttribute('href')||a.getAttributeNS('http://www.w3.org/1999/xlink','href')||'',automatically_navigated:false}))''')
            png=_screenshot(page);require(not blocked,'source_external_resources_blocked')
            _write(work/'browser_source.png',png);_write(work/'dom.json',raw(dom));_write(work/'positions.json',raw(positions))
            return {'dom':dom,'positions':positions,'faces':faces,'png':png,'browser_version':browser.version,'anchors':anchors,
                    'source_dom_extraction_preserved_all_pixels':True}
        finally:context.close();browser.close()


def _expected_text_regions(positions,size):
    """Count every source line crop, including independently positioned glyphs."""
    count=0
    for identifier,row in positions.items():
        lines={}
        for char in row['chars']:
            if not char.get('text','').strip() or char.get('width',0)<=0 or char.get('height',0)<=0:continue
            lines.setdefault(round(char['y']/2)*2,[]).append(char)
        require(lines,'source_logical_text_has_no_visible_glyphs')
        for chars in lines.values():
            x0=max(0,math.floor(min(c['x'] for c in chars))-2);y0=max(0,math.floor(min(c['y'] for c in chars))-2)
            x1=min(size[0],math.ceil(max(c['x']+c['width'] for c in chars))+2);y1=min(size[1],math.ceil(max(c['y']+c['height'] for c in chars))+2)
            require(x1-x0>=3 and y1-y0>=3,'source_visible_glyph_region_needs_explicit_viewport_clip_mapping');count+=1
    return count


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
    _write(work/'cairosvg_source.png',engine);capture=_capture(code,size,work,cairo_fonts)
    positions=domain._positions(capture['positions'],(0,0))
    reference_check=image_quality(reference,engine,{},positions)
    bridge=image_quality(engine,capture['png'],{},positions)
    cairo_font_proof=_cairo_font_check(cairo_fonts,capture)
    expected_regions=_expected_text_regions(capture['positions'],size)
    require(reference_check['text_regions_checked']==expected_regions,'source_reference_text_region_scope_incomplete')
    require(bridge['text_regions_checked']==expected_regions,'source_domain_bridge_text_region_scope_incomplete')
    proof={'policy':VERSION,'source_code_sha256':sha(code),'source_image_sha256':sha(reference),
           'source_metadata_sha256':sha(raw(source)),'predicate':predicate,'source_renderer':'recorded_cairosvg',
           'source_engine_png_sha256':sha(engine),'source_browser_png_sha256':sha(capture['png']),
           'fresh_source_dom_sha256':sha(raw(capture['dom'])),'source_reference':reference_check,
           'source_browser_bridge_diagnostic_only':bridge,'cairo_browser_physical_font_equivalence':cairo_font_proof,
           'source_dom_extraction_preserved_all_pixels':capture['source_dom_extraction_preserved_all_pixels'],
           'source_browser_font_policy':'Cairo actual FT face bytes embedded before SVG geometry extraction',
           'source_anchor_metadata':capture['anchors'],'complete_source_objects':len(capture['dom']['objects']),
           'required_text_cell_ids':sorted(capture['positions']),'complete_logical_source_text_runs':len(capture['positions']),'source_reference_raster_regions_checked':reference_check['text_regions_checked'],'candidate_independent':True,
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
        # CairoSVG's first text traversal builds glyph outlines with text_path;
        # the fill traversal uses show_text (surface.py:452). The path traversal
        # is not a second logical source string. Both remain in the observation,
        # but this admitted filled/no-stroke unit is physically painted by the
        # show_text calls whose exact FT faces are independently read above.
        painted=[(char,actual[row['face']]) for row in observation['paint'] if row['operation']=='show_text'
                 for char in row['text'] if not char.isspace()]
        result['actual_source_font_faces']=len(actual)
        result['nonblank_scalars']=len(painted)
        result['diagnostic_path_build_operations']=sum(row['operation']=='text_path' for row in observation['paint'])
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
    from compiler_svg_explicit_coordinates_v2 import verify
    from native_svg_screen_offset_v1 import observe,transform
    frame=observe(xml);canonical=transform(xml,frame['offsets'],1)
    result=verify(dom,canonical,(dom['sceneMetadata']['root']['width'],dom['sceneMetadata']['root']['height']))
    result['failures']=result['errors'];result['native_actual_screen_offset_proof']=frame
    return result


def structure_checks(xml,record=None):
    from compiler_svg_explicit_coordinates_v2 import structure_checks as check
    return check(xml)


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
        from compiler_svg_scene_backend_v7 import build
        from svg_convert_v3 import unpack,pack
        from pdf_to_native import attach_fonts
        xml,stats=build(copy.deepcopy(capture['dom']),size)
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
        _preserve_source_whitespace(cells,capture['positions'])
        xml=attach_fonts(ET.tostring(tree,encoding='unicode'),fonts)
        from native_svg_screen_offset_v1 import observe,transform
        native_frame=observe(xml);xml=transform(xml,native_frame['offsets'],-1)
        _write(work/'native_screen_offset_proof.json',raw(native_frame))
        stage='source_derived_text_anchor';initial=_native(xml,size)
        _write(work/'initial_native_render.json',raw(initial['native_render']))
        from compiler_scene_text_v2 import offsets
        corrections=offsets(capture['positions'],initial['native_render']);xml=_apply_offsets(xml,capture['positions'],corrections)
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
             'compiler_svg_scene_frontend_v8':{'sourceproof':prepared['sourceproof'],'anchor_offsets':corrections}}
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
        if all(check.get('ok') for check in checks.values()):
            from native_marker_geometry_explicit_v3 import prove
            checks['actual_native_marker_geometry']=prove(xml,capture['dom'],prepared['size'],backend_module='compiler_svg_scene_backend_v7')
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


def _base_quality_visual(record,xml,native_info,png,reference,source_profile,data_root=R):
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


def _marker_contours(prepared,native_png):
    import numpy as np
    from PIL import Image
    from scipy.ndimage import binary_erosion,distance_transform_edt
    from tikz_execution_marker_quality import _mask,_color
    from compiler_svg_scene_backend_v7 import derive
    semantic,proof=derive(prepared['capture']['dom'],prepared['size'])
    source=np.asarray(Image.open(io.BytesIO(prepared['capture']['png'])).convert('RGB'))
    native=np.asarray(Image.open(io.BytesIO(native_png)).convert('RGB'));require(source.shape==native.shape,'source_native_marker_canvas_differs');byid={o['id']:o for o in semantic['objects']};rows=[]
    for marker in proof['markers']:
        head=byid[marker['head']];b=head['bbox'];w,h=prepared['size'];x0=max(0,math.floor(b['x'])-3);y0=max(0,math.floor(b['y'])-3);x1=min(w,math.ceil(b['x']+b['w'])+3);y1=min(h,math.ceil(b['y']+b['h'])+3);color=_color(head['style']['fill']);a=_mask(source[y0:y1,x0:x1],color);z=_mask(native[y0:y1,x0:x1],color)
        require(a.any() and z.any(),'source_native_marker_ink_missing');aa=a&~binary_erosion(a,structure=np.ones((3,3)),border_value=0);zz=z&~binary_erosion(z,structure=np.ones((3,3)),border_value=0);distance=float(max(distance_transform_edt(~zz)[aa].max(),distance_transform_edt(~aa)[zz].max()));ratio=float(z.sum()/a.sum());rows.append({'source_head':marker['head'],'edge':marker['owner'],'side':marker['side'],'boundary_distance_px':distance,'ink_area_ratio':ratio,'ok':distance<=1+1e-8 and .8<=ratio<=1.25})
    return {'ok':bool(rows) and all(r['ok'] for r in rows),'markers':rows,'failures':[] if rows and all(r['ok'] for r in rows) else ['source_native_marker_contour_changed'],'thresholds':{'boundary_distance_px':1,'ink_area_ratio':[.8,1.25]}}


def audit_editing(record,xml,profile,data_root):
    from compiler_svg_explicit_coordinates_v2 import audit
    result=audit(xml,profile)
    marker_edits=profile['evidence']['checks'].get('actual_native_marker_geometry')
    require(marker_edits and marker_edits['ok'] and marker_edits['all_actual_editing'] and marker_edits['code_sha256']==sha(xml.encode()),'fresh_independent_marker_geometry_and_editing_proof_missing')
    return {'ok':True,'policy':VERSION+'_all_source_endpoints_and_marker_direction','endpoint_moves':len(result['moves']),'all_endpoint_interventions':result,'actual_marker_direction_edits':marker_edits}


def quality_visual(record,xml,native_info,png,reference,source_profile,data_root=R):
    result=_base_quality_visual(record,xml,native_info,png,reference,source_profile,data_root)
    prepared=prepare_source(record);markers=_marker_contours(prepared,png)
    proof=source_profile['evidence']['checks'].get('actual_native_marker_geometry');require(proof and proof['ok'] and proof['code_sha256']==sha(xml.encode()),'exact_marker_alias_requires_fresh_actual_native_geometry')
    actual={(m['edge'],m['head'],m['side']):m for m in proof['markers']}
    from native_marker_geometry_exact_v1 import contour_decision
    for marker in markers['markers']:
        key=(marker['edge'],marker['source_head'],marker['side']);require(key in actual,'actual_native_source_marker_inventory_incomplete')
        geometry=actual[key];decision=contour_decision(marker['boundary_distance_px'],marker['ink_area_ratio'],geometry,source_viewport_containment=geometry['source_viewport_containment'],actual_editing=geometry['actual_endpoint_and_direction_editing']);marker.update(decision)
    markers['ok']=bool(markers['markers']) and all(m['ok'] for m in markers['markers']);markers['failures']=[] if markers['ok'] else ['source_native_marker_contour_changed']
    markers['exact_geometry_calibration_policy']='actual_native_marker_geometry_exact_pixel_grid_alias_v1';markers['old_nonexact_rule_unchanged']=True
    result['source_native_marker_contours']=markers
    if not markers['ok']:result['failures']+=markers['failures'];result['ok']=False
    return result
