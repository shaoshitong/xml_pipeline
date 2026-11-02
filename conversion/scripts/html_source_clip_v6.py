"""Compile missing rectangular SOURCE text masks and exact Range placement.

The original-reference PNG is never used to select parameters. Source CSS
overflow intersections, actual physical fonts and grapheme Ranges determine
one native candidate. Fresh source/native ink is independently measurable.
"""
import copy,hashlib,html,io,json,math,mimetypes,urllib.parse,uuid
from pathlib import Path
import xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='fresh_html_missing_rectangular_source_masks_v5'
sha=lambda b:hashlib.sha256(b).hexdigest()

def plan(xml,dom,info,viewport,offset=(0.,0.),all_text=False):
 from html_actual_text_alignment import analyze,_plain
 from html_actual_text_clip_alignment_v4 import source_rectangle
 analysis=analyze(dom,info,xml,offset);rows={r['cell']:r for r in analysis['objects']};cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')}
 actual_clips={r['cell']:r['clips'] for r in info.get('actual_clip_boxes',[])};changes=[];unsupported=[]
 for o in dom['objects']:
  if o['type']!='text' or not(all_text or o.get('sourceClip',{}).get('partial')):continue
  key=str(o['id']+1);c=cells.get(key);g=rows.get(key)
  try:
   assert c is not None and g is not None,'source_text_object_missing'
   assert not actual_clips.get(key) and 'clip-path' not in c.get('value',''),'existing_source_clip_needs_separate_replay'
   assert _plain(c.get('value',''))==o['text'],'source_text_changed'
   assert o.get('actualSourcePhysicalFonts',{}).get('basis')=='actual_text_node','source_font_inventory_not_exact_text_node'
   assert g.get('source_faces') and (set(g.get('native_faces') or ())<=set(g['source_faces']) if all_text else g['source_faces']==g.get('native_faces')),'source_native_physical_face_set_differs'
   assert len(g.get('native_font_sizes',[]))==1 and abs(g['native_font_sizes'][0]-g.get('source_font_size',0))<.001,'source_native_font_size_differs'
   assert g.get('maximum_glyph_size_difference',math.inf)<=.08,'source_native_actual_glyph_sizes_differ'
   assert g.get('maximum_residual_from_translation',math.inf)<=.08,'source_native_glyph_positions_not_one_translation'
   assert max(abs(g['translation'][a]) for a in ['dx','dy'])<=8,'source_glyph_translation_exceeds_finite_contract'
   assert not o.get('underline'),'source_underline_ink_is_separate_paint'
   source_object=o
   if all_text and not o.get('sourceClip',{}).get('partial'):
    source_object=copy.deepcopy(o);source_object.setdefault('sourceClip',{})['partial']=True
    # The raster viewport is itself a source paint boundary. Ordinary fixed
    # poster HTML also declares body/ancestor overflow rectangles.
    if not source_object['sourceClip'].get('chain'):
     source_object['sourceClip']['chain']=[dict(left=0,top=0,right=viewport[0],bottom=viewport[1],clipX=True,clipY=True,radius=['0px']*4)]
   bounds=source_rectangle(source_object,viewport,offset)
   assert all(abs(x-round(x))<1e-8 for x in bounds),'fractional_source_mask_needs_raster_contract'
   st=dict(p.split('=',1) for p in c.get('style','').split(';') if '=' in p)
   assert st.get('rotation','0') in ('0','0.0') and c.get('parent')=='1','source_transformed_or_nested_text_pending'
   changes.append(dict(cell=key,before_value=c.get('value',''),source_clip_bounds=bounds,delta=g['translation'],source_css=o['actualSourceCss'],source_faces=g['source_faces'],source_clip=o['sourceClip']))
  except AssertionError as exc:unsupported.append(dict(cell=key,reason=str(exc)))
 return dict(version=5,all_text=all_text,changes=changes,unsupported=unsupported,offset=list(offset),source_viewport=list(viewport),no_original_reference_image_parameter_selection=True)

def initialize(xml,proof):
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')}
 for ch in proof['changes']:
  c=cells[ch['cell']];assert c.get('value','')==ch['before_value'];d=ch['delta']
  inner='<span data-img2code-source-glyph="v5" style="position:relative;left:'+format(d['dx'],'.10g')+'px;top:'+format(d['dy'],'.10g')+'px;">'+ch['before_value']+'</span>'
  c.set('value','<span data-img2code-source-clip="v5" style="clip-path:inset(0px);">'+inner+'</span>')
 return E.tostring(root,encoding='unicode')

def finalize(xml,proof,info):
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};actual={r['cell']:r['clips'] for r in info['actual_clip_boxes']};proof=copy.deepcopy(proof)
 for ch in proof['changes']:
  clips=actual.get(ch['cell'],[]);assert len(clips)==1 and len(clips[0]['fragments'])==1,'new_source_mask_reference_box_ambiguous'
  box=clips[0];left,top,right,bottom=ch['source_clip_bounds'];insets=[top-box['y'],box['x']+box['width']-right,box['y']+box['height']-bottom,left-box['x']]
  c=cells[ch['cell']];before=c.get('value');new=before.replace('clip-path:inset(0px);','clip-path:inset('+' '.join(format(x,'.10g')+'px' for x in insets)+');',1)
  assert new!=before or insets==[0.,0.,0.,0.];c.set('value',new);ch.update(initial_reference_box={k:box[k] for k in ('x','y','width','height')},insets=insets,after_value=new)
 return E.tostring(root,encoding='unicode'),proof

def source_hidden_capture(record,dom,selected,expected_source_png,work):
 from playwright.sync_api import sync_playwright
 from html_actual_text_alignment import source_js,SOURCE_GLYPHS,CHROME
 source=(R/record['original_source_code']).read_bytes();assert sha(source)==record['source_code_sha256']
 from html_source_resources_v6 import asset_contract,verify_served
 asset,resources=asset_contract(source,record.get('original_asset_root'),R);viewport=__import__('PIL.Image',fromlist=['Image']).open(io.BytesIO(expected_source_png)).size;blocked=[];served={}
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage']);context=browser.new_context(viewport=dict(zip(['width','height'],viewport)),java_script_enabled=False,service_workers='block')
  try:
   def route(req):
    u=urllib.parse.urlparse(req.request.url);name=urllib.parse.unquote(u.path.lstrip('/'))
    if u.hostname!='source.invalid':blocked.append(req.request.url);req.abort();return
    if name=='index.html':req.fulfill(body=source,content_type='text/html');return
    target=(asset/name).resolve() if asset is not None else None
    if target is None or not target.is_relative_to(asset) or not target.is_file():blocked.append(req.request.url);req.abort();return
    blob=target.read_bytes();served[req.request.url]=blob;req.fulfill(body=blob,content_type=mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
   context.route('**/*',route);page=context.new_page();page.goto('http://source.invalid/index.html',wait_until='networkidle');page.evaluate('document.fonts.ready')
   fresh=page.evaluate(source_js());fresh=page.evaluate(SOURCE_GLYPHS,fresh)['dom'];normal=page.screenshot();assert normal==expected_source_png,'fresh_source_capture_not_repeatable'
   a=[{k:o[k] for k in ('id','text','qaOwner','qaTextNodeIndex','qaTextStart','qaTextEnd')} for o in fresh['objects'] if o['type']=='text' and str(o['id']+1) in selected]
   b=[{k:o[k] for k in ('id','text','qaOwner','qaTextNodeIndex','qaTextStart','qaTextEnd')} for o in dom['objects'] if o['type']=='text' and str(o['id']+1) in selected];assert a==b,'source_range_identity_changed'
   result=page.evaluate('''rows=>{const ranges=rows.map(o=>{const n=window.__img2codeAlignOwners[o.qaOwner].childNodes[o.qaTextNodeIndex];const r=document.createRange();r.setStart(n,o.qaTextStart);r.setEnd(n,o.qaTextEnd);return r;});CSS.highlights.set('img2code-source-ink-v6',new Highlight(...ranges));const s=document.createElement('style');s.textContent='::highlight(img2code-source-ink-v6){color:transparent;text-shadow:none;text-decoration-color:transparent;}';document.head.append(s);return {ranges:ranges.length,highlight:CSS.highlights.has('img2code-source-ink-v6')};}''',a)
   hidden=page.screenshot();assert not blocked;assert result['ranges']==len(selected);result['source_resources']=verify_served(served,asset,resources)
  finally:context.close();browser.close()
 Path(work).mkdir(parents=True,exist_ok=True);(Path(work)/'source.hidden.png').write_bytes(hidden)
 return hidden,result

def ink_metrics(source_png,source_hidden,native_png,native_hidden,offset):
 import numpy as np
 from PIL import Image
 src,bg,nat,nbg=[np.asarray(Image.open(io.BytesIO(b)).convert('RGB')).astype(int) for b in (source_png,source_hidden,native_png,native_hidden)]
 assert len(offset)==2 and all(abs(x-round(x))<1e-8 and x>=0 for x in offset)
 dx,dy=map(lambda n:int(round(n)),offset);a=np.zeros_like(nat);a[dy:dy+src.shape[0],dx:dx+src.shape[1]]=src-bg;b=nat-nbg
 masks=[np.any(x!=0,axis=2) for x in [a,b]];both=masks[0]&masks[1];delta=np.abs(a-b);ink=masks[0]|masks[1];ys,xs=np.where(ink)
 return {'source_ink_pixels':int(masks[0].sum()),'native_ink_pixels':int(masks[1].sum()),'mask_disagreement_pixels':int((masks[0]^masks[1]).sum()),'actual_color_contribution_disagreement_pixels':int(np.any(delta!=0,axis=2).sum()),'maximum_channel_difference':int(delta.max()),'source_ink_recall':float(both.sum()/max(masks[0].sum(),1)),'native_ink_precision':float(both.sum()/max(masks[1].sum(),1)),'ink_bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)] if len(xs) else None,'exact_same_domain_source_native_ink':bool(np.array_equal(a,b))}
