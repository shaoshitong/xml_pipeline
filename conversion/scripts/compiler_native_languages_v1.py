"""Finite native-language frontend. Candidate production is never qualification.

All source/artifact paths must reside on HKUST. The support predicate is pure Python
and shared with the pre-execution release-group selector.
"""
import argparse,collections,hashlib,html,json,os,re,sys,time,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
VERSION='compiler_native_languages_v1'
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
CHROME='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome'
REFERENCE_MERMAID_SHA='61b335a46df05a7ce1c98378f60e5f3e77a7fb608a1056997e8a649304a936d6'
PINNED={
 'js/diagramly/EditorUi.js':'3fee65f86362f942fa278384c1c820ef7c59ae8431209c6dd25eaaa4be53d1bf',
 'js/elk/drawio-elk.min.js':'aaa4bcf4564a25ce0c59376932eb553cca6b14d39734bb030aed48125719ade4',
 'js/mermaid/drawio-mermaid.min.js':'b21457ceed395089d66c644d9eff78396237e493747a9aefd9faef4a279921eb',
 'js/plantuml/drawio-plantuml.min.js':'036f7a6f873b671092e08fa3fe26af9a5abae78076699ba72e4b388406a2cf28'}
ID=r'[A-Za-z_][A-Za-z_0-9]*'
def sha(data):return hashlib.sha256(data).hexdigest()
def cleantext(value):return re.sub(r'\s+',' ',html.unescape(str(value or ''))).strip()
def statements(source):
 out=[];buf=[];quote=None;stack=[]
 for ch in source.replace('\r\n','\n'):
  if quote:
   buf.append(ch)
   if ch==quote:quote=None
  elif ch=='"':quote=ch;buf.append(ch)
  elif ch in '[({':stack.append(ch);buf.append(ch)
  elif ch in '])}':
   if stack:stack.pop()
   buf.append(ch)
  elif ch in ';\n' and not stack:
   if ''.join(buf).strip():out.append(''.join(buf).strip())
   buf=[]
  else:buf.append(ch)
 if ''.join(buf).strip():out.append(''.join(buf).strip())
 if stack or quote:raise ValueError('unclosed delimiter or quote')
 return out
def _label(value):
 value=value.strip()
 if value.startswith('"') and value.endswith('"'):value=value[1:-1]
 if not value or any(x in value for x in ['<','>','`','\\','\n','[',']','{','}','(',')']):raise ValueError('unsupported label markup/delimiter')
 return cleantext(value)
def parse_mermaid(source):
 if any(x in source for x in ['%%{','---\n','<','>"','`']):raise ValueError('configuration or marked-up label unsupported')
 lines=[s for s in statements(source) if not s.startswith('%%')]
 if not lines:raise ValueError('empty source')
 m=re.fullmatch(r'(?:graph|flowchart)\s+(TB|TD|BT|LR|RL)',lines[0])
 if not m:raise ValueError('only ordinary graph/flowchart directions supported')
 nodes={};edges=[];declared={};shapes={'[':(']','rect'),'(':(')','round'),'{':('}','diamond')}
 def node(s,pos):
  match=re.match(ID,s[pos:])
  if not match:raise ValueError('expected ASCII node identifier')
  ident=match.group();pos+=len(ident);pos0=pos
  while pos<len(s) and s[pos].isspace():pos+=1
  label=ident;shape='rect';explicit=False
  if s[pos:pos+2]=='((':
   end=s.find('))',pos+2)
   if end<0:raise ValueError('unclosed circle')
   label=_label(s[pos+2:end]);shape='circle';pos=end+2;explicit=True
  elif pos<len(s) and s[pos] in shapes:
   close,shape=shapes[s[pos]];end=s.find(close,pos+1)
   if end<0:raise ValueError('unclosed node label')
   label=_label(s[pos+1:end]);pos=end+1;explicit=True
  else:pos=pos0
  if explicit:
   if ident in declared and declared[ident]!=(label,shape):raise ValueError('conflicting node redefinition')
   declared[ident]=(label,shape);nodes[ident]={'id':ident,'text':label,'shape':shape}
  elif ident not in nodes:nodes[ident]={'id':ident,'text':label,'shape':shape}
  return ident,pos
 for s in lines[1:]:
  left,pos=node(s,0)
  while s[pos:].strip():
   pos+=len(s[pos:])-len(s[pos:].lstrip());edge=re.match(r'(-->|---|==>|===|-\.->|-\.-)',s[pos:])
   if not edge:raise ValueError('unrecognized statement or edge syntax: '+s[pos:pos+80])
   operator=edge.group();pos+=len(operator);pos+=len(s[pos:])-len(s[pos:].lstrip());label=''
   if s[pos:pos+1]=='|':
    end=s.find('|',pos+1)
    if end<0:raise ValueError('unclosed edge label')
    label=_label(s[pos+1:end]);pos=end+1
   pos+=len(s[pos:])-len(s[pos:].lstrip());right,pos=node(s,pos)
   edges.append({'source':left,'target':right,'text':label,'arrow':operator.endswith('>'),'dashed':'.' in operator,'thick':'=' in operator});left=right
 if not nodes:raise ValueError('no nodes')
 return {'unit':'mermaid_flowchart_native_v1','direction':m.group(1),'nodes':list(nodes.values()),'edges':edges,'statements_total':len(lines),'statements_recognized':len(lines),'mermaid_defaults_version':'10'}
def parse_plantuml(source):
 lines=[s.strip() for s in source.splitlines() if s.strip() and not s.strip().startswith("'")]
 if not lines or lines[0]!='@startuml' or lines[-1]!='@enduml':raise ValueError('exact @startuml/@enduml wrappers required')
 nodes={};edges=[];kinds='component|rectangle|node|database|cloud|queue|interface'
 for s in lines[1:-1]:
  m=re.fullmatch(r'('+kinds+r')\s+(?:"([^"\\<>]+)"\s+as\s+('+ID+r')|('+ID+r'))',s)
  bracket=re.fullmatch(r'\[([^\]\\<>]+)\]\s+as\s+('+ID+r')',s)
  relation=re.fullmatch(r'('+ID+r')\s+(-->|\.\.>|--|\.\.)\s+('+ID+r')(?:\s*:\s*(.+))?',s)
  if m:
   kind,label,alias,bare=m.groups();ident=alias or bare;label=_label(label or bare)
   if ident in nodes:raise ValueError('duplicate node declaration')
   nodes[ident]={'id':ident,'text':label,'shape':kind}
  elif bracket:
   label,ident=bracket.groups()
   if ident in nodes:raise ValueError('duplicate node declaration')
   nodes[ident]={'id':ident,'text':_label(label),'shape':'component'}
  elif relation:
   src,operator,tgt,label=relation.groups();edges.append({'source':src,'target':tgt,'text':_label(label) if label else '','arrow':operator.endswith('>'),'dashed':'.' in operator,'thick':False})
  else:raise ValueError('unrecognized statement: '+s[:100])
 if not nodes:raise ValueError('no declared nodes')
 for edge in edges:
  if edge['source'] not in nodes or edge['target'] not in nodes:raise ValueError('implicit undeclared endpoint unsupported')
 return {'unit':'plantuml_component_native_v1','nodes':list(nodes.values()),'edges':edges,'statements_total':len(lines),'statements_recognized':len(lines)}
def support_predicate(source,language):
 try:
  if len(source.encode())>200000:raise ValueError('source size limit')
  ir={'mermaid':parse_mermaid,'plantuml':parse_plantuml}[language](source)
  return {'supported':True,'unit':ir['unit'],'ir':ir,'unsupported':[]}
 except (ValueError,KeyError) as e:return {'supported':False,'unit':None,'unsupported':[str(e)]}
def _style(cell):
 result={}
 for part in cell.get('style','').split(';'):
  if '=' in part:
   key,value=part.split('=',1);result[key]=value
  elif part:result['_preset_'+part]='1'
 return result
def semantic_coverage(xml,ir,language):
 root=ET.fromstring(xml);parents={c:p for p in root.iter() for c in p};cells=list(root.iter('mxCell'));mapping={};labels={};edges=[];errors=[];stats=collections.Counter();source_labels={}
 def ident(c):return c.get('id') or parents.get(c,ET.Element('none')).get('id')
 for c in cells:
  stats['vertices' if c.get('vertex')=='1' else 'edges' if c.get('edge')=='1' else 'structural_cells']+=1
  if c.get('edge')=='1':edges.append(c)
  if c.get('vertex')!='1':continue
  p=parents.get(c);label=cleantext(c.get('value',p.get('label','') if p is not None else ''));mid=c.get('mermaidId') or (p.get('mermaidId') if p is not None else None)
  owner=c.get('parent') if _style(c).get('part')=='1' and label else ident(c)
  labels.setdefault(label,[]).append(owner)
  if label:source_labels[owner]=label
  if mid and mid.startswith('n:'):mapping[ident(c)]=mid[2:]
  if _style(c).get('shape')=='image' or 'image' in _style(c):errors.append({'code':'image_fallback','cell':ident(c)})
 if language=='plantuml':
  counts=collections.Counter(n['text'] for n in ir['nodes'])
  for n in ir['nodes']:
   candidates=labels.get(n['text'],[])
   if len(candidates)==1 and counts[n['text']]==1:mapping[candidates[0]]=n['id']
   else:errors.append({'code':'ambiguous_or_missing_source_node','source_id':n['id'],'text':n['text'],'candidate_count':len(candidates)})
 actual_nodes={mapping[cid]:source_labels.get(cid,'') for cid in mapping}
 expected_nodes={n['id']:n['text'] for n in ir['nodes']}
 if collections.Counter(mapping.values())!=collections.Counter(expected_nodes.keys()):errors.append({'code':'native_node_identity_multiplicity_mismatch'})
 if actual_nodes!=expected_nodes:errors.append({'code':'node_identity_or_text_mismatch','expected':expected_nodes,'actual':actual_nodes})
 for c in cells:
  if c.get('vertex')!='1' or ident(c) in mapping:continue
  # PlantUML decoration/caption parts are editable children of a semantic node.
  if language=='plantuml' and _style(c).get('part')=='1' and c.get('parent') in mapping:continue
  errors.append({'code':'uncovered_native_vertex','cell':ident(c),'style':_style(c)})
 by_id={ident(c):c for c in cells};source_node_by_id={n['id']:n for n in ir['nodes']};shape_evidence=[]
 for cid,sid in mapping.items():
  if sid not in source_node_by_id:continue
  cell=by_id[cid];style=_style(cell);shape=source_node_by_id[sid]['shape'];native_shape=style.get('shape');children=[c for c in cells if c.get('parent')==cid and _style(c).get('part')=='1'];ok=True
  if language=='mermaid':
   ok={'circle':native_shape=='ellipse' or '_preset_ellipse' in style,'diamond':native_shape=='rhombus' or '_preset_rhombus' in style,'round':style.get('rounded')=='1' and native_shape is None,'rect':native_shape in (None,'rectangle') and not any('_preset_'+x in style for x in ('ellipse','rhombus')) and style.get('rounded','0')=='0'}[shape]
  else:
   ok={'node':native_shape=='cube','database':native_shape=='cylinder3','cloud':native_shape=='cloud','queue':native_shape=='cylinder3' and style.get('direction')=='south','interface':native_shape=='ellipse' or '_preset_ellipse' in style,'component':len(children)>=3 and native_shape is None,'rectangle':native_shape in (None,'rectangle') and not children}[shape]
  shape_evidence.append({'source_id':sid,'source_shape':shape,'native_cell':cid,'native_shape':native_shape,'style':style,'type_match':ok})
  if not ok:errors.append({'code':'native_node_type_mismatch','source_id':sid,'source_shape':shape,'cell':cid,'style':style})
 actual_edges=[]
 for c in edges:
  p=parents.get(c);style=_style(c);src=mapping.get(c.get('source'));tgt=mapping.get(c.get('target'));label=cleantext(c.get('value',p.get('label','') if p is not None else ''))
  actual_edges.append((src,tgt,label,style.get('endArrow','none')!='none',style.get('dashed','0')=='1',float(style.get('strokeWidth','1'))>=3))
  if src is None or tgt is None:errors.append({'code':'unbound_or_unmapped_edge','cell':ident(c)})
 expected_edges=[(e['source'],e['target'],e['text'],e['arrow'],e['dashed'],e['thick']) for e in ir['edges']]
 missing=list((collections.Counter(expected_edges)-collections.Counter(actual_edges)).elements());extra=list((collections.Counter(actual_edges)-collections.Counter(expected_edges)).elements())
 if missing or extra:errors.append({'code':'edge_identity_label_or_marker_mismatch','missing':missing,'extra':extra})
 ids=[ident(c) for c in cells]
 if not all(ids) or len(set(ids))!=len(ids):errors.append({'code':'duplicate_or_missing_cell_id'})
 stats['bound_edges']=sum(c.get('source') in mapping and c.get('target') in mapping for c in edges)
 # Independent shape/style coverage is deliberately explicit; it is not a visual fidelity score.
 return {'ok':not errors,'errors':errors,'source_nodes':len(expected_nodes),'source_edges':len(expected_edges),'source_statements':ir['statements_total'],'recognized_statements':ir['statements_recognized'],'statement_coverage':1.0,'native_objects':dict(stats),'shape_evidence':shape_evidence,'limitations':['Font/layout and exact shape/style fidelity require independent target rendering validation.','No publication or qualification is performed by this module.']}
def validate(source_text,candidate_xml,frontend_report):
 """Reparse source and candidate independently of report-derived object counts."""
 language=frontend_report.get('language');support=support_predicate(source_text,language);failures=[];evidence={}
 if not support['supported']:return {'supported':False,'ok':False,'failures':[{'code':'unsupported_source','details':support['unsupported']}],'evidence':{'unit':None}}
 if frontend_report.get('source_sha256')!=sha(source_text.encode('utf-8')):failures.append({'code':'source_hash_mismatch'})
 if frontend_report.get('candidate_sha256')!=sha(candidate_xml.encode('utf-8')):failures.append({'code':'candidate_hash_mismatch'})
 try:
  coverage=semantic_coverage(candidate_xml,support['ir'],language);evidence={'unit':support['unit'],'coverage':coverage};failures.extend(coverage['errors'])
 except Exception as e:failures.append({'code':'invalid_candidate_xml','details':str(e)[:1000]})
 diagnostics=frontend_report.get('native_frontend',{})
 for field in ('warnings','diagnostics','logs'):
  if diagnostics.get(field):failures.append({'code':'native_'+field,'details':diagnostics[field]})
 if frontend_report.get('blocked_requests'):failures.append({'code':'blocked_resource_dependency'})
 return {'supported':True,'ok':not failures,'failures':failures,'evidence':evidence}
def prepare_runtime():
 target=W/'runtime'/VERSION;target.mkdir(parents=True,exist_ok=True);z=zipfile.ZipFile(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war');assets=[]
 for name,expected in PINNED.items():
  data=z.read(name)
  if sha(data)!=expected:raise ValueError('pinned archive member changed: '+name)
  path=target/Path(name).name
  if not path.exists():path.write_bytes(data)
  if sha(path.read_bytes())!=expected:raise ValueError('pinned extracted asset changed')
  assets.append({'archive_member':name,'path':str(path),'sha256':expected,'bytes':len(data)})
 # Retain the source license. This is code provenance, never a dataset download.
 licensefile=target/'LICENSE.drawio'
 if not licensefile.exists():
  import urllib.request
  licensefile.write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/jgraph/drawio/v32.6.1/LICENSE',timeout=30).read())
 reference=W/'runtime/mermaid_versions/10.9.1/mermaid.min.js'
 if sha(reference.read_bytes())!=REFERENCE_MERMAID_SHA:raise ValueError('independent Mermaid reference parser hash changed')
 manifest={'version':VERSION,'upstream_version':'draw.io v32.6.1','mermaid_defaults_version':'10','assets':assets,'independent_source_parser':{'version':'Mermaid 10.9.1','path':str(reference),'sha256':REFERENCE_MERMAID_SHA,'spdx':'MIT','license_path':str(W/'runtime/mermaid/node_modules/mermaid/LICENSE')},'license':{'spdx':'Apache-2.0','path':str(licensefile),'sha256':sha(licensefile.read_bytes()),'url':'https://github.com/jgraph/drawio/blob/v32.6.1/LICENSE'},'archive_path':str(R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war'),'upstream_editor_source_sha256':PINNED['js/diagramly/EditorUi.js'],'scope':'Ordinary flowchart without ELK/swimlane/postpass features; PlantUML component subset. All other source statements are rejected before conversion.'}
 (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
JS=r'''async ({source,language})=>{
 const logs=[];console.warn=(...a)=>logs.push(a.map(String).join(' '));console.error=(...a)=>logs.push(a.map(String).join(' '));
 const config={securityLevel:'strict',startOnLoad:false,maxTextSize:900000},options={version:'10'};
 const converter=language==='mermaid'?mxMermaidToDrawio:mxPlantUmlToDrawio;
 const fonts=language==='mermaid'?(converter.getFonts(source,config,options)||[]):[];
 if(fonts.length)throw Error('web_font_dependency_unsupported: '+JSON.stringify(fonts));
 await document.fonts.ready;
 const elk=language==='mermaid'?converter.getElkLayoutOptions(source,config,options):null;
 if(elk?.postPass)throw Error('required_layout_postpass_unsupported: '+JSON.stringify(elk));
 const resolved=language==='mermaid'?converter.resolveConfig(source,config,options):null;
 const xml=converter.parseText(source,config,options);
 // Copy process-global diagnostics immediately. Each CLI invocation owns its page.
 const warnings=structuredClone(converter.lastWarnings||[]),diagnostics=structuredClone(converter.lastDiagnostics||[]);
 if(!xml)throw Error('native_converter_no_output');
 let parserIR=null;
 if(language==='mermaid'){parserIR=Mermaid.MermaidParser.parse(source);}
 const g=new Graph(document.createElement('div')),doc=mxUtils.parseXml(xml);new mxCodec(doc).decode(doc.documentElement,g.model);g.view.validate();const bounds=g.getGraphBounds();
 const graphBounds={x:bounds.x,y:bounds.y,width:bounds.width,height:bounds.height};g.destroy();
 return {xml,warnings,diagnostics,logs,resolved_config:resolved,elk,web_fonts:fonts,compiler_parser_ir:parserIR,graphBounds};
}'''
def convert(source_path,language,output_dir):
 started=time.monotonic();source_path=Path(source_path).resolve();output_dir=Path(output_dir).resolve()
 if not source_path.is_relative_to(R) or not output_dir.is_relative_to(R):raise ValueError('source and output must remain on HKUST dataset root')
 output_dir.mkdir(parents=True,exist_ok=True);sourcebytes=source_path.read_bytes();source=sourcebytes.decode('utf-8-sig');support=support_predicate(source,language)
 report={'converter_version':VERSION,'source_path':str(source_path),'source_sha256':sha(sourcebytes),'language':language,'support':support,'qualified':False,'model_calls':0,'status':'unsupported_source','candidate_file':None}
 try:
  if not support['supported']:return report
  runtime=prepare_runtime();sys.path.insert(0,str(W/'scripts'));from native_worker import native
  from playwright.sync_api import sync_playwright
  viewer=native.renderer_path(R).parent/'assets/viewer-static.min.js';report['runtime']=runtime;report['viewer']={'path':str(viewer),'sha256':sha(viewer.read_bytes())}
  blocked=[]
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=CHROME,args=['--disable-dev-shm-usage'])
   try:
    context=browser.new_context(service_workers='block');context.set_offline(True);page=context.new_page();page.set_default_timeout(60000);page.route('**/*',lambda route:(blocked.append(route.request.url),route.abort()));page.set_content('<html><body></body></html>');page.evaluate('window.mxLoadResources=false;window.mxLoadStylesheets=false;window.onDrawioViewerLoad=()=>{}');page.add_script_tag(path=str(viewer))
    for asset in runtime['assets']:
     if asset['path'].endswith('.min.js'):page.add_script_tag(path=asset['path'])
    result=page.evaluate(JS,{'source':source,'language':language});report['browser_version']=browser.version
    if language=='mermaid':
     reference=context.new_page();reference.route('**/*',lambda route:route.abort());reference.set_content('<html></html>');reference.add_script_tag(path=runtime['independent_source_parser']['path']);reference.evaluate("mermaid.initialize({startOnLoad:false,securityLevel:'strict',maxTextSize:200000,flowchart:{htmlLabels:false}})")
     ast=reference.evaluate('''async source=>{const d=await mermaid.mermaidAPI.getDiagramFromText(source);const v=d.db.getVertices();return {type:d.type,vertices:v instanceof Map?Object.fromEntries(v):v,edges:d.db.getEdges(),groups:d.db.getSubGraphs?.()||[]};}''',source);report['independent_source_ast']=ast
   finally:browser.close()
  xml=result.pop('xml');report['native_frontend']=result;coverage=semantic_coverage(xml,support['ir'],language);report['semantic_coverage']=coverage;report['blocked_requests']=blocked
  if language=='mermaid':
   ast_nodes={k:cleantext(v.get('text') or k) for k,v in ast['vertices'].items()};ir_nodes={n['id']:n['text'] for n in support['ir']['nodes']};ast_edges=collections.Counter((e['start'],e['end'],cleantext(e.get('text',''))) for e in ast['edges']);ir_edges=collections.Counter((e['source'],e['target'],e['text']) for e in support['ir']['edges'])
   if ast_nodes!=ir_nodes or ast_edges!=ir_edges or ast['groups']:coverage['ok']=False;coverage['errors'].append({'code':'independent_source_parser_ir_mismatch','ast_nodes':ast_nodes,'ir_nodes':ir_nodes,'ast_edge_count':sum(ast_edges.values()),'ir_edge_count':sum(ir_edges.values())})
  if blocked or result['warnings'] or result['diagnostics'] or result['logs']:coverage['ok']=False;coverage['errors'].append({'code':'native_diagnostics_or_blocked_resource','warnings':result['warnings'],'diagnostics':result['diagnostics'],'logs':result['logs'],'blocked':blocked})
  path=output_dir/'candidate.drawio';path.write_text(xml);report.update(candidate_file=str(path),candidate_sha256=sha(path.read_bytes()),status='candidate_ready' if coverage['ok'] else 'semantic_coverage_failed')
  (output_dir/'scene_ir.json').write_text(json.dumps(support['ir'],ensure_ascii=False,indent=2)+'\n')
 except Exception as e:report.update(status='frontend_error',error=type(e).__name__+': '+str(e)[:3000])
 finally:
  report['seconds']=time.monotonic()-started;(output_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--language',choices=['mermaid','plantuml'],required=True);p.add_argument('--output-dir',required=True);a=p.parse_args();r=convert(a.source,a.language,a.output_dir);print(json.dumps({'status':r['status'],'report':str(Path(a.output_dir)/'report.json'),'candidate':r['candidate_file'],'qualified':False},ensure_ascii=False))
if __name__=='__main__':main()
