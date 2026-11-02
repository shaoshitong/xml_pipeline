"""Rebuild Graphviz/native markers from fresh source; no queues, DB writes or models.

This is a per-case adapter for an independently timed child process. Source and
quality gates are unchanged. Existing physical-font definitions are transferred
only to matching logical text IDs with identical characters and font size.
"""
import copy,hashlib,html,io,json,re,time,uuid,xml.etree.ElementTree as E
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
FORMATS=('svg','python','plantuml')
TRIGGERS=('source_arrow_missing_attached_native_marker','source_arrow_remains_standalone_object',
          'source_connector_missing_native_edge','source_connector_terminal_mismatch','source_node_group_missing')
sha=lambda b:hashlib.sha256(b).hexdigest()
def eligible(record,failure):
    return record.get('source_format') in FORMATS and any(s in json.dumps(failure,ensure_ascii=False) for s in TRIGGERS)
def _plain(s):return html.unescape(re.sub(r'<[^>]*>','',s or ''))
def _style(s):return dict(x.split('=',1) for x in (s or '').split(';') if '=' in x)
def preserve_fonts(previous,rebuilt):
    old=E.fromstring(previous);new=E.fromstring(rebuilt)
    oldcells={c.get('id'):c for c in old.iter('mxCell')};transfers=[]
    a=old.find('.//mxGraphModel');b=new.find('.//mxGraphModel')
    if a is None or b is None:raise ValueError('missing_native_model')
    if a.get('extFonts'):b.set('extFonts',a.get('extFonts'))
    for c in new.iter('mxCell'):
        if not c.get('value'):continue
        p=oldcells.get(c.get('id'))
        if p is None or _plain(p.get('value'))!=_plain(c.get('value')):continue
        ps=_style(p.get('style'));ns=_style(c.get('style'))
        if ps.get('fontSize')!=ns.get('fontSize'):continue
        if not ps.get('fontSource') and 'Native' not in ps.get('fontFamily',''):continue
        # Preserve already-proven physical faces and spans, never old position,
        # routing, node membership, color or unrelated style fields.
        for key in ['fontFamily','fontSource','fontStyle']:
            if key in ps:ns[key]=ps[key]
        c.set('style',';'.join(k+'='+v for k,v in ns.items())+';')
        c.set('value',p.get('value'))
        transfers.append(c.get('id'))
    return E.tostring(new,encoding='unicode'),transfers
def _read(logical,digest):
    if not isinstance(logical,str) or Path(logical).is_absolute():raise ValueError('invalid_relative_source_locator')
    p=(R/logical).resolve(strict=True)
    if not p.is_relative_to((R/'clean').resolve()):raise ValueError('source_payload_not_under_clean')
    blob=p.read_bytes()
    if sha(blob)!=digest:raise ValueError('source_or_candidate_hash_mismatch')
    return blob
def _write(p,blob):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(blob)
def _capture(record,blob,width,height,work):
    from playwright.sync_api import sync_playwright
    from fixed_batch_conversion_adapters_v1 import CHROME
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
        try:
            ctx=b.new_context(java_script_enabled=False,viewport={'width':width,'height':height},service_workers='block');blocked=[]
            try:
                ctx.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page=ctx.new_page();page.set_default_timeout(45000)
                page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+blob.decode())
                if record['source_format']=='plantuml':
                    variant=record.get('variant_selection',{}).get('chosen')
                    if variant not in ('natural','scaled'):raise ValueError('missing_pinned_plantuml_layout')
                    page.evaluate('''({w,h,variant})=>{const s=document.querySelector('svg');if(variant==='scaled'){s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}else{const bg=s.querySelector(':scope > g > rect');if(bg&&+bg.getAttribute('x')===0&&+bg.getAttribute('y')===0){bg.setAttribute('width',w);bg.setAttribute('height',h);}}}''',{'w':width,'h':height,'variant':variant})
                    from plantuml_fonts import resolve
                    fonts=resolve(page,work);page.evaluate('document.fonts.ready')
                    metadata=page.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text())
                    dom=page.evaluate((W/'scripts/svg_dom_plantuml_v4.js').read_text());dom['_plantuml_metadata']=metadata;dom['_plantuml_fonts']=fonts
                else:
                    page.evaluate('''([w,h])=>{const s=document.querySelector('svg');if(!s.viewBox.baseVal.width)s.setAttribute('viewBox',`0 0 ${s.width.baseVal.value} ${s.height.baseVal.value}`);s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);}''',[width,height]);page.evaluate('document.fonts.ready')
                    dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text())
                if blocked:raise ValueError('blocked_source_resources:'+repr(blocked[:4]))
                return dom
            finally:ctx.close()
        finally:b.close()
def repair(record,job,work):
    """Return a new immutable candidate or a typed, finite refusal. Never accept."""
    started=time.monotonic();work=Path(work).resolve()
    try:
        if not work.is_relative_to(W.resolve()):raise ValueError('work_outside_conversion_root')
        work.mkdir(parents=True,exist_ok=True);old=copy.deepcopy(record)
        source=json.loads(job[4]) if not isinstance(job,dict) else json.loads(job['input_record'])
        if record.get('source_format') not in FORMATS:raise ValueError('unsupported_source_format')
        if (record.get('id'),record.get('source_pair_sha256'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(source['pair_sha256'],source['pair_sha256'],source['code_sha256'],source['image_sha256']):raise ValueError('authoritative_source_identity_mismatch')
        xml_before=_read(record['code_file'],record['code_sha256']).decode();_read(record['image_file'],record['image_sha256'])
        reference=_read(record['original_reference'],source['image_sha256']);_read(record['original_source_code'],source['code_sha256'])
        if record.get('automatic_quality_policy') and str(record.get('quality_state','')).startswith('accepted'):
            return {'ok':True,'record':copy.deepcopy(record),'evidence':{'policy':'fresh_source_native_graph_markers_v1','unchanged_success_control':True,'requires_full_quality_revalidation':True},'model_calls':0,'seconds':time.monotonic()-started}
        from PIL import Image
        width,height=Image.open(io.BytesIO(reference)).size
        if max(width,height)>8192 or width*height>64000000:raise ValueError('source_canvas_exceeds_fixed_limits')
        svg=_read(record['original_source_code'],source['code_sha256']) if record['source_format']=='svg' else _read(record['source_render_svg'],record['source_render_svg_sha256'])
        dom=_capture(record,svg,width,height,work)
        if not dom.get('nodes'):raise ValueError('no_source_graphviz_semantic_node_groups')
        if record['source_format']=='plantuml':
            from plantuml_native_v4 import build
            xml,stats=build(dom,width,height,dom['_plantuml_metadata'])
        else:
            from svg_convert_v5 import build
            xml,stats=build(dom,width,height)
        xml,font_transfers=preserve_fonts(xml_before,xml)
        from auto_quality_source_vector_v2 import _graphviz_coverage
        coverage=_graphviz_coverage(dom,xml,stats);stats['source_coverage']=coverage
        if not coverage['ok']:raise ValueError('source_reconstruction_still_incomplete:'+json.dumps(coverage['errors'],ensure_ascii=False)[:3000])
        from fixed_batch_conversion_adapters_v1 import _render
        png,info=_render(xml,width,height)
        dest=R/'clean/round2_source_repair_v1'/record['id'][:2]/record['id']/uuid.uuid4().hex;dest.mkdir(parents=True,exist_ok=False)
        _write(dest/'diagram.drawio',xml.encode());_write(dest/'image.png',png)
        cells=list(E.fromstring(xml).iter('mxCell'));vertices={c.get('id') for c in cells if c.get('vertex')=='1'};edges=[c for c in cells if c.get('edge')=='1']
        evidence={'policy':'fresh_source_native_graph_markers_v1','source_code_sha256':source['code_sha256'],'source_image_sha256':source['image_sha256'],
                  'prior_code_sha256':record['code_sha256'],'prior_image_sha256':record['image_sha256'],'source_svg_sha256':sha(svg),'coverage':coverage,'preserved_font_cells':font_transfers,
                  'new_native_markers':stats.get('native_graphviz_arrowheads',[]),'model_calls':0,'requires_full_quality_revalidation':True}
        out={**record,'code_file':str((dest/'diagram.drawio').relative_to(R)),'code_sha256':sha(xml.encode()),'image_file':str((dest/'image.png').relative_to(R)),
             'image_sha256':sha(png),'svg_conversion':stats,'vertices':len(vertices),'edges':len(edges),'bound_edges':sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),
             'render':info,'quality_state':'pending_round2_full_source_native_quality','round2_source_repair':evidence}
        for key in ['automatic_quality_policy','automatic_quality_audit','accepted_at_utc']:out.pop(key,None)
        from auto_quality_source_vector_v2 import check_vector_profile
        full_source=check_vector_profile(out,xml)
        evidence['complete_source_profile']=full_source
        if not full_source.get('supported') or not full_source.get('ok'):
            raise ValueError('full_source_profile_still_incomplete:'+json.dumps(full_source.get('failures'),ensure_ascii=False)[:3000])
        _write(dest/'source_repair_evidence.json',(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n').encode())
        _write(dest/'candidate_record.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
        if record!=old:raise ValueError('input_record_mutated')
        return {'ok':True,'record':out,'evidence':evidence,'model_calls':0,'seconds':time.monotonic()-started}
    except Exception as e:return {'ok':False,'reason':str(e).split(':',1)[0],'error_type':type(e).__name__,'error':str(e)[:4000],'model_calls':0,'seconds':time.monotonic()-started}

# The root second-round coordinator uses one common adapter name.
convert=repair
