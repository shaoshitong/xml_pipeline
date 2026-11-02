"""Non-mutating SOURCE typography observation; no conversion or acceptance."""
import hashlib,io,json,mimetypes,urllib.parse
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
sha=lambda data:hashlib.sha256(data).hexdigest()
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
  const css=getComputedStyle(el);o.actualSourceCss={fontSize:parseFloat(css.fontSize),fontWeight:css.fontWeight,fontStyle:css.fontStyle,fontFamily:css.fontFamily,fontKerning:css.fontKerning,fontFeatureSettings:css.fontFeatureSettings,fontVariationSettings:css.fontVariationSettings,letterSpacing:css.letterSpacing,lineHeight:css.lineHeight,direction:css.direction,textRendering:css.textRendering,textAlign:css.textAlign,textTransform:css.textTransform,whiteSpace:css.whiteSpace,wordSpacing:css.wordSpacing,fontStretch:css.fontStretch,fontVariantCaps:css.fontVariantCaps,fontVariantLigatures:css.fontVariantLigatures,textDecorationLine:css.textDecorationLine,textDecorationColor:css.textDecorationColor,textDecorationStyle:css.textDecorationStyle,textDecorationThickness:css.textDecorationThickness,textUnderlineOffset:css.textUnderlineOffset,color:css.color,opacity:css.opacity,mixBlendMode:css.mixBlendMode,webkitTextStrokeWidth:css.webkitTextStrokeWidth,webkitTextStrokeColor:css.webkitTextStrokeColor};
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
