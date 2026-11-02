"""Prototype: actual source/native glyph alignment, never SSIM-directed fitting.

Reads a current HTML poster revision and writes only W/prototype. A translation
is proposed only when physical face, CSS size and EVERY matched grapheme's
positions/advance/height support one common displacement. Existing clips are
left untouched; clipped objects requiring a locked global clip are diagnosed,
not blindly moved. Source/reference disagreement is independently diagnosed.
"""
import argparse
import collections
import concurrent.futures
import copy
import datetime
import hashlib
import html
import io
import json
import math
import mimetypes
from pathlib import Path
import re
import sqlite3
import statistics
import time
import urllib.parse
import uuid
import xml.etree.ElementTree as E

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
POSITION_TOLERANCE=.08
SIZE_TOLERANCE=.08
sha=lambda blob:hashlib.sha256(blob).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def source_js():
    from html_range_extractor_v2 import source_js as base_js
    source=base_js(W/'scripts/html_dom_clip.js')
    substitutions={
      "last.text+=hidden+item.segment;hidden='';":"last.text+=hidden+item.segment;last.qaTextEnd=start+item.segment.length;hidden='';",
      'qaTextStart:start}':'qaTextStart:start,qaTextEnd:start+item.segment.length}',
      "type:'text',qaOwner:":"type:'text',qaTextNodeIndex:[...el.childNodes].indexOf(n),qaOwner:",
      "last.text+=' '+match[0];":"last.text+=' '+match[0];last.qaTextEnd=match.index+match[0].length;",
      'qaTextStart:match.index}':'qaTextStart:match.index,qaTextEnd:match.index+match[0].length}',
      'qaTextStart:g.qaTextStart,color:':'qaTextStart:g.qaTextStart,qaTextNodeIndex:[...el.childNodes].indexOf(n),color:',
      'objects.push(extra);}return {qaWrappedWords':'objects.push(extra);}window.__img2codeAlignOwners=qaElements;return {qaWrappedWords',
    }
    for old,new in substitutions.items():
        assert old in source,'Source extractor instrumentation target absent: '+old
        source=source.replace(old,new)
    return source


SOURCE_GLYPHS=r'''dom=>{
 const owners=window.__img2codeAlignOwners,nodes=[],errors=[],segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});
 for(const o of dom.objects){if(o.type!=='text')continue;try{
  const el=owners[o.qaOwner],n=el?.childNodes[o.qaTextNodeIndex];
  if(!n||n.nodeType!==Node.TEXT_NODE)throw Error('source text node identity missing');
  const start=o.qaTextStart,end=o.qaTextEnd;
  if(!Number.isInteger(start)||!Number.isInteger(end)||end<start)throw Error('source UTF16 range missing');
  const raw=n.textContent.slice(start,end),mapped=[];
  if(o.qaWrappedFragment){for(const g of segmenter.segment(raw))mapped.push({text:g.segment,raw:g.segment,start:start+g.index,end:start+g.index+g.segment.length});}
  else{for(const token of raw.matchAll(/\s+|\S+/gu)){
   if(/^\s+$/u.test(token[0]))mapped.push({text:' ',raw:token[0],start:start+token.index,end:start+token.index+token[0].length});
   else for(const g of segmenter.segment(token[0]))mapped.push({text:g.segment,raw:g.segment,start:start+token.index+g.index,end:start+token.index+g.index+g.segment.length});
  }}
  if(mapped.map(g=>g.text).join('').replaceAll('\u00a0',' ')!==o.text.replaceAll('\u00a0',' '))throw Error('source logical characters do not match exact mapped range');
  o.actualSourceGlyphs=mapped.map(g=>{const range=document.createRange();range.setStart(n,g.start);range.setEnd(n,g.end);const b=range.getBoundingClientRect();return {...g,x:b.x,y:b.y,width:b.width,height:b.height,rectCount:[...range.getClientRects()].filter(x=>x.width&&x.height).length};});
  const css=getComputedStyle(el);o.actualSourceCss={fontSize:parseFloat(css.fontSize),fontWeight:css.fontWeight,fontStyle:css.fontStyle,fontFamily:css.fontFamily,fontKerning:css.fontKerning,fontFeatureSettings:css.fontFeatureSettings,fontVariationSettings:css.fontVariationSettings,letterSpacing:css.letterSpacing,lineHeight:css.lineHeight,direction:css.direction};
  if(!nodes.includes(n))nodes.push(n);o.actualSourceTextNode=nodes.indexOf(n);
 }catch(error){o.actualSourceGlyphError=String(error);errors.push({cell:String(o.id+1),error:String(error)});}}
 window.__img2codeAlignTextNodes=nodes;return {dom,textNodeCount:nodes.length,errors};}'''


def capture_source(record,work):
    from PIL import Image
    from playwright.sync_api import sync_playwright
    import auto_quality_source_vector_v2 as source_profile
    work=Path(work);work.mkdir(parents=True,exist_ok=True)
    code=source_profile._read_clean(record['original_source_code'],record['source_code_sha256'])
    reference=source_profile._read_clean(record['original_reference'],record['source_image_sha256'])
    width,height=Image.open(io.BytesIO(reference)).size
    assets=(R/record['original_asset_root']).resolve() if record.get('original_asset_root') else None
    if assets is not None:assert assets.is_relative_to((R/'clean').resolve())
    blocked=[];served={};font_nodes={};attempts=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':width,'height':height},java_script_enabled=False,service_workers='block')
        try:
            def route(req):
                url=urllib.parse.urlparse(req.request.url);name=urllib.parse.unquote(url.path.lstrip('/'))
                if url.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
                if name=='index.html':req.fulfill(body=code,content_type='text/html');return
                target=(assets/name).resolve() if assets else None
                if target is None or not target.is_relative_to(assets) or not target.is_file():blocked.append(req.request.url);req.abort();return
                data=target.read_bytes();served[req.request.url]=data;req.fulfill(body=data,content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            context.route('**/*',route);page=context.new_page();page.set_default_timeout(45000)
            page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready')
            dom=page.evaluate(source_js());captured=page.evaluate(SOURCE_GLYPHS,dom);dom=captured['dom']
            cdp=context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');cdp.send('DOM.getDocument',{'depth':-1})
            try:
                snapshot=cdp.send('DOMSnapshot.captureSnapshot',{'computedStyles':[],'includePaintOrder':True});dom['_source_paint_order']=source_profile._snapshot_paint_orders(dom,snapshot)
                for index in range(captured['textNodeCount']):
                    obj=cdp.send('Runtime.evaluate',{'expression':'window.__img2codeAlignTextNodes['+str(index)+']','returnByValue':False})['result'];object_id=obj['objectId'];basis='actual_text_node'
                    try:
                        node=cdp.send('DOM.requestNode',{'objectId':object_id})['nodeId'];fonts=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
                    finally:cdp.send('Runtime.releaseObject',{'objectId':object_id})
                    if not fonts:
                        owner=next(o['qaOwner'] for o in dom['objects'] if o.get('actualSourceTextNode')==index)
                        obj=cdp.send('Runtime.evaluate',{'expression':'window.__img2codeAlignOwners['+str(owner)+']','returnByValue':False})['result'];object_id=obj['objectId']
                        try:
                            node=cdp.send('DOM.requestNode',{'objectId':object_id})['nodeId'];fonts=cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts'];basis='actual_owner_subtree'
                        finally:cdp.send('Runtime.releaseObject',{'objectId':object_id})
                    font_nodes[index]={'fonts':fonts,'basis':basis}
            finally:cdp.detach()
            for obj in dom['objects']:
                if obj.get('actualSourceTextNode') in font_nodes:obj['actualSourcePhysicalFonts']=font_nodes[obj['actualSourceTextNode']]
            for attempt in range(3):
                try:png=page.screenshot();attempts.append({'attempt':attempt+1,'ok':True});break
                except Exception as error:
                    attempts.append({'attempt':attempt+1,'error':repr(error)})
                    if attempt==2:raise
            assert not blocked,'Source resources unresolved: '+repr(blocked[:8])
        finally:context.close();browser.close()
    (work/'source.native.png').write_bytes(png);(work/'source.glyph_dom.json').write_text(json.dumps(dom,ensure_ascii=False,indent=2)+'\n')
    metadata={'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'fresh_source_png_sha256':sha(png),'fresh_source_dom_sha256':sha(json.dumps(dom,sort_keys=True).encode()),'source_range_errors':captured['errors'],'source_capture_attempts':attempts,'viewport':[width,height]}
    (work/'source.capture.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return dom,served,png,metadata


def _plain(value):
    from auto_quality_source_vector_v2 import _plain as logical
    return logical(value)


def _style(cell):
    return dict(value.split('=',1) for value in cell.get('style','').split(';') if '=' in value)


def _canonical_text(value):return value.replace('\u00a0',' ')


def _font_size(run):
    match=re.search(r'([\d.]+)px(?:[ /]|$)',run.get('font',''))
    return float(match.group(1)) if match else None


def _faces(fonts):
    return sorted({font.get('postScriptName') for font in fonts if font.get('glyphCount',0)>0 and font.get('postScriptName')})


def registration(record,source_size,native_canvas,dom=None,xml=None):
    contract=record.get('native_canvas_contract') or record.get('native_page_padding') or {}
    offset=contract.get('offset')
    if isinstance(offset,dict):offset=[offset.get('x'),offset.get('y')]
    if offset and len(offset)==2:return float(offset[0]),float(offset[1])
    if list(source_size)==list(native_canvas):return 0.,0.
    if dom is not None and xml is not None:
        import auto_quality_source_vector_v2 as source_profile
        nontext=[obj for obj in dom['objects'] if obj['type']!='text']
        text_ids={str(obj['id']+1) for obj in dom['objects'] if obj['type']=='text'}
        paint=source_profile._paint_coverage(dom,xml,'html')
        errors=[error for error in paint['errors'] if error.get('cell') not in text_ids]
        assert nontext and not errors,'Nontext source geometry cannot prove canvas registration'
        dx,dy=paint['source_layout_translation']['dx'],paint['source_layout_translation']['dy']
        assert dx>=0 and dy>=0 and source_size[0]+dx<=native_canvas[0] and source_size[1]+dy<=native_canvas[1],'Original source page does not fit the verified native frame'
        return dx,dy
    raise ValueError('Source/native canvas registration is missing')


def analyze(dom,native_info,xml,offset=(0.,0.)):
    cells={cell.get('id'):cell for cell in E.fromstring(xml).iter('mxCell')}
    native_rows={row['cell']:row for row in native_info.get('actual_text_positions',[])}
    native_fonts={row['cell']:row.get('fonts',[]) for row in native_info.get('actual_platform_font_usage',[])}
    results=[]
    for obj in dom['objects']:
        if obj['type']!='text':continue
        key=str(obj['id']+1);result={'cell':key,'text_preview':obj['text'][:48],'source_glyphs':len(obj.get('actualSourceGlyphs',[])),'category':'unclassified','safe_translation':False}
        results.append(result)
        if key not in cells or key not in native_rows:
            result['category']='missing_native_text_object';continue
        if obj.get('actualSourceGlyphError'):
            result.update(category='source_range_mapping_error',error=obj['actualSourceGlyphError']);continue
        if _canonical_text(_plain(cells[key].get('value','')))!=_canonical_text(obj['text']):
            result['category']='source_xml_logical_text_mismatch';continue
        row=native_rows[key];native_glyphs=[char for run in row.get('runs',[]) for char in run.get('chars',[])]
        source_glyphs=obj.get('actualSourceGlyphs',[])
        if [ _canonical_text(g['text']) for g in source_glyphs ] != [ _canonical_text(g['text']) for g in native_glyphs ]:
            result.update(category='source_native_grapheme_sequence_mismatch',native_text=''.join(g.get('text','') for g in native_glyphs)[:80]);continue
        if not source_glyphs:
            result['category']='empty_source_glyphs';continue
        source_font=obj.get('actualSourcePhysicalFonts',{});source_faces=_faces(source_font.get('fonts',[]));native_faces=_faces(native_fonts.get(key,[]));result.update(source_faces=source_faces,native_faces=native_faces,source_font_basis=source_font.get('basis'))
        source_size=float(obj.get('actualSourceCss',{}).get('fontSize',obj['fontSize']));native_sizes=sorted({size for run in row.get('runs',[]) if (size:=_font_size(run)) is not None})
        result.update(source_font_size=source_size,native_font_sizes=native_sizes)
        residuals=[{'text':s['text'],'dx':s['x']+offset[0]-n['x'],'dy':s['y']+offset[1]-n['y'],'dw':s['width']-n['width'],'dh':s['height']-n['height'],'source_raw':s.get('raw',s['text'])} for s,n in zip(source_glyphs,native_glyphs)]
        dx=statistics.median(r['dx'] for r in residuals);dy=statistics.median(r['dy'] for r in residuals)
        spread=max(max(abs(r['dx']-dx),abs(r['dy']-dy)) for r in residuals)
        size_error=max(max(abs(r['dw']),abs(r['dh'])) for r in residuals)
        width_ratios=[s['width']/n['width'] for s,n in zip(source_glyphs,native_glyphs) if s['width']>0 and n['width']>0]
        height_ratios=[s['height']/n['height'] for s,n in zip(source_glyphs,native_glyphs) if s['height']>0 and n['height']>0]
        result.update(translation={'dx':dx,'dy':dy},maximum_residual_from_translation=spread,maximum_glyph_size_difference=size_error,maximum_absolute_position_error=max(max(abs(r['dx']),abs(r['dy'])) for r in residuals),source_over_native_median_advance_ratio=statistics.median(width_ratios) if width_ratios else None,source_over_native_median_range_height_ratio=statistics.median(height_ratios) if height_ratios else None,native_css_fonts=[run.get('font') for run in row.get('runs',[])],source_css=obj.get('actualSourceCss',{}),residuals=residuals)
        if len(source_faces)!=1 or len(native_faces)!=1:
            result['category']='mixed_or_unresolved_physical_faces';continue
        if source_faces!=native_faces:
            result['category']='physical_face_mismatch';continue
        if len(native_sizes)!=1 or abs(native_sizes[0]-source_size)>.001:
            result['category']='font_size_mismatch';continue
        if any(g.get('rectCount',1)!=1 and g.get('width',0)>0 for g in source_glyphs):
            result['category']='source_grapheme_has_multiple_paint_ranges';continue
        if size_error>SIZE_TOLERANCE:
            result['category']='same_face_font_size_but_range_metrics_differ';continue
        if spread>POSITION_TOLERANCE:
            result['category']='nonuniform_spacing_or_position_residual'
            if any(r['source_raw']!=r['text'] for r in residuals):result['whitespace_normalization_present']=True
            continue
        if max(abs(dx),abs(dy))<=POSITION_TOLERANCE:
            result['category']='actual_glyphs_aligned';continue
        if 'clip-path' in cells[key].get('value','') or obj.get('sourceClip',{}).get('partial'):
            result['category']='uniform_translation_requires_fixed_clip';continue
        if _style(cells[key]).get('rotation','0') not in ('0','0.0'):
            result['category']='uniform_translation_requires_rotated_geometry';continue
        result.update(category='uniform_baseline_translation',safe_translation=True)
    return {'objects':results,'categories':dict(collections.Counter(result['category'] for result in results)),'source_text_objects':len(results),'safe_translation_objects':sum(result['safe_translation'] for result in results),'position_tolerance_px':POSITION_TOLERANCE,'glyph_size_tolerance_px':SIZE_TOLERANCE,'source_registration_offset':list(offset),'native_scale':native_info.get('scale',1)}


def translate(xml,analysis):
    assert abs(float(analysis.get('native_scale',1))-1)<1e-9,'Analytic label-rounding covariance requires native scale one'
    root=E.fromstring(xml);cells={cell.get('id'):cell for cell in root.iter('mxCell')};original={key:E.tostring(cell) for key,cell in cells.items()};changes=[]
    for result in analysis['objects']:
        if not result.get('safe_translation'):continue
        cell=cells[result['cell']];geo=cell.find('mxGeometry');assert geo is not None and geo.get('relative')!='1' and cell.get('parent')=='1','Only flat absolute poster text can be shifted'
        assert 'clip-path' not in cell.get('value',''),'Existing global source clip must stay fixed'
        before={key:float(geo.get(key,0)) for key in ('x','y')};delta=result['translation']
        # Integer changes commute with mxGraph's label rounding. The fractional
        # remainder comes directly from the original source/native Ranges, so
        # no intermediate PNG is needed to discover the rounding remainder.
        integer={'dx':int(round(delta['dx'])),'dy':int(round(delta['dy']))}
        remainder={key:delta[key]-integer[key] for key in ('dx','dy')}
        assert max(abs(value) for value in remainder.values())<=.500000001
        geo.set('x',format(before['x']+integer['dx'],'.10g'));geo.set('y',format(before['y']+integer['dy'],'.10g'))
        value=cell.get('value','');prefix=None
        if max(abs(value) for value in remainder.values())>1e-9:
            prefix='<span data-img2code-glyph-offset="v1-analytic" style="position:relative;left:'+format(remainder['dx'],'.10g')+'px;top:'+format(remainder['dy'],'.10g')+'px;">'
            cell.set('value',prefix+value+'</span>')
        changes.append({'cell':result['cell'],'before':before,'delta':delta,'geometry_delta':integer,'analytic_fractional_glyph_offset':remainder,'before_value':value,'wrapper_prefix':prefix,'physical_face':result['source_faces'][0],'font_size':result['source_font_size'],'maximum_source_glyph_residual':result['maximum_residual_from_translation']})
    proposed=E.tostring(root,encoding='unicode');verification=E.fromstring(proposed);changed={change['cell']:change for change in changes}
    for cell in verification.iter('mxCell'):
        key=cell.get('id')
        if key in changed:
            change=changed[key]
            if change['wrapper_prefix']:
                assert cell.get('value')==change['wrapper_prefix']+change['before_value']+'</span>'
                assert _plain(cell.get('value'))==_plain(change['before_value'])
                cell.set('value',change['before_value'])
            geo=cell.find('mxGeometry');prior_geo=E.fromstring(original[key]).find('mxGeometry')
            for axis in ('x','y'):
                if axis in prior_geo.attrib:geo.set(axis,prior_geo.get(axis))
                else:geo.attrib.pop(axis,None)
        assert E.canonicalize(E.tostring(cell,encoding='unicode'))==E.canonicalize(original[key].decode()),'A nontranslation graph/text/style/clip change occurred'
    return proposed,{'changes':changes,'all_other_shapes_assets_text_styles_clips_preserved':True,'logical_text_fonts_and_clips_preserved':True,'integer_geometry_commutes_with_label_rounding':True,'fractional_remainder_analytic_no_intermediate_render_search':True,'decision_basis':'Source/native physical face, CSS size, every grapheme Range size and uniform position residual; no image-score search','accepted':False}


def bridge_renderer_rounding(xml,after_geometry,changed_cells):
    """One analytic CSS remainder after mxGraph rounds label placement.

    The remainder is measured from actual glyph Ranges, bounded by one device
    pixel and never searched by image score. A relative span changes no text,
    font, object geometry, source clipping or layout flow.
    """
    root=E.fromstring(xml);cells={cell.get('id'):cell for cell in root.iter('mxCell')};changes=[]
    for result in after_geometry['objects']:
        if result['cell'] not in changed_cells or result['category']=='actual_glyphs_aligned':continue
        assert result.get('safe_translation') and result['category']=='uniform_baseline_translation','Geometry move caused a nonuniform or font/size mismatch'
        dx,dy=result['translation']['dx'],result['translation']['dy']
        assert max(abs(dx),abs(dy))<=1.01,'Renderer displacement exceeds a bounded label-rounding remainder'
        cell=cells[result['cell']];value=cell.get('value','');assert 'clip-path' not in value,'A clip reference box needs independent locking'
        prefix='<span data-img2code-glyph-offset="v1" style="position:relative;left:'+format(dx,'.10g')+'px;top:'+format(dy,'.10g')+'px;">'
        cell.set('value',prefix+value+'</span>')
        changes.append({'cell':result['cell'],'dx':dx,'dy':dy,'before_value':value,'wrapper_prefix':prefix,'physical_face':result['source_faces'][0],'font_size':result['source_font_size'],'maximum_actual_glyph_residual_spread':result['maximum_residual_from_translation']})
    proposed=E.tostring(root,encoding='unicode');restored=E.fromstring(proposed);lookup={item['cell']:item for item in changes}
    for cell in restored.iter('mxCell'):
        if cell.get('id') in lookup:
            change=lookup[cell.get('id')];assert cell.get('value')==change['wrapper_prefix']+change['before_value']+'</span>'
            assert _plain(cell.get('value'))==_plain(change['before_value'])
            cell.set('value',change['before_value'])
    assert E.canonicalize(E.tostring(restored,encoding='unicode'))==E.canonicalize(xml),'Residual bridge changed non-glyph-offset content'
    return proposed,{'changes':changes,'one_device_pixel_maximum_remainder':True,'logical_text_fonts_clips_and_graph_geometry_unchanged':True,'decision_basis':'Actual glyph Range remainder after deterministic geometry translation; no SSIM parameter search'}


def check_source_profile_v3(record,xml,native_info,dom,served,offset=(0.,0.),changed_cells=None):
    import auto_quality_source_vector_v2 as source_profile
    glyphs=analyze(dom,native_info,xml,offset)
    changed_cells=set(changed_cells or ())
    verified={obj['cell'] for obj in glyphs['objects'] if obj['cell'] in changed_cells and obj['category']=='actual_glyphs_aligned'}
    source=source_profile._html_coverage(dom,xml,served);paint=source_profile._html_paint_order(dom,xml)
    # Nominal text rectangles can differ only where every ACTUAL source/native
    # grapheme matches tightly. Nontext geometry and all other errors remain gates.
    allowed={'source_text_position_changed','source_object_size_changed'}
    remaining=[error for error in source['errors'] if not(error.get('reason') in allowed and error.get('cell') in verified)]
    nominal=[error for error in source['errors'] if error not in remaining]
    source={**source,'ok':not remaining,'errors':remaining,'nominal_text_box_differences_proven_by_actual_glyphs':nominal}
    unsupported=[issue for issue in dom.get('unsupported',[]) if issue.get('reason')!='css_stacking_order']
    failures=remaining+paint['errors']+[{'reason':'actual_source_native_glyph_mismatch','cell':obj['cell'],'category':obj['category']} for obj in glyphs['objects'] if obj['cell'] in changed_cells and obj['cell'] not in verified]
    if unsupported:failures.append({'reason':'unsupported_fresh_source_features','issues':unsupported})
    return {'supported':True,'ok':not failures,'profile':'fresh_html_actual_glyph_geometry_v3_prototype','failures':failures,'evidence':{'output_code_sha256':sha(xml.encode()),'source_code_sha256':record['source_code_sha256'],'actual_glyphs_verified_cells':sorted(verified),'changed_text_cells':sorted(changed_cells),'unchanged_text_uses_v2_source_geometry_gate':True,'source_coverage':source,'source_css_paint_order':paint,'actual_glyph_alignment':glyphs,'nominal_text_box_waivers_only_with_actual_glyph_proof':True,'position_tolerance_px':POSITION_TOLERANCE,'glyph_size_tolerance_px':SIZE_TOLERANCE}}


def source_region_quality(reference,source_png,dom):
    """Source/reference diagnostic only; never a generation gate or offset search."""
    import numpy as np
    from PIL import Image,ImageFilter
    from skimage.metrics import structural_similarity
    def rgb(blob):
        image=Image.open(io.BytesIO(blob)).convert('RGBA');white=Image.new('RGBA',image.size,'white');white.alpha_composite(image);return white.convert('RGB')
    original,source=rgb(reference),rgb(source_png)
    assert original.size==source.size,'Source/reference canvas differs'
    results={}
    for obj in dom['objects']:
        if obj['type']!='text' or not obj.get('actualSourceGlyphs'):continue
        chars=obj['actualSourceGlyphs'];key=str(obj['id']+1)
        left=min(c['x'] for c in chars);top=min(c['y'] for c in chars);right=max(c['x']+c['width'] for c in chars);bottom=max(c['y']+c['height'] for c in chars)
        clip=obj.get('sourceClip',{}).get('rect')
        if clip:
            left=max(left,clip['x']);top=max(top,clip['y']);right=min(right,clip['right']);bottom=min(bottom,clip['bottom'])
        box=[max(0,math.floor(left)-2),max(0,math.floor(top)-2),min(original.width,math.ceil(right)+2),min(original.height,math.ceil(bottom)+2)]
        if box[2]-box[0]<3 or box[3]-box[1]<3:
            results[key]={'reason':'no_verifiable_visible_source_region','box':box};continue
        a=np.array(original.crop(box));b=np.array(source.crop(box));window=min(7,min(a.shape[:2]));window-=int(window%2==0)
        score=float(structural_similarity(a,b,channel_axis=2,data_range=255,win_size=window))
        results[key]={'ssim':score,'exact_pixels':bool(np.array_equal(a,b)),'box':box,'decision_role':'Diagnostic only; candidate position comes exclusively from glyph Ranges and original-reference before/after crops decide whether to retain it'}
    return results


def registered_reference(reference,png,record,offset):
    from PIL import Image
    def rgb(blob):
        image=Image.open(io.BytesIO(blob)).convert('RGBA');white=Image.new('RGBA',image.size,'white');white.alpha_composite(image);return white.convert('RGB')
    original,native=rgb(reference),rgb(png)
    if original.size!=native.size:
        x,y=offset;assert x==int(x) and y==int(y),'A padded reference frame needs exact integer page offset'
        assert x>=0 and y>=0 and x+original.width<=native.width and y+original.height<=native.height,'Original reference does not fit native canvas'
        frame=Image.new('RGB',native.size,'white');frame.paste(original,(int(x),int(y)));original=frame
    return original,native


def reference_windows(before_info,after_info,cells,image_size):
    rows=lambda info:{row['cell']:[char for run in row.get('runs',[]) for char in run.get('chars',[]) if char.get('width',0)>0 and char.get('height',0)>0] for row in info.get('actual_text_positions',[])}
    before,after=rows(before_info),rows(after_info);windows={}
    for cell in cells:
        chars=before.get(cell,[])+after.get(cell,[])
        assert chars,'Moved object has no actual glyph crop'
        windows[cell]=[max(0,math.floor(min(c['x'] for c in chars))-2),max(0,math.floor(min(c['y'] for c in chars))-2),min(image_size[0],math.ceil(max(c['x']+c['width'] for c in chars))+2),min(image_size[1],math.ceil(max(c['y']+c['height'] for c in chars))+2)]
    return windows


def same_crop_metrics(reference,before_png,after_png,record,offset,windows):
    import numpy as np
    from skimage.metrics import structural_similarity
    original,before=registered_reference(reference,before_png,record,offset);_,after=registered_reference(reference,after_png,record,offset)
    assert original.size==before.size==after.size,'Before/after local comparison requires the same registered canvas'
    rows={}
    for cell,box in windows.items():
        a,b,c=[np.array(image.crop(box)) for image in (original,before,after)]
        assert min(a.shape[:2])>=3,'Moved glyph crop is too small for local comparison'
        window=min(7,min(a.shape[:2]));window-=int(window%2==0)
        old=float(structural_similarity(a,b,channel_axis=2,data_range=255,win_size=window));new=float(structural_similarity(a,c,channel_axis=2,data_range=255,win_size=window))
        rows[cell]={'box':box,'before_ssim':old,'after_ssim':new,'delta':new-old,'nonworsening':new+1e-7>=old,'same_fixed_crop_and_original_reference':True,'position_parameters_selected_by_metric':False}
    return rows


def revert_cells(original_xml,candidate_xml,cells_to_revert):
    original={cell.get('id'):cell for cell in E.fromstring(original_xml).iter('mxCell')};root=E.fromstring(candidate_xml);parents={cell:parent for parent in root.iter() for cell in parent}
    for cell in list(root.iter('mxCell')):
        if cell.get('id') in cells_to_revert:
            parent=parents[cell];index=list(parent).index(cell);parent.remove(cell);parent.insert(index,copy.deepcopy(original[cell.get('id')]))
    return E.tostring(root,encoding='unicode')


def run_case(id,propose=False,full_common=False):
    from PIL import Image
    from native_worker import native
    from auto_quality_common import checked,resource_checks,image_quality,require_rendered_text
    db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True);state,raw=db.execute('select state,output_record from jobs where id=?',(id,)).fetchone();record=json.loads(raw)
    assert record['source_format']=='html' and record['category']=='poster'
    xml=checked(R,record['code_file'],record['code_sha256']).decode();reference=checked(R,record['original_reference'],record['source_image_sha256']);resource_checks(R,record,xml,reference)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]
    work=W/'prototype/html_actual_text_alignment'/id/(record['code_sha256']+'_'+record['image_sha256'][:16])/stamp;work.mkdir(parents=True,exist_ok=True)
    report={'id':id,'at':now(),'full_common_text_gate_run':full_common,'requires_full_common_before_acceptance':True,'timings_seconds':{},'input_state':state,'input_code_sha256':record['code_sha256'],'input_image_sha256':record['image_sha256'],'record_sha256':sha(raw.encode()),'work':str(work.relative_to(R)),'accepted':False,'canonical_changed':False}
    timing=time.monotonic();dom,served,source_png,source_metadata=capture_source(record,work);report['timings_seconds']['source_capture']=time.monotonic()-timing
    source_positions=[{'cell':str(obj['id']+1),'runs':[{'chars':obj['actualSourceGlyphs']}]} for obj in dom['objects'] if obj['type']=='text' and obj.get('actualSourceGlyphs')]
    timing=time.monotonic();report['source_reference_quality']=image_quality(reference,source_png,record,source_positions if full_common else None);report['timings_seconds']['source_reference_diagnostic']=time.monotonic()-timing
    report['source_metadata']=source_metadata
    model=E.fromstring(xml).find('.//mxGraphModel');width,height=[int(round(float(model.get(key,0)))) for key in ('pageWidth','pageHeight')]
    renderer=W/'rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
    timing=time.monotonic();baseline=native.native_job(xml,width,height,180,renderer,8192,runtime);report['timings_seconds']['baseline_native_render']=time.monotonic()-timing;assert baseline['ok'];info=baseline['native_render'];(work/'baseline.native.png').write_bytes(baseline['png']);(work/'baseline.native_render.json').write_text(json.dumps(info,indent=2)+'\n')
    offset=registration(record,Image.open(io.BytesIO(reference)).size,[width,height],dom,xml);analysis=analyze(dom,info,xml,offset);report['analysis']=analysis
    report['registration']={'offset':list(offset),'source_size':list(Image.open(io.BytesIO(reference)).size),'native_canvas':[width,height],'nontext_geometry_proof_used':Image.open(io.BytesIO(reference)).size!=(width,height) and not(record.get('native_canvas_contract') or record.get('native_page_padding'))}
    native_record=copy.deepcopy(record)
    if Image.open(io.BytesIO(reference)).size!=(width,height) and not(native_record.get('native_canvas_contract') or native_record.get('native_page_padding')):native_record['native_canvas_contract']={'offset':list(offset),'basis':'fresh_source_nontext_geometry_exact'}
    timing=time.monotonic()
    try:report['baseline_reference_quality']=image_quality(reference,baseline['png'],native_record,info.get('actual_text_positions') if full_common else None)
    except ValueError as error:report['baseline_reference_quality']={'ok':False,'ssim_1024':None,'error':str(error),'requires_canvas_registration_or_repair':True}
    report['timings_seconds']['baseline_reference_diagnostic']=time.monotonic()-timing
    timing=time.monotonic();regions=source_region_quality(reference,source_png,dom);report['source_reference_text_regions']=regions;report['timings_seconds']['source_region_diagnostics']=time.monotonic()-timing
    eligible=analysis;report['translation_eligibility']=eligible
    if propose and analysis['safe_translation_objects']:
        if info.get('selected_image')!='declared_first_page':
            report['proposal_blocked']='Repair/register the complete native canvas before a same-crop translation comparison'
        else:
            proposal_started=time.monotonic();candidate,proof=translate(xml,eligible);fresh=native.native_job(candidate,width,height,180,renderer,8192,runtime);assert fresh['ok'];require_rendered_text(candidate,fresh['native_render'])
            after=analyze(dom,fresh['native_render'],candidate,offset);changed={change['cell'] for change in proof['changes']}
            (work/'analytic_range_candidate.drawio').write_text(candidate);(work/'analytic_range_candidate.native.png').write_bytes(fresh['png']);(work/'analytic_range_candidate.native_render.json').write_text(json.dumps(fresh['native_render'],indent=2)+'\n');(work/'analytic_range_candidate.analysis.json').write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n')
            bridged,bridge=bridge_renderer_rounding(candidate,after,changed)
            proof['renderer_label_rounding_bridge']=bridge
            if bridge['changes']:
                candidate=bridged;fresh=native.native_job(candidate,width,height,180,renderer,8192,runtime);assert fresh['ok'];require_rendered_text(candidate,fresh['native_render']);after=analyze(dom,fresh['native_render'],candidate,offset)
            assert all(obj['category']=='actual_glyphs_aligned' for obj in after['objects'] if obj['cell'] in changed),'Moved glyphs did not match current source Ranges after bounded renderer rounding bridge'
            assert fresh['native_render'].get('selected_image')=='declared_first_page','A translated glyph introduced visible page overflow'
            windows=reference_windows(info,fresh['native_render'],changed,[width,height]);rejected=[];passes=[]
            for pass_index in range(4):
                local=same_crop_metrics(reference,baseline['png'],fresh['png'],native_record,offset,{cell:windows[cell] for cell in changed})
                bad={cell for cell,row in local.items() if not row['nonworsening']};passes.append({'pass':pass_index,'cells':local,'rejected_cells':sorted(bad)})
                if not bad:break
                rejected.extend({'cell':cell,'reason':'same_original_same_crop_local_fidelity_regressed','metrics':local[cell]} for cell in sorted(bad))
                candidate=revert_cells(xml,candidate,bad);changed-=bad
                fresh=native.native_job(candidate,width,height,180,renderer,8192,runtime);assert fresh['ok'];after=analyze(dom,fresh['native_render'],candidate,offset)
            else:
                # This is monotone rollback, never a parameter search. If overlapping
                # crop interactions do not settle, retain all remaining original cells.
                candidate=revert_cells(xml,candidate,changed);rejected.extend({'cell':cell,'reason':'local_crop_rollback_did_not_settle'} for cell in sorted(changed));changed=set()
                fresh=native.native_job(candidate,width,height,180,renderer,8192,runtime);assert fresh['ok'];after=analyze(dom,fresh['native_render'],candidate,offset)
            proof['proposed_changes']=proof['changes'];proof['changes']=[change for change in proof['changes'] if change['cell'] in changed]
            proof['rejected_changes']=rejected;proof['same_crop_before_after_validation']=passes;proof['renderer_label_rounding_bridge']['changes']=[change for change in proof['renderer_label_rounding_bridge']['changes'] if change['cell'] in changed]
            assert all(obj['category']=='actual_glyphs_aligned' for obj in after['objects'] if obj['cell'] in changed),'A kept glyph translation lost actual Range agreement'
            old_fonts={row['cell']:row['fonts'] for row in info['actual_platform_font_usage']};new_fonts={row['cell']:row['fonts'] for row in fresh['native_render']['actual_platform_font_usage']};assert old_fonts==new_fonts,'Physical font/glyph counts changed during translation'
            report['timings_seconds']['range_generation_render_and_local_nonregression']=time.monotonic()-proposal_started
            timing=time.monotonic()
            try:quality_after=image_quality(reference,fresh['png'],native_record,fresh['native_render'].get('actual_text_positions') if full_common else None)
            except ValueError as error:quality_after={'ok':False,'ssim_1024':None,'error':str(error),'requires_canvas_registration_or_repair':True}
            report['timings_seconds']['candidate_reference_diagnostic']=time.monotonic()-timing
            report['proposal']={'output_code_sha256':sha(candidate.encode()),'output_image_sha256':sha(fresh['png']),'proof':proof,'analysis_after':after,'reference_quality_after':quality_after,'source_profile_v3':check_source_profile_v3(record,candidate,fresh['native_render'],dom,served,offset,changed),'all_actual_fonts_and_glyph_counts_unchanged':True}
            (work/'candidate.drawio').write_text(candidate);(work/'candidate.native.png').write_bytes(fresh['png']);(work/'candidate.native_render.json').write_text(json.dumps(fresh['native_render'],indent=2)+'\n')
    current=db.execute('select output_record from jobs where id=?',(id,)).fetchone()[0];report['current_record_unchanged']=current==raw
    (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    result={'id':id,'work':report['work'],'input_code_sha256':record['code_sha256'],'categories':analysis['categories'],'safe_translation_objects':analysis['safe_translation_objects'],'range_eligible_translation_objects':eligible['safe_translation_objects'],'source_reference_ok':report['source_reference_quality']['ok'],'source_reference_ssim':report['source_reference_quality']['ssim_1024'],'baseline_reference_ssim':report['baseline_reference_quality']['ssim_1024'],'proposal_generated':'proposal' in report,'proposal_blocked':report.get('proposal_blocked'),'current_record_unchanged':report['current_record_unchanged'],'accepted':False,'canonical_changed':False,'full_common_text_gate_run':full_common,'timings_seconds':report['timings_seconds']}
    if 'proposal' in report:result.update(changed_cells=len(report['proposal']['proof']['changes']),after_reference_ssim=report['proposal']['reference_quality_after']['ssim_1024'],source_profile_v3_ok=report['proposal']['source_profile_v3']['ok'])
    print(json.dumps(result),flush=True);return result


def local_exception_ids(limit):
    db=sqlite3.connect(f'file:{W}/jobs.sqlite?mode=ro',uri=True)
    rows=db.execute("""select distinct j.id from jobs j join auto_quality_exceptions_v1 e on e.id=j.id and e.code_hash=json_extract(j.output_record,'$.code_sha256') and e.image_hash=json_extract(j.output_record,'$.image_sha256') where j.format='html' and json_extract(j.output_record,'$.category')='poster' and j.state in ('rendered','needs_quality_repair','harness_review_pending') and j.worker_pid is null and e.state='pending' and e.reason like '%local_text_line_ssim_below_0.55%' order by j.id limit ?""",(limit,)).fetchall();db.close()
    return [row[0] for row in rows]


def _run(task):
    id,propose,full_common=task
    try:return run_case(id,propose,full_common)
    except Exception as error:
        result={'id':id,'error':repr(error),'accepted':False,'canonical_changed':False};print(json.dumps(result),flush=True);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--id',action='append',default=[]);parser.add_argument('--current-local-exceptions',type=int,default=0);parser.add_argument('--workers',type=int,default=2);parser.add_argument('--propose',action='store_true');parser.add_argument('--full-common',action='store_true',help='Also run the expensive complete common local-text gate diagnostically; final QA must always run it before acceptance');args=parser.parse_args()
    ids=list(dict.fromkeys(args.id+local_exception_ids(args.current_local_exceptions))) if args.current_local_exceptions else args.id
    if not ids:parser.error('Provide --id or a nonempty --current-local-exceptions cohort')
    if not 1<=args.workers<=8:parser.error('workers must be 1..8')
    started=time.monotonic();results=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(_run,[(id,args.propose,args.full_common) for id in ids]):results.append(result)
    categories=collections.Counter()
    for result in results:categories.update(result.get('categories',{}))
    batch={'at':now(),'cases':results,'categories':dict(categories),'elapsed_seconds':time.monotonic()-started,'accepted':0,'canonical_changed':False,'jobs_changed':False}
    parent=W/'prototype/html_actual_text_alignment';parent.mkdir(parents=True,exist_ok=True);path=parent/('batch_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]+'.json');path.write_text(json.dumps(batch,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'batch':str(path.relative_to(R)),'cases':len(results),'categories':dict(categories),'elapsed_seconds':batch['elapsed_seconds'],'accepted':0,'canonical_changed':False,'jobs_changed':False}),flush=True)

if __name__=='__main__':main()
