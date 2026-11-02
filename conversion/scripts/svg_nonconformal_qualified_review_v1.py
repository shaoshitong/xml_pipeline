"""Read-only, two existing qualified native paint measurements; no conversion."""
from pathlib import Path
import hashlib,io,json,math,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion';sha=lambda b:hashlib.sha256(b).hexdigest()
AUDIT=R/'conversion/audits/svg_general_qualified_stroke_source_v1/dac4f6a66d384eb083866f8154be51d8/proof.json'
AUDIT_SHA='faf5569f59fb9b0f1a45dc98251646133146a24816681707daef366c316cab9a'
META_SHA={'b21f0ddad39441d9b70ff57c0750bc61752485fa23c9f04ea9b4dc6f52d046f1':'6489c12ea383487f57d5bb0595fd8dec81da70c6f2dbff5a299244a517f4dee4','fdde92d0d175ef8920afd72e79104930b1c5be509f56c4b61b3c962e62a81c82':'49e874c9a7ecae44459e11545a4f111f482ff55a67a1411d331c2a29d112992d'}

def witnesses(path):
 from fontTools.pens.recordingPen import RecordingPen
 from fontTools.svgLib.path import parse_path
 p=RecordingPen();parse_path(path,p);current=None;start=None;result=[]
 def add(points,degree):
  for t in([.5]if degree==1 else[.25,.5,.75]):
   if degree==1:point=[(1-t)*a+t*b for a,b in zip(*points)];tangent=[b-a for a,b in zip(*points)]
   elif degree==2:
    a,b,c=points;point=[(1-t)**2*a[k]+2*(1-t)*t*b[k]+t*t*c[k]for k in(0,1)];tangent=[2*((1-t)*(b[k]-a[k])+t*(c[k]-b[k]))for k in(0,1)]
   else:
    a,b,c,d=points;point=[(1-t)**3*a[k]+3*(1-t)**2*t*b[k]+3*(1-t)*t*t*c[k]+t**3*d[k]for k in(0,1)];tangent=[3*((1-t)**2*(b[k]-a[k])+2*(1-t)*t*(c[k]-b[k])+t*t*(d[k]-c[k]))for k in(0,1)]
   if math.hypot(*tangent)>1e-8:result.append(dict(local_point=point,local_tangent=tangent,source_parameter=t,source_segment_degree=degree))
 for operation,values in p.value:
  if operation=='moveTo':current=start=values[0]
  elif operation in('lineTo','qCurveTo','curveTo'):
   points=[current,*values];add(points,len(points)-1);current=values[-1]
  elif operation=='closePath':
   if current!=start:add([current,start],1)
   current=start
 return result

SOURCE_JS=r'''items=>{const root=document.querySelector('svg'),matrix=m=>[m.a,m.b,m.c,m.d,m.e,m.f],out=[];for(const expected of items){const obj=expected.object,candidates=[...root.querySelectorAll(obj.tag)].filter(el=>!el.closest('defs,marker,symbol,pattern,clipPath,mask')).filter(el=>{const m=el.getScreenCTM();if(!m||matrix(m).some((x,i)=>Math.abs(x-obj.matrix[i])>1e-5))return false;if(obj.tag==='path')return el.getAttribute('d')===obj.d;if(obj.tag==='polyline'||obj.tag==='polygon')return el.getAttribute('points')===obj.pointsAttr;return Object.entries(obj.attrs).every(([k,v])=>Math.abs((el[k]?.baseVal?.value??+(el.getAttribute(k)||0))-v)<1e-5);});if(candidates.length!==1)throw Error('original_source_primitive_binding_not_unique:'+obj.id+':'+candidates.length);const el=candidates[0],cs=getComputedStyle(el);out.push({id:obj.id,tag:el.localName,matrix:matrix(el.getScreenCTM()),d:expected.path,computed:{stroke:cs.stroke,strokeWidth:parseFloat(cs.strokeWidth),strokeLinecap:cs.strokeLinecap,strokeLinejoin:cs.strokeLinejoin,strokeMiterlimit:parseFloat(cs.strokeMiterlimit),strokeDasharray:cs.strokeDasharray,strokeDashoffset:parseFloat(cs.strokeDashoffset),strokeOpacity:+cs.strokeOpacity,opacity:+cs.opacity,vectorEffect:cs.vectorEffect},witnesses:expected.witnesses,original_outerHTML:el.outerHTML});}return out;}'''

NATIVE_JS=r'''async ({xml,ids,size})=>{document.body.style.cssText='margin:0;padding:0;background:white';const doc=mxUtils.parseXml(xml),model=doc.getElementsByTagName('mxGraphModel')[0];for(const item of(model.getAttribute('extFonts')||'').split('|')){if(!item)continue;const i=item.indexOf('^'),face=new FontFace(item.slice(0,i),'url('+JSON.stringify(item.slice(i+1))+')');document.fonts.add(await face.load());}const div=document.createElement('div');div.style.cssText='position:absolute;left:0;top:0;width:'+size[0]+'px;height:'+size[1]+'px;overflow:hidden';document.body.append(div);const graph=new Graph(div);new mxCodec(doc).decode(model,graph.model);graph.view.scaleAndTranslate(1,0,0);graph.refresh();graph.view.validate();await document.fonts.ready;const before=mxUtils.getXml(new mxCodec().encode(graph.model)),matrix=m=>[m.a,m.b,m.c,m.d,m.e,m.f],rows=[];for(const id of ids){const cell=graph.model.getCell(id),state=graph.view.getState(cell);if(!state?.shape?.node)throw Error('existing_native_paint_missing:'+id);const paints=[state.shape.node,...state.shape.node.querySelectorAll('path,rect,line,polyline,polygon,circle,ellipse')].filter(e=>['path','rect','line','polyline','polygon','circle','ellipse'].includes(e.localName)).map(e=>{const c=getComputedStyle(e);return{tag:e.localName,d:e.getAttribute('d'),visibility:c.visibility,stroke:c.stroke,strokeWidth:parseFloat(c.strokeWidth),strokeOpacity:+c.strokeOpacity,opacity:+c.opacity,fill:c.fill,vectorEffect:c.vectorEffect,strokeLinecap:c.strokeLinecap,strokeLinejoin:c.strokeLinejoin,strokeMiterlimit:parseFloat(c.strokeMiterlimit),strokeDasharray:c.strokeDasharray,strokeDashoffset:parseFloat(c.strokeDashoffset),matrix:matrix(e.getScreenCTM()),outerHTML:e.outerHTML};}).filter(p=>p.visibility==='visible'&&p.stroke!=='none'&&p.stroke!=='transparent'&&!/rgba\([^)]*,\s*0\)$/.test(p.stroke)&&p.strokeOpacity>0&&p.opacity>0&&p.strokeWidth>0);rows.push({id,role:cell.edge?'native_connector_edge':'stencil_vertex',source:cell.source?.id??null,target:cell.target?.id??null,actual_shape_strokewidth:state.shape.strokewidth,actual_shape_scale:state.shape.scale,actual_screen_offset:state.shape.getSvgScreenOffset(),actual_stencil_definition:state.shape.stencil?.desc?.outerHTML??null,paint:paints});}window.__strokeReviewGraph=graph;return{rows,whole_model_unchanged:mxUtils.getXml(new mxCodec().encode(graph.model))===before};}'''

MEASURE_JS=r'''({source,native})=>{const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d'),setup=p=>{ctx.setTransform(...p.matrix);ctx.lineWidth=p.strokeWidth;ctx.lineCap=p.strokeLinecap;ctx.lineJoin=p.strokeLinejoin;ctx.miterLimit=p.strokeMiterlimit;ctx.setLineDash(p.strokeDasharray==='none'?[]:p.strokeDasharray.split(/[ ,]+/).filter(Boolean).map(parseFloat));ctx.lineDashOffset=p.strokeDashoffset||0;return new Path2D(p.d);},normalWidth=(paint,world,tangent,span)=>{if(paint.vectorEffect!=='none')return{unsupported:'nondefault_vector_effect'};const path=setup(paint),length=Math.hypot(...tangent),n=[-tangent[1]/length,tangent[0]/length],hit=v=>ctx.isPointInStroke(path,world[0]+n[0]*v,world[1]+n[1]*v);if(!hit(0))return{unsupported:'source_center_not_in_actual_stroke'};const boundary=sign=>{if(hit(sign*span))throw Error('fixed_cross_section_span_does_not_bound_stroke');let lo=0,hi=span;for(let i=0;i<35;i++){const mid=(lo+hi)/2;if(hit(sign*mid))lo=mid;else hi=mid;}return sign*(lo+hi)/2;};const a=boundary(-1),b=boundary(1);return{physical_width_px:b-a,negative_boundary:a,positive_boundary:b,engine:'actual_Chromium_Canvas_isPointInStroke_with_original_path_and_actual_paint_CTM',binary_steps:35};};const m=source.matrix,actual=native.paint.filter(p=>p.tag==='path');if(actual.length!==1)throw Error('actual_native_source_stroke_paint_not_single_path:'+source.id+':'+actual.length);const out=[];for(const w of source.witnesses){const p=w.local_point,t=w.local_tangent,world=[m[0]*p[0]+m[2]*p[1]+m[4],m[1]*p[0]+m[3]*p[1]+m[5]],tangent=[m[0]*t[0]+m[2]*t[1],m[1]*t[0]+m[3]*t[1]],expected=source.computed.strokeWidth*Math.abs(m[0]*m[3]-m[1]*m[2])*Math.hypot(...t)/Math.hypot(...tangent),sourcePaint={...source.computed,d:source.d,matrix:m},s=normalWidth(sourcePaint,world,tangent,10),n=normalWidth(actual[0],world,tangent,10);out.push({...w,world_point:world,world_tangent:tangent,source_analytic_transformed_normal_width:expected,source_actual_stroke:s,native_actual_stroke:n});}return out;}'''

def actual_source_nodes(page):
 session=page.context.new_cdp_session(page);session.send('DOM.enable');session.send('CSS.enable');tree=session.send('DOM.getDocument',dict(depth=-1,pierce=True))['root'];result=[]
 def walk(node):
  if node['nodeName'].lower()in('path','rect','line','polyline','polygon','ellipse','circle'):
   obj=session.send('DOM.resolveNode',dict(backendNodeId=node['backendNodeId']))['object']
   try:
    value=session.send('Runtime.callFunctionOn',dict(objectId=obj['objectId'],functionDeclaration="""function(){if(!(this instanceof SVGElement)||this.closest('defs,marker,symbol,pattern,clipPath,mask'))return null;const m=this.getScreenCTM(),cs=getComputedStyle(this);if(!m||cs.display==='none'||cs.visibility!=='visible')return null;const root=this.getRootNode();return{tag:this.localName,d:this.getAttribute('d'),pointsAttr:this.getAttribute('points'),attrs:Object.fromEntries(['cx','cy','height','r','rx','ry','width','x','x1','x2','y','y1','y2'].map(k=>[k,this[k]?.baseVal?.value??+(this.getAttribute(k)||0)])),matrix:[m.a,m.b,m.c,m.d,m.e,m.f],computed:{stroke:cs.stroke,strokeWidth:parseFloat(cs.strokeWidth),strokeLinecap:cs.strokeLinecap,strokeLinejoin:cs.strokeLinejoin,strokeMiterlimit:parseFloat(cs.strokeMiterlimit),strokeDasharray:cs.strokeDasharray,strokeDashoffset:parseFloat(cs.strokeDashoffset),strokeOpacity:+cs.strokeOpacity,opacity:+cs.opacity,vectorEffect:cs.vectorEffect},actual_original_outerHTML:this.outerHTML,actual_root_type:root.constructor.name,actual_shadow_host:root.host?{tag:root.host.localName,href:root.host.getAttribute('href')||root.host.getAttributeNS('http://www.w3.org/1999/xlink','href'),outerHTML:root.host.outerHTML}:null};}""",returnByValue=True))['result'].get('value')
    if value is not None:result.append({**value,'actual_original_backendNodeId':node['backendNodeId'],'source_binding':'actual_Chrome_original_document_or_use_UA_shadow_element_not_synthetic_clone'})
   finally:session.send('Runtime.releaseObject',dict(objectId=obj['objectId']))
  for c in node.get('children',[]):walk(c)
  for c in node.get('shadowRoots',[]):walk(c)
 try:walk(tree);return result
 finally:session.detach()

def bind_actual_sources(page,items):
 nodes=actual_source_nodes(page);out=[]
 for expected in items:
  o=expected['object'];matches=[]
  for node in nodes:
   if node['tag']!=o['tag']or any(abs(a-b)>1e-5 for a,b in zip(node['matrix'],o['matrix'])):continue
   if o['tag']=='path':same=node['d']==o['d']
   elif o['tag']in('polygon','polyline'):same=node['pointsAttr']==o['pointsAttr']
   else:same=all(abs(node['attrs'][k]-v)<1e-5 for k,v in o['attrs'].items())
   if same:matches.append(node)
  if len(matches)!=1:raise ValueError('actual_original_UA_source_primitive_not_unique:'+o['id']+':'+str(len(matches)))
  out.append({**matches[0],'id':o['id'],'d':expected['path'],'witnesses':expected['witnesses']})
 return out

def child(work):
 from playwright.sync_api import sync_playwright
 from portable_native_fonts import ready_page
 from native_worker import native
 from PIL import Image
 import numpy as np,xml.etree.ElementTree as E
 from svg_convert_v2 import path_for
 work=Path(work);work.mkdir(parents=True,exist_ok=False);assert sha(AUDIT.read_bytes())==AUDIT_SHA;audit=json.loads(AUDIT.read_bytes());assert len(audit['flags'])==2;runtime=native.renderer_path(R).parent/'assets/viewer-static.min.js';manifest=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';assert sha(runtime.read_bytes())==json.loads(manifest.read_bytes())['viewer_bundle_sha256'];cases=[]
 with sync_playwright()as pw:
  browser=pw.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu'])
  try:
   for flag in audit['flags']:
    metadata=R/flag['metadata_file'];assert sha(metadata.read_bytes())==META_SHA[flag['id']];record=json.loads(metadata.read_bytes());domfile=Path(flag['source_dom']);assert sha(domfile.read_bytes())==flag['source_dom_sha256'];dom=json.loads(domfile.read_bytes());objects={o['id']:o for o in dom['objects']};xml=(R/record['code_file']).read_text();source=(R/record['original_source_code']).read_bytes();stored=(R/record['image_file']).read_bytes();assert sha(xml.encode())==record['code_sha256']and sha(source)==record['source_code_sha256']and sha(stored)==record['image_sha256'];size=Image.open(io.BytesIO(stored)).size
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:canonical_before=db.execute('select*from jobs where id=?',(flag['id'],)).fetchone()
    source_page=browser.new_page(viewport=dict(zip(('width','height'),size)));source_page.route('**/*',lambda r:r.abort());source_page.set_content('<style>html,body{margin:0;padding:0;background:white}svg{display:block}</style>'+source.decode('utf-8-sig'));source_page.evaluate('size=>{const s=document.querySelector("svg");s.style.width=size[0]+"px";s.style.height=size[1]+"px";s.setAttribute("width",size[0]);s.setAttribute("height",size[1]);}',list(size));source_dom_before=source_page.content();items=[dict(object=objects[o['id']],path=path_for(objects[o['id']]),witnesses=witnesses(path_for(objects[o['id']])))for o in flag['suspect']];observed_source=bind_actual_sources(source_page,items);assert source_page.content()==source_dom_before
    native_page=ready_page(browser);native_page.set_viewport_size(dict(zip(('width','height'),size)));observed_native=native_page.evaluate(NATIVE_JS,dict(xml=xml,ids=[o['id']for o in flag['suspect']],size=list(size)));assert observed_native['whole_model_unchanged'];(work/(flag['id']+'_source_observation.json')).write_text(json.dumps(observed_source,indent=2));(work/(flag['id']+'_native_observation.json')).write_text(json.dumps(observed_native,indent=2));by_id={r['id']:r for r in observed_native['rows']};measurements=[]
    for obj in observed_source:
     current=by_id[obj['id']];samples=native_page.evaluate(MEASURE_JS,dict(source=obj,native=current));measurements.append(dict(id=obj['id'],source=obj,native=current,cross_sections=samples))
    image=native_page.screenshot(animations='disabled');fresh=Image.open(io.BytesIO(image)).convert('RGB');old=Image.open(io.BytesIO(stored)).convert('RGB');assert fresh.size==old.size;difference=int(np.any(np.asarray(fresh)!=np.asarray(old),axis=2).sum());destination=work/flag['id'];destination.mkdir();(destination/'actual_native_replay.png').write_bytes(image);quality=R/record['automatic_quality_audit'];qa=json.loads(quality.read_bytes());source_page.close();native_page.close()
    with sqlite3.connect((W/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as db:canonical_after=db.execute('select*from jobs where id=?',(flag['id'],)).fetchone()
    assert canonical_before==canonical_after and sha(metadata.read_bytes())==META_SHA[flag['id']]and sha(domfile.read_bytes())==flag['source_dom_sha256']and sha((R/record['code_file']).read_bytes())==record['code_sha256'];case=dict(id=flag['id'],metadata=dict(file=str(metadata),sha256=META_SHA[flag['id']]),source_dom=dict(file=str(domfile),sha256=flag['source_dom_sha256']),XML=dict(file=record['code_file'],sha256=record['code_sha256']),original_code=dict(file=record['original_source_code'],sha256=record['source_code_sha256']),original_reference=dict(file=record['original_reference'],sha256=record['source_image_sha256']),existing_QA=dict(file=str(quality),sha256=sha(quality.read_bytes()),ok=qa.get('ok'),visual=qa.get('checks',{}).get('visual')),actual_native_replay_stored_image_different_RGB_pixels=difference,actual_native_replay_PNG_sha256=sha(image),measurements=measurements,canonical_original_unchanged=True,qualified_metadata_and_payloads_unchanged=True);(destination/'measurement.json').write_text(json.dumps(case,indent=2));cases.append(case)
  finally:browser.close()
 report=dict(schema='two_existing_qualified_SVG_actual_nonconformal_stroke_review_v1',audit=dict(file=str(AUDIT),sha256=AUDIT_SHA),actual_native_runtime=dict(file=str(runtime),sha256=sha(runtime.read_bytes())),cases=cases,normal_frontend_calls=0,model_calls=0,new_heldout=0,qualified_ledger_writes=0,goal_complete=False);p=work/'proof.json';p.write_text(json.dumps(report,indent=2));print(json.dumps(dict(file=str(p),sha256=sha(p.read_bytes()),cases=len(cases),actual_source_objects=sum(len(c['measurements'])for c in cases))))

def run():
 import initial_conversion_process_v1 as bounded
 work=W/'svg_nonconformal_qualified_review_v1'/uuid.uuid4().hex;result=bounded.run([sys.executable,'-B',str(Path(__file__).resolve()),'--child',str(work/'measurements')],work/'owned_child',180);receipt=dict(work=str(work),process=result,normal_frontend_calls=0,qualified_ledger_writes=0,model_calls=0);work.mkdir(parents=True,exist_ok=True);(work/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(dict(receipt=str(work/'receipt.json'),ok=result['ok'],stdout=result['stdout_file'],stderr=result['stderr_file'],cleanup_complete=result['cleanup_complete'])))
if __name__=='__main__':child(sys.argv[2])if'--child'in sys.argv else run()
