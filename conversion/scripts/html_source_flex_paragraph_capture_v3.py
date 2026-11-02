"""Untouched original SOURCE authority plus independently rebound original mask document."""
import hashlib,io,json,mimetypes,time,urllib.parse
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda b:hashlib.sha256(b).hexdigest()
def capture_source(record,work):
 from PIL import Image
 from playwright.sync_api import sync_playwright
 import html_source_whitespace_capture_v8 as old
 from html_source_text_node_binding_v9 import physical_fonts_for_object
 import auto_quality_source_vector_v2 as profile
 started=time.monotonic();last=started;stages={};screenshots=[];source_ir_path=W/'scripts/html_source_flex_paragraph_ir_v3.js';source_ir_bytes=source_ir_path.read_bytes()
 def mark(name):
  nonlocal last
  now=time.monotonic();stages[name]=now-last;last=now
 def shot(pg):
  tick=time.monotonic();image=pg.screenshot();screenshots.append({'index':len(screenshots),'wall_monotonic_seconds':time.monotonic()-tick,'sha256':sha(image)});return image
 work=Path(work);work.mkdir(parents=True,exist_ok=True);source=profile._read_clean(record['original_source_code'],record['source_code_sha256']);reference=profile._read_clean(record['original_reference'],record['source_image_sha256']);size=list(Image.open(io.BytesIO(reference)).size);assets=(R/record['original_asset_root']).resolve()if record.get('original_asset_root')else None;served={};blocked=[];mark('read_original_source_and_reference_header')
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
   context.route('**/*',route);page=context.new_page();page.set_default_timeout(45000);page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready');png=shot(page);dom=page.evaluate(old.source_js());glyphs=page.evaluate(old.SOURCE_GLYPHS,dom);dom=glyphs['dom'];assert not glyphs['errors'],'paragraph_SOURCE_Unicode_Range_binding_pending';ir=page.evaluate(source_ir_bytes.decode(),dom)
   rounded=[u for u in dom.get('unsupported',[])if u.get('reason')=='rounded_ancestor_clip_requires_shape_mask']
   ownership=ir['sourceRoundedClipOwnership'];assert len(rounded)==len(ownership),'paragraph_original_rounded_text_clip_scope_not_proved'
   dom['qaRoundedParagraphClipProof']={'original_warning_count':len(rounded),'ownership':ownership,'all_clips_inside_unchanged_cloned_CSS_markup':True}
   dom['unsupported']=[u for u in dom.get('unsupported',[])if u.get('reason')!='rounded_ancestor_clip_requires_shape_mask']
   dom['qaCSSRectangleProofs']=page.evaluate("""dom=>dom.objects.filter(o=>o.type==='rect').map(o=>{const e=window.__img2codeAlignOwners[o.qaOwner],c=getComputedStyle(e);if(c.backgroundClip!=='border-box')throw Error('paragraph_nondefault_CSS_background_clip_pending');const widths=['borderTopWidth','borderRightWidth','borderBottomWidth','borderLeftWidth'].map(k=>parseFloat(c[k])),styles=['borderTopStyle','borderRightStyle','borderBottomStyle','borderLeftStyle'].map(k=>c[k]),colors=['borderTopColor','borderRightColor','borderBottomColor','borderLeftColor'].map(k=>c[k]),radii=['borderTopLeftRadius','borderTopRightRadius','borderBottomLeftRadius','borderBottomRightRadius'].map(k=>c[k]);if(widths.some(v=>v!==o.bw)||o.bw>0&&(styles.some(v=>v!=='solid')||new Set(colors).size!==1||o.stroke.opacity!==1))throw Error('paragraph_nonuniform_or_translucent_CSS_border_pending');if(radii.some(v=>!v.endsWith('px')||parseFloat(v)!==o.radius))throw Error('paragraph_nonuniform_or_relative_CSS_radius_pending');return{cell:String(o.id+1),source_border_box:{x:o.x,y:o.y,width:o.w,height:o.h},uniform_border_width:o.bw,styles,colors,radii,source_background_clip:c.backgroundClip,source_background_origin:c.backgroundOrigin};})""",dom)
   mark('browser_load_source_DOM_Ranges_CSS_and_initial_pixels');session=context.new_cdp_session(page);session.send('DOM.enable',{'includeWhitespace':'all'});session.send('CSS.enable');session.send('DOM.getDocument',{'depth':-1});snapshot=session.send('DOMSnapshot.captureSnapshot',{'computedStyles':[],'includePaintOrder':True});dom['_source_paint_order']=profile._snapshot_paint_orders(dom,snapshot)
   try:
    for group in ir['groups']:
     for run in group['textNodes']:
      expr='window.__sourceParagraphAllNodes['+str(run['globalTextNode'])+']';textobj=session.send('Runtime.evaluate',{'expression':expr,'returnByValue':False})['result'];obj=session.send('Runtime.evaluate',{'expression':expr+'.parentElement','returnByValue':False})['result']
      try:
       node=session.send('DOM.requestNode',{'objectId':obj['objectId']})['nodeId'];run['actual_fonts'],run['actual_original_Text_backend_binding']=physical_fonts_for_object(session,textobj['objectId'],node,run['child_index'],run['text'])
      finally:
       session.send('Runtime.releaseObject',{'objectId':obj['objectId']});session.send('Runtime.releaseObject',{'objectId':textobj['objectId']})
   finally:session.detach()
   mark('all_original_Text_backend_physical_fonts')
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
   mark('all_element_primary_M_physical_struts');assert shot(page)==png,'paragraph_SOURCE_observation_changed_pixels';assert not blocked,'paragraph_SOURCE_missing_resources:'+repr(blocked[:8])
   # The authority page is never masked. A second untouched original document
   # must match its complete pixels, semantic Text paths and Range geometry
   # before a scoped throwaway background observation may be used.
   mark('authority_after_metadata_exact_pixels');maskpage=context.new_page();maskpage.set_default_timeout(45000);maskpage.goto('http://source.invalid/index.html',wait_until='networkidle');maskpage.evaluate('document.fonts.ready')
   maskdom=maskpage.evaluate(old.source_js());maskglyphs=maskpage.evaluate(old.SOURCE_GLYPHS,maskdom);assert not maskglyphs['errors'],'paragraph_mask_original_Text_scope_pending';maskir=maskpage.evaluate(source_ir_bytes.decode(),maskglyphs['dom'])
   def semantic_observation(value):
    return [{k:g[k]for k in('rootOwner','rootRect','markup','sourceObjectIDs','ancestorClipFrame')}|{'textNodes':[{k:t[k]for k in('path','text','child_index','css','chars')}for t in g['textNodes']]}for g in value['groups']]
   assert semantic_observation(maskir)==semantic_observation(ir),'paragraph_independent_mask_SOURCE_DOM_or_glyph_geometry_changed'
   mask_before=shot(maskpage);assert mask_before==png,'paragraph_independent_original_mask_page_pixels_changed'
   mark('independent_mask_original_DOM_glyph_and_pixel_binding');maskpage.evaluate("""()=>{const rs=window.__sourceParagraphAllNodes.map(n=>{const r=document.createRange();r.selectNodeContents(n);return r;});CSS.highlights.set('paragraph-source-all-v2',new Highlight(...rs));for(const e of document.querySelectorAll('*'))if(getComputedStyle(e).textDecorationLine!=='none')e.style.setProperty('text-decoration-color','transparent','important');const s=document.createElement('style');s.textContent='::highlight(paragraph-source-all-v2){color:transparent;text-shadow:none;text-decoration-color:transparent;}';document.head.append(s)}""");hidden=shot(maskpage);maskpage.close()
   assert not blocked,'paragraph_isolated_mask_SOURCE_missing_resources';assert shot(page)==png,'paragraph_authority_SOURCE_context_changed_by_isolated_mask_probe'
   mark('mask_hidden_pixels_and_untouched_authority_pixels');mask_proof={'mode':'independent_original_source_mask_context_v2','source_authority_context_never_masked':True,'source_authority_original_Text_backend_identity_preserved':True,'mask_document_raw_original_source_and_assets_unchanged':True,'all_source_Text_paths_raw_Unicode_CSS_Ranges_and_original_border_boxes_exact':True,'independent_mask_before_equals_authority_PNG':True,'authority_after_equals_original_PNG':True,'mask_before_sha256':sha(mask_before),'authority_after_sha256':sha(png),'mask_context_is_disposable_not_a_restored_authority':True}

  finally:context.close();browser.close()
 assert source_ir_path.read_bytes()==source_ir_bytes,'infrastructure_SOURCE_owner_IR_changed_during_capture'
 metadata={'source_owner_ir_script':{'file':str(source_ir_path),'sha256':sha(source_ir_bytes)},'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'viewport':size,'source_png_sha256':sha(png),'source_observation_pixel_identical':True,'whole_original_Unicode_nodes_preserved':True,'source_text_objects':len(ir['allSourceTextObjects']),'native_paragraph_objects':len(ir['groups']),'actual_source_Text_nodes':ir['allOriginalTextNodes'],'font_basis':'direct_materialized_original_Text_backend_node','source_mask_observation':mask_proof,'performance':{'stage_monotonic_seconds':stages,'total_monotonic_seconds':time.monotonic()-started,'actual_screenshots':len(screenshots),'screenshot_calls':screenshots}}
 for name,blob in [('source.native.png',png),('source.hidden.png',hidden),('source.dom.json',json.dumps(dom,ensure_ascii=False,sort_keys=True).encode()),('source.paragraphs.json',json.dumps(ir,ensure_ascii=False,sort_keys=True).encode()),('source.capture.json',json.dumps(metadata,sort_keys=True).encode())]:(work/name).write_bytes(blob)
 return dom,ir,served,png,hidden,metadata
