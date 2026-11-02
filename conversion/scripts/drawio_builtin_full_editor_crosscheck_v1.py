"""Audit native PDF metadata extraction and exercise the full pinned draw.io UI.

Only the main entrypoint receives a callback to expose the official UI instance.
The PDF importer and EditorUi import methods execute unchanged from draw.war.
Controls are in-memory metadata byte strings, never PDF artifacts.
"""
from pathlib import Path
import base64, hashlib, http.server, json, mimetypes, re, subprocess, threading, urllib.parse, zipfile
from playwright.sync_api import sync_playwright

R=Path('/backup/shaoshitong/img2code_20261029')
WAR=R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war'
D=R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v2/full_editor_crosscheck_v1/attempt_03'
PDF=R/'clean/arxiv_research_figures_v1/acquisition_pilot_v1/2505.09388v1/source/figures/posttrain_pipeline.pdf'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
sha=lambda b:hashlib.sha256(b).hexdigest()
def once(path,obj):
    with path.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
z=zipfile.ZipFile(WAR)
def function(file,prefix,name):
    text=z.read(file).decode();m=re.search(re.escape(prefix+name)+r' = function\b[\s\S]*?\n\t?};',text)
    if not m:raise ValueError('missing_official_function:'+name)
    return m.group(0),m.group(0).split(' = ',1)[1][:-1]
parts=[function('js/diagramly/Editor.js','Editor.',name)[0] for name in ['extractGraphModelFromPdf','extractGraphModelFromXref']]
official='\n\n'.join(parts)+'\n'
graph_helper=function('js/grapheditor/Graph.js','Graph.','stringToArrayBuffer')[0]
controls_js=r'''const fs=require('fs'),vm=require('vm'),zlib=require('zlib'),crypto=require('crypto');
let input=JSON.parse(fs.readFileSync(0,'utf8'));
const c={Editor:{},Graph:{},mxClient:{IS_SF:false},window:{},atob:s=>Buffer.from(s,'base64').toString('latin1')};c.window.atob=c.atob;c.Base64={decode:c.atob};vm.createContext(c);
vm.runInContext(input.pako,c);vm.runInContext(input.graph_helper,c);vm.runInContext(input.official,c);
const xml='<mxfile><diagram name="metadata-control"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>';
const enc=encodeURIComponent(xml);const hex=Buffer.from(enc,'ascii').toString('hex');
const items=[
['negative_plain','%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n',null],
['positive_inline_subject','%PDF-1.4\n1 0 obj\n<< /Subject ('+enc+') >>\nendobj\n%%EOF\n',xml],
['positive_xref_subject','%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n2 0 obj\n<< /Subject 3 0 R >>\nendobj\n3 0 obj\n('+enc+')\nendobj\ntrailer\n<< /Root 1 0 R /Info 2 0 R >>\n%%EOF\n',xml],
['negative_embedded_mime_bad_stream','%PDF-1.7\n1 0 obj\n<< /Type /EmbeddedFile /Subtype /application#2Fvnd.jgraph.mxfile >>\nstream\nnotdeflate\nendstream\nendobj\n',null],
['positive_embedded_zlib_wrapped','%PDF-1.7\n1 0 obj\n<< /Type /EmbeddedFile /Subtype /application#2Fvnd.jgraph.mxfile >>\nstream\n'+zlib.deflateSync(Buffer.from(xml)).toString('latin1')+'\nendstream\nendobj\n',xml],
['positive_object_stream_subject','%PDF-1.7\n1 0 obj\n<< /Type /ObjStm >>\nstream\n'+zlib.deflateSync(Buffer.from('a /Subject <FEFF'+hex+'>')).toString('latin1')+'\nendstream\nendobj\n',xml]];
const controls=items.map(([name,content,want])=>{c.data='data:application/pdf;base64,'+Buffer.from(content,'latin1').toString('base64');let got=vm.runInContext('Editor.extractGraphModelFromPdf(data)',c,{timeout:10000});return {name,pass:got===want,result_type:got===null?'null':typeof got,result_bytes:got===null?0:Buffer.byteLength(got),result_sha256:got===null?null:crypto.createHash('sha256').update(got).digest('hex')}});
process.stdout.write(JSON.stringify({controls,all_pass:controls.every(x=>x.pass),control_pdf_artifacts_created:0}));'''
result=subprocess.run(['/usr/bin/node','-e',controls_js],input=json.dumps({'pako':z.read('js/deflate/pako.min.js').decode(),'graph_helper':graph_helper,'official':official}),text=True,capture_output=True,timeout=30)
if result.returncode:raise RuntimeError(result.stderr[-2000:])
controls=json.loads(result.stdout)
D.mkdir(parents=True,exist_ok=False)
once(D/'controls.json',dict(controls,official_functions_sha256=sha(official.encode()),official_graph_helper_sha256=sha(graph_helper.encode()),pako_sha256=sha(z.read('js/deflate/pako.min.js')),control_harness_sha256=sha(controls_js.encode()),dependencies=['window.atob/atob','mxClient.IS_SF','Base64.decode fallback','pako.inflateRaw','Graph.stringToArrayBuffer','Editor.extractGraphModelFromXref','built-in decodeURIComponent and Uint8Array'],dependency_shims='Browser base64 globals only; actual official Graph.stringToArrayBuffer used.'))
print(json.dumps({'stage':'controls','all_pass':controls['all_pass'],'controls':controls['controls'],'output':str(D/'controls.json')}),flush=True)
assert controls['all_pass'],'official_extractor_control_failure'

requests=[];zip_read_lock=threading.Lock()
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path=urllib.parse.unquote(urllib.parse.urlparse(self.path).path).lstrip('/') or 'index.html'
        if '..' in Path(path).parts:self.send_error(400);return
        try:
            with zip_read_lock:body=z.read(path)
        except KeyError:self.send_error(404);return
        if path=='js/main.js':
            body=b'App.main(function(ui){window.__nativePdfProbeUi=ui;});\n'+body
        requests.append(path)
        self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();origin='http://127.0.0.1:'+str(server.server_port)
errors=[];blocked=[]
def guard(route):
    if route.request.url.startswith(origin+'/'):route.continue_()
    else:blocked.append(route.request.url.split('?',1)[0]);route.abort()
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage','--disable-gpu'])
        context=browser.new_context(service_workers='block');context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:1000]));page.on('dialog',lambda dialog:dialog.dismiss())
        page.goto(origin+'/?dev=1&offline=1&local=1&splash=0&libs=0&math=0&ui=kennedy&stealth=1',wait_until='domcontentloaded',timeout=45000)
        page.wait_for_function('window.__nativePdfProbeUi && window.__nativePdfProbeUi.editor && typeof window.__nativePdfProbeUi.importFiles === "function"',timeout=45000)
        runtime_sources=page.evaluate('''()=>({extractGraphModelFromPdf:Editor.extractGraphModelFromPdf.toString(),extractGraphModelFromXref:Editor.extractGraphModelFromXref.toString(),importFiles:EditorUi.prototype.importFiles.toString(),importFile:EditorUi.prototype.importFile.toString(),insertTextAt:EditorUi.prototype.insertTextAt.toString(),version:EditorUi.VERSION})''')
        hashes={name:sha(value.encode()) for name,value in runtime_sources.items() if name!='version'}
        expected={name:sha(function('js/diagramly/Editor.js','Editor.',name)[1].encode()) for name in ['extractGraphModelFromPdf','extractGraphModelFromXref']}
        expected.update({name:sha(function('js/diagramly/EditorUi.js','EditorUi.prototype.',name)[1].encode()) for name in ['importFiles','importFile','insertTextAt']})
        assert hashes==expected,{'runtime_method_hash_mismatch':{k:[hashes[k],expected[k]] for k in hashes if hashes[k]!=expected[k]}}
        print(json.dumps({'stage':'full_editor_ready','version':runtime_sources['version'],'all_5_official_runtime_method_hashes_match':True}),flush=True)
        run_js=r'''async({base64,name})=>{
          const ui=window.__nativePdfProbeUi,graph=ui.editor.graph;graph.getModel().clear();graph.setEnabled(true);
          function facts(){let cells=Object.values(graph.getModel().cells);return {cells:cells.length,vertices:cells.filter(c=>c.vertex).length,edges:cells.filter(c=>c.edge).length,image_vertices:cells.filter(c=>c.vertex&&/(?:^|;)shape=image(?:;|$)/.test(c.style||'')).length,vertex_metadata:cells.filter(c=>c.vertex).map(c=>{let s=String(c.style||''),v=typeof c.value==='string'?c.value:'',g=c.geometry;return {id:c.id,vertex:!!c.vertex,edge:!!c.edge,style_keys:s.split(';').filter(Boolean).map(x=>x.split('=')[0]),shape:(s.match(/(?:^|;)shape=([^;]*)/)||[])[1]||null,image_value_prefix:(s.match(/(?:^|;)image=([^;]{0,36})/)||[])[1]||null,value_type:typeof c.value,value_characters:v.length,value_contains_pdf_data_uri:v.includes('data:application/pdf;base64,'),value_sha256_pending:v,geometry:g?{x:g.x,y:g.y,width:g.width,height:g.height}:null};})};}
          const before=facts(),calls=[],errors=[];const originalExtract=Editor.extractGraphModelFromPdf,originalError=ui.handleError;
          Editor.extractGraphModelFromPdf=function(data){const result=originalExtract.call(this,data);calls.push({input_bytes:data.length,result_type:result===null?'null':typeof result,result_bytes:result===null?0:result.length});return result;};
          let resolveDone;const promise=new Promise(resolve=>resolveDone=resolve);let timer;
          ui.handleError=function(e){errors.push(String(e?.message||e));resolveDone({terminal:'official_ui_handleError'});};
          const data=Uint8Array.from(atob(base64),c=>c.charCodeAt(0));const file=new File([data],name,{type:'application/pdf'});
          try{ui.importFiles([file],0,0,ui.maxImageSize,null,cells=>resolveDone({terminal:'official_importFiles_resultFn',returned_cells:cells?.length??null}));}
          catch(e){errors.push(String(e?.message||e));resolveDone({terminal:'thrown'});}
          timer=setTimeout(()=>resolveDone({terminal:'bounded_observation_timeout_10000ms'}),10000);
          const terminal=await promise;clearTimeout(timer);await new Promise(r=>setTimeout(r,200));
          Editor.extractGraphModelFromPdf=originalExtract;ui.handleError=originalError;const after=facts();for(const state of [before,after]){for(const cell of state.vertex_metadata){const data=new TextEncoder().encode(cell.value_sha256_pending);const h=await crypto.subtle.digest('SHA-256',data);cell.value_sha256=Array.from(new Uint8Array(h),v=>v.toString(16).padStart(2,'0')).join('');delete cell.value_sha256_pending;}}return {name,before,after,calls,errors,...terminal};
        }'''
        pdf=PDF.read_bytes();ordinary=page.evaluate(run_js,{'base64':base64.b64encode(pdf).decode(),'name':PDF.name})
        xml='<mxfile><diagram name="control"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="a" parent="1" vertex="1" value="control A"><mxGeometry x="0" y="0" width="80" height="40" as="geometry"/></mxCell><mxCell id="b" parent="1" vertex="1" value="control B"><mxGeometry x="150" y="0" width="80" height="40" as="geometry"/></mxCell><mxCell id="e" parent="1" edge="1" source="a" target="b"><mxGeometry relative="1" as="geometry"/></mxCell></root></mxGraphModel></diagram></mxfile>'
        raw=('%PDF-1.4\n1 0 obj\n<< /Subject ('+urllib.parse.quote(xml,safe="~()*!.'-")+') >>\nendobj\n%%EOF\n').encode()
        positive=page.evaluate(run_js,{'base64':base64.b64encode(raw).decode(),'name':'in_memory_metadata_control.pdf'})
        crosscheck={'schema':'drawio_full_editor_builtin_pdf_crosscheck_v1','official_war':str(WAR),'official_war_sha256':sha(WAR.read_bytes()),'version':runtime_sources['version'],
          'entrypoint_observation':'Only js/main.js is prefixed with App.main(callback) to capture its normal UI instance. Official Editor/EditorUi functions remain byte-exact by function-source hashes.',
          'official_runtime_method_sha256':hashes,'all_official_method_hashes_match':True,'file_api':'new File -> ui.importFiles -> official ui.importFile -> official ui.insertTextAt -> official Editor.extractGraphModelFromPdf',
          'ordinary_pdf':dict(ordinary,pdf_file=str(PDF.relative_to(R)),pdf_sha256=sha(pdf),pdf_bytes=len(pdf)),'in_memory_positive_control':positive,'metadata_controls_all_pass':controls['all_pass'],
          'page_errors':errors,'external_network_blocked_count':len(blocked),'served_asset_count':len(requests),'pdf_artifacts_created':0,'new_conversions':0,'model_calls':0,'qualified_pairs':0,'custom_pdf_geometry_converter_used':False,'data_on_HKUST_only':True}
        once(D/'result.json',crosscheck);print(json.dumps(crosscheck,ensure_ascii=False),flush=True)
        browser.close()
finally:server.shutdown();server.server_close();z.close()
