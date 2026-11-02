"""Finite source-layout language compiler; no jobs/queues/model/publication APIs.

Fresh fixed source renderer -> one declared full-viewBox projection -> source
DOM -> existing native objects. Source/reference failure is terminal, not fitted.
All dataset bytes, DOM, XML, fonts and images stay under the registered HKUST root.
"""
from __future__ import annotations
import collections, copy, hashlib, html, io, json, re, uuid
from pathlib import Path
import xml.etree.ElementTree as ET

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='compiler_languages_source_layout_v1';FIELD=VERSION
UNITS={'mermaid':'mermaid_flat_source_svg_v1','plantuml':'plantuml_flat_engine_entity_svg_v1'}
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
PROJECTION='sole_complete_full_viewbox_xMidYMid_meet_v1'
DEPENDENCIES=('compiler_languages_source_layout_v1.py','mermaid_dom_adapter_v2.js','svg_dom_mermaid_v3.js','mermaid_native_v1.py','mermaid_native_v2.py','mermaid_semantic_audit.py','mermaid_semantic_v4.py','mermaid_geometry_coverage.py','mermaid_geometry_batch.py','plantuml_runtime.py','plantuml_fonts.py','plantuml_dom_adapter_v2.js','plantuml_native.py','svg_dom_v6.js','svg_convert_v2.py','svg_convert_v3.py','svg_source_coverage_v2.py','portable_native_fonts.py','pdf_to_native.py','native_label_paint_order.py','auto_quality_move.py','auto_quality_common_v4.py','compiler_native_languages_v1.py')
sha=lambda b:hashlib.sha256(b).hexdigest()
raw=lambda v:(json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()

def require(ok,reason):
 if not ok:raise ValueError(reason)

def _write(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():require(p.read_bytes()==b,'immutable_payload_changed')
 else:
  with p.open('xb') as f:f.write(b)

def _entry(p):return {'file':str(Path(p).relative_to(R)),'sha256':sha(Path(p).read_bytes())}

def _read(entry,clean=False):
 p=(R/entry['file']).resolve(strict=True);require(p.is_relative_to(R/'clean' if clean else R),'payload_outside_root')
 b=p.read_bytes();require(sha(b)==entry['sha256'],'payload_hash_changed');return b

def configuration(data_root=R):
 require(Path(data_root).resolve()==R,'requires_registered_HKUST_root')
 pins={str(W/'scripts'/n):sha((W/'scripts'/n).read_bytes()) for n in DEPENDENCIES}
 from mermaid_geometry_batch import BUNDLE,BUNDLE_SHA
 from plantuml_runtime import JAR,JAR_SHA
 require(sha(BUNDLE.read_bytes())==BUNDLE_SHA and sha(JAR.read_bytes())==JAR_SHA,'source_runtime_changed')
 for p in (BUNDLE,JAR,Path(CHROME),R/'evaluation/assets/viewer-static.min.js'):
  pins[str(p)]=sha(p.read_bytes())
 return {'policy':VERSION+':'+sha(raw(pins))[:20],'pins':pins,'units':UNITS,'source_requires_native_info':False,
         'projection':PROJECTION,'unseen_ready':False,'automatic_rollout':False}

def _job(job):
 if isinstance(job,dict):return job
 names=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
 require(len(job)==len(names),'invalid_full_job');return dict(zip(names,job))

def _inputs(record,job=None):
 j=_job(job or record) if (job is not None or 'input_record' in record) else None
 if j:
  source=json.loads(j['input_record']);manifest=json.loads(j['input_manifest']) if j.get('input_manifest') else None
  require(manifest is not None,'requires_existing_original_manifest')
  code=_read({'file':manifest['source_code'],'sha256':source['code_sha256']})
  ref=_read({'file':manifest['reference_image'],'sha256':source['image_sha256']})
  return source,code,ref
 source=record.get('source_record')
 require(isinstance(source,dict),'missing_authoritative_source_record')
 code=_read({'file':record['original_source_code'],'sha256':source['code_sha256']},True)
 ref=_read({'file':record['original_reference'],'sha256':source['image_sha256']},True)
 return source,code,ref

def static_support(record_or_job):
 out={'supported':False,'unit':None,'reasons':[],'scope':'Static eligibility; complete source/scene and reference reproduction remain mandatory.'}
 try:
  source,code,ref=_inputs(record_or_job);fmt=source['format'];text=code.decode('utf-8-sig')
  require(fmt in UNITS,'unsupported_language');require(len(code)<=200000,'source_too_large')
  if fmt=='mermaid':
   require(re.search(r'^\s*(?:graph|flowchart)\s+(?:TB|TD|BT|LR|RL)\b',text,re.M),'unsupported_mermaid_type')
   require(not re.search(r'^\s*subgraph\b',text,re.M),'source_hierarchy_unsupported')
   require('%%{' not in text and not text.lstrip().startswith('---'),'source_runtime_configuration_unsupported')
  else:
   from compiler_native_languages_v1 import parse_plantuml
   ir=parse_plantuml(text)
   require(all(n['shape'] in ('component','rectangle','node','database','cloud','queue','interface') for n in ir['nodes']),'unsupported_entity_type')
  from PIL import Image
  size=Image.open(io.BytesIO(ref)).size;require(max(size)<=8192 and size[0]*size[1]<=64000000,'source_canvas_resource_bound')
  out.update(supported=True,unit=UNITS[fmt],source_id=source['pair_sha256'],source_format=fmt,reference_canvas=list(size))
 except Exception as e:out['reasons']=[str(e)[:1500]]
 return out

PROJECT_JS=r'''([w,h])=>{const s=document.querySelector('svg');if(!s)throw Error('source_svg_missing');let v=s.viewBox.baseVal;if(!(v.width>0&&v.height>0)){const sw=s.width.baseVal.value,sh=s.height.baseVal.value;if(!(sw>0&&sh>0))throw Error('source_viewbox_missing');s.setAttribute('viewBox',`0 0 ${sw} ${sh}`);v=s.viewBox.baseVal;}const original=[v.x,v.y,v.width,v.height];s.style.maxWidth='none';s.style.width=w+'px';s.style.height=h+'px';s.setAttribute('width',w);s.setAttribute('height',h);s.setAttribute('preserveAspectRatio','xMidYMid meet');const scale=Math.min(w/v.width,h/v.height);return {policy:'sole_complete_full_viewbox_xMidYMid_meet_v1',source_viewBox:original,reference_viewport:[w,h],scale,translation:[(w-v.width*scale)/2-v.x*scale,(h-v.height*scale)/2-v.y*scale],crop:false,parameter_search:false,individual_object_changes:false};}'''

def _capture(source,code,reference,work):
 """Fresh source only. Target never calls a layout algorithm."""
 from PIL import Image
 from playwright.sync_api import sync_playwright
 fmt=source['format'];w,h=Image.open(io.BytesIO(reference)).size;work=Path(work);work.mkdir(parents=True,exist_ok=True)
 ast=None;engine_png=None
 if fmt=='plantuml':
  from plantuml_runtime import run
  svg=run(work,code,'svg');engine_png=run(work,code,'png')
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
  try:
   context=browser.new_context(viewport={'width':w,'height':h},service_workers='block');blocked=[]
   context.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page=context.new_page();page.set_default_timeout(45000)
   if fmt=='mermaid':
    from mermaid_geometry_batch import BUNDLE
    from mermaid_semantic_audit import PARSE
    page.set_content('<html><body></body></html>');page.add_script_tag(path=str(BUNDLE))
    svg=page.evaluate("async code=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:200000,flowchart:{htmlLabels:true}});return (await mermaid.render('source_layout_fixed_v1',code)).svg;}",code.decode('utf-8-sig')).encode()
    ast=page.evaluate(PARSE,code.decode('utf-8-sig'))
    require(ast['type'] in ('flowchart','flowchart-v2') and not ast.get('groups'),'source_hierarchy_or_diagram_type_unsupported')
    require(all(e.get('type') in ('arrow_point','arrow_open','double_arrow_point') for e in ast['edges']),'source_marker_type_unsupported')
   page.set_content('<style>html,body{margin:0;padding:0;background:white;overflow:hidden}</style>'+svg.decode())
   frame=page.evaluate(PROJECT_JS,[w,h]);font_resolution=None
   if fmt=='plantuml':
    from plantuml_fonts import resolve
    font_resolution=resolve(page,work);require(not font_resolution['needs_glyph_fallback_review'],'source_physical_multifont_unsupported')
   page.evaluate('document.fonts.ready');source_png=page.screenshot();projected_svg=page.locator('svg').evaluate('s=>s.outerHTML').encode()
   if fmt=='mermaid':
    metadata=page.evaluate((W/'scripts/mermaid_dom_adapter_v2.js').read_text(),ast)
    require(page.screenshot()==source_png,'source_adapter_changed_pixels')
    dom=page.evaluate((W/'scripts/svg_dom_mermaid_v3.js').read_text())
    require(page.screenshot()==source_png,'source_extractor_changed_pixels')
   else:
    metadata=page.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text())
    require(metadata['groups'] and not metadata.get('parents'),'source_entity_hierarchy_unsupported')
    require(all(g['kind']=='entity' and g['method']=='engine_entity_metadata' for g in metadata['groups']),'source_entity_identity_inferred_unsupported')
    require(not metadata.get('issues') and len(metadata['links'])==metadata['expectedLinkCount'],'source_link_identity_incomplete')
    require(page.screenshot()==source_png,'source_adapter_changed_pixels')
    dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text())
    require(page.screenshot()==source_png,'source_extractor_changed_pixels')
   require(not blocked,'source_external_resources');require(not dom.get('issues'),'source_visible_feature_unsupported:'+json.dumps(dom.get('issues'))[:800])
   if fmt=='plantuml':
    from compiler_native_languages_v1 import parse_plantuml
    ir=parse_plantuml(code.decode('utf-8-sig'));expected={n['id'] for n in ir['nodes']};require(expected=={g['name'] for g in metadata['groups']},'source_engine_entity_inventory_mismatch')
    require(collections.Counter((e['source'],e['target']) for e in ir['edges'])==collections.Counter(tuple(e['entities']) for e in metadata['links']),'source_engine_link_inventory_mismatch')
    ast=ir
   return dict(svg=svg,projected_svg=projected_svg,png=source_png,engine_png=engine_png,ast=ast,metadata=metadata,dom=dom,frame=frame,font_resolution=font_resolution,browser_version=browser.version)
  finally:browser.close()

def _source_visual(reference,capture):
 from auto_quality_common_v4 import image_quality
 positions=[]
 for o in capture['dom']['objects']:
  if o['type']=='text' and o.get('text','').strip():
   b=o['bbox'];positions.append({'cell':'source:'+o['id'],'runs':[{'chars':[{'text':o['text'],'x':b['x'],'y':b['y'],'width':b['w'],'height':b['h']}]}]})
 result=image_quality(reference,capture['png'],{},positions)
 return {'ok':result['ok'],'reason':'source_reference_reproduced' if result['ok'] else 'source_engine_reference_mismatch','visual':result,'projection':capture['frame'],'fixed_config_no_search':True}

def _emit(fmt,capture,width,height):
 from svg_source_coverage_v2 import audit
 if fmt=='mermaid':
  from mermaid_native_v2 import build
  from mermaid_geometry_coverage import check
  from mermaid_semantic_v4 import check as semantic
  xml,stats,dom=build(capture['dom'],width,height,capture['metadata'])
  geometry=check(capture['ast'],xml,capture['metadata']);sem=semantic(capture['ast'],xml)
  require(geometry['ok'] and sem['status']=='node_edge_text_match','source_native_semantic_loss')
 else:
  from plantuml_native import build
  xml,stats=build(capture['dom'],width,height,capture['metadata']);dom=capture['dom'];geometry={};sem={}
 coverage=audit(dom,xml,stats);require(coverage['ok'],'source_native_object_loss:'+json.dumps(coverage['errors'])[:1000])
 require(not any(o.get('type')=='image' for o in dom['objects']),'source_image_fallback_unsupported')
 markers=stats.get('native_graphviz_arrowheads',[])
 if fmt=='plantuml':
  require(not any(o.get('filterDefinition') for o in dom['objects']),'source_filter_unsupported')
  # Every source arrow primitive must become an attached native marker.
  source_arrows={o['id'] for o in dom['objects'] if o.get('edge') and o.get('tag')=='polygon'}
  require(source_arrows=={m['source_arrow_object'] for m in markers},'source_marker_coverage_incomplete')
 return xml,stats,dom,{'object_coverage':coverage,'geometry':geometry,'semantic':sem}

def _canonical(xml):return ET.canonicalize(xml)

def _replay_font_delta(xml,proof,fonts):
 from svg_convert_v3 import unpack,pack
 from pdf_to_native import attach_fonts
 root=ET.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')}
 for c in proof['changes']:
  cell=cells[c['cell']];st=unpack(cell.get('style'));require(st.get('fontFamily')==c['before_family'] and int(st.get('fontStyle',0))==c['before_flags'],'font_delta_origin_changed')
  st.update(fontFamily=c['family'],fontStyle=str(c['after_flags']));cell.set('style',pack(st))
 return attach_fonts(ET.tostring(root,encoding='unicode'),fonts) if fonts else ET.tostring(root,encoding='unicode')

def convert(record,job,work):
 result={'ok':False,'supported':False,'reason':None,'model_calls':0,'qualified':False};stage='input'
 try:
  work=Path(work).resolve();require(work.is_relative_to(W/VERSION),'unowned_compiler_work');work.mkdir(parents=True,exist_ok=False)
  j=_job(job);predicate=static_support(j);result['static_support']=predicate
  require(predicate['supported'],'typed_unsupported:'+json.dumps(predicate['reasons']))
  source,code,reference=_inputs(record,j);fmt=source['format'];config=configuration();result['supported']=True
  stage='source_reference';capture=_capture(source,code,reference,work/'source');reproduction=_source_visual(reference,capture)
  _write(work/'source_reproduction.json',raw(reproduction));result['source_reproduction']=reproduction
  if not reproduction['ok']:result.update(reason='source_engine_reference_mismatch',diagnostic_stage='source_engine_reference_mismatch',development_not_ready=True);return result
  from PIL import Image
  width,height=Image.open(io.BytesIO(reference)).size;stage='conversion';xml,stats,dom,coverage=_emit(fmt,capture,width,height)
  from playwright.sync_api import sync_playwright
  from portable_native_fonts import ready_page,capture as capture_fonts,embed
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
   try:
    paint_order=None
    if fmt=='mermaid':
     from native_label_paint_order import repair
     xml,paint_order=repair(browser,xml,stats['native_html_label_backgrounds'])
    base_xml=xml;page=ready_page(browser)
    try:observations=capture_fonts(page,xml);xml,fonts,fontproof=embed(xml,observations,work/'fonts');require(not fontproof['issues'],'source_font_embedding_unsupported')
    finally:page.close()
   finally:browser.close()
  from native_worker import native
  from strict_canvas_gate import require_declared_page
  renders=[]
  for x in (base_xml,xml):
   v=native.native_job(x,width,height,180,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');require(v['ok'],'native_render_failed');require_declared_page(v['native_render'],width,height);renders.append(v)
  require(renders[0]['png']==renders[1]['png'],'font_embedding_changed_native_pixels')
  dest=R/'clean'/VERSION/source['pair_sha256'][:2]/source['pair_sha256']/uuid.uuid4().hex;dest.mkdir(parents=True)
  payloads={'original_source':(code,'txt'),'original_reference':(reference,'png'),'source_raw_svg':(capture['svg'],'svg'),'source_svg':(capture['projected_svg'],'svg'),'source_png':(capture['png'],'png'),'source_dom':(raw(capture['dom']),'json'),'source_ast':(raw(capture['ast']),'json'),'source_metadata':(raw(capture['metadata']),'json'),'source_frame':(raw(capture['frame']),'json'),'source_stats':(raw(stats),'json'),'unembedded_xml':(base_xml.encode(),'drawio'),'font_proof':(raw(fontproof),'json'),'source_reproduction':(raw(reproduction),'json'),'candidate_xml':(xml.encode(),'drawio'),'candidate_png':(renders[1]['png'],'png')}
  if capture['engine_png']:payloads['engine_png']=(capture['engine_png'],'png')
  files={}
  for k,(b,ext) in payloads.items():p=dest/(k+'.'+ext);_write(p,b);files[k]=_entry(p)
  for f in fonts.values():
   for key,hkey in [('file','sha256'),('original_file','original_sha256')]:
    b=Path(f[key]).read_bytes();require(sha(b)==f[hkey],'font_bytes_changed');p=dest/(key+'_'+f[hkey]+Path(f[key]).suffix);_write(p,b);f[key]=str(p.relative_to(R))
  _write(dest/'fonts.json',raw(fonts));files['fonts']=_entry(dest/'fonts.json')
  cells=list(ET.fromstring(xml).iter('mxCell'));text_ids=[c.get('id') for c in cells if c.get('value','').strip()];edges=[c for c in cells if c.get('edge')=='1'];vertices={c.get('id') for c in cells if c.get('vertex')=='1'}
  proof={'unit':UNITS[fmt],'policy':config['policy'],'pins':config['pins'],'files':files,'source_code_sha256':source['code_sha256'],'source_image_sha256':source['image_sha256'],'candidate_code_sha256':sha(xml.encode()),'coverage':coverage,'projection':capture['frame'],'required_text_cell_ids':text_ids,'paint_order':paint_order,'source_reference_reproduced':True}
  out={k:source[k] for k in ('source','category')};out.update(id=source['pair_sha256'],source_pair_sha256=source['pair_sha256'],source_format=fmt,source_record=source,format='drawio',source_code_sha256=source['code_sha256'],source_image_sha256=source['image_sha256'],code_file=files['candidate_xml']['file'],code_sha256=files['candidate_xml']['sha256'],image_file=files['candidate_png']['file'],image_sha256=files['candidate_png']['sha256'],original_source_code=files['original_source']['file'],original_reference=files['original_reference']['file'],source_render_svg=files['source_svg']['file'],source_render_svg_sha256=files['source_svg']['sha256'],source_render_png=files['source_png']['file'],source_render_png_sha256=files['source_png']['sha256'],native_embedded_fonts=list(fonts.values()),conversion_method=VERSION,quality_state='pending_independent_full_quality',vertices=len(vertices),edges=len(edges),bound_edges=sum(e.get('source') in vertices and e.get('target') in vertices for e in edges),svg_conversion=stats,model=None,model_calls=0,accepted=False,candidate_quality_adapter={'file':str(Path(__file__).resolve()),'sha256':sha(Path(__file__).read_bytes()),'policy':config['policy']},**{FIELD:proof})
  _write(dest/'record.json',raw(out));result.update(ok=True,reason='native_candidate_pending_full_quality',record=out,record_file=str(dest/'record.json'),diagnostic_stage=None)
 except Exception as e:result.update(reason=str(e).split(':',1)[0],detail=str(e)[:2500],diagnostic_stage=stage,error_type=type(e).__name__,development_not_ready=True)
 finally:
  if 'work' in locals() and work.is_dir():_write(work/'result.json',raw(result))
 return result

def validate_source(record,xml):
 out={'profile':VERSION,'supported':False,'ok':False,'failures':[],'evidence':{}}
 try:
  proof=record[FIELD];config=configuration();require(proof['policy']==config['policy'] and proof['pins']==config['pins'],'source_implementation_changed')
  require(record['code_sha256']==proof['candidate_code_sha256']==sha(xml.encode()),'candidate_revision_changed')
  for f in proof['files'].values():_read(f,True)
  source,code,reference=_inputs(record);require((sha(code),sha(reference))==(proof['source_code_sha256'],proof['source_image_sha256']),'source_revision_changed')
  replay_work=W/VERSION/'source_validation'/record['id']/uuid.uuid4().hex
  capture=_capture(source,code,reference,replay_work)
  require(capture['svg']==_read(proof['files']['source_raw_svg'],True),'fresh_source_svg_changed')
  require(capture['projected_svg']==_read(proof['files']['source_svg'],True),'fresh_source_projection_changed')
  require(capture['png']==_read(proof['files']['source_png'],True),'fresh_source_pixels_changed')
  require(raw(capture['dom'])==_read(proof['files']['source_dom'],True),'fresh_source_DOM_changed')
  require(_source_visual(reference,capture)['ok'],'source_engine_reference_mismatch')
  from PIL import Image
  w,h=Image.open(io.BytesIO(reference)).size;base,stats,dom,coverage=_emit(source['format'],capture,w,h)
  if proof.get('paint_order'):
   from native_label_paint_order import reorder
   base=reorder(base,proof['paint_order'])
  require(_canonical(base)==_canonical(_read(proof['files']['unembedded_xml'],True).decode()),'fresh_source_native_replay_changed')
  fonts=json.loads(_read(proof['files']['fonts'],True));fontproof=json.loads(_read(proof['files']['font_proof'],True))
  for f in fonts.values():
   for k,d in [('file','sha256'),('original_file','original_sha256')]:_read({'file':f[k],'sha256':f[d]},True)
  replay=_replay_font_delta(base,fontproof,fonts);require(_canonical(replay)==_canonical(xml),'source_geometry_text_or_paint_changed')
  cells=list(ET.fromstring(xml).iter('mxCell'));require(all(c.get('visible','1')!='0' for c in cells),'source_object_hidden')
  out.update(supported=True,ok=True,evidence={'complete_source_coverage':True,'required_text_cell_ids':proof['required_text_cell_ids'],'unit':proof['unit'],'coverage':coverage,'candidate_code_sha256':record['code_sha256'],'source_code_sha256':sha(code),'source_image_sha256':sha(reference),'source_layout_replay_exact':True,'source_objects_cropped':False,'source_reference_reproduced':proof['source_reference_reproduced']})
 except Exception as e:out['failures']=[{'reason':str(e).split(':',1)[0],'detail':str(e)[:2500]}]
 return out

def source_reproduction(record,work):
 try:
  source,code,ref=_inputs(record);capture=_capture(source,code,ref,work);result=_source_visual(ref,capture)
  if record.get(FIELD):
   f=record[FIELD]['files'];require(capture['svg']==_read(f['source_raw_svg'],True),'fresh_source_svg_changed');require(capture['projected_svg']==_read(f['source_svg'],True),'fresh_source_projection_changed');require(capture['png']==_read(f['source_png'],True),'fresh_source_pixels_changed')
  return {'supported':True,**result}
 except Exception as e:return {'supported':False,'ok':False,'reason':str(e).split(':',1)[0],'detail':str(e)[:2000]}

def check_source(record,xml,source,data_root,native_info=None):
 require(Path(data_root).resolve()==R,'requires_registered_root');require(sha(source.encode())==record['source_code_sha256'],'source_argument_changed');return validate_source(record,xml)

def audit_editing(record,xml,source_profile,data_root):
 require(source_profile.get('ok') and source_profile['evidence']['candidate_code_sha256']==sha(xml.encode()),'editing_source_profile_missing')
 from auto_quality_move import audit
 result=audit(xml);require(len(result['moves'])==2*record['edges'],'endpoint_move_coverage_incomplete')
 for m in result['moves']:
  require(abs(m['delta']['x']-17)<.05 and abs(m['delta']['y']-11)<.05,'edge_endpoint_did_not_follow')
  require(all(abs(c['x']-17)<.05 and abs(c['y']-11)<.05 for c in m['child_deltas']),'node_children_did_not_follow')
  for label in m['label_member_deltas']:
   ds=label['members'];require(not ds or all(abs(v[a]-ds[0][a])<.05 for v in ds for a in ('x','y')),'edge_label_group_split')
 if record['source_format']=='mermaid':
  from mermaid_native_v2 import check_backgrounds
  check_backgrounds(xml,record['svg_conversion']['native_html_label_backgrounds'])
 return {'ok':True,'profile':VERSION+'_editing','endpoint_moves':len(result['moves']),'details':result}
