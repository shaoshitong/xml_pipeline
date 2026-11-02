"""Original SOURCE zero-paint facts from an untouched authority and bound mask page.

Only original paragraph Text ranges and solid CSS rectangle paint are supported.
Nonzero SOURCE contribution is a hard failure, never a visibility exemption.
"""
from pathlib import Path
import base64,hashlib,io,json,mimetypes,re,urllib.parse
from contextlib import ExitStack
import numpy as np
from PIL import Image
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
sha=lambda b:hashlib.sha256(b).hexdigest()
def require(x,r):
 if not x:raise ValueError(r)
def pixels(b):
 with Image.open(io.BytesIO(b))as im:return np.asarray(im.convert('RGBA')).copy()
def audit(record,xml,cells,work,expected_source=None,browser=None):
 from playwright.sync_api import sync_playwright
 import html_source_whitespace_capture_v8 as old
 work=Path(work);work.mkdir(parents=True,exist_ok=False);require(work.resolve().is_relative_to(R/'clean'),'SOURCE_zero_paint_evidence_not_clean');require(sha(xml.encode())==record['code_sha256'],'SOURCE_zero_paint_other_candidate')
 source_path=R/record['original_source_code'];source=source_path.read_bytes();require(sha(source)==record['source_code_sha256'],'SOURCE_zero_paint_original_bytes_changed');reference=R/record['original_reference'];require(sha(reference.read_bytes())==record['source_image_sha256'],'SOURCE_zero_paint_original_reference_changed')
 with Image.open(reference)as im:size=list(im.size)
 assets=(R/record['original_asset_root']).resolve()if record.get('original_asset_root')else None;blocked=[];served={};rows=[];image_calls=0;irjs=W/'scripts/html_source_flex_paragraph_ir_v2.js'
 if expected_source is not None and expected_source['capture'].get('source_owner_ir_script'):
  declared=expected_source['capture']['source_owner_ir_script'];irjs=Path(declared['file']).resolve();require(irjs.parent==(W/'scripts').resolve()and re.fullmatch(r'html_source_flex_paragraph_ir_v[0-9]+\.js',irjs.name)and sha(irjs.read_bytes())==declared['sha256'],'SOURCE_owner_IR_script_not_registered_or_hash_bound')
 source_script=old.source_js();ir_script=irjs.read_text();pins={str(p):sha(p.read_bytes())for p in(Path(__file__),Path(old.__file__),irjs,Path(old.CHROME))}
 def route(req):
  u=urllib.parse.urlparse(req.request.url);name=urllib.parse.unquote(u.path.lstrip('/'))
  if u.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
  if name=='index.html':req.fulfill(body=source,content_type='text/html');return
  target=(assets/name).resolve()if assets else None
  if target is None or not target.is_relative_to(assets)or not target.is_file():blocked.append(req.request.url);req.abort();return
  b=target.read_bytes();served[str(target)]=sha(b);req.fulfill(body=b,content_type=mimetypes.guess_type(str(target))[0]or'application/octet-stream')
 def shot(page,name):
  nonlocal image_calls
  session=page.context.new_cdp_session(page)
  try:b=base64.b64decode(session.send('Page.captureScreenshot',dict(format='png',fromSurface=True,captureBeyondViewport=False,optimizeForSpeed=True))['data'])
  finally:session.detach()
  image_calls+=1;p=work/(name+'.png');p.write_bytes(b);return pixels(b),dict(file=str(p),sha256=sha(b))
 def observe(page):
  dom=page.evaluate(source_script);g=page.evaluate(old.SOURCE_GLYPHS,dom);require(not g['errors'],'SOURCE_zero_paint_original_Range_binding_pending');return g['dom'],page.evaluate(ir_script,g['dom'])
 def signature(dom,ir):return dict(objects=dom['objects'],groups=[{k:g[k]for k in('rootOwner','rootRect','sourceObjectIDs')}|{'textNodes':[{k:t[k]for k in('path','text','css','chars','globalTextNode')}for t in g['textNodes']]}for g in ir['groups']])
 with ExitStack()as stack:
  if browser is None:
   pw=stack.enter_context(sync_playwright());browser=pw.chromium.launch(executable_path=old.CHROME,args=['--disable-dev-shm-usage']);stack.callback(browser.close)
  ctx=browser.new_context(viewport=dict(zip(('width','height'),size)),java_script_enabled=False,service_workers='block');ctx.route('**/*',route)
  try:
   authority=ctx.new_page();authority.goto('http://source.invalid/index.html',wait_until='networkidle');authority.evaluate('document.fonts.ready');base,base_asset=shot(authority,'authority_original');require(np.array_equal(base,pixels(authority.screenshot())),'SOURCE_optimized_capture_not_exact_normal_RGBA');adom,air=observe(authority);observed,_=shot(authority,'authority_after_readonly_observation');require(np.array_equal(base,observed),'SOURCE_authority_observation_changed_pixels')
   if expected_source is not None:
    require((expected_source['capture']['source_code_sha256'],expected_source['capture']['source_image_sha256'])==(record['source_code_sha256'],record['source_image_sha256']),'SOURCE_preverified_authority_other_source_identity');require(np.array_equal(base,pixels(expected_source['source_png'])),'SOURCE_zero_paint_not_same_preverified_source_authority')
    expected_groups={g['rootOwner']:g for g in expected_source['ir']['groups']}
    for g in air['groups']:
     e=expected_groups.get(g['rootOwner']);require(e is not None and g['rootRect']==e['rootRect']and[{k:t[k]for k in('path','text','chars')}for t in g['textNodes']]==[{k:t[k]for k in('path','text','chars')}for t in e['textNodes']],'SOURCE_zero_paint_original_owner_not_preverified_Text_Path_Range_binding')
   page=ctx.new_page();page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready');dom,ir=observe(page);require(signature(dom,ir)==signature(adom,air),'SOURCE_independent_original_DOM_Text_CSS_Range_scope_mismatch');before,before_asset=shot(page,'independent_original_mask_before');require(np.array_equal(before,base),'SOURCE_independent_original_mask_pixels_mismatch');mask_original_DOM=page.evaluate('document.documentElement.outerHTML')
   for cell in sorted(set(cells)):
    if cell.startswith('source_paragraph_owner_'):
     owner=int(cell.removeprefix('source_paragraph_owner_'));matches=[g for g in ir['groups']if g['rootOwner']==owner];require(len(matches)==1,'SOURCE_original_paragraph_owner_not_unique');group=matches[0];indices=[t['globalTextNode']for t in group['textNodes']];page.evaluate("""ids=>{const rs=ids.map(i=>{const n=window.__sourceParagraphAllNodes[i];for(let e=n.parentElement;e;e=e.parentElement){const c=getComputedStyle(e);if(c.textDecorationLine!=='none'||c.textShadow!=='none'||parseFloat(c.webkitTextStrokeWidth||'0')>0)throw Error('SOURCE zero-paint text effect needs separate mapping')}const r=document.createRange();r.selectNodeContents(n);return r});window.__zeroPaintPreviousHighlight=CSS.highlights.get('source-zero-paint-v1');CSS.highlights.set('source-zero-paint-v1',new Highlight(...rs));const s=document.createElement('style');s.textContent='::highlight(source-zero-paint-v1){color:transparent!important;text-shadow:none!important;text-decoration-color:transparent!important;}';document.head.append(s);window.__zeroPaintMaskRestore=()=>{s.remove();if(window.__zeroPaintPreviousHighlight)CSS.highlights.set('source-zero-paint-v1',window.__zeroPaintPreviousHighlight);else CSS.highlights.delete('source-zero-paint-v1');delete window.__zeroPaintPreviousHighlight};document.documentElement.getBoundingClientRect()}""",indices);binding=dict(kind='all_original_paragraph_Text_ranges',rootOwner=owner,source_root_rect=group['rootRect'],original_Text_nodes=len(indices),original_Unicode_characters=sum(len(t['text'])for t in group['textNodes']),original_Unicode_sha256=sha(''.join(t['text']for t in group['textNodes']).encode()))
    else:
     matches=[o for o in dom['objects']if str(o['id']+1)==cell];require(len(matches)==1 and matches[0]['type']=='rect','SOURCE_zero_paint_only_original_Text_or_solid_CSS_rectangle_supported');obj=matches[0];require(not obj.get('image'),'SOURCE_zero_paint_CSS_asset_requires_separate_mapping');page.evaluate("""owner=>{const e=window.__img2codeAlignOwners[owner];if(!e)throw Error('SOURCE rectangle owner absent');const css=getComputedStyle(e);if(css.backgroundImage!=='none'||css.boxShadow!=='none')throw Error('SOURCE zero-paint effects require separate primitive mapping');const original=e.getAttribute('style');e.style.setProperty('background-color','transparent','important');e.style.setProperty('border-color','transparent','important');window.__zeroPaintMaskRestore=()=>{if(original===null){e.style.cssText='';e.getAttribute('style');e.removeAttribute('style')}else{e.style.cssText=original;e.getAttribute('style');e.setAttribute('style',original)}};document.documentElement.getBoundingClientRect();if(getComputedStyle(e).backgroundColor!=='rgba(0, 0, 0, 0)')throw Error('SOURCE rectangle transparent mask not actually applied')}""",obj['qaOwner']);binding=dict(kind='original_solid_CSS_rectangle_background_and_border',source_object_id=obj['id'],source_qa_owner=obj['qaOwner'],original_Unicode_characters=0)
    hidden,hidden_asset=shot(page,cell+'_original_paint_hidden');changed=int(np.count_nonzero(np.any(hidden!=before,axis=2)));require(changed==0,'SOURCE_owner_has_visible_original_paint_visibility_witness_forbidden:'+cell);page.evaluate("""()=>{window.__zeroPaintMaskRestore();delete window.__zeroPaintMaskRestore;document.documentElement.getBoundingClientRect()}""");restored_DOM=page.evaluate('document.documentElement.outerHTML')
    if restored_DOM!=mask_original_DOM:
     (work/(cell+'_observer_DOM_before.html')).write_text(mask_original_DOM);(work/(cell+'_observer_DOM_failed_restore.html')).write_text(restored_DOM)
    require(restored_DOM==mask_original_DOM,'SOURCE_mask_observer_original_DOM_not_exactly_restored');restored,restore_asset=shot(page,cell+'_mask_observer_restored');require(np.array_equal(base,restored),'SOURCE_mask_observer_original_RGBA_not_exactly_restored');rows.append(dict(cell=cell,source_original_visible_paint_changed_pixels=changed,original_source_owner_binding=binding,independent_before=before_asset,independent_hidden=hidden_asset,independent_original_restored=restore_asset,mask_observer_original_DOM_and_whole_RGBA_restored=True,source_nonpainted_layout_only=True));before=restored;before_asset=restore_asset
   page.evaluate("""()=>{const rs=window.__sourceParagraphAllNodes.map(n=>{const r=document.createRange();r.selectNodeContents(n);return r});CSS.highlights.set('source-visible-paint-control-v1',new Highlight(...rs));const s=document.createElement('style');s.textContent='::highlight(source-visible-paint-control-v1){color:transparent!important;text-shadow:none!important;text-decoration-color:transparent!important;}';document.head.append(s);window.__sourceVisiblePaintControlRestore=()=>{s.remove();CSS.highlights.delete('source-visible-paint-control-v1')};document.documentElement.getBoundingClientRect()}""");positive,positive_asset=shot(page,'all_SOURCE_Text_mask_positive_control');positive_changed=int(np.count_nonzero(np.any(positive!=base,axis=2)));require(positive_changed>0,'SOURCE_actual_mask_capture_pipeline_has_no_positive_visible_Text_control');page.evaluate("""()=>{window.__sourceVisiblePaintControlRestore();delete window.__sourceVisiblePaintControlRestore;document.documentElement.getBoundingClientRect()}""");positive_restore,positive_restore_asset=shot(page,'all_SOURCE_Text_mask_control_restored');require(np.array_equal(positive_restore,base)and page.evaluate('document.documentElement.outerHTML')==mask_original_DOM,'SOURCE_actual_mask_positive_control_not_exactly_restored')
   page.close();unchanged,authority_after=shot(authority,'authority_after_all_independent_masks');require(np.array_equal(base,unchanged),'SOURCE_authority_mutated_by_independent_mask_context')
   for row in rows:row.update(authority_after=authority_after,authority_whole_RGBA_unchanged=True,mask_context_disposed_after_all_probes=True)
  finally:ctx.close()
 require(not blocked,'SOURCE_original_resource_closure_pending');require(all(sha(Path(p).read_bytes())==h for p,h in pins.items()),'SOURCE_zero_paint_implementation_changed');require(sha(source_path.read_bytes())==record['source_code_sha256'],'SOURCE_original_bytes_changed_during_probe')
 require(old.source_js()==source_script,'SOURCE_observer_script_changed_during_probe');require(all(sha(Path(p).read_bytes())==h for p,h in served.items()),'SOURCE_original_assets_changed_during_probe')
 out=dict(ok=True,policy='untouched_original_SOURCE_zero_visible_paint_v1',id=record['id'],candidate_code_sha256=record['code_sha256'],source_code_sha256=record['source_code_sha256'],source_image_sha256=record['source_image_sha256'],source_authority_never_masked=True,original_SOURCE_JavaScript_disabled=True,source_authority=base_asset,preverified_source_authority_RGBA_bound=expected_source is not None,source_DOM_observer_script_sha256=sha(source_script.encode()),source_IR_script_sha256=sha(ir_script.encode()),pins=pins,served_original_asset_hashes=served,rows=rows,actual_visible_Text_mask_positive_control=dict(actual_changed_pixels=positive_changed,masked_PNG=positive_asset,whole_RGBA_and_DOM_restored=True,restored_PNG=positive_restore_asset),source_paint_flush='synchronous layout followed by actual official viewport capture; SOURCE scripts stay disabled, no unsupported scheduled callbacks',screenshot_calls=image_calls,models=0,normal_conversions=0)
 p=work/'report.json';p.write_text(json.dumps(out,sort_keys=True,ensure_ascii=False,indent=2)+'\n');return out|dict(report=str(p),report_sha256=sha(p.read_bytes()))
