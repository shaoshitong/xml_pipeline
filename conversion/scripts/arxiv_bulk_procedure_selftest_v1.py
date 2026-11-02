from pathlib import Path
import hashlib,json,subprocess,sys,urllib.parse
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
from arxiv_bulk_official_xml_png_v1 import OfficialXmlPng
D=R/'clean/arxiv_research_figures_v1/new_bulk_200_v1/procedure_selftest';D.mkdir(exist_ok=True)
cells=['<mxCell id="0"/><mxCell id="1" parent="0"/>']
for i in range(30):cells.append(f'<mxCell id="n{i}" parent="1" vertex="1" value="Procedure control node {i}"><mxGeometry x="{(i%6)*140}" y="{(i//6)*80}" width="110" height="45" as="geometry"/></mxCell>')
for i in range(40):cells.append(f'<mxCell id="e{i}" parent="1" edge="1" source="n{i%30}" target="n{(i+7)%30}"><mxGeometry relative="1" as="geometry"/></mxCell>')
xml='<mxfile><diagram><mxGraphModel><root>'+''.join(cells)+'</root></mxGraphModel></diagram></mxfile>'
S=R/'clean/arxiv_research_figures_v1/drawio_builtin_import_v1/official_importer'
js="""const fs=require('fs'),vm=require('vm');let x=JSON.parse(fs.readFileSync(0,'utf8'));let c={Editor:{},mxClient:{IS_SF:false},window:{},atob:s=>Buffer.from(s,'base64').toString('latin1')};c.window.atob=c.atob;c.Base64={decode:c.atob};vm.createContext(c);vm.runInContext(fs.readFileSync(x.root+'/pako.min.js','utf8'),c);vm.runInContext('var Graph={stringToArrayBuffer:s=>Uint8Array.from(s,c=>c.charCodeAt(0))};',c);vm.runInContext(fs.readFileSync(x.root+'/official_pdf_functions.js','utf8'),c);c.input='data:application/pdf;base64,'+Buffer.from('%PDF-1.4\\n1 0 obj\\n<< /Subject ('+encodeURIComponent(x.xml)+') >>\\nendobj\\n%%EOF\\n').toString('base64');process.stdout.write(vm.runInContext('Editor.extractGraphModelFromPdf(input)',c));"""
q=subprocess.run(['/usr/bin/node','-e',js],input=json.dumps({'root':str(S),'xml':xml}),capture_output=True,text=True,check=True,timeout=20);assert q.stdout==xml
(D/'control.drawio').write_text(xml)
renderer=OfficialXmlPng()
try:evidence=renderer.render(xml,D)
finally:renderer.close()
report={'schema':'sourceonly_bulk_procedure_selftest_v1','success':True,'official_inmemory_embedded_extraction_exact':True,'independent_control_vertices':30,'control_edges':40,'official_render_edit':evidence,'synthetic_control_excluded_from_dataset':True,'PDF_artifacts_created':0,'external_models':0,'custom_PDF_geometry_converter':False,'program_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(D/'success.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
