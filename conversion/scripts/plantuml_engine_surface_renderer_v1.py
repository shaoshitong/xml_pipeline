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
    if re.search(r'https?://[^;"\s]+\.(?:png|jpe?g|webp)', xml, re.I):
        raise ValueError('external raster references are disallowed; embedded source assets are permitted for conversion')
    opts = dict(headless=True, args=['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text'])
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
    from playwright.sync_api import sync_playwright
    xml=source.read_text();root=ET.fromstring(xml)
    if root.tag not in ('mxfile','mxGraphModel'):
        raise ValueError('drawio requires mxfile or mxGraphModel root')
    if re.search(r'https?://[^;"\s]+\.(?:png|jpe?g|webp)',xml,re.I):
        raise ValueError('external raster references are disallowed; embedded source assets are permitted for conversion')
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
    attrs={k:'plantumlSourceInspection'+k.title()+'V1' for k in ('x','y','width','height')}
    if not all(model.get(a) is not None for a in attrs.values()):raise ValueError('Explicit source-only inspection declaration required')
    plan={k:int(model.get(a)) for k,a in attrs.items()}
    left,top=-plan['x'],-plan['y'];pw,ph=plan['width'],plan['height']
    if not (left>=32 and top>=32 and left+canvas_w+32<=pw and top+canvas_h+32<=ph):raise ValueError('Source inspection must include original viewport and 32px guard')
    if max(pw,ph)>8192 or pw*ph>64000000:raise ValueError('Source inspection exceeds pixel budget')
    installed=sorted(Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),
        key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
    opts={'headless':True,'args':['--disable-dev-shm-usage']}
    opts['executable_path']='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
    if proxy:opts['proxy']={'server':proxy}
    trace=[]
    with sync_playwright()as p:
        browser=p.chromium.launch(**opts)
        page=browser.new_page(viewport={'width':max(pw,640),'height':max(ph,480)},
                              device_scale_factor=1)
        page.set_default_timeout(30000)
        page.on('pageerror',lambda error:trace.append({'kind':'pageerror','text':str(error)[:2000]}))
        page.on('requestfailed',lambda req:trace.append({'kind':'requestfailed','url':req.url,'error':req.failure}))
        page.on('console',lambda msg:trace.append({'kind':'console','type':msg.type,'text':msg.text[:1200]})
                if msg.type in ('error','warning') else None)
        page.set_content('<!doctype html><html><head><style>html,body{margin:0;padding:0;background:white;}'+
            '#surface{position:relative;overflow:hidden;background:white;}#graph{position:absolute;left:0;top:0;margin:0;padding:0;border:0;overflow:visible;background:transparent;'+
            f'width:{canvas_w}px;height:{canvas_h}px;left:{left}px;top:{top}px;'+
            '}</style></head><body><div id="surface"><div id="graph"></div></div></body></html>')
        page.evaluate('''()=>{window.onDrawioViewerLoad=()=>{window.viewerBundleReady=true};
            window.mxLoadResources=false;window.mxLoadStylesheets=false;}''')
        page.add_script_tag(path=str(bundle))
        page.wait_for_function("typeof GraphViewer==='function'")
        page.evaluate('''xml=>{
            const d=document.getElementById('graph');
            d.setAttribute('data-mxgraph',JSON.stringify({xml,nav:false,resize:false,
              responsive:false,'auto-fit':false,'auto-origin':false,'browser-translate':false,
              'allow-zoom-in':false,'allow-zoom-out':false,center:false,border:0,zoom:1,
              lightbox:false,editable:false,'dark-mode':'light','show-note-icons':false,'toolbar-nohide':1}));
            GraphViewer.createViewerForElement(d,v=>{window.evalViewer=v});
        }''',xml)
        page.wait_for_function('window.evalViewer && window.evalViewer.graph && window.evalViewer.graph.view')
        info=page.evaluate('''dims=>{
            const v=window.evalViewer,g=v.graph,d=document.getElementById('graph');
            g.sizeDidChange=function(){};
            g.view.scaleAndTranslate(1,0,0);g.view.validate();
            d.style.width=dims[0]+'px';d.style.height=dims[1]+'px';
            d.style.border='0';d.style.padding='0';d.style.overflow='visible';const surface=document.getElementById('surface');surface.style.width=dims[2]+'px';surface.style.height=dims[3]+'px';
            d.scrollLeft=0;d.scrollTop=0;
            const b=g.getGraphBounds(),t=g.view.translate;
            return {graphBounds:{x:b.x,y:b.y,width:b.width,height:b.height},
              scale:g.view.scale,translate:{x:t.x,y:t.y},
              cells:Object.keys(g.model.cells).length,
              svgCount:d.querySelectorAll('svg').length,
              foreignObjectCount:d.querySelectorAll('foreignObject').length,
              version:typeof EditorUi==='undefined'?null:EditorUi.VERSION};
        }''',[canvas_w,canvas_h,pw,ph])
        page.evaluate('document.fonts.ready')
        info['loaded_fonts']=page.evaluate('Array.from(document.fonts).map(f=>({family:f.family,status:f.status}))')
        page.evaluate('window.evalViewer.graph.refresh();window.evalViewer.graph.view.validate()')
        # getSvg temporarily revalidates states/container CSS. Perform it before
        # final inspection clips, font provenance, glyph positions and pixels.
        # Independent native SVG export gives a second editable render artifact.
        try:
            svg=page.evaluate('''()=>new XMLSerializer().serializeToString(
                window.evalViewer.graph.getSvg('#ffffff',1,0))''')
            (source.parent/'render.svg').write_text(svg)
            info['svg_export']=str(source.parent/'render.svg')
        except Exception as exc:info['svg_export_error']=str(exc)[:1000]
        info['native_outer_svg_inspection_clip_policy']=page.evaluate("""()=>{const g=window.evalViewer.graph,e=g.view.canvas.ownerSVGElement;if(!e||e.parentElement.id!=='graph')throw Error('One actual top-level native graph SVG required');const d=document.getElementById('graph'),containerBefore=getComputedStyle(d).overflow;const before=getComputedStyle(e).overflow,attrs=[...e.attributes].map(a=>[a.name,a.value]),xml=mxUtils.getXml(new mxCodec().encode(g.model));e.style.setProperty('overflow','visible','important');d.style.setProperty('overflow','visible','important');if(getComputedStyle(e).overflow!=='visible'||getComputedStyle(d).overflow!=='visible'||mxUtils.getXml(new mxCodec().encode(g.model))!==xml)throw Error('Inspection root clip policy changed model');return {original_computed_overflow:before,original_container_computed_overflow:containerBefore,inspection_computed_overflow:'visible',inspection_container_computed_overflow:'visible',root_attributes_before:attrs,only_actual_graph_outer_SVG_and_container_clips_disabled:true,model_unchanged:true,export_clip_is_external_recorded_source_surface:true,official_viewer_config_toolbar_nohide:1};}""")
        info.update(page.evaluate('() => { const g=window.evalViewer.graph,b=g.getGraphBounds(); return {graphBounds:{x:b.x,y:b.y,width:b.width,height:b.height}}; }'))
        font_nodes=page.evaluate("""()=>{const g=window.evalViewer.graph,rows=[];for(const c of Object.values(g.model.cells)){const label=g.getLabel(c),s=g.view.getState(c);if(typeof label!=='string'||!label.trim()||!s?.text?.node)continue;const id='physical-font-evidence-'+rows.length;s.text.node.id=id;const walker=document.createTreeWalker(s.text.node,NodeFilter.SHOW_TEXT),parents=new Set();while(walker.nextNode())if(walker.currentNode.textContent.length)parents.add(walker.currentNode.parentElement);const selectors=[...parents].map((el,i)=>{el.id=id+'_'+i;return '#'+el.id});rows.push({cell:c.id,selectors});}return rows;}""")
        cdp=page.context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');doc_node=cdp.send('DOM.getDocument',{'depth':1})['root']['nodeId']
        for font_node in font_nodes:
            seen_fonts={}
            for selector in font_node['selectors']:
                node=cdp.send('DOM.querySelector',{'nodeId':doc_node,'selector':selector})['nodeId']
                for font in cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']:
                    key=(font['postScriptName'],font['isCustomFont']);seen_fonts.setdefault(key,{**font,'glyphCount':0})['glyphCount']+=font['glyphCount']
            font_node['fonts']=list(seen_fonts.values())
        cdp.detach();info['actual_platform_font_usage']=font_nodes
        info['actual_text_positions']=page.evaluate("""()=>{const g=window.evalViewer.graph,rows=[];for(const c of Object.values(g.model.cells)){const s=g.view.getState(c);if(!s?.text?.node)continue;const w=document.createTreeWalker(s.text.node,NodeFilter.SHOW_TEXT),runs=[];while(w.nextNode()){const n=w.currentNode;if(!n.textContent)continue;const cs=getComputedStyle(n.parentElement),chars=[];for(const {segment,index} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);const b=r.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}runs.push({text:n.textContent,font:cs.font,fontKerning:cs.fontKerning,fontFeatureSettings:cs.fontFeatureSettings,letterSpacing:cs.letterSpacing,lineHeight:cs.lineHeight,chars});}if(runs.length)rows.push({cell:c.id,runs});}return rows;}""")

        # Browser element bounds include stencil paths outside nominal mxCell geometry.
        paint=page.evaluate("()=>{const d=document.getElementById('graph'),origin=d.getBoundingClientRect(),g=window.evalViewer.graph,rows=[],unsupported=[],shadows=[],known=new Map;const wanted={shadow:'1',shadowColor:'#000000',shadowOpacity:'40',shadowOffsetX:'4',shadowOffsetY:'4',shadowBlur:'2'};\n const probe=document.createElement('div');probe.style.filter='drop-shadow(rgba(0,0,0,0.4) 4px 4px 2px)';document.body.append(probe);const expected=getComputedStyle(probe).filter;probe.remove();\n for(const c of Object.values(g.model.cells)){const state=g.view.getState(c),style=g.getCellStyle(c);if(style.shadow!=='1'&&style.shadow!==1)continue;const node=state?.shape?.node;if(!node||!Object.entries(wanted).every(([k,v])=>String(style[k])===v)||getComputedStyle(node).filter!==expected||c.edge){unsupported.push({cell:c.id,reason:'actual_native_shadow_not_original_PlantUML_operator_profile'});continue;}known.set(node,c.id);shadows.push({cell:c.id,computed_filter:getComputedStyle(node).filter,exact_declared_parameters:wanted,actual_primary_shape_css_filter:true});}\n const shadowOf=e=>{let found=null;for(let n=e;n&&n!==d;n=n.parentElement)if(getComputedStyle(n).filter!=='none'){if(!known.has(n)||found!==null){unsupported.push({tag:n.localName,filter:getComputedStyle(n).filter,reason:'unproved_or_nested_filter'});return false;}found=known.get(n);}return found;};\n for(const e of d.querySelectorAll('svg path,svg rect,svg circle,svg ellipse,svg line,svg polyline,svg polygon,svg image,svg text,svg use')){if(e.closest('defs,clipPath,mask,pattern,marker,symbol'))continue;const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')continue;const r=e.getBoundingClientRect();if(!r.width&&!r.height)continue;const m=e.getScreenCTM?.(),scale=m?Math.max(Math.hypot(m.a,m.b),Math.hypot(m.c,m.d)):1,stroke=cs.stroke==='none'?0:(parseFloat(cs.strokeWidth)||0),owner=shadowOf(e),pad=2+stroke*scale*Math.max(1,parseFloat(cs.strokeMiterlimit)||4)+(owner?16:0);if(cs.boxShadow!=='none'||cs.textShadow!=='none')unsupported.push({tag:e.tagName,reason:'unproved_box_or_text_shadow'});rows.push({x:r.x-origin.x-pad,y:r.y-origin.y-pad,width:r.width+2*pad,height:r.height+2*pad,source_shadow_owner:owner});}\n for(const c of Object.values(g.model.cells)){const n=g.view.getState(c)?.text?.node;if(!n)continue;const walker=document.createTreeWalker(n,NodeFilter.SHOW_TEXT);while(walker.nextNode()){const text=walker.currentNode;if(!text.textContent)continue;const range=document.createRange();range.selectNodeContents(text);for(const r of range.getClientRects())rows.push({x:r.x-origin.x-2,y:r.y-origin.y-2,width:r.width+4,height:r.height+4});}}\n for(const e of d.querySelectorAll('*')){const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')continue;if(cs.filter!=='none'&&!known.has(e))unsupported.push({tag:e.tagName,reason:'non_primary_or_undeclared_filter',filter:cs.filter});if(cs.boxShadow!=='none'||cs.textShadow!=='none')unsupported.push({tag:e.tagName,reason:'unproved_box_or_text_shadow'});}\n if(!rows.length)return{bounds:null,unsupported,source_shadow_effects:shadows};const x=Math.min(...rows.map(r=>r.x)),y=Math.min(...rows.map(r=>r.y));return{bounds:{x,y,width:Math.max(...rows.map(r=>r.x+r.width))-x,height:Math.max(...rows.map(r=>r.y+r.height))-y},element_count:rows.length,unsupported,source_shadow_effects:shadows,filter_bounds_policy:'actual_exact_PlantUML_source_operator_CSS_with_6sigma_plus_offset_padding_and_full_pixel_guard',not_pixel_exact_alias:true};}")
        info['native_actual_clip_ancestry']=page.evaluate("""()=>{const e=document.querySelector('#graph svg path,#graph svg rect'),rows=[];for(let p=e;p;p=p.parentElement){const c=getComputedStyle(p),b=p.getBoundingClientRect();rows.push({tag:p.localName,id:p.id,style:p.getAttribute('style'),overflow:c.overflow,overflowX:c.overflowX,overflowY:c.overflowY,clipPath:c.clipPath,clip:c.clip,rect:[b.x,b.y,b.width,b.height]});}return rows;}""")
        if page.evaluate("()=>{const g=window.evalViewer.graph;return getComputedStyle(g.container).overflow==='visible'&&getComputedStyle(g.view.canvas.ownerSVGElement).overflow==='visible'}") is not True:raise ValueError('Native inspection graph clips were restored by renderer')
        info['actual_dom_paint_bounds']=paint
        if paint['unsupported']:raise ValueError('Native filter/shadow effects require an explicit painted-bounds audit')
        from PIL import Image
        import numpy as np
        import copy
        bounds=paint['bounds'];inspection_right=plan['x']+pw;inspection_bottom=plan['y']+ph
        if bounds and not (bounds['x']>=plan['x'] and bounds['y']>=plan['y'] and bounds['x']+bounds['width']<=inspection_right and bounds['y']+bounds['height']<=inspection_bottom):raise ValueError('Native actual DOM paint bounds exceed independently declared SOURCE inspection')
        info['actual_native_dom_bounds_contained_in_source_inspection']=True
        encoded_before=page.evaluate("()=>mxUtils.getXml(new mxCodec().encode(window.evalViewer.graph.model))")
        probe=page.locator('#surface').screenshot(animations='disabled');(source.parent/'render.inspection.png').write_bytes(probe)
        im=Image.open(io.BytesIO(probe)).convert('RGB');arr=np.asarray(im);mask=np.min(arr,axis=2)<255
        boundary=mask.copy();boundary[32:-32,32:-32]=False
        if boundary.any():raise ValueError('Native paint touches independently declared full-source inspection guard')
        # Export is the ORIGINAL SOURCE surface, not a target/content bbox.
        # The same fixed DOM is observed throughout; no geometry/view moves.
        final=page.screenshot(type='png',clip={'x':left,'y':top,'width':canvas_w,'height':canvas_h},animations='disabled')
        actual=Image.open(io.BytesIO(final)).convert('RGB');expected=im.crop((left,top,left+canvas_w,top+canvas_h))
        if expected.size!=actual.size or expected.tobytes()!=actual.tobytes():raise ValueError('SOURCE viewport export differs from exact fixed native inspection crop')
        output.write_bytes(final)
        outside=mask.copy();outside[top:top+canvas_h,left:left+canvas_w]=False
        raw_text=copy.deepcopy(info['actual_text_positions'])
        for row in info['actual_text_positions']:
            for run in row['runs']:
                for ch in run['chars']:ch['x']-=left;ch['y']-=top
        view=page.evaluate("()=>{const g=window.evalViewer.graph;return {scale:g.view.scale,translate:{x:g.view.translate.x,y:g.view.translate.y},xml:mxUtils.getXml(new mxCodec().encode(g.model))}}")
        if view['scale']!=1 or view['translate']!={'x':0,'y':0} or view['xml']!=encoded_before:raise ValueError('SOURCE viewport export modified native geometry/model/view')
        svgroot=ET.fromstring((source.parent/'render.svg').read_text())
        info.update(export_mode='original_official_PlantUML_PNG_surface_complete_native_paint_and_shadow_v1',paint_safety_frame='full_unclipped_native_paint_inspection_viewport',source_inspection_plan=plan,source_viewport=[0,0,canvas_w,canvas_h],strict_outside_inspection_pixels=int(boundary.sum()),unclipped_native_outside_source_viewport_pixels=int(outside.sum()),native_inspection_to_export_pixels_exact=True,complete_native_model_paint_inspected=True,model_geometry_preserved=True,graph_view_unchanged=True,actual_text_positions_full_inspection=raw_text,actual_text_positions_frame='original_source_viewport',full_native_inspection_png_sha256=hashlib.sha256(probe).hexdigest(),native_svg_export_sha256=hashlib.sha256((source.parent/'render.svg').read_bytes()).hexdigest(),native_svg_export_frame={k:svgroot.get(k) for k in ('width','height','viewBox')},export_viewport=[canvas_w,canvas_h],original_declared_page=[canvas_w,canvas_h],native_model_encoded_before_after_sha256=hashlib.sha256(encoded_before.encode()).hexdigest())
        info['page_capture_policy']='actual_native_fixed_full_inspection_DOM_crop_at_recorded_original_SOURCE_surface_viewport'
        browser.close()
    (source.parent/'viewer.trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2))
    return {'renderer_profile':'tikz_complete_native_fixed_inspection_export_v1','renderer_module_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'renderer':'official draw.io viewer-static.min.js GraphViewer in local Chromium',
      'viewer_bundle_sha256':hashlib.sha256(bundle.read_bytes()).hexdigest(),
      'viewer_bundle_url':url,'canvas':[canvas_w,canvas_h],**info,
      'vertices':sum(c.get('vertex')=='1'for c in root.iter('mxCell')),
      'edges':sum(c.get('edge')=='1'for c in root.iter('mxCell')),
      'browser_trace':trace,
      'renderer_note':'Actual upstream Graph renders geometry/styles/text. No custom mxCell approximation; model coordinates preserved on declared page.'}



def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['drawio'],required=True);ap.add_argument('--source',required=True);ap.add_argument('--width',type=int,required=True);ap.add_argument('--height',type=int,required=True);ap.add_argument('--reference');ap.add_argument('--proxy',default='');a=ap.parse_args();source=Path(a.source).resolve();output=source.parent/'render.png';result={'ok':False,'kind':a.kind,'source':str(source),'output':str(output)}
 try:result.update(drawio_png(source,output,a.width,a.height,a.proxy));result['ok']=True
 except Exception as e:result['error']=type(e).__name__+': '+str(e)
 (source.parent/'render.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result),flush=True);return 0 if result['ok'] else 1
if __name__=='__main__':sys.exit(main())
