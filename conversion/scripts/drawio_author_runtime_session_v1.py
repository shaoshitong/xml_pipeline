"""Actual metadata-selected author runtime: native DOM, text backends and export.

No reference input, fit, screen-coordinate inversion or geometry mutation.
Pristine upstream export is proved equal to a separately attributed export;
expanded source-only SVG inspection rejects cropped paint before publication.
"""
from pathlib import Path
import base64,hashlib,json,math,xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright
import drawio_author_version_export_v3 as legacy
R,W,CHROME,ROOT=legacy.R,legacy.W,legacy.CHROME,legacy.ROOT
raw,sha,put=legacy.raw,legacy.sha,legacy.put
POLICY='author_native_metadata_version_original_export_complete_text_backend_and_paint_inspection_v1'
LOAD=r'''async xml=>{
 if(window.sourceGraph){sourceGraph.destroy();delete window.sourceGraph;delete window.sourceEditor}
 document.body.innerHTML='<div id="author-graph" style="position:relative;width:8192px;height:8192px"></div>';
 const doc=mxUtils.parseXml(xml),models=doc.getElementsByTagName('mxGraphModel');if(models.length!==1)throw Error('one_complete_author_model_required');
 const model=models[0];if(model.getAttribute('math')==='1')throw Error('typed_source_math_pending');
 for(const entry of(model.getAttribute('extFonts')||'').split('|')){
  if(!entry)continue;const i=entry.indexOf('^'),family=entry.slice(0,i),uri=entry.slice(i+1);
  if(i<=0||!uri.startsWith('data:font/'))throw Error('only_exact_inline_portable_font_assets_supported');
  const face=new FontFace(family,'url('+JSON.stringify(uri)+')');document.fonts.add(await face.load());
 }
 const graph=new Graph(document.getElementById('author-graph')),editor=new Editor(false,null,null,graph,true),style=model.getAttribute('style')||'default-style2';
 if(!graph.themes?.[style])throw Error('missing_source_official_theme');editor.setGraphXml(model);graph.clearSelection();await document.fonts.ready;graph.refresh();graph.view.validate();
 window.sourceGraph=graph;window.sourceEditor=editor;
 return {version:EditorUi.VERSION,source_math_enabled:graph.mathEnabled,source_math_queue:Editor.mathJaxQueue?.length??0,graph_bounds:{x:graph.getGraphBounds().x,y:graph.getGraphBounds().y,width:graph.getGraphBounds().width,height:graph.getGraphBounds().height},native_model:mxUtils.getXml(new mxCodec().encode(graph.model)),cells:Object.keys(graph.model.cells).length,vertices:Object.values(graph.model.cells).filter(c=>c.vertex).length,edges:Object.values(graph.model.cells).filter(c=>c.edge).length,current_style:graph.currentStyle,source_model_attributes:Object.fromEntries(Array.from(model.attributes).map(a=>[a.name,a.value]))};
}'''
OBSERVE=r'''()=>{
 const g=sourceGraph,result=[];let serial=0;
 for(const cell of Object.values(g.model.cells)){
  const s=g.view.getState(cell),label=g.getLabel(cell);if(typeof label!=='string'||!label.length||!s?.text?.node)continue;
  const fo=s.text.node.querySelector('foreignObject'),scope=fo||s.text.node,walker=document.createTreeWalker(scope,NodeFilter.SHOW_TEXT),runs=[];let node;
  while(node=walker.nextNode()){
   if(!node.textContent.length)continue;const parent=node.parentElement;let id=parent.getAttribute('data-author-text-parent');if(!id){id='author_text_'+serial++;parent.setAttribute('data-author-text-parent',id)}
   const cs=getComputedStyle(parent),metric=document.createElement('span');metric.id='author_metric_'+serial++;metric.textContent='M';Object.assign(metric.style,{position:'absolute',left:'0px',top:'0px',fontFamily:cs.fontFamily,fontWeight:cs.fontWeight,fontStyle:cs.fontStyle,fontSize:cs.fontSize});document.body.append(metric);
   const chars=[];let i=0;for(const char of Array.from(node.textContent)){const range=document.createRange();range.setStart(node,i);i+=char.length;range.setEnd(node,i);const b=range.getBoundingClientRect();chars.push({text:char,x:b.x,y:b.y,width:b.width,height:b.height})}
   const range=document.createRange();range.selectNodeContents(node);const b=range.getBoundingClientRect();runs.push({index:runs.length,selector:'[data-author-text-parent="'+id+'"]',child_index:Array.from(parent.childNodes).indexOf(node),metricSelector:'#'+metric.id,text:node.textContent,fontFamily:cs.fontFamily,fontSize:cs.fontSize,fontWeight:cs.fontWeight,fontStyle:cs.fontStyle,lineHeight:cs.lineHeight,rect:{x:b.x,y:b.y,width:b.width,height:b.height},chars});
  }
  const frag=document.createElement('div');frag.innerHTML=Graph.sanitizeHtml(label);result.push({cell:cell.id,label,normalized_markup:frag.innerHTML,html:!!fo,style:g.getCellStyle(cell),bbox:{x:s.x,y:s.y,width:s.width,height:s.height},runs});
 }
 return result;
}'''
EXPORT=r'''async({scale,border})=>{
 const graph=sourceGraph,editor=sourceEditor;
 const draw=()=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('official_export_timeout')),120000);editor.exportToCanvas((c,s)=>{clearTimeout(timer);resolve({png:c.toDataURL('image/png').split(',')[1],svg:mxUtils.getXml(s),width:c.width,height:c.height})},null,null,null,e=>{clearTimeout(timer);reject(Error(e?.message||String(e)))},null,true,scale,false,graph.shadowVisible,null,graph,border,null,false,'light','diagram',null)});
 const pristine=await draw(),factory=graph.createSvgImageExport;
 graph.createSvgImageExport=function(){const exp=factory.apply(this,arguments),original=exp.drawCellState;exp.drawCellState=function(state,canvas){const container=canvas.root,before=new Set(container.childNodes);const value=original.apply(this,arguments);for(const child of container.childNodes)if(!before.has(child)&&child.nodeType===1)child.setAttribute('data-author-native-cell',state.cell.id);return value};return exp};
 let owned;try{owned=await draw()}finally{graph.createSvgImageExport=factory}
 const svg=document.importNode(mxUtils.parseXml(owned.svg).documentElement,true),vb=svg.getAttribute('viewBox').trim().split(/\s+/).map(Number),w=parseFloat(svg.getAttribute('width')),h=parseFloat(svg.getAttribute('height'));
 if(vb.length!==4||vb.some(x=>!Number.isFinite(x))||Math.ceil(w*scale)!==pristine.width||Math.ceil(h*scale)!==pristine.height)throw Error('metadata_scale_was_clamped_or_natural_export_invalid');
 Object.assign(svg.style,{position:'absolute',left:'0px',top:'0px'});document.body.append(svg);await document.fonts.ready;
 if(svg.querySelector('filter,mask'))throw Error('typed_unbounded_filter_or_mask_paint_pending');
 const origin=svg.getBoundingClientRect(),bycell={},walker=document.createTreeWalker(svg,NodeFilter.SHOW_TEXT);let text;
 while(text=walker.nextNode()){
  if(!text.textContent.length||!text.parentElement.closest('foreignObject,text'))continue;
  const owner=text.parentElement.closest('[data-author-native-cell]');if(!owner)continue;
  const cell=owner.getAttribute('data-author-native-cell'),chars=[];let i=0;
  for(const char of Array.from(text.textContent)){const range=document.createRange();range.setStart(text,i);i+=char.length;range.setEnd(text,i);const b=range.getBoundingClientRect();chars.push({text:char,x:(b.x-origin.x)*scale,y:(b.y-origin.y)*scale,width:b.width*scale,height:b.height*scale})}
  if(!chars.some(c=>c.width>0&&c.height>0))continue;
  (bycell[cell]??=[]).push({text:text.textContent,chars});
 }
 const bgraw=graph.background&&graph.background!==mxConstants.NONE?graph.background:(Editor.getDefaultPageBackgroundColor?.()||('light-dark(#ffffff,'+Editor.darkColor+')')),bg=mxUtils.getLightDarkColor(bgraw).light;
 const padded=svg.cloneNode(true);padded.style.position='';padded.style.left='';padded.style.top='';const pad=32;padded.setAttribute('width',(w+2*pad)+'px');padded.setAttribute('height',(h+2*pad)+'px');padded.setAttribute('viewBox',[vb[0]-pad,vb[1]-pad,vb[2]+2*pad,vb[3]+2*pad].join(' '));
 const inspection=await new Promise((resolve,reject)=>{const image=new Image;image.onload=()=>{const c=document.createElement('canvas');c.width=Math.ceil((w+64)*scale);c.height=Math.ceil((h+64)*scale);const ctx=c.getContext('2d');ctx.fillStyle=bg;ctx.fillRect(0,0,c.width,c.height);ctx.scale(scale,scale);ctx.drawImage(image,0,0);const color=document.createElement('canvas').getContext('2d');color.fillStyle=bg;color.fillRect(0,0,1,1);resolve({png:c.toDataURL('image/png').split(',')[1],width:c.width,height:c.height,pad:Math.round(pad*scale),background_RGBA:Array.from(color.getImageData(0,0,1,1).data)})};image.onerror=()=>reject(Error('inspection_source_SVG_not_rendered'));image.src=Editor.createSvgDataUri(mxUtils.getXml(padded))});
 svg.remove();return {pristine,owned,inspection,actual_export_text_positions:Object.entries(bycell).map(([cell,runs])=>({cell,runs})),natural_svg_viewBox:vb,observational_owner_attributes_only:true};
}'''
def ready_page(browser,version):
 legacy.configuration(version)
 page=browser.new_page(viewport={'width':1200,'height':1000},device_scale_factor=1,color_scheme='light',locale='en-US');page.set_default_timeout(150000)
 page.author_requests=[];page.author_errors=[]
 page.route('**/*',lambda r:(page.author_requests.append(r.request.url),r.abort())[-1]);page.on('pageerror',lambda e:page.author_errors.append(str(e)))
 page.set_content('<!doctype html><html><head></head><body style="margin:0"></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_style_tag(path=str(ROOT/version/'styles/grapheditor.css'));page.add_script_tag(path=str(ROOT/version/'js/viewer-static.min.js'));return page

def load(page,xml):
 model=ET.fromstring(xml);models=list(model.iter('mxGraphModel'))
 if len(models)!=1 or models[0].get('math')=='1':raise ValueError('typed_author_source_math_or_model_scope_pending')
 result=page.evaluate(LOAD,xml)
 if result['source_math_enabled']or result['source_math_queue']:raise ValueError('author_source_math_execution_not_supported')
 return result

def observe(page):
 from compiler_native_text_node_cdp_v2 import physical_fonts
 rows=page.evaluate(OBSERVE);session=page.context.new_cdp_session(page);session.send('DOM.enable');session.send('CSS.enable');root=session.send('DOM.getDocument',{'depth':1})['root']['nodeId']
 try:
  for row in rows:
   total=[]
   for run in row['runs']:
    parent=session.send('DOM.querySelector',{'nodeId':root,'selector':run['selector']})['nodeId'];run['actual_fonts']=physical_fonts(session,parent,run['child_index'],run['text']);total.extend(run['actual_fonts'])
    if run['text'].strip()and not any(f.get('glyphCount',0)for f in run['actual_fonts']):raise ValueError('author_source_text_physical_font_unobserved')
    metric=session.send('DOM.querySelector',{'nodeId':root,'selector':run['metricSelector']})['nodeId'];run['primary_metric_fonts']=session.send('CSS.getPlatformFontsForNode',{'nodeId':metric})['fonts']
   merged={}
   for f in total:
    key=(f['postScriptName'],f['isCustomFont']);merged.setdefault(key,{**f,'glyphCount':0})['glyphCount']+=f['glyphCount']
   row['actual_fonts']=list(merged.values())
 finally:session.detach()
 return rows

def capture(page,xml):load(page,xml);return observe(page)
def capture_runs(page,xml):return[row for row in capture(page,xml)if row['html']]
def pixels(png):
 from PIL import Image
 import io
 im=Image.open(io.BytesIO(png)).convert('RGBA');return im.size,im.tobytes()
def render(xml,profile,work):
 import numpy as np
 from PIL import Image
 import io
 work=Path(work).resolve();assert work.is_relative_to(W.resolve())and not work.exists();work.mkdir(parents=True)
 version=profile['version'];scale=float(profile['scale']);border=float(profile['border'])
 if not math.isfinite(scale)or scale<=0 or not math.isfinite(border)or border<0:raise ValueError('invalid_source_metadata_export_parameters')
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path=str(CHROME),args=['--disable-dev-shm-usage'])
  try:
   page=ready_page(browser,version);initial=load(page,xml);observations=observe(page);result=page.evaluate(EXPORT,{'scale':scale,'border':border});requests=list(page.author_requests);errors=list(page.author_errors)
  finally:browser.close()
 allowed=['https://viewer.diagrams.net/math/es5/startup.js']if not initial['source_math_enabled']and not initial['source_math_queue']else[]
 if any(u not in allowed for u in requests)or errors:raise ValueError('author_source_unresolved_asset_or_browser_error:'+json.dumps({'requests':requests,'errors':errors}))
 pristine=base64.b64decode(result['pristine'].pop('png'),validate=True);owned=base64.b64decode(result['owned'].pop('png'),validate=True);inspection=base64.b64decode(result['inspection'].pop('png'),validate=True)
 if pixels(pristine)!=pixels(owned):raise ValueError('author_export_observational_ownership_changed_pixels')
 ins=np.array(Image.open(io.BytesIO(inspection)).convert('RGBA'));pad=result['inspection']['pad'];width=result['pristine']['width'];height=result['pristine']['height'];center=Image.fromarray(ins[pad:pad+height,pad:pad+width]);src=Image.open(io.BytesIO(pristine)).convert('RGBA')
 if center.size!=src.size or center.tobytes()!=src.tobytes():raise ValueError('author_source_inspection_changes_actual_interior_paint')
 mask=np.ones(ins.shape[:2],dtype=bool);mask[pad:pad+height,pad:pad+width]=False;outside=int(np.any(ins!=np.array(result['inspection']['background_RGBA'],dtype='uint8'),axis=2)[mask].sum())
 if outside:raise ValueError('author_source_official_frame_crops_actual_paint:'+str(outside))
 before={r['cell']:''.join(run['text']for run in r['runs'])for r in observations};after={r['cell']:''.join(run['text']for run in r['runs'])for r in result['actual_export_text_positions']}
 if before!=after:raise ValueError('author_source_actual_export_full_text_inventory_changed')
 native={'cells':initial['cells'],'vertices':initial['vertices'],'edges':initial['edges'],'graphBounds':initial['graph_bounds'],'actual_platform_font_usage':[{'cell':row['cell'],'fonts':row['actual_fonts']}for row in observations],'actual_text_positions':result['actual_export_text_positions'],'source_DOM_glyph_positions':[{'cell':r['cell'],'runs':r['runs']}for r in observations],'actual_dom_paint_bounds':{'unsupported':False,'source_full_paint_inspection':True,'strict_outside_export_pixels':outside},'source_metadata_export':{'version':version,'scale':scale,'border':border,'viewBox':result['natural_svg_viewBox'],'viewport':[width,height]},'author_export_pristine_RGBA_equals_owned_RGBA':True,'author_source_full_inspection_center_RGBA_exact':True,'author_source_no_paint_outside_original_export_frame':True}
 assets={'source_png':put(work/'source.official.png',pristine),'source_svg':put(work/'source.official.svg',result['pristine'].pop('svg').encode()),'owned_svg':put(work/'source.owned.svg',result['owned'].pop('svg').encode()),'inspection_png':put(work/'source.inspection.png',inspection),'native_model':put(work/'source.native_model.xml',initial.pop('native_model').encode())}
 proof={'policy':POLICY,'source_metadata_profile':profile,'source_XML_sha256':sha(xml.encode()),'initial':initial,'export':result,'native_render':native,'network_requests_denied':requests,'unresolved_paint_resources':False,'assets':assets,'no_reference_input':True,'source_geometry_or_viewport_fitting':False,'model_calls':0}
 put(work/'source_export_proof.json',raw(proof));return {'ok':True,'png':pristine,'native_render':native,'proof':proof,'source_observations':observations,'assets':assets}
