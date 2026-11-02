"""Untouched SOURCE HTML block and flex formatting hosts and actual Text-node fonts."""
import hashlib,io,json,mimetypes,urllib.parse
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda b:hashlib.sha256(b).hexdigest()
def capture_source(record,work):
 from PIL import Image
 from playwright.sync_api import sync_playwright
 import html_source_whitespace_capture_v8 as old
 from html_source_text_node_binding_v9 import physical_fonts_for_object
 import auto_quality_source_vector_v2 as profile
 work=Path(work);work.mkdir(parents=True,exist_ok=True);source=profile._read_clean(record['original_source_code'],record['source_code_sha256']);reference=profile._read_clean(record['original_reference'],record['source_image_sha256']);size=list(Image.open(io.BytesIO(reference)).size);assets=(R/record['original_asset_root']).resolve()if record.get('original_asset_root')else None;served={};blocked=[]
 with sync_playwright()as pw:
  browser=pw.chromium.launch(executable_path=old.CHROME,args=['--disable-dev-shm-usage']);context=browser.new_context(viewport=dict(zip(('width','height'),size)),java_script_enabled=False,service_workers='block')
  try:
   def route(req):
    u=urllib.parse.urlparse(req.request.url);name=urllib.parse.unquote(u.path.lstrip('/'))
    if u.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
    if name=='index.html':req.fulfill(body=source,content_type='text/html');return
    target=(assets/name).resolve()if assets else None
    if target is None or not target.is_relative_to(assets)or not target.is_file():blocked.append(req.request.url);req.abort();return
    blob=target.read_bytes();served[req.request.url]=blob;req.fulfill(body=blob,content_type=mimetypes.guess_type(str(target))[0]or'application/octet-stream')
   context.route('**/*',route);page=context.new_page();page.set_default_timeout(45000);page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready');png=old.screenshot(page);dom=page.evaluate(old.source_js());glyphs=page.evaluate(old.SOURCE_GLYPHS,dom);dom=glyphs['dom'];assert not glyphs['errors'],'paragraph_SOURCE_Unicode_Range_binding_pending';ir=page.evaluate((W/'scripts/html_source_flex_paragraph_ir_v1.js').read_text(),dom)
   rounded=[u for u in dom.get('unsupported',[])if u.get('reason')=='rounded_ancestor_clip_requires_shape_mask']
   ownership=ir['sourceRoundedClipOwnership'];assert len(rounded)==len(ownership),'paragraph_original_rounded_text_clip_scope_not_proved'
   dom['qaRoundedParagraphClipProof']={'original_warning_count':len(rounded),'ownership':ownership,'all_clips_inside_unchanged_cloned_CSS_markup':True}
   dom['unsupported']=[u for u in dom.get('unsupported',[])if u.get('reason')!='rounded_ancestor_clip_requires_shape_mask']
   dom['qaCSSRectangleProofs']=page.evaluate("""dom=>dom.objects.filter(o=>o.type==='rect').map(o=>{const e=window.__img2codeAlignOwners[o.qaOwner],c=getComputedStyle(e);if(c.backgroundClip!=='border-box')throw Error('paragraph_nondefault_CSS_background_clip_pending');const widths=['borderTopWidth','borderRightWidth','borderBottomWidth','borderLeftWidth'].map(k=>parseFloat(c[k])),styles=['borderTopStyle','borderRightStyle','borderBottomStyle','borderLeftStyle'].map(k=>c[k]),colors=['borderTopColor','borderRightColor','borderBottomColor','borderLeftColor'].map(k=>c[k]),radii=['borderTopLeftRadius','borderTopRightRadius','borderBottomLeftRadius','borderBottomRightRadius'].map(k=>c[k]);if(widths.some(v=>v!==o.bw)||o.bw>0&&(styles.some(v=>v!=='solid')||new Set(colors).size!==1||o.stroke.opacity!==1))throw Error('paragraph_nonuniform_or_translucent_CSS_border_pending');if(radii.some(v=>!v.endsWith('px')||parseFloat(v)!==o.radius))throw Error('paragraph_nonuniform_or_relative_CSS_radius_pending');return{cell:String(o.id+1),source_border_box:{x:o.x,y:o.y,width:o.w,height:o.h},uniform_border_width:o.bw,styles,colors,radii,source_background_clip:c.backgroundClip,source_background_origin:c.backgroundOrigin};})""",dom)
   session=context.new_cdp_session(page);session.send('DOM.enable',{'includeWhitespace':'all'});session.send('CSS.enable');session.send('DOM.getDocument',{'depth':-1});snapshot=session.send('DOMSnapshot.captureSnapshot',{'computedStyles':[],'includePaintOrder':True});dom['_source_paint_order']=profile._snapshot_paint_orders(dom,snapshot)
   try:
    for group in ir['groups']:
     for run in group['textNodes']:
      expr='window.__sourceParagraphAllNodes['+str(run['globalTextNode'])+']';textobj=session.send('Runtime.evaluate',{'expression':expr,'returnByValue':False})['result'];obj=session.send('Runtime.evaluate',{'expression':expr+'.parentElement','returnByValue':False})['result']
      try:
       node=session.send('DOM.requestNode',{'objectId':obj['objectId']})['nodeId'];run['actual_fonts'],run['actual_original_Text_backend_binding']=physical_fonts_for_object(session,textobj['objectId'],node,run['child_index'],run['text'])
      finally:
       session.send('Runtime.releaseObject',{'objectId':obj['objectId']});session.send('Runtime.releaseObject',{'objectId':textobj['objectId']})
   finally:session.detach()
   # Actual SOURCE element primary-M selection is measured on an isolated
   # page with the original computed typography, never in the data screenshot.
   metric=context.new_page();metric.set_content('<html><body><span id="source-primary-M">M</span></body></html>');ms=context.new_cdp_session(metric);ms.send('DOM.enable',{'includeWhitespace':'all'});ms.send('CSS.enable');mdoc=ms.send('DOM.getDocument',{'depth':-1})['root']['nodeId']
   try:
    for group in ir['groups']:
     for evidence in group['cssEvidence']:
      metric.evaluate('''async e=>{const n=document.getElementById('source-primary-M');n.style.cssText='position:absolute;left:0;top:0;white-space:pre;';for(const[k,v]of Object.entries(e.css))if(k.startsWith('font-')||['line-height','letter-spacing','word-spacing','direction','text-rendering'].includes(k))n.style.setProperty(k,v);for(const[k,v]of Object.entries(e.typedNumericCSS||{}))n.style.setProperty(k,v.literal);await document.fonts.ready;n.getBoundingClientRect();}''',evidence)
      node=ms.send('DOM.querySelector',{'nodeId':mdoc,'selector':'#source-primary-M'})['nodeId'];evidence['source_primary_M_fonts']=ms.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts'];evidence['source_primary_M_basis']='isolated_SOURCE_computed_typography_and_exact_TypedOM_numeric_values'
      assert len([f for f in evidence['source_primary_M_fonts']if f.get('glyphCount',0)])==1,'paragraph_SOURCE_primary_M_font_ambiguous'
   finally:ms.detach();metric.close()
   assert old.screenshot(page)==png,'paragraph_SOURCE_observation_changed_pixels';assert not blocked,'paragraph_SOURCE_missing_resources:'+repr(blocked[:8])
   page.evaluate("""()=>{const rs=window.__sourceParagraphAllNodes.map(n=>{const r=document.createRange();r.selectNodeContents(n);return r;});CSS.highlights.set('paragraph-source-all-v9',new Highlight(...rs));const s=document.createElement('style');s.id='paragraph-source-hide-v9';s.textContent='*{text-decoration-color:transparent!important;}::highlight(paragraph-source-all-v9){color:transparent;text-shadow:none;text-decoration-color:transparent;}';document.head.append(s)}""");hidden=old.screenshot(page)
   page.evaluate("()=>{CSS.highlights.delete('paragraph-source-all-v9');document.getElementById('paragraph-source-hide-v9').remove()}");assert old.screenshot(page)==png,'paragraph_SOURCE_paint_hiding_not_reversible'
  finally:context.close();browser.close()
 metadata={'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'viewport':size,'source_png_sha256':sha(png),'source_observation_pixel_identical':True,'whole_original_Unicode_nodes_preserved':True,'source_text_objects':len(ir['allSourceTextObjects']),'native_paragraph_objects':len(ir['groups']),'actual_source_Text_nodes':ir['allOriginalTextNodes'],'font_basis':'direct_materialized_original_Text_backend_node','source_paint_hiding_reversible':True}
 for name,blob in [('source.native.png',png),('source.hidden.png',hidden),('source.dom.json',json.dumps(dom,ensure_ascii=False,sort_keys=True).encode()),('source.paragraphs.json',json.dumps(ir,ensure_ascii=False,sort_keys=True).encode()),('source.capture.json',json.dumps(metadata,sort_keys=True).encode())]:(work/name).write_bytes(blob)
 return dom,ir,served,png,hidden,metadata
