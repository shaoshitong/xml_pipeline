"""Non-mutating SOURCE typography observation; no conversion or acceptance."""
import hashlib,io,json,mimetypes,urllib.parse
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
sha=lambda data:hashlib.sha256(data).hexdigest()
def screenshot(page):
    for attempt in range(3):
        try:return page.screenshot()
        except Exception as error:
            if 'Unable to capture screenshot'not in str(error)or attempt==2:raise


def source_js():
    return (W/'scripts/html_source_whitespace_ir_v8.js').read_text()

SOURCE_GLYPHS=r'''dom=>{
 const owners=window.__img2codeAlignOwners,nodes=[],errors=[],segmenter=new Intl.Segmenter(undefined,{granularity:'grapheme'});
 for(const o of dom.objects){if(o.type!=='text')continue;try{
  const el=owners[o.qaOwner],n=el?.childNodes[o.qaTextNodeIndex];
  if(!n||n.nodeType!==Node.TEXT_NODE)throw Error('source text node identity missing');
  const start=o.qaTextStart,end=o.qaTextEnd;
  if(!Number.isInteger(start)||!Number.isInteger(end)||end<start)throw Error('source UTF16 range missing');
  const raw=n.textContent.slice(start,end),cssMode=getComputedStyle(el).whiteSpace;
  const mapped=window.__img2codeMapCSSWhitespace(n,start,end,cssMode).filter(g=>g.text);
  if(mapped.some(g=>g.kind==='line_break')||mapped.map(g=>g.text).join('')!==o.text)throw Error('source CSS whitespace logical range differs');
  o.actualSourceGlyphs=mapped.map(g=>{const range=document.createRange();range.setStart(n,g.start);range.setEnd(n,g.end);const b=range.getBoundingClientRect();return {text:g.text,raw:g.raw,start:g.start,end:g.end,kind:g.kind,x:b.x,y:b.y,width:b.width,height:b.height,rectCount:[...range.getClientRects()].filter(x=>x.width&&x.height).length};});
  const css=getComputedStyle(el);o.actualSourceCss={fontSize:parseFloat(css.fontSize),fontWeight:css.fontWeight,fontStyle:css.fontStyle,fontFamily:css.fontFamily,fontKerning:css.fontKerning,fontFeatureSettings:css.fontFeatureSettings,fontVariationSettings:css.fontVariationSettings,letterSpacing:css.letterSpacing,lineHeight:css.lineHeight,direction:css.direction,textRendering:css.textRendering,textAlign:css.textAlign,textTransform:css.textTransform,whiteSpace:css.whiteSpace,tabSize:css.tabSize,whiteSpaceCollapse:css.whiteSpaceCollapse,textWrapMode:css.textWrapMode,wordSpacing:css.wordSpacing,fontStretch:css.fontStretch,fontVariantCaps:css.fontVariantCaps,fontVariantLigatures:css.fontVariantLigatures,textDecorationLine:css.textDecorationLine,textDecorationColor:css.textDecorationColor,textDecorationStyle:css.textDecorationStyle,textDecorationThickness:css.textDecorationThickness,textUnderlineOffset:css.textUnderlineOffset,color:css.color,opacity:css.opacity,mixBlendMode:css.mixBlendMode,webkitTextStrokeWidth:css.webkitTextStrokeWidth,webkitTextStrokeColor:css.webkitTextStrokeColor};
  o.actualSourcePaintDecorations=[];
  for(let a=el;a;a=a.parentElement){const c=getComputedStyle(a);if(c.textDecorationLine!=='none')o.actualSourcePaintDecorations.push({owner:owners.indexOf(a),line:c.textDecorationLine,color:c.textDecorationColor,style:c.textDecorationStyle,thickness:c.textDecorationThickness,underlineOffset:c.textUnderlineOffset});}
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
            before_png=screenshot(page);dom=page.evaluate(source_js());captured=page.evaluate(SOURCE_GLYPHS,dom);dom=captured['dom']
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
                try:png=screenshot(page);attempts.append({'attempt':attempt+1,'ok':True});break
                except Exception as error:
                    attempts.append({'attempt':attempt+1,'error':repr(error)})
                    if attempt==2:raise
            omitted=dom.get('qaOmittedWhitespace',[]);omitted_proof={'ranges':len(omitted),'no_visible_source_paint_omitted':True,'exact_source_range_geometry_retained':True}
            if omitted:
                before_ranges=page.evaluate("""rows=>rows.map(o=>{const n=window.__img2codeAlignOwners[o.owner].childNodes[o.node],r=document.createRange();r.setStart(n,o.start);r.setEnd(n,o.end);const b=r.getBoundingClientRect();return [b.x,b.y,b.width,b.height]})""",omitted)
                page.evaluate("""rows=>{const ranges=rows.map(o=>{const n=window.__img2codeAlignOwners[o.owner].childNodes[o.node],r=document.createRange();r.setStart(n,o.start);r.setEnd(n,o.end);return r});CSS.highlights.set('img2code-whitespace-no-paint-v8',new Highlight(...ranges));const style=document.createElement('style');style.id='img2code-whitespace-no-paint-v8';style.textContent='::highlight(img2code-whitespace-no-paint-v8){color:transparent;text-shadow:none;text-decoration-color:transparent;}';document.head.append(style)}""",omitted)
                noink=screenshot(page);assert noink==before_png,'Whitespace-only layout range has actual SOURCE paint'
                page.evaluate("()=>{CSS.highlights.delete('img2code-whitespace-no-paint-v8');document.getElementById('img2code-whitespace-no-paint-v8').remove()}")
                restored_ranges=page.evaluate("""rows=>rows.map(o=>{const n=window.__img2codeAlignOwners[o.owner].childNodes[o.node],r=document.createRange();r.setStart(n,o.start);r.setEnd(n,o.end);const b=r.getBoundingClientRect();return [b.x,b.y,b.width,b.height]})""",omitted)
                assert before_ranges==restored_ranges and screenshot(page)==before_png,'No-paint SOURCE layout token verification changed layout/pixels'
            assert png==before_png,'Whitespace metadata collection changed SOURCE pixels' 
            assert not captured['errors'],'Source whitespace Range mapping failed: '+repr(captured['errors'][:5])
            assert not blocked,'Source resources unresolved: '+repr(blocked[:8])
        finally:context.close();browser.close()
    (work/'source.native.png').write_bytes(png);(work/'source.glyph_dom.json').write_text(json.dumps(dom,ensure_ascii=False,indent=2)+'\n')
    metadata={'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'fresh_source_png_sha256':sha(png),'fresh_source_dom_sha256':sha(json.dumps(dom,sort_keys=True).encode()),'omitted_whitespace_layout_proof':omitted_proof,'source_range_errors':captured['errors'],'source_metadata_png_byte_identical':png==before_png,'source_whitespace_unicode_node_roundtrip':all(x['rawUnicodeRoundtrip'] for x in dom['qaWhitespaceIR']),'source_capture_attempts':attempts,'viewport':[width,height]}
    (work/'source.capture.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return dom,served,png,metadata
