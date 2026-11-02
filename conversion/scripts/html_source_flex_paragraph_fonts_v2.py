"""Per-source text-node physical font binding, with exact native pixels.

Preserves each complete original text node and its ancestor markup, geometry,
all graph cells and topology. No glyph positioning, image wrapper, font search,
content rewrite or model calls. Failure remains typed pending.
"""
import base64
import copy
import hashlib
import json
import math
import time
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
POLICY='HTML_paragraph_complete_Text_node_physical_faces_same_case_full_render_v2'
sha=lambda data:hashlib.sha256(data).hexdigest()
raw=lambda value:(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()

CAPTURE=r'''async xml=>{
 document.body.innerHTML='<div id="source-run-graph" style="position:relative;width:8192px;height:8192px"></div>';
 const g=new Graph(document.getElementById('source-run-graph'));window.sourceRunGraph=g;
 const d=mxUtils.parseXml(xml),model=d.getElementsByTagName('mxGraphModel')[0];
 for(const entry of (model.getAttribute('extFonts')||'').split('|')){if(!entry)continue;const index=entry.indexOf('^'),family=entry.slice(0,index),uri=entry.slice(index+1);if(index<=0||!uri.startsWith('data:'))throw new Error('native_source_font_observer_requires_inline_font_asset');const face=new FontFace(family,'url('+JSON.stringify(uri)+')');document.fonts.add(await face.load());}
 new mxCodec(d).decode(model,g.model);g.view.validate();await document.fonts.ready;g.refresh();g.view.validate();
 const result=[];window.sourceRunTextObjects=[];const texts=root=>{const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),out=[];while(w.nextNode())if(w.currentNode.textContent.length)out.push(w.currentNode);return out;};
 for(const cell of Object.values(g.model.cells)){
  const label=g.getLabel(cell),s=g.view.getState(cell);if(typeof label!=='string'||!label.length||!s?.text?.node)continue;
  const fo=s.text.node.querySelector('foreignObject');if(!fo)continue;
  const fragment=document.createElement('div');fragment.innerHTML=Graph.sanitizeHtml(label);
  const original=texts(fragment),live=texts(fo);
  if(JSON.stringify(original.map(n=>n.textContent))!==JSON.stringify(live.map(n=>n.textContent)))throw new Error('native_source_HTML_text_node_binding_pending:'+cell.id);
  const runs=[];
  for(let i=0;i<live.length;i++){
   const parent=live[i].parentElement,id='source_run_'+result.length+'_'+i;parent.id=id;
   const c=getComputedStyle(parent);const metric=document.createElement('span');metric.id='source_metric_'+result.length+'_'+i;metric.textContent='M';Object.assign(metric.style,{position:'absolute',left:'0px',top:'0px',fontFamily:c.fontFamily,fontWeight:c.fontWeight,fontStyle:c.fontStyle,fontSize:c.fontSize});document.body.append(metric);const range=document.createRange();range.selectNodeContents(live[i]);const b=range.getBoundingClientRect();
   window.sourceRunTextObjects.push(live[i]);runs.push({index:i,direct_text_index:window.sourceRunTextObjects.length-1,metricSelector:'#'+metric.id,child_index:Array.from(parent.childNodes).indexOf(live[i]),text:original[i].textContent,selector:'#'+id,fontFamily:c.fontFamily,fontWeight:c.fontWeight,fontStyle:c.fontStyle,fontSize:c.fontSize,lineHeight:c.lineHeight,rect:{x:b.x,y:b.y,width:b.width,height:b.height}});
  }
  // Parent IDs are assigned before selectors are finalized because adjacent
  // text nodes can share one parent. No source/model attribute is changed.
  for(let i=0;i<live.length;i++)runs[i].selector='#'+live[i].parentElement.id;
  if(typeof cell.value!=='string'||cell.value!==label)throw Error('HTML_paragraph_dynamic_or_nonliteral_source_label_pending');
  HTML_PARAGRAPH_STRUT_CAPTURE_V9
  result.push({cell:cell.id,label,normalized_markup:fragment.innerHTML,runs,struts});
 }
 return result;
}'''

REWRITE=r'''([label,specs])=>{
 const fragment=document.createElement('div');fragment.innerHTML=Graph.sanitizeHtml(label);
 const w=document.createTreeWalker(fragment,NodeFilter.SHOW_TEXT),nodes=[];while(w.nextNode())if(w.currentNode.textContent.length)nodes.push(w.currentNode);
 if(nodes.length!==specs.length)throw new Error('native_source_font_run_scope_changed');
 for(let i=0;i<nodes.length;i++){
  const node=nodes[i],spec=specs[i];if(node.textContent!==spec.text||spec.index!==i)throw new Error('native_source_font_run_text_changed');
  if(spec.preserve_unpainted_whitespace)continue;
  const span=document.createElement('span');span.setAttribute('data-native-source-font-run-v1',String(i));span.style.fontFamily=spec.family;span.style.fontWeight=spec.weight;span.style.fontStyle=spec.style;
  node.replaceWith(span);span.append(node);
 }
 // Exact inverse must return the same sanitized DOM, including all original
 // ancestor attributes, comments, whitespace and complete text-node content.
 const inverse=fragment.cloneNode(true);for(const span of inverse.querySelectorAll('[data-native-source-font-run-v1]'))span.replaceWith(...span.childNodes);
 const original=document.createElement('div');original.innerHTML=Graph.sanitizeHtml(label);
 if(inverse.innerHTML!==original.innerHTML)throw new Error('native_source_nonfont_markup_or_text_changed');
 return {markup:fragment.innerHTML,inverse_exact:true};
}'''


def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb')as file:file.write(data)


def render(xml,page,work):
    from html_flex_paragraph_render_evidence_v2 import render_full
    return render_full(xml,page,work)


def capture_runs(page,xml):
    rows=page.evaluate(CAPTURE,xml);session=page.context.new_cdp_session(page);session.send('DOM.enable',{'includeWhitespace':'all'});session.send('CSS.enable');root=session.send('DOM.getDocument',{'depth':1})['root']['nodeId']
    try:
        for row in rows:
            for strut in row.get('struts',[]):
                metric=session.send('DOM.querySelector',{'nodeId':root,'selector':strut['metricSelector']})['nodeId']
                strut['primary_metric_fonts']=session.send('CSS.getPlatformFontsForNode',{'nodeId':metric})['fonts']
            for run in row['runs']:
                node=session.send('DOM.querySelector',{'nodeId':root,'selector':run['selector']})['nodeId']
                from html_source_text_node_binding_v9 import physical_fonts_for_object
                obj=session.send('Runtime.evaluate',{'expression':'window.sourceRunTextObjects['+str(run['direct_text_index'])+']','returnByValue':False})['result']
                try:run['actual_fonts'],run['original_actual_Text_backend_binding']=physical_fonts_for_object(session,obj['objectId'],node,run['child_index'],run['text'])
                finally:session.send('Runtime.releaseObject',{'objectId':obj['objectId']})
                metric=session.send('DOM.querySelector',{'nodeId':root,'selector':run['metricSelector']})['nodeId']
                run['primary_metric_fonts']=session.send('CSS.getPlatformFontsForNode',{'nodeId':metric})['fonts']
    finally:session.detach();page.evaluate('sourceRunGraph.destroy();delete window.sourceRunGraph')
    return rows


def spec(run,by_postscript,fonts):
    actual=[font for font in run['actual_fonts']if font.get('glyphCount',0)]
    if not actual:
        if run['text'].isspace():return dict(index=run['index'],text=run['text'],preserve_unpainted_whitespace=True)
        raise ValueError('native_source_font_run_no_observed_physical_face')
    if any(font.get('isCustomFont')for font in actual):raise ValueError('native_source_mixed_existing_custom_font_run_pending')
    chosen=[fonts[by_postscript[font['postScriptName']]]for font in actual]
    flags={(font['physical_bold'],font['physical_italic'])for font in chosen}
    if len(flags)!=1:raise ValueError('native_source_same_text_node_mixed_physical_styles_pending')
    bold,italic=next(iter(flags));weight='normal'if bold else run['fontWeight'];style='normal'if italic else run['fontStyle']
    if style not in ('normal','italic','oblique'):raise ValueError('native_source_unsupported_synthetic_font_slant')
    metric=[font for font in run['primary_metric_fonts']if font.get('glyphCount',0)]
    if len(metric)!=1:raise ValueError('native_source_primary_CSS_metric_face_ambiguous')
    primary=fonts[by_postscript[metric[0]['postScriptName']]];families=list(dict.fromkeys([primary['family']]+[font['family']for font in chosen]))
    return dict(index=run['index'],text=run['text'],family=','.join(families),weight=weight,style=style,physical_postscript=[font['postScriptName']for font in actual],source_primary_metric_postscript=metric[0]['postScriptName'])

def nonfont_graph_identity(xml,rich_cells=(),ordinary_cells=()):
    """Full model tree identity after explicitly scoped font-value elision."""
    from native_source_font_profile_v4 import _cells,style_tokens,FONT_KEYS
    root=ET.fromstring(xml);cells=_cells(root);parents={child:parent for parent in root.iter()for child in parent}
    for model in root.iter('mxGraphModel'):model.attrib.pop('extFonts',None)
    for cid in rich_cells:
        cell=cells[cid];carrier=parents[cell]if cell.get('id')is None and parents[cell].get('label')is not None else cell
        carrier.set('label'if carrier is not cell else'value','SOURCE_complete_text_node_font_delta_verified_separately')
    for cid in ordinary_cells:
        cell=cells[cid];value=cell.get('style','');tokens=style_tokens(value)
        cell.set('style',json.dumps(dict(leading_default_reset=value.startswith(';'),ordered_nonfont_tokens=[token for token in tokens if token and not('='in token and token.split('=',1)[0]in FONT_KEYS)]),sort_keys=True))
    def tree(node):return [node.tag,sorted(node.attrib.items()),node.text,node.tail,[tree(child)for child in node]]
    return raw(tree(root))


def compile(xml,page_size,work,baseline=None):
    """Fresh SOURCE observations -> portable native XML; output still needs QA."""
    started=time.monotonic();last=started;phase_seconds={}
    def phase(name):
        nonlocal last
        now=time.monotonic();phase_seconds[name]=now-last;last=now
    from native_source_font_profile_v4 import _cells,signature,_pixels
    from portable_native_fonts import capture,ready_page,embed as embed_faces
    from pdf_to_native import attach_fonts
    from auto_quality_font_repair import preserve_named_styles,merge_fonts
    from playwright.sync_api import sync_playwright
    from fixed_batch_conversion_adapters_v1 import CHROME
    work=Path(work).resolve()
    if not work.is_relative_to(W.resolve()):raise ValueError('native_source_font_work_outside_owner')
    work.mkdir(parents=True,exist_ok=False)
    if baseline is None:baseline=render(xml,page_size,work/'baseline_native')
    else:
        from html_flex_paragraph_render_evidence_v2 import reuse_full
        baseline=reuse_full(xml,page_size,baseline,work.parent,work/'baseline_same_case_reuse.json')
    phase('full_baseline_native_render_or_verified_same_case_reuse')
    painted_fonts=[font for row in baseline['native_render']['actual_platform_font_usage']for font in row.get('fonts',[])if font.get('glyphCount',0)]
    if painted_fonts and all(font.get('isCustomFont')for font in painted_fonts):raise ValueError('paragraph_original_custom_font_SOURCE_profile_pending')
    if any(font.get('isCustomFont')for font in painted_fonts):raise ValueError('native_source_existing_custom_and_system_mix_pending')
    with sync_playwright()as playwright:
        browser=playwright.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
        try:
            source_observations=capture(ready_page(browser),xml);source_runs=capture_runs(ready_page(browser),xml)
            phase('original_native_physical_Text_and_strut_observations')
            actual={font['postScriptName']:font for row in source_observations for font in row['actual_fonts']if font.get('glyphCount',0)and not font.get('isCustomFont')}
            actual.update({font['postScriptName']:font for row in source_runs for run in row['runs']for font in run['primary_metric_fonts']if font.get('glyphCount',0)and not font.get('isCustomFont')})
            actual.update({font['postScriptName']:font for row in source_runs for strut in row.get('struts',[])for font in strut['primary_metric_fonts']if font.get('glyphCount',0)and not font.get('isCustomFont')})
            if not actual:
                raise ValueError('paragraph_no_observed_original_physical_font_source')
            if any(font.get('isCustomFont')for row in source_observations for font in row['actual_fonts']if font.get('glyphCount',0)):raise ValueError('native_source_existing_custom_and_system_mix_pending')
            fake=ET.Element('mxfile');cells=ET.SubElement(ET.SubElement(ET.SubElement(fake,'diagram'),'mxGraphModel'),'root');fakeobs=[]
            for index,(postscript,font)in enumerate(sorted(actual.items())):
                cid='physical_'+str(index);ET.SubElement(cells,'mxCell',id=cid,vertex='1',value='probe',style='fontStyle=0;')
                fakeobs.append(dict(cell=cid,label='probe',style=dict(fontStyle=0),actual_fonts=[font]))
            _,fonts,details=embed_faces(ET.tostring(fake,encoding='unicode'),fakeobs,work/'physical_fonts')
            if details['issues']:raise ValueError('native_source_physical_font_asset_pending:'+json.dumps(details['issues']))
            by_postscript={font['physical_postscript_name']:family for family,font in fonts.items()}
            phase('physical_font_embedding_and_inventory')
            root=ET.fromstring(xml);native_cells=_cells(root);parents={child:parent for parent in root.iter()for child in parent};runmap={row['cell']:row for row in source_runs};changed=[];runproof=[];ordinary=[]
            from fontTools.ttLib import TTFont
            from native_font_order_probe_v3 import Probe
            cmaps={}
            for asset in fonts.values():
                face=TTFont(asset['original_file'],fontNumber=asset.get('collection_index',0))
                try:cmaps[asset['physical_postscript_name']]=set(face.getBestCmap()or{})
                finally:face.close()
            order_probe=Probe(browser)
            page=ready_page(browser)
            for row in source_observations:
                if not any(font.get('glyphCount',0)and not font.get('isCustomFont')for font in row['actual_fonts']):continue
                cell=native_cells[row['cell']]
                if row['cell']in runmap:
                    runrow=runmap[row['cell']];specs=[spec(run,by_postscript,fonts,order_probe,cmaps)for run in runrow['runs']]
                    from html_source_paragraph_strut_fonts_v9 import spec as strut_spec
                    struts=[strut_spec(item,by_postscript,fonts)for item in runrow['struts']]
                    result=page.evaluate(REWRITE,[row['label'],specs,struts]);carrier=parents[cell]if cell.get('id')is None and parents[cell].get('label')is not None else cell;carrier.set('label'if carrier is not cell else'value',result['markup'])
                    host=next(item for item in struts if item['kind']=='cell');style=cell.get('style','');tokens=style.split(';');flags=next((int(t.split('=',1)[1])for t in tokens if t.startswith('fontStyle=')),0)
                    if host['physical_bold']:flags&=~1
                    if host['physical_italic']:flags&=~2
                    tokens=[t for t in tokens if not t.startswith('fontFamily=')and not t.startswith('fontStyle=')]
                    cell.set('style',';'.join(t for t in tokens if t)+';fontFamily='+host['family']+';fontStyle='+str(flags)+';')
                    runproof.append(dict(cell=row['cell'],source_label=row['label'],source_run_specs=specs,source_strut_specs=struts,inverse_exact=result['inverse_exact'],all_original_nonfont_markup_restored=result['element_strut_styles_restored_exactly']))
                else:ordinary.append(row)
                changed.append(row['cell'])
            new=ET.tostring(root,encoding='unicode')
            if ordinary:
                new,more,ordinary_details=embed_faces(new,ordinary,work/'ordinary_fonts')
                if ordinary_details['issues']:raise ValueError('native_source_non_HTML_cell_font_pending:'+json.dumps(ordinary_details['issues']))
                new=preserve_named_styles(xml,new,{row['cell']for row in ordinary})
                restored=ET.fromstring(new);restored_cells=_cells(restored)
                for item in ordinary:
                    cid=item['cell']
                    if native_cells[cid].get('style','').startswith(';')and not restored_cells[cid].get('style','').startswith(';'):restored_cells[cid].set('style',';'+restored_cells[cid].get('style',''))
                new=ET.tostring(restored,encoding='unicode');fonts.update(more)
            old_model=next(ET.fromstring(xml).iter('mxGraphModel'));new=merge_fonts(attach_fonts(new,fonts),old_model.get('extFonts'))
            from native_font_final_named_style_v1 import restore as restore_final_styles
            new=restore_final_styles(xml,new,[row['cell']for row in source_observations])
            if nonfont_graph_identity(xml,[row['cell']for row in runproof],[row['cell']for row in source_observations])!=nonfont_graph_identity(new,[row['cell']for row in runproof],[row['cell']for row in source_observations]):raise ValueError('native_source_nonfont_cell_geometry_topology_or_metadata_changed')
            phase('per_Text_font_fallback_cmap_and_exact_markup_rewrite');current_runs=capture_runs(ready_page(browser),new);phase('portable_native_physical_Text_and_strut_observations')
        finally:
            if 'order_probe'in locals():order_probe.close()
            browser.close()
    current=render(new,page_size,work/'portable_native')
    phase('portable_full_official_native_render')
    if _pixels(baseline['png'])!=_pixels(current['png']):raise ValueError('native_source_per_run_font_changes_native_pixels')
    before=signature(baseline['native_render']['actual_platform_font_usage']);after=signature(current['native_render']['actual_platform_font_usage'],custom=True)
    # The old observer asks on parent elements and double-counts descendant
    # glyphs across nested markup. CDP also supports the actual Text backend
    # node, so compare every complete source text node directly.
    direct=lambda rows:{(row['cell'],run['index']):{font['postScriptName']:font['glyphCount']for font in run['actual_fonts']if font.get('glyphCount',0)}for row in rows for run in row['runs']}
    save(work/'source_actual_text_nodes.json',raw(source_runs));save(work/'current_actual_text_nodes.json',raw(current_runs));save(work/'original_renderer_fonts.json',raw(baseline['native_render']['actual_platform_font_usage']));save(work/'current_renderer_fonts.json',raw(current['native_render']['actual_platform_font_usage']))
    save(work/'exact_native_pixels.json',raw(dict(source_RGBA_equals_portable_RGBA=True,source_sha256=sha(baseline['png']),portable_sha256=sha(current['png']))))
    if direct(source_runs)!=direct(current_runs):raise ValueError('native_source_per_text_node_physical_PS_or_glyph_inventory_changed')
    from html_source_paragraph_strut_fonts_v9 import signature as strut_signature
    if strut_signature(source_runs)!=strut_signature(current_runs):raise ValueError('paragraph_primary_element_or_host_strut_physical_PS_changed')
    if any(not font.get('isCustomFont')for row in current_runs for item in row.get('struts',[])for font in item['primary_metric_fonts']if font.get('glyphCount',0)):raise ValueError('paragraph_primary_element_or_host_strut_not_portable')
    if any(not font.get('isCustomFont')for row in current_runs for run in row['runs']for font in run['actual_fonts']if font.get('glyphCount',0)):raise ValueError('native_source_per_text_node_has_system_font_after_binding')
    rich_ids=set(runmap);ordinary_before={cid:value for cid,value in before.items()if cid not in rich_ids};ordinary_after={cid:value for cid,value in after.items()if cid not in rich_ids}
    if ordinary_before!=ordinary_after:raise ValueError('native_source_non_HTML_physical_PS_or_glyph_inventory_changed')
    # Same renderer and exact source geometry must retain complete glyph ranges.
    original={row['cell']:[c for run in row['runs']for c in run.get('chars',[])]for row in baseline['native_render']['actual_text_positions']}
    candidate={row['cell']:[c for run in row['runs']for c in run.get('chars',[])]for row in current['native_render']['actual_text_positions']}
    if set(original)!=set(candidate):raise ValueError('native_source_font_text_cell_scope_changed')
    maximum=0.
    for cid,wanted in original.items():
        got=candidate[cid]
        if[c['text']for c in wanted]!=[c['text']for c in got]:raise ValueError('native_source_font_grapheme_text_changed')
        for a,b in zip(wanted,got):
            values=[abs(float(a[k])-float(b[k]))for k in ('x','y','width','height')]
            if not all(math.isfinite(value)for value in values):raise ValueError('native_source_nonfinite_glyph_geometry')
            maximum=max(maximum,*values)
    save(work/'glyph_geometry.json',raw(dict(maximum_error_px=maximum,tolerance_px=.03)))
    if maximum>.03:raise ValueError('native_source_font_glyph_geometry_changed')
    destination=R/'clean/html_source_flex_paragraph_fonts_v2'/uuid.uuid4().hex;destination.mkdir(parents=True,exist_ok=False);assets=[]
    for font in fonts.values():
        original=Path(font['original_file']);origin=original.read_bytes();blob=Path(font['file']).read_bytes()
        if sha(origin)!=font['original_sha256']or sha(blob)!=font['sha256']:raise ValueError('native_source_font_asset_changed')
        target=destination/'fonts'/Path(font['file']).name;sourcecopy=destination/'fonts'/(sha(origin)+original.suffix.lower())
        if not target.exists():save(target,blob)
        if not sourcecopy.exists():save(sourcecopy,origin)
        assets.append({**{k:v for k,v in font.items()if k not in ('file','original_file','uri')},'file':str(target.relative_to(R)),'original_file':str(sourcecopy.relative_to(R))})
    proof=dict(all_original_nonwhitespace_graphemes_verified_in_actual_physical_font_cmaps=True,all_original_element_and_host_strut_primary_physical_fonts_preserved=True,all_current_element_and_host_struts_use_embedded_faces=True,original_TypedOM_line_height_semantics_untouched=True,policy=POLICY,source_code_sha256=sha(xml.encode()),output_code_sha256=sha(new.encode()),source_RGBA_equals_portable_RGBA=True,complete_physical_PS_and_glyph_inventory_preserved=True,glyph_max_error_px=maximum,glyph_tolerance_px=.03,changed_cells=changed,per_run_bindings=runproof,ordinary_cells=[row['cell']for row in ordinary],original_source_markup_recovers_exactly=True,model_calls=0)
    for name,value in [('source_observations.json',source_observations),('source_runs.json',source_runs),('current_runs.json',current_runs),('proof.json',proof)]:save(destination/name,raw(value))
    save(destination/'source.normalized.drawio',xml.encode());save(destination/'diagram.drawio',new.encode());save(destination/'image.png',current['png'])
    phase('complete_pixel_glyph_font_and_graph_acceptance_and_clean_assets')
    performance={'stage_monotonic_seconds':phase_seconds,'total_monotonic_seconds':time.monotonic()-started,'baseline_full_render_reused':baseline.get('exact_full_render_identity')is not None}
    save(work/'performance.json',raw(performance))
    return dict(performance=performance,xml=new,png=current['png'],info=current['native_render'],assets=assets,proof=proof,proof_file=str((destination/'proof.json').relative_to(R)),source_observations=source_observations,source_strut_runs=source_runs,current_strut_runs=current_runs)

# Source probes exist only in the separate native font observer page.
from html_source_paragraph_strut_fonts_v9 import CAPTURE_JS as _STRUT_CAPTURE_V9
from html_flex_paragraph_strut_rewrite_v2 import REWRITE as _STRUT_REWRITE_V9
CAPTURE=CAPTURE.replace('HTML_PARAGRAPH_STRUT_CAPTURE_V9',_STRUT_CAPTURE_V9)
REWRITE=_STRUT_REWRITE_V9

# Keep the established Font3 per-grapheme cmap/fallback gate. No Unicode or
# missing-cmap exception is introduced by the paragraph lowering.
_original_complete_run_spec_v9=spec
def spec(run,by_postscript,fonts,probe,cmaps):
    from native_font_order_probe_v3 import derive_order
    import html
    out=_original_complete_run_spec_v9(run,by_postscript,fonts)
    if out.get('preserve_unpainted_whitespace'):return out
    flags=(1 if float(run['fontWeight'])>=600 else 0)|(2 if run['fontStyle'].startswith(('italic','oblique'))else 0)
    row=dict(style=dict(fontFamily=run['fontFamily'],fontStyle=flags,fontSize=float(run['fontSize'].removesuffix('px'))),label=html.escape(run['text']),actual_fonts=run['actual_fonts'])
    actual=[f['postScriptName']for f in run['actual_fonts']if f.get('glyphCount',0)];primary=out['source_primary_metric_postscript'];preferred=list(dict.fromkeys([primary]+actual))
    order,proof=derive_order(probe,row,set(actual),preferred,cmaps)
    families=[fonts[by_postscript[ps]]['family']for ps in dict.fromkeys([primary]+order)]
    out['family']=','.join(families);out['source_physical_fallback_order_and_cmap_proof']=proof
    return out
