"""Source-only PlantUML integer-canvas proof, independent of B/C candidates.

Exactly one policy: retain natural source coordinates, pad Java PNG only on
right/bottom by zero or one white pixel. No reference-pixel search or target
conversion. Source proof failure is terminal for this proposed release unit.
"""
from __future__ import annotations
import io,json,math,sqlite3,uuid
from pathlib import Path
import xml.etree.ElementTree as ET
import compiler_languages_source_layout_v1 as base

R=base.R;W=base.W;VERSION='compiler_plantuml_integer_canvas_v2'
UNIT='plantuml_flat_engine_entity_natural_integer_canvas_v2'
sha=base.sha;raw=base.raw;require=base.require
CASES=('04fab87123d9acfe24b7a8ef0b016177bba1851406b97a069a17302159b7f93f','05d8175a2fb3584a719ae6f25a656ba9b75a857d6b5355be417b53155f584798','07095aef5ebedf54481c4f3c0ff4ab6e5baaf2526e7f457abca706320509a290','741dba10f203580e613cfc70c0aa6e9d3650ef4188379018741dc6b7d762c1bd')
NATURAL=r'''()=>{const s=document.querySelector('svg'),v=s.viewBox.baseVal,w=s.width.baseVal.value,h=s.height.baseVal.value;if(!(w>0&&h>0&&v.width>0&&v.height>0))throw Error('missing_natural_source_canvas');if(Math.abs(v.x)>1e-8||Math.abs(v.y)>1e-8||Math.abs(w-v.width)>1e-8||Math.abs(h-v.height)>1e-8)throw Error('source_natural_viewBox_not_one_pixel_units');s.style.maxWidth='none';s.style.width=w+'px';s.style.height=h+'px';s.style.position='absolute';s.style.left='0px';s.style.top='0px';return {source_viewBox:[v.x,v.y,v.width,v.height],natural_size:[w,h],scale:[1,1],translation:[0,0],preserveAspectRatio:s.getAttribute('preserveAspectRatio')||'xMidYMid meet',no_reference_derived_parameters:true};}'''
EXTENT=r'''()=>{const s=document.querySelector('svg'),items=[],issues=[];for(const e of s.querySelectorAll('*')){if(e.closest('defs,style,metadata,title,desc'))continue;const tag=e.localName;if(['g','a','switch','tspan'].includes(tag))continue;if(!['path','rect','circle','ellipse','line','polygon','polyline','text'].includes(tag)){issues.push({tag,reason:'unhandled_source_element'});continue;}const c=getComputedStyle(e);if(c.display==='none'||c.visibility==='hidden')continue;let opacity=1;for(let p=e;p&&p!==s.parentElement;p=p.parentElement)opacity*=+getComputedStyle(p).opacity;if(!opacity)continue;for(const key of ['clipPath','filter','mask','maskImage'])if(c[key]&&c[key]!=='none')issues.push({tag,reason:'unproved_effect',effect:key});if(c.markerStart!=='none'||c.markerEnd!=='none'||c.markerMid!=='none')issues.push({tag,reason:'unexpanded_marker'});const fill=c.fill!=='none'&&+c.fillOpacity>0,stroke=c.stroke!=='none'&&parseFloat(c.strokeWidth)>0&&+c.strokeOpacity>0;if(!fill&&!stroke)continue;if(tag==='text'&&!e.textContent.trim())continue;const b=e.getBoundingClientRect(),m=e.getScreenCTM();if(!m)throw Error('missing_source_matrix');const aa=m.a*m.a+m.b*m.b,bb=m.c*m.c+m.d*m.d,ab=m.a*m.c+m.b*m.d;const maxScale=Math.sqrt((aa+bb+Math.sqrt((aa-bb)**2+4*ab*ab))/2);let pad=stroke?parseFloat(c.strokeWidth)*maxScale/2:0;const miter=parseFloat(c.strokeMiterlimit);if(stroke&&c.strokeLinejoin==='miter'){if(!(miter>0&&isFinite(miter)))issues.push({tag,reason:'missing_miterlimit'});else pad*=Math.max(1,miter);}items.push({tag,sourceId:e.id||null,bbox:[b.x,b.y,b.right,b.bottom],stroke_half_width_padding:pad,linejoin:c.strokeLinejoin,miter_limit:miter,paint_envelope:[b.x-pad,b.y-pad,b.right+pad,b.bottom+pad],text:tag==='text',background:tag==='rect'&&b.x<=0&&b.y<=0});}if(!items.length)issues.push({reason:'blank_source'});return {issues,items,envelope:items.length?[Math.min(...items.map(x=>x.paint_envelope[0])),Math.min(...items.map(x=>x.paint_envelope[1])),Math.max(...items.map(x=>x.paint_envelope[2])),Math.max(...items.map(x=>x.paint_envelope[3]))]:null,method:'Visible graphics/text CSS boxes, exact maximum singular transform scale, actual CSS stroke-miterlimit conservative expansion. Source PlantUML arrows must be explicit polygon/path primitives; SVG marker references are unsupported.',conservative_not_tight:true};}'''

def configuration(data_root=R):
 require(Path(data_root).resolve()==R,'requires_registered_root');v1=base.configuration();pins=dict(v1['pins']);pins[str(Path(__file__).resolve())]=sha(Path(__file__).read_bytes())
 return {'policy':UNIT+':'+sha(raw(pins))[:20],'unit':UNIT,'pins':pins,'projection':'natural_pixel_origin_zero_right_bottom_white_padding_each_axis_0_or_1','source_proof_independent_of_candidate':True,'candidate_checker_ready':False,'unseen_ready':False,'automatic_rollout':False}

def static_support(record_or_fulljob):
 result=base.static_support(record_or_fulljob)
 if result.get('source_format')!='plantuml':return {'supported':False,'unit':UNIT,'reasons':['requires_plantuml']}
 return {**result,'unit':UNIT}

def _natural_capture(code,reference_size,work):
 from PIL import Image
 from playwright.sync_api import sync_playwright
 from plantuml_runtime import run
 from plantuml_fonts import resolve
 svg=run(work,code,'svg');png=run(work,code,'png');root=ET.fromstring(svg);vb=[float(v) for v in root.get('viewBox','').replace(',',' ').split()];require(len(vb)==4,'missing_source_viewbox')
 natural=[math.ceil(vb[2]),math.ceil(vb[3])];viewport=[max(natural[i],reference_size[i]) for i in range(2)]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=base.CHROME,args=['--disable-dev-shm-usage'])
  try:
   context=browser.new_context(viewport={'width':viewport[0],'height':viewport[1]},java_script_enabled=False,service_workers='block');blocked=[];context.route('**/*',lambda r:(blocked.append(r.request.url),r.abort()));page=context.new_page();page.set_default_timeout(45000)
   page.set_content('<style>html,body{margin:0;padding:0;background:white}</style>'+svg.decode());frame=page.evaluate(NATURAL);fonts=resolve(page,work);page.evaluate('document.fonts.ready');before=page.screenshot();extent=page.evaluate(EXTENT)
   require(not extent['issues'],'source_paint_extent_unsupported:'+json.dumps(extent['issues'])[:1000]);require(not fonts['needs_glyph_fallback_review'],'source_font_fallback_unsupported')
   metadata=page.evaluate((W/'scripts/plantuml_dom_adapter_v2.js').read_text());require(page.screenshot()==before,'source_adapter_changed_pixels');require(not metadata.get('parents') and not metadata.get('issues'),'source_entity_hierarchy_unsupported');require(metadata['groups'] and all(g['kind']=='entity' and g['method']=='engine_entity_metadata' for g in metadata['groups']),'source_entity_identity_inferred')
   dom=page.evaluate((W/'scripts/svg_dom_v6.js').read_text());require(page.screenshot()==before,'source_extractor_changed_pixels');require(not dom['issues'] and not blocked,'source_visible_feature_or_resource_unsupported')
   require(len(metadata['links'])==metadata['expectedLinkCount'],'source_link_identity_incomplete')
   return {'svg':svg,'engine_png':png,'browser_png':before,'dom':dom,'metadata':metadata,'frame':frame,'extent':extent,'physical_fonts':fonts}
  finally:browser.close()

def prepare_source(record_or_fulljob,work):
 """Prepare authoritative source proof without reading any candidate or C-proof."""
 from PIL import Image
 from auto_quality_common_v4 import image_quality
 out={'ok':False,'supported':False,'unit':UNIT,'stage':'source_reference','model_calls':0,'candidate_read':False,'target_converted':False,'source_proof_independent_of_candidate':True}
 work=Path(work).resolve();require(work.is_relative_to(W/VERSION),'unowned_source_proof_work');work.mkdir(parents=True,exist_ok=False)
 try:
  support=static_support(record_or_fulljob);out['static_support']=support;require(support['supported'],'typed_unsupported_source')
  config=configuration();source,code,ref=base._inputs(record_or_fulljob);reference=Image.open(io.BytesIO(ref)).convert('RGB');capture=_natural_capture(code,reference.size,work)
  engine=Image.open(io.BytesIO(capture['engine_png'])).convert('RGBA');enginebg=Image.new('RGBA',engine.size,'white');enginebg.alpha_composite(engine);engine=enginebg.convert('RGB');delta=[reference.size[i]-engine.size[i] for i in range(2)]
  out.update(supported=True,source_id=source['pair_sha256'],source_code_sha256=sha(code),reference_sha256=sha(ref),provider=source['source'],reference_size=list(reference.size),engine_png_size=list(engine.size),canvas_delta=delta,source_frame=capture['frame'],source_paint_extent=capture['extent'])
  require(all(d in (0,1) for d in delta),'source_engine_canvas_difference_not_0_or_1')
  require(all(capture['frame']['natural_size'][i]-reference.size[i] in (0,1) for i in range(2)),'source_svg_canvas_difference_not_0_or_1')
  x0,y0,x1,y1=capture['extent']['envelope'];require(x0>=-1e-7 and y0>=-1e-7 and x1<=reference.width+1e-7 and y1<=reference.height+1e-7,'source_paint_would_be_cropped')
  padded=Image.new('RGB',reference.size,'white');padded.paste(engine,(0,0));stream=io.BytesIO();padded.save(stream,format='PNG');padded_png=stream.getvalue()
  positions=[]
  for o in capture['dom']['objects']:
   if o['type']=='text' and o.get('text','').strip():
    b=o['bbox'];positions.append({'cell':'source:'+o['id'],'runs':[{'chars':[{'text':o['text'],'x':b['x'],'y':b['y'],'width':b['w'],'height':b['h']}]}]})
  visual=image_quality(ref,padded_png,{},positions);out.update(source_reference_visual=visual,policy=config['policy'],source_padding={'left':0,'top':0,'right':delta[0],'bottom':delta[1]},source_objects_cropped=False,no_pixel_parameter_search=True,ok=visual['ok'],reason='source_reference_reproduced' if visual['ok'] else 'source_engine_reference_mismatch')
  for name,blob in [('original_source.puml',code),('original_reference.png',ref),('source.svg',capture['svg']),('source_engine.png',capture['engine_png']),('source_engine_padded.png',padded_png),('source_browser_natural.png',capture['browser_png']),('source_dom.json',raw(capture['dom'])),('source_entity_metadata.json',raw(capture['metadata'])),('source_paint_extent.json',raw(capture['extent']))]:(work/name).write_bytes(blob)
  out['source_artifacts']={p.name:{'file':str(p.relative_to(R)),'sha256':sha(p.read_bytes())} for p in work.iterdir() if p.is_file()}
 except Exception as e:out.update(ok=False,reason=str(e).split(':',1)[0],detail=str(e)[:2500],development_not_ready=True)
 (work/'source_proof.json').write_bytes(raw(out));return out

def source_reproduction(record_or_fulljob,work):return prepare_source(record_or_fulljob,work)

def development():
 db=sqlite3.connect('file:'+str(W/'jobs.sqlite')+'?mode=ro',uri=True,timeout=30);db.execute('pragma query_only=ON');config=configuration();basework=W/VERSION/'development'/uuid.uuid4().hex;basework.mkdir(parents=True);(basework/'frozen_source_policy.json').write_bytes(raw({'configuration':config,'ids':list(CASES),'sample_replacement':False,'projection_frozen_before_source_results':True}));results=[]
 print(json.dumps({'development_directory':str(basework),'policy':config['policy'],'ids':list(CASES)}),flush=True)
 for ident in CASES:
  columns=[x[1] for x in db.execute('pragma table_info(jobs)')];row=db.execute('select * from jobs where id=?',(ident,)).fetchone();job=dict(zip(columns,row));r=prepare_source(job,basework/ident);r['canonical_job_unchanged']=db.execute('select * from jobs where id=?',(ident,)).fetchone()==row;results.append(r);print(json.dumps({'id':ident,'ok':r['ok'],'reason':r['reason'],'engine_png_size':r.get('engine_png_size'),'reference_size':r.get('reference_size'),'visual':r.get('source_reference_visual')}),flush=True)
 db.close();report={'version':VERSION,'unit':UNIT,'configuration':config,'configuration_unchanged':configuration()==config,'results':results,'source_passed':sum(r['ok'] for r in results),'source_cases':len(results),'state':'source_passed_candidate_checker_still_required' if all(r['ok'] for r in results) else 'development_not_ready','candidate_checker_ready':False,'B_C_fair_source_preparation':True,'B_C_candidate_validation_implemented':False,'unseen_consumed':0,'new_model_calls':0,'canonical_mutations':0,'target_conversions':0,'report':str(basework/'report.json')};(basework/'report.json').write_bytes(raw(report));print(json.dumps({k:v for k,v in report.items() if k not in ('configuration','results')}),flush=True)

if __name__=='__main__':development()
