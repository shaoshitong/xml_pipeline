"""Fresh HTML source DOM -> source glyph placement/masks -> portable fonts.

Never seeds from an old native approximation. The target reference selects no
layout/font/clip parameter; its declared pixel dimensions define the source
poster viewport. Qualification remains a separate independent operation.
"""
import copy,hashlib,html,io,json,re,sqlite3,urllib.parse,uuid
from pathlib import Path
import xml.etree.ElementTree as E
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='html_source_frontend_v5';PADDING=32
UNIT='fresh_html_poster_DOM_ranges_rectangular_masks_source_ink_v5'
sha=lambda b:hashlib.sha256(b).hexdigest()

def configuration(data_root=R):
 if Path(data_root).resolve()!=R.resolve():raise ValueError('fresh_html_requires_HKUST_root')
 from compiler_html_source_quality_ro_v5 import pins
 p=pins();return dict(unit=UNIT,policy=VERSION+':'+sha(json.dumps(p,sort_keys=True).encode())[:20],pins=p)

def source_inputs(given):
 identifier=given['id'] if isinstance(given,dict) else given[0]
 with sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30) as d:row=d.execute('select input_record,input_manifest,format,category from jobs where id=?',(identifier,)).fetchone()
 if not row or not row[1] or row[2]!='html' or row[3]!='poster':raise ValueError('fresh_html_original_poster_scope_only')
 source,manifest=json.loads(row[0]),json.loads(row[1]);assert source['pair_sha256']==identifier,'fresh_html_original_ID_changed'
 code,image=[(R/manifest[k]).resolve(strict=True) for k in ['source_code','reference_image']]
 assert all(p.is_relative_to((R/'clean').resolve()) for p in [code,image]),'fresh_html_original_inputs_not_in_clean'
 cb,ib=code.read_bytes(),image.read_bytes();assert sha(cb)==source['code_sha256'] and sha(ib)==source['image_sha256'],'fresh_html_original_payload_hash_changed'
 return source,manifest,cb,ib

def static_support(given):
 result=dict(supported=False,unit=UNIT,reasons=[],source_only=True)
 try:
  from PIL import Image
  from compiler_types_source_ir_v1 import html_ir
  source,manifest,code,image=source_inputs(given);text=code.decode('utf-8');assert len(code)<=2_000_000,'fresh_html_source_size_pending'
  html_ir(text)
  forbidden=[('fresh_html_background_paint_pending',r'(?:linear|radial|conic)-gradient\s*\('),('fresh_html_font_face_source_pending',r'@font-face')]
  for reason,pattern in forbidden:
   assert not re.search(pattern,text,re.I),reason
  assert all(v.strip().lower()=='none' for v in re.findall(r'background-image\s*:([^;}]+)',text,re.I)),'fresh_html_background_paint_pending'
  assert all(v.strip().lower()=='none' for v in re.findall(r'(?:transform|filter|clip-path|mask(?:-image)?|text-shadow)\s*:([^;}]+)',text,re.I)),'fresh_html_css_transform_or_effect_pending'
  # A rounded background is an ordinary editable rectangle. Whether it also
  # clips a source text descendant is a computed-DOM fact, independently
  # rejected by the runtime source/mask verifier when unsupported.
  viewport=list(Image.open(io.BytesIO(image)).size);assert all(0<n<=8192-64 for n in viewport),'fresh_html_source_canvas_pending'
  asset=(R/(manifest.get('asset_root') or source.get('asset_root') or '')).resolve(strict=True);assert asset.is_relative_to((R/'clean').resolve()) and asset.is_dir(),'fresh_html_original_assets_not_in_clean'
  result.update(supported=True,source_viewport=viewport,original_source_code_sha256=source['code_sha256'],original_source_image_sha256=source['image_sha256'],source_poster_DOM_rectangular_masks=True)
 except Exception as exc:result['reasons']=[str(exc)[:1800]]
 return result

def repair(record,job,work):
 from fixed_batch_case_v1 import save,raw,checked
 from html_actual_text_alignment import capture_source,analyze
 from html_batch_v3 import convert
 from html_source_clip_v5 import plan,initialize,finalize,source_hidden_capture,ink_metrics
 from html_actual_text_clip_alignment_v4 import native_rectangle
 from html_text_whitespace_advance_v5 import plan as space_plan,propose as space_propose,actual_advance_checks
 from native_html_font_compiler_v3 import repair_fonts
 from native_worker import native
 import auto_quality_source_vector_v2 as coverage
 try:
  if record.get('source_format')!='html' or record.get('category')!='poster':raise ValueError('fresh_html_only_poster_scope')
  source,manifest,original_code,original_image=source_inputs(job)
  if (record['id'],record['source_code_sha256'],record['source_image_sha256'])!=(source['pair_sha256'],source['code_sha256'],source['image_sha256']):raise ValueError('fresh_html_source_job_identity_mismatch')
  checked(record['original_source_code'],source['code_sha256']);checked(record['original_reference'],source['image_sha256'])
  work=Path(work).resolve();assert work.is_relative_to(W.resolve());work.mkdir(parents=True,exist_ok=False)
  # Minimal identity only: old font/canvas/glyph metadata cannot affect source
  # reconstruction, ordering, native glyph positioning or clipping.
  seed={k:record[k] for k in ('id','source_pair_sha256','source','category','source_format','original_source_code','original_reference','original_asset_root','source_code_sha256','source_image_sha256')}
  seed.update(format='drawio',model=None,conversion_method=VERSION)
  dom,served,png,capture=capture_source(seed,work/'source');viewport=capture['viewport'];size=[n+2*PADDING for n in viewport]
  assert all(n<=8192 for n in size),'fresh_html_padded_viewport_limit'
  assert not [i for i in dom.get('unsupported',[]) if i.get('reason')!='css_stacking_order'],'fresh_html_unsupported_source_features'
  # Existing asset converter verifies original embedded payload provenance.
  assets=(R/seed['original_asset_root']).resolve();paths={}
  for url,blob in served.items():
   target=(assets/urllib.parse.unquote(urllib.parse.urlparse(url).path.lstrip('/'))).resolve();assert target.is_relative_to(assets) and target.read_bytes()==blob;paths[url]=target
  native_dom=copy.deepcopy(dom)
  for obj in native_dom['objects']:
   obj['x']+=PADDING;obj['y']+=PADDING
   if obj['type']=='text':obj['fontFamily']=obj.get('actualSourceCss',{}).get('fontFamily',obj.get('fontFamilyRaw',obj['fontFamily']))
  xml,asset_map=convert(native_dom,paths,*size);root=E.fromstring(xml);cellroot=root.find('.//mxGraphModel/root');lookup={str(o['id']+1):o for o in dom['objects']};order=dom['_source_paint_order'];vertices=[c for c in list(cellroot) if c.get('vertex')=='1']
  for c in vertices:cellroot.remove(c)
  for c in sorted(vertices,key=lambda c:(order[str(lookup[c.get('id')]['id'])],lookup[c.get('id')].get('qaPaintEvent',0),lookup[c.get('id')].get('qaTextStart',0))):cellroot.append(c)
  xml=E.tostring(root,encoding='unicode');renderer=W/'rendering_clipbox_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
  def render(code,name):
   a=native.native_job(code,*size,180,renderer,8192,runtime);assert a.get('ok'),a.get('error');assert a['native_render'].get('selected_image')=='declared_first_page','fresh_html_source_padding_not_complete';save(work/(name+'.drawio'),code.encode());save(work/(name+'.png'),a['png']);save(work/(name+'.native.json'),raw(a['native_render']));return a
  before=render(xml,'source_seed');spacedom=copy.deepcopy(dom)
  for o in spacedom['objects']:
   if o['type']=='text':o.setdefault('sourceClip',{})['partial']=False
  spaces=space_plan(spacedom,before['native_render'],xml,(PADDING,PADDING));spaceproof=None
  if spaces['objects']:
   new,spaceproof=space_propose(xml,spaces);after=render(new,'source_spaces');assert all(a['ok'] for a in actual_advance_checks(spaceproof,before['native_render'],after['native_render'])),'fresh_html_space_run_boundary_changed';xml=new;before=after
  mask=plan(xml,dom,before['native_render'],viewport,(PADDING,PADDING),all_text=True)
  assert not mask['unsupported'],'fresh_html_source_glyph_or_mask_pending:'+json.dumps(mask['unsupported'])[:3500]
  assert len(mask['changes'])==sum(o['type']=='text' for o in dom['objects']),'fresh_html_unmapped_source_text'
  init=render(initialize(xml,mask),'source_mask_reference');new,mask=finalize(initialize(xml,mask),mask,init['native_render']);final=render(new,'source_compiled')
  glyphs={row['cell']:row for row in analyze(dom,final['native_render'],new,(PADDING,PADDING))['objects']};clips={row['cell']:row['clips'] for row in final['native_render']['actual_clip_boxes']}
  for row in mask['changes']:
   g=glyphs[row['cell']];assert g['maximum_absolute_position_error']<=.08 and g['maximum_glyph_size_difference']<=.08,'fresh_html_final_source_glyph_mismatch'
   assert len(clips[row['cell']])==1 and all(abs(a-b)<=.03 for a,b in zip(native_rectangle(clips[row['cell']][0]),row['source_clip_bounds'])),'fresh_html_final_source_clip_mismatch'
  selected={r['cell'] for r in mask['changes']};bg=E.fromstring(new)
  for c in bg.iter('mxCell'):
   if c.get('id') in selected:c.set('value','')
  background=render(E.tostring(bg,encoding='unicode'),'source_native_background');hidden,hiddenproof=source_hidden_capture(seed,dom,selected,png,work/'source_hidden');ink=ink_metrics(png,hidden,final['png'],background['png'],(PADDING,PADDING));assert ink['exact_same_domain_source_native_ink'],'fresh_html_source_native_text_ink_mismatch:'+json.dumps(ink)
  paint=coverage._html_coverage(dom,new,served);stack=coverage._html_paint_order(dom,new);assert paint['ok'] and stack['ok'],'fresh_html_complete_source_coverage_failed'
  dest=R/'clean/html_source_frontend_v5'/seed['id'][:2]/seed['id']/uuid.uuid4().hex;dest.mkdir(parents=True)
  save(dest/'source_compiled.drawio',new.encode());save(dest/'source_compiled.png',final['png'])
  manifest=dict(schema=VERSION,unit=UNIT,implementation_pins=configuration()['pins'],source_code_sha256=seed['source_code_sha256'],source_image_sha256=seed['source_image_sha256'],source_viewport=viewport,source_offset=[PADDING,PADDING],native_canvas=size,source_dom_sha256=sha(raw(dom)),source_seed_sha256=sha((work/'source_seed.drawio').read_bytes()),pre_font_code_sha256=sha(new.encode()),pre_font_png_sha256=sha(final['png']),source_text_objects=len(selected),spaces=spaceproof,masks=mask,all_source_native_text_ink=ink,source_coverage=paint,source_paint_order=stack,work=str(work.relative_to(R)),target_image_score_parameter_search=False)
  save(work/'source_compilation.json',raw(manifest))
  seed.update(code_file=str((dest/'source_compiled.drawio').relative_to(R)),image_file=str((dest/'source_compiled.png').relative_to(R)),code_sha256=sha(new.encode()),image_sha256=sha(final['png']),source_assets=asset_map,render=final['native_render'],vertices=len(dom['objects']),text_objects=len(selected),edges=0,bound_edges=0,html_source_frontend_v5=manifest)
  save(work/'pre_font_record.json',raw(seed));a=repair_fonts(seed,job,work/'portable_fonts')
  if not a.get('ok'):return dict(ok=False,reason='fresh_html_font_embedding_pending',detail=a,model_calls=0)
  out=a['record'];save(work/'candidate_record.json',raw(out));return dict(ok=True,record=out,record_file=str(work/'candidate_record.json'),work=str(work),model_calls=0)
 except Exception as exc:return dict(ok=False,reason=str(exc)[:5000],error_type=type(exc).__name__,model_calls=0)

def convert(record,job,work):return repair(record,job,work)
