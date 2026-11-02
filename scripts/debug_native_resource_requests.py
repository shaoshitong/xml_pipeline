#!/usr/bin/env python3
"""HKUST-only, offline GraphViewer dependency trace; never creates canonical pairs.
No resource fetches are permitted. Request URLs are reduced to host/path/type and
query KEY names before any trace is written. Source assets are already on HKUST.
"""
import argparse,collections,copy,hashlib,importlib.util,json,math,os,re,signal,subprocess,sys,time,urllib.parse,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
MAX_XML=20*1024*1024


def now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def sha(data):return hashlib.sha256(data).hexdigest()
def atomic_json(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));os.replace(tmp,path)
def load_helpers(path=None):
 path=Path(path) if path else Path(__file__).resolve().with_name('curate_derived.py')
 spec=importlib.util.spec_from_file_location('native_resource_debug_helpers',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def safe_url(url,resource_type='unknown'):
 try:parsed=urllib.parse.urlsplit(str(url))
 except ValueError:return {'scheme':'invalid','host':None,'path':'[invalid]','resource_type':resource_type,'query_keys':[]}
 scheme=parsed.scheme.lower();path=parsed.path if scheme in ('http','https','file') else ''
 # Long opaque path components are unnecessary for classifying CSS/stencils/media.
 path='/'.join('[opaque]' if re.fullmatch(r'[A-Za-z0-9_=-]{48,}',x) else x for x in path.split('/'))[:500]
 keys=[]
 for part in parsed.query.split('&'):
  key=urllib.parse.unquote_plus(part.split('=',1)[0])
  if not key:continue
  key=key if re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}',key) else '[other]'
  if key not in keys:keys.append(key)
 return {'scheme':scheme,'host':parsed.hostname,'path':path,'resource_type':resource_type,'query_keys':keys[:30]}

def safe_message(value):
 def replace(match):
  item=safe_url(match.group(0));return str(item['host'] or '')+item['path']+('?[keys:'+','.join(item['query_keys'])+']' if item['query_keys'] else '')
 return re.sub(r'https?://[^\s\"\'<>]+',replace,str(value))[-1200:]

def font_families(tree):
 values=[]
 for node in tree.iter():
  for key,value in node.attrib.items():
   if key.lower() in ('fontfamily','font-family'):values.append(value)
   values.extend(re.findall(r'(?:^|;)fontFamily=([^;]+)',value,re.I))
   values.extend(re.findall(r'font-family\s*:\s*([^;"<>]+)',value,re.I))
 return sorted({x.strip().strip('\"\'')[:150] for x in values if x.strip()})[:50]

def selected_xml(text,page_index,h):
 if len(text.encode())>MAX_XML or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('unsafe_or_oversized_source_xml')
 tree=ET.fromstring(text)
 if h.localtag(tree)=='mxfile':
  pages=[x for x in tree if h.localtag(x)=='diagram']
  if not 0<=page_index<len(pages):raise ValueError('requested_original_page_index_out_of_bounds')
  selected=ET.Element(tree.tag,dict(tree.attrib));selected.append(copy.deepcopy(pages[page_index]));count=len(pages);name=pages[page_index].get('name')
 elif h.localtag(tree)=='mxGraphModel':
  if page_index!=0:raise ValueError('single_model_has_only_page_zero')
  selected=tree;count=1;name=None
 else:raise ValueError('native_drawio_root_required')
 native=h.extract_native(selected)
 if not native:raise ValueError('cannot_normalize_selected_native_page')
 issue=h.native_asset_issue(native)
 if issue=='active_drawio_html_content':raise ValueError(issue)
 return native['code'],{'original_page_count':count,'source_page_index':page_index,'source_page_name':name,'static_asset_issue':issue,'font_families_from_xml':font_families(native['tree'])}

def render_child(args):
 from playwright.sync_api import sync_playwright
 case=args.case_directory;spec=json.loads((case/'case.json').read_text());source=case/'selected.drawio';code=source.read_text();tree=ET.fromstring(code);bundle=Path(spec['viewer_bundle'])
 if not bundle.is_file() or bundle.stat().st_size<100000:raise ValueError('cached_official_viewer_missing_no_download_attempted')
 model=tree if tree.tag=='mxGraphModel' else tree.find('.//mxGraphModel')
 def dimension(key,default):
  try:value=float(model.get(key,default)) if model is not None else default
  except (ValueError,TypeError):raise ValueError('invalid_canvas_dimensions')
  if not math.isfinite(value) or value<=0:raise ValueError('invalid_canvas_dimensions')
  return math.ceil(value)
 width,height=dimension('pageWidth',1280),dimension('pageHeight',720)
 if max(width,height)>8192 or width*height>64000000:raise ValueError('canvas_exceeds_renderer_limits')
 trace=[];unique={};logs=collections.Counter();result={'ok':False,'started_at':now(),'network_and_file_resources_blocked':True,'viewer_bundle_sha256':sha(bundle.read_bytes()),'canvas':[width,height],'font_families_from_xml':spec.get('font_families_from_xml',[]),'source':{k:spec.get(k) for k in ('source_kind','source_member','source_page_index','source_page_name','original_page_count','selected_code_sha256')}}
 stream=(case/'requests.sanitized.jsonl').open('w')
 def event(kind,request,detail=None):
  item={'event':kind,**safe_url(request.url,request.resource_type)}
  if detail:item['detail']=safe_message(detail)
  if len(trace)<200:trace.append(item);stream.write(json.dumps(item,ensure_ascii=False)+'\n');stream.flush()
  key=json.dumps({k:v for k,v in item.items() if k not in ('event','detail')},sort_keys=True);unique[key]=unique.get(key,0)+1
 started=time.monotonic();browser=None
 try:
  installed=sorted(Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),key=lambda p:int(re.search(r'chromium-(\d+)',str(p)).group(1)),reverse=True)
  options={'headless':True,'args':['--disable-dev-shm-usage'],'timeout':10000}
  if installed:options['executable_path']=str(installed[0])
  with sync_playwright() as p:
   browser=p.chromium.launch(**options);context=browser.new_context(viewport={'width':max(width,640),'height':max(height,480)},device_scale_factor=1,service_workers='block');context.set_offline(True)
   page=context.new_page();page.set_default_timeout(7000)
   page.on('request',lambda request:event('requested',request))
   page.on('requestfailed',lambda request:event('failed',request,request.failure))
   page.on('pageerror',lambda error:logs.update(['pageerror']))
   page.on('console',lambda msg:logs.update(['console_'+msg.type]) if msg.type in ('error','warning') else None)
   def deny(route):event('blocked',route.request);route.abort()
   context.route('**/*',deny)
   page.set_content('<!doctype html><html><head><style>html,body{margin:0;padding:0;background:white}#graph{position:relative;margin:0;padding:0;border:0;overflow:hidden;background:white;width:'+str(width)+'px;height:'+str(height)+'px}</style></head><body><div id="graph"></div></body></html>',wait_until='domcontentloaded')
   page.evaluate('''()=>{window.onDrawioViewerLoad=()=>{window.viewerBundleReady=true};window.mxLoadResources=false;window.mxLoadStylesheets=false;}''')
   page.add_script_tag(path=str(bundle));page.wait_for_function("typeof GraphViewer==='function'")
   page.evaluate('''xml=>{const d=document.getElementById('graph');d.setAttribute('data-mxgraph',JSON.stringify({xml,nav:false,resize:false,responsive:false,'auto-fit':false,'auto-origin':false,'browser-translate':false,'allow-zoom-in':false,'allow-zoom-out':false,center:false,border:0,zoom:1,lightbox:false,editable:false,'dark-mode':'light','show-note-icons':false}));GraphViewer.createViewerForElement(d,v=>{window.evalViewer=v});}''',code)
   page.wait_for_function('window.evalViewer && window.evalViewer.graph && window.evalViewer.graph.view')
   info=page.evaluate('''dims=>{const g=window.evalViewer.graph,d=document.getElementById('graph');g.sizeDidChange=function(){};g.view.scaleAndTranslate(1,0,0);g.view.validate();d.style.width=dims[0]+'px';d.style.height=dims[1]+'px';d.style.overflow='hidden';d.scrollLeft=0;d.scrollTop=0;const b=g.getGraphBounds();return {graphBounds:{x:b.x,y:b.y,width:b.width,height:b.height},cells:Object.keys(g.model.cells).length,svgCount:d.querySelectorAll('svg').length,foreignObjectCount:d.querySelectorAll('foreignObject').length};}''',[width,height]);result.update(info)
   page.evaluate('document.fonts.ready')
   result['dom_font_families']=page.evaluate('''()=>Array.from(new Set(Array.from(document.fonts).map(f=>f.family))).slice(0,50)''')
   page.locator('#graph').screenshot(path=str(case/'debug.render.png'),animations='disabled',timeout=10000)
   result['png']='debug.render.png';result['ok']=True
   browser.close();browser=None
 except Exception as exc:result['error']=type(exc).__name__+':'+safe_message(exc)
 finally:
  if browser:
   try:browser.close()
   except Exception:pass
  stream.close();result.update({'seconds':round(time.monotonic()-started,3),'requests':trace,'unique_requests':[{**json.loads(k),'events':v} for k,v in unique.items()],'console_and_pageerror_counts':dict(logs),'no_resource_fetches_attempted_by_collector':True,'note':'A diagnostic PNG may contain fallback fonts or missing assets. It is never accepted as a canonical image/code pair.'});atomic_json(case/'debug.trace.json',result)
 print(json.dumps({'case':case.name,'ok':result['ok'],'seconds':result['seconds'],'unique_requests':result['unique_requests'],'font_families_from_xml':result['font_families_from_xml'],'trace':str(case/'debug.trace.json')},ensure_ascii=False),flush=True)
 return 0 if result['ok'] else 1

def main_run(args):
 root=args.root.resolve();h=load_helpers(args.helpers);renderer=h.renderer_path(root,args.drawio_renderer);bundle=renderer.parent/'assets/viewer-static.min.js'
 if not bundle.is_file() or bundle.stat().st_size<100000:raise ValueError('cached_official_viewer_missing_no_download_attempted')
 archive=root/'raw/jgraph--drawio-diagrams/source.zip';cases=[]
 with zipfile.ZipFile(archive) as package:
  members=[x for x in package.infolist() if not x.is_dir() and x.filename.lower().endswith(args.member_suffix.lower())]
  if len(members)!=1:raise ValueError('member_suffix_must_match_exactly_one_existing_zip_member')
  member=members[0]
  if member.file_size>MAX_XML:raise ValueError('source_member_over_20MB')
  code,info=selected_xml(package.read(member).decode('utf-8-sig'),args.page_index,h);cases.append(('official-csv-page-'+str(args.page_index),code,{**info,'source_kind':'already_downloaded_official_zip','source_member':member.filename,'source_member_crc':member.CRC}))
 if args.include_pilot:
  source=(args.pilot_source or root/'evaluation/native_xml_pilot/case_01/native.drawio').resolve()
  try:source.relative_to(root)
  except ValueError:raise ValueError('pilot_source_must_be_inside_collection')
  if not source.is_file():raise ValueError('requested_existing_pilot_source_missing')
  code,info=selected_xml(source.read_text(),0,h);cases.append(('existing-native-pilot',code,{**info,'source_kind':'already_existing_evaluation_native_xml','source_path':str(source.relative_to(root))}))
 destination=root/'remote/evaluation/native_resource_debug'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());destination=destination.with_name(destination.name+'-'+str(os.getpid()));destination.mkdir(parents=True,exist_ok=False)
 results=[]
 for name,code,info in cases[:2]:
  case=destination/name;case.mkdir();(case/'selected.drawio').write_text(code);atomic_json(case/'case.json',{**info,'selected_code_sha256':sha(code.encode()),'viewer_bundle':str(bundle),'viewer_bundle_sha256':sha(bundle.read_bytes())})
  process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker','--case-directory',str(case)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
  try:out,err=process.communicate(timeout=args.timeout)
  except subprocess.TimeoutExpired:
   os.killpg(process.pid,signal.SIGKILL);out,err=process.communicate();atomic_json(case/'hard_timeout.json',{'timeout_seconds':args.timeout,'note':'The subprocess group was stopped; incremental sanitized request JSONL remains available.'})
  detail_path=case/'debug.trace.json'
  detail=json.loads(detail_path.read_text()) if detail_path.is_file() else {'ok':False,'error':'hard_timeout_or_worker_failure','sanitized_stderr':safe_message(err.decode(errors='replace'))}
  results.append({'case':name,'diagnostic_directory':str(case),'ok':detail.get('ok'),'unique_requests':detail.get('unique_requests',[]),'font_families_from_xml':info.get('font_families_from_xml'),'dom_font_families':detail.get('dom_font_families',[]),'error':detail.get('error'),'png_present':(case/'debug.render.png').is_file()})
 summary={'created_at':now(),'diagnostic_only':True,'network_resources_fetched':False,'output_directory':str(destination),'cases':results};atomic_json(destination/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True);return 0

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path);p.add_argument('--helpers',type=Path);p.add_argument('--drawio-renderer',type=Path);p.add_argument('--member-suffix',default='CSVimport-examples.drawio');p.add_argument('--page-index',type=int,default=1,help='Zero-based original source page index');p.add_argument('--include-pilot',action='store_true');p.add_argument('--pilot-source',type=Path);p.add_argument('--timeout',type=int,default=30);p.add_argument('--worker',action='store_true');p.add_argument('--case-directory',type=Path);p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:
  source='https://user:password@fonts.googleapis.com/css2?family=Secret+Font&display=swap&token=PRIVATE_TOKEN';item=safe_url(source,'stylesheet');encoded=json.dumps(item);assert item['host']=='fonts.googleapis.com' and item['path']=='/css2' and set(item['query_keys'])=={'family','display','token'};assert all(x not in encoded for x in ('password','Secret','PRIVATE_TOKEN'));assert 'PRIVATE_TOKEN' not in safe_message('error '+source);print('{"self_test":"passed","checks":["request query values and credentials omitted","safe diagnostic errors"]}');return 0
 if a.worker:return render_child(a)
 if not a.root:p.error('--root required')
 if not 1<=a.timeout<=30:p.error('--timeout must be 1..30 seconds')
 return main_run(a)
if __name__=='__main__':raise SystemExit(main())
