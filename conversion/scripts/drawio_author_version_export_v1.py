"""Official source-only native export, isolated per author-version runtime.

No reference image, dimensions, scores, font substitution or graph fitting API.
Executes unmodified vendor Editor.setGraphXml/exportToCanvas/Graph.getSvg.
"""
from pathlib import Path
import base64,hashlib,json,math
from playwright.sync_api import sync_playwright
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
ROOT=W/'runtime/drawio_author_export_27_28_v2'
CHROME=Path('/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome')
SHA={'27.0.9':'4a0ebb65d95cf63b1faeffaf3d50ec155d2e697b4b0945e54bcbdc12f9e4d8ed','28.0.6':'8023bd90a95df002ecbb0fcd848941b48438dedc73484eece07b91b22702c416','32.6.1':'0c12ccf10dcaf0d0ef40ca60a5bc881ba27b57e076797ee39bce46602371f769'}
POLICY='unmodified_official_drawio_author_version_source_only_export_v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(x):return(json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False,indent=2)+'\n').encode()
def put(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b)
 return {'file':str(p),'sha256':sha(b),'bytes':len(b)}
def configuration(version):
 if version not in SHA:raise ValueError('unregistered_official_source_runtime')
 viewer=ROOT/version/'js/viewer-static.min.js';assert sha(viewer.read_bytes())==SHA[version]
 pins={str(p):sha(p.read_bytes())for p in (Path(__file__).resolve(),viewer,ROOT/version/'styles/grapheditor.css',ROOT/version/'provenance.json',CHROME)if p.exists()}
 # 32.6.1 copied baseline viewer has no new stylesheet; use the official
 # stylesheet from that exact core commit, never one from another version.
 if not(ROOT/version/'styles/grapheditor.css').exists():raise ValueError('matching_version_editor_CSS_missing')
 return {'policy':POLICY,'version':version,'pins':pins,'source_loading':'unmodified Editor.setGraphXml on uniquely source-matched full mxGraphModel','export':'unmodified Editor.exportToCanvas, no width limit, full graph, source scale/border, official PNG dialog default opaque/light/diagram/no-grid','host_browser':str(CHROME),'author_Electron_and_OS_reproduced':False,'no_reference_input_to_exporter':True,'network':'all requests denied; missing external source resources are errors'}
INIT='''({xml,scale,border})=>{
 const graph=new Graph(document.getElementById('graph'));
 const editor=new Editor(false,null,null,graph,true);
 const root=mxUtils.parseXml(xml).documentElement;
 if(root.nodeName!=='mxGraphModel')throw Error('source_must_be_one_complete_author_model');
 const style=root.getAttribute('style')||'default-style2';
 if(!graph.themes?.[style])throw Error('source_stylesheet_not_in_pinned_official_bundle');
 editor.setGraphXml(root);graph.clearSelection();graph.refresh();
 window.sourceGraph=graph;window.sourceEditor=editor;
 return{version:EditorUi.VERSION,style,currentStyle:graph.currentStyle,themeXml:mxUtils.getXml(graph.themes[style]),scale,border,graphView:{scale:graph.view.scale,translate:{x:graph.view.translate.x,y:graph.view.translate.y}},background:graph.background,shadow:graph.shadowVisible,adaptiveColors:graph.getAdaptiveColors(),graphBounds:graph.getGraphBounds(),nativeModel:mxUtils.getXml(new mxCodec().encode(graph.model)),cellCount:Object.keys(graph.model.cells).length,sourceFunctions:{setGraphXml:Editor.prototype.setGraphXml.toString(),exportToCanvas:Editor.prototype.exportToCanvas.toString(),getSvg:Graph.prototype.getSvg.toString()}};
}'''
OBSERVE='''()=>{
 const graph=window.sourceGraph,rows=[];
 for(const id of Object.keys(graph.model.cells)){
  const cell=graph.model.cells[id],state=graph.view.getState(cell);
  if(!state)continue;
  let texts=[];
  if(state.text?.node){
   const node=state.text.node;node.setAttribute('data-author-source-cell',id);
   const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT);let leaf;
   while(leaf=walker.nextNode()){
    const cs=getComputedStyle(leaf.parentElement),chars=[];
    let cursor=0;
    for(const char of Array.from(leaf.textContent||'')){
     const range=document.createRange();range.setStart(leaf,cursor);cursor+=char.length;range.setEnd(leaf,cursor);const r=range.getBoundingClientRect();
     chars.push({text:char,x:r.x,y:r.y,width:r.width,height:r.height});
    }
    texts.push({text:leaf.textContent,fontFamily:cs.fontFamily,fontSize:cs.fontSize,fontWeight:cs.fontWeight,fontStyle:cs.fontStyle,chars});
   }
  }
  rows.push({id,vertex:!!cell.vertex,edge:!!cell.edge,parent:cell.parent?.id,source:cell.source?.id,target:cell.target?.id,style:cell.style,value:typeof cell.value==='string'?cell.value:cell.value?.outerHTML??null,bounds:{x:state.x,y:state.y,width:state.width,height:state.height},texts});
 }
 return rows;
}'''
EXPORT='''({scale,border})=>new Promise((resolve,reject)=>{
 const graph=window.sourceGraph,editor=window.sourceEditor;
 const timer=setTimeout(()=>reject(Error('official_source_export_timeout')),120000);
 editor.exportToCanvas((canvas,svg)=>{clearTimeout(timer);resolve({png:canvas.toDataURL('image/png').split(',')[1],svg:mxUtils.getXml(svg),width:canvas.width,height:canvas.height,svgWidth:svg.getAttribute('width'),svgHeight:svg.getAttribute('height')})},null,null,null,error=>{clearTimeout(timer);reject(Error(error?.message||String(error)))},null,true,scale,false,graph.shadowVisible,null,graph,border,null,false,'light','diagram',null);
})'''
def render(model_bytes,scale,border,version,output):
 output=Path(output).resolve();assert output.is_relative_to(W/'drawio_author_export_source_dev_v1')and not output.exists();output.mkdir(parents=True)
 if not math.isfinite(scale)or scale<=0 or not math.isfinite(border)or border<0:raise ValueError('invalid_author_metadata_scale_or_border')
 cfg=configuration(version);put(output/'configuration.json',raw(cfg));put(output/'source_complete_model.xml',model_bytes)
 requests=[];errors=[]
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path=str(CHROME),args=['--disable-dev-shm-usage'])
  context=browser.new_context(viewport={'width':1200,'height':1000},device_scale_factor=1,color_scheme='light',locale='en-US')
  context.route('**/*',lambda route:(requests.append(route.request.url),route.abort())[-1])
  page=context.new_page();page.set_default_timeout(150000);page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content('<!doctype html><html><head></head><body style="margin:0"><div id="graph" style="position:relative;width:1200px;height:1000px"></div></body></html>')
  page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}')
  page.add_style_tag(path=str(ROOT/version/'styles/grapheditor.css'));page.add_script_tag(path=str(ROOT/version/'js/viewer-static.min.js'))
  initial=page.evaluate(INIT,{'xml':model_bytes.decode('utf-8'),'scale':scale,'border':border});assert initial['version']==version
  page.evaluate('()=>document.fonts.ready.then(()=>{sourceGraph.refresh()})')
  rows=page.evaluate(OBSERVE);cdp=context.new_cdp_session(page);cdp.send('DOM.enable');cdp.send('CSS.enable');document=cdp.send('DOM.getDocument',{'depth':0});usage=[]
  for row in rows:
   if not row['texts']:continue
   css='[data-author-source-cell='+json.dumps(row['id'])+']';node=cdp.send('DOM.querySelector',{'nodeId':document['root']['nodeId'],'selector':css})['nodeId']
   if node:usage.append({'cell':row['id'],'fonts':cdp.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']})
  result=page.evaluate(EXPORT,{'scale':scale,'border':border})
  png=base64.b64decode(result.pop('png'),validate=True);svg=result.pop('svg').encode();native=initial.pop('nativeModel').encode();functions=initial.pop('sourceFunctions');theme=initial.pop('themeXml').encode()
  evidence={'configuration':cfg,'initial_source_graph':initial,'actual_cell_states_and_glyph_ranges':rows,'actual_platform_font_usage':usage,'source_export':result,'network_requests_denied':requests,'page_errors':errors,'browser_version':browser.version,'source_model_bytes_sha256':sha(model_bytes),'exporter_has_no_reference_image_or_target_dimensions':True,'parameters_derived_from_reference':False,'source_cells_removed':False,'source_fonts_substituted':False,'manual_viewport_or_paint_translation':False,'author_OS_and_Electron_reproduced':False,'portability_or_qualified_claim':False}
  context.close();browser.close()
 if requests or errors:raise ValueError('unresolved_source_runtime_request_or_error:'+json.dumps({'requests':requests,'errors':errors}))
 assets={'source_svg':put(output/'source.official.svg',svg),'source_png':put(output/'source.official.png',png),'native_roundtrip_model':put(output/'native_roundtrip_model.xml',native),'official_functions':put(output/'actual_official_functions.json',raw(functions)),'official_embedded_theme':put(output/'actual_official_source_theme.xml',theme)}
 evidence['assets']=assets
 for name,digest in cfg['pins'].items():assert sha(Path(name).read_bytes())==digest
 put(output/'source_export_evidence.json',raw(evidence));return evidence
