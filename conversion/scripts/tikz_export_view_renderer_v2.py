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
    installed=sorted(Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),
        key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
    opts={'headless':True,'args':['--disable-dev-shm-usage','--disable-gpu','--disable-lcd-text']}
    opts['executable_path']='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
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
            '#surface{position:relative;overflow:hidden;background:white;}#graph{position:absolute;left:0;top:0;margin:0;padding:0;border:0;overflow:visible;background:transparent;'+
            f'width:{canvas_w}px;height:{canvas_h}px;'+
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
              lightbox:false,editable:false,'dark-mode':'light','show-note-icons':false}));
            GraphViewer.createViewerForElement(d,v=>{window.evalViewer=v});
        }''',xml)
        page.wait_for_function('window.evalViewer && window.evalViewer.graph && window.evalViewer.graph.view')
        info=page.evaluate('''dims=>{
            const v=window.evalViewer,g=v.graph,d=document.getElementById('graph');
            g.sizeDidChange=function(){};
            g.view.scaleAndTranslate(1,0,0);g.view.validate();
            d.style.width=dims[0]+'px';d.style.height=dims[1]+'px';
            d.style.border='0';d.style.padding='0';d.style.overflow='visible';const surface=document.getElementById('surface');surface.style.width=dims[0]+'px';surface.style.height=dims[1]+'px';
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
        info['loaded_fonts']=page.evaluate('Array.from(document.fonts).map(f=>({family:f.family,status:f.status}))')
        page.evaluate('window.evalViewer.graph.refresh();window.evalViewer.graph.view.validate()')
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

        page.locator('#surface').screenshot(path=str(output),animations='disabled',timeout=20000)
        (source.parent/'render.declared.png').write_bytes(output.read_bytes())
        # Independent native SVG export gives a second editable render artifact.
        try:
            svg=page.evaluate('''()=>new XMLSerializer().serializeToString(
                window.evalViewer.graph.getSvg('#ffffff',1,0))''')
            (source.parent/'render.svg').write_text(svg)
            info['svg_export']=str(source.parent/'render.svg')
        except Exception as exc:info['svg_export_error']=str(exc)[:1000]
        # Browser element bounds include stencil paths outside nominal mxCell geometry.
        paint=page.evaluate("""()=>{const d=document.getElementById('graph'),origin=d.getBoundingClientRect(),rows=[],unsupported=[];for(const e of d.querySelectorAll('svg path,svg rect,svg circle,svg ellipse,svg line,svg polyline,svg polygon,svg image,svg text,svg use')){if(e.closest('defs,clipPath,mask,pattern,marker,symbol'))continue;const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')continue;const r=e.getBoundingClientRect();if(!r.width&&!r.height)continue;const m=e.getScreenCTM?.();const scale=m?Math.max(Math.hypot(m.a,m.b),Math.hypot(m.c,m.d)):1;const stroke=cs.stroke==='none'?0:(parseFloat(cs.strokeWidth)||0);const pad=2+stroke*scale*Math.max(1,parseFloat(cs.strokeMiterlimit)||4);if(cs.filter!=='none'||cs.boxShadow!=='none')unsupported.push({tag:e.tagName,filter:cs.filter,boxShadow:cs.boxShadow});rows.push({x:r.x-origin.x-pad,y:r.y-origin.y-pad,width:r.width+2*pad,height:r.height+2*pad});}const g=window.evalViewer.graph;for(const c of Object.values(g.model.cells)){const n=g.view.getState(c)?.text?.node;if(!n)continue;const walker=document.createTreeWalker(n,NodeFilter.SHOW_TEXT);while(walker.nextNode()){const text=walker.currentNode;if(!text.textContent)continue;const range=document.createRange();range.selectNodeContents(text);for(const r of range.getClientRects())rows.push({x:r.x-origin.x-2,y:r.y-origin.y-2,width:r.width+4,height:r.height+4});}}for(const e of d.querySelectorAll('*')){const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')continue;if(cs.filter!=='none'||cs.boxShadow!=='none'||cs.textShadow!=='none')unsupported.push({tag:e.tagName,filter:cs.filter,boxShadow:cs.boxShadow,textShadow:cs.textShadow});}if(!rows.length)return {bounds:null,unsupported};const x=Math.min(...rows.map(r=>r.x)),y=Math.min(...rows.map(r=>r.y));return {bounds:{x,y,width:Math.max(...rows.map(r=>r.x+r.width))-x,height:Math.max(...rows.map(r=>r.y+r.height))-y},element_count:rows.length,unsupported};}""")
        info['actual_dom_paint_bounds']=paint
        if paint['unsupported']:raise ValueError('Native filter/shadow effects require an explicit painted-bounds audit')
        nominal=info['graphBounds'];p=paint['bounds'] or nominal
        # Conservative full paint inspection includes original page, all DOM
        # paint bounds, graph bounds and at least 32 physical white pixels.
        x=min(0,nominal['x'],p['x']);y=min(0,nominal['y'],p['y'])
        right=max(canvas_w,nominal['x']+nominal['width'],p['x']+p['width'])
        bottom=max(canvas_h,nominal['y']+nominal['height'],p['y']+p['height'])
        left=max(32,math.ceil(-x)+32);top=max(32,math.ceil(-y)+32)
        pw=math.ceil(right)+left+32;ph=math.ceil(bottom)+top+32
        if max(pw,ph)>8192 or pw*ph>64000000:raise ValueError('Full actual painted extent exceeds native audit pixel budget')
        # ONLY the external CSS viewport moves. No graph.view translation,
        # graph refresh, geometry, port, label or path rewriting is performed.
        position="a=>{const d=document.getElementById('graph'),s=document.getElementById('surface');d.style.left=a[0]+'px';d.style.top=a[1]+'px';s.style.width=a[2]+'px';s.style.height=a[3]+'px';}"
        page.evaluate(position,[left,top,pw,ph]);page.set_viewport_size({'width':max(pw,640),'height':max(ph,480)})
        from PIL import Image
        import numpy as np
        probe=page.locator('#surface').screenshot(animations='disabled');(source.parent/'render.inspection.png').write_bytes(probe)
        im=Image.open(io.BytesIO(probe)).convert('RGB');arr=np.asarray(im);mask=np.min(arr,axis=2)<255
        boundary=mask.copy();boundary[32:-32,32:-32]=False
        if boundary.any():raise ValueError('Native source paint touches full inspection guard')
        ys,xs=np.nonzero(mask)
        if not len(xs):raise ValueError('Native source has no visible paint')
        # Union original source PAGE with ALL actual paint and one physical AA
        # guard. No reference pixels determine bounds, offset or dimensions.
        bx0=min(left,int(xs.min())-1);by0=min(top,int(ys.min())-1)
        bx1=max(left+canvas_w,int(xs.max())+2);by1=max(top+canvas_h,int(ys.max())+2)
        plan={'dx':left-bx0,'dy':top-by0,'width':bx1-bx0,'height':by1-by0,'inspection_offset':[left,top],'inspection_size':[pw,ph],'export_crop_in_inspection':[bx0,by0,bx1,by1],'painted_pixel_bbox':[int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]}
        if max(plan['width'],plan['height'])>8192 or plan['width']*plan['height']>64000000:raise ValueError('Native export exceeds pixel budget')
        declared={k:model.get('tikzExport'+k.title()+'V1') for k in ('dx','dy','width','height')}
        if any(v is not None for v in declared.values()):
            if any(v is None or int(v)!=plan[k] for k,v in declared.items()):raise ValueError('Declared export viewport does not contain the complete source paint/source page')
        outside=mask.copy();outside[top:top+canvas_h,left:left+canvas_w]=False
        info['original_declared_page_outside_pixels']=int(outside.sum())
        info['strict_outside_inspection_pixels']=int(boundary.sum())
        # A real screenshot clip of the SAME fixed, completely inspected native
        # DOM. No object/CSS/view translation or viewport relayout occurs.
        final=page.screenshot(clip={'x':bx0,'y':by0,'width':plan['width'],'height':plan['height']},animations='disabled');output.write_bytes(final)
        expected=im.crop((bx0,by0,bx1,by1));actual=Image.open(io.BytesIO(final)).convert('RGB')
        if expected.size!=actual.size or expected.tobytes()!=actual.tobytes():raise ValueError('External viewport translation changed actual complete native paint')
        finalmask=np.min(np.asarray(actual),axis=2)<255
        exportguard=finalmask.copy();exportguard[1:-1,1:-1]=False
        if exportguard.any():raise ValueError('Export viewport would crop source paint')
        # Original source page and every intended paint pixel are retained.
        retained=np.zeros_like(mask);retained[by0:by1,bx0:bx1]=True
        if (mask&~retained).any():raise ValueError('Export omitted actual source paint')
        before_text=info['actual_text_positions']
        info['actual_text_positions']=page.evaluate("""()=>{const g=window.evalViewer.graph,rows=[];for(const c of Object.values(g.model.cells)){const s=g.view.getState(c);if(!s?.text?.node)continue;const w=document.createTreeWalker(s.text.node,NodeFilter.SHOW_TEXT),runs=[];while(w.nextNode()){const n=w.currentNode;if(!n.textContent)continue;const cs=getComputedStyle(n.parentElement),chars=[];for(const {segment,index} of new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(n.textContent)){const r=document.createRange();r.setStart(n,index);r.setEnd(n,index+segment.length);const b=r.getBoundingClientRect();chars.push({text:segment,x:b.x,y:b.y,width:b.width,height:b.height});}runs.push({text:n.textContent,font:cs.font,fontKerning:cs.fontKerning,fontFeatureSettings:cs.fontFeatureSettings,letterSpacing:cs.letterSpacing,lineHeight:cs.lineHeight,chars});}if(runs.length)rows.push({cell:c.id,runs});}return rows;}""")
        info['actual_inspection_text_positions']=json.loads(json.dumps(info['actual_text_positions']))
        for row in info['actual_text_positions']:
            for run in row['runs']:
                for char in run['chars']:char['x']-=bx0;char['y']-=by0
        info['actual_export_range_coordinate_frame']={'inspection_offset':[left,top],'screenshot_clip':[bx0,by0,plan['width'],plan['height']],'native_model_translate':[0,0],'source_to_export_offset':[plan['dx'],plan['dy']]}
        a={r['cell']:[c for run in r['runs'] for c in run['chars']] for r in before_text};b={r['cell']:[c for run in r['runs'] for c in run['chars']] for r in info['actual_text_positions']}
        if a.keys()!=b.keys():raise ValueError('Export text scope changed')
        for cid,chars in a.items():
            if len(chars)!=len(b[cid]):raise ValueError('Export glyph count changed')
            for old,new in zip(chars,b[cid]):
                if old['text']!=new['text'] or any(abs(new[k]-old[k]-d)>1e-6 for k,d in [('x',plan['dx']),('y',plan['dy']),('width',0),('height',0)]):raise ValueError('External viewport changed native glyph layout')
        view=page.evaluate("()=>{const g=window.evalViewer.graph;return {scale:g.view.scale,translate:{x:g.view.translate.x,y:g.view.translate.y},xml:mxUtils.getXml(new mxCodec().encode(g.model))}}")
        if view['scale']!=1 or view['translate']!={'x':0,'y':0}:raise ValueError('Native model view was modified by export')
        # Native model's actual SVG export remains independently available and
        # records its own root frame; it is never substituted for the page PNG.
        svgroot=ET.fromstring((source.parent/'render.svg').read_text())
        info.update(export_plan=plan,export_mode='complete_native_paint_fixed_inspection_export_v1',paint_safety_frame='full_paint_inspection_viewport',strict_outside_export_pixels=int(exportguard.sum()),complete_source_paint_retained=True,complete_original_page_retained=True,model_geometry_preserved=True,graph_view_unchanged=True,full_native_inspection_png_sha256=hashlib.sha256(probe).hexdigest(),native_svg_export_sha256=hashlib.sha256((source.parent/'render.svg').read_bytes()).hexdigest(),native_svg_export_frame={k:svgroot.get(k) for k in ('width','height','viewBox')},exact_complete_paint_export_pixels=True,actual_export_glyph_translation_verified=True,export_viewport=[plan['width'],plan['height']],original_declared_page=[canvas_w,canvas_h])
        info['content_outside_declared_canvas']=bool(info['original_declared_page_outside_pixels'])
        info['page_capture_policy']='actual_browser_screenshot_clip_of_complete_native_paint_in_fixed_inspection_DOM_model_geometry_unchanged'
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
