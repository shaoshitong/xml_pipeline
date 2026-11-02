"""Execution-time PGF node instances; no source/global-name rewriting or publish.

v2 hook events identify the actual installed node table at each anchor read.
Aliases retain the source instance they copied even after that spelling is
redefined. The original byte source, all node events, and all paint remain.
The v1 graph validator is reused on an explicitly audited per-event identity
projection; numeric/anonymous painted terminals remain unsupported.
"""
import builtins,collections,copy,hashlib,json,math,re
from pathlib import Path
import tikz_execution_graph as v1

VERSION='actual_pgf_versioned_node_instances_v2'
ARITY={**v1.ARITY,'extension':2,'instance':7,'nodelink':4,'anchorread':9,'alias':5,'unbind':4}
sha=lambda b:hashlib.sha256(b).hexdigest()


def parse_events(data,extra_arity=None):
 arity={**ARITY,**(extra_arity or {})}
 events=[];pos=0
 while pos<len(data):
  while pos<len(data) and data[pos].isspace():pos+=1
  if pos==len(data):break
  match=re.match(r'\\IIC([A-Za-z]+)',data[pos:])
  if not match or match[1] not in arity:raise ValueError('Unknown/corrupt v2 event near '+repr(data[pos:pos+80]))
  kind=match[1];pos+=match.end();fields=[]
  for _ in range(arity[kind]):
   while pos<len(data) and data[pos].isspace():pos+=1
   if pos==len(data) or data[pos]!='{':raise ValueError('Missing v2 field '+kind)
   start=pos+1;pos+=1;depth=1
   while pos<len(data) and depth:
    if data[pos]=='\\' and pos+1<len(data) and not data[pos+1].isalpha():pos+=2;continue
    if data[pos]=='{':depth+=1
    if data[pos]=='}':depth-=1
    pos+=1
   if depth:raise ValueError('Truncated v2 event '+kind)
   fields.append(data[start:pos-1])
  events.append({'kind':kind,'fields':fields})
 if not events or events[0]['kind']!='header' or events[-1]['kind']!='complete' or sum(e['kind']=='header' for e in events)!=1 or sum(e['kind']=='complete' for e in events)!=1:raise ValueError('Incomplete or multiple execution sessions')
 if [e['fields'] for e in events if e['kind']=='extension']!=[['2','actual-node-table-instance-and-anchor-read']]:raise ValueError('Required execution-time identity hook extension missing')
 return events


def _pt(value):
 if not re.fullmatch(r'[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)pt',value):raise ValueError('Nonliteral actual PGF point')
 return float(value[:-2])


def _same_point(a,b,tolerance=.001):return math.dist(list(map(_pt,a)),list(map(_pt,b)))<=tolerance


def graph_from_events(events):
 failures=[];instances={};links={};active={};latest_reads={};pending_dependencies=collections.defaultdict(list);ownership=[];generations=collections.Counter();projected=[];event_map={};alias_events=[];unknown_reads=[]
 # Links join a concrete callback identity to the corresponding original node
 # event, even if nested multipart nodes cause serial and birth order to differ.
 for sequence,event in enumerate(events):
  if event['kind']=='nodelink':
   picture,path,serial,instance=event['fields'];key=(picture,serial)
   if key in links:failures.append({'reason':'duplicate_node_instance_link','serial':serial})
   links[key]=instance
 for sequence,event in enumerate(events):
  kind=event['kind'];f=event['fields'];cloned=copy.deepcopy(event)
  if kind=='instance':
   picture,path,id,name,shape,x,y=f
   if id in instances:failures.append({'reason':'duplicate_instance_birth','instance':id});continue
   generations[(picture,name)]+=1;instances[id]={'instance_id':id,'picture':picture,'path':path,'source_name':name,'shape':shape,'center_pt':[x,y],'definition_sequence':sequence,'name_generation':generations[(picture,name)]}
   if name:active[name]=id
  elif kind=='alias':
   picture,path,new,old,id=f
   if id and (active.get(old)!=id or id not in instances):failures.append({'reason':'alias_does_not_copy_current_source_instance','sequence':sequence,'alias':new,'original':old,'instance':id})
   if id:active[new]=id
   else:active.pop(new,None)
   alias_events.append({'sequence':sequence,'alias':new,'original':old,'instance_id':id,'picture':picture,'path':path})
  elif kind=='unbind':active.pop(f[2],None)
  elif kind=='anchorread':
   picture,path,name,anchor,id,lx,ly,x,y=f;read={'picture':picture,'path':path,'name':name,'anchor':anchor,'instance_id':id,'point_pt':[x,y],'returned_local_point_pt':[lx,ly],'sequence':sequence}
   if id and (id not in instances or active.get(name)!=id):failures.append({'reason':'anchor_read_identity_not_current_installed_table','read':read})
   if id and anchor=='center' and id in instances and not _same_point([x,y],instances[id]['center_pt']):failures.append({'reason':'anchor_read_center_disagrees_with_instance','read':read,'instance_center':instances[id]['center_pt']})
   if not id:unknown_reads.append(read)
   latest_reads[(picture,path,name,anchor)]=read
   pending=pending_dependencies[(picture,path,name,anchor)]
   if pending:
    dependency=pending.pop();dependency['fields'][2]=id or name
  elif kind=='node':
   picture,path,serial,role,name,shape,text,x,y,segment=f;id=links.get((picture,serial))
   if not id or id not in instances:failures.append({'reason':'original_node_event_has_no_executed_instance','serial':serial,'name':name})
   else:
    definition=instances[id]
    if definition['source_name']!=name or definition['shape']!=shape or not _same_point([x,y],definition['center_pt']):failures.append({'reason':'original_node_event_differs_from_instance_birth','serial':serial,'instance_id':id})
    definition.update(serial=serial,role=role,expanded_label_tex=text,node_event_sequence=sequence)
    if name:cloned['fields'][4]=id
  elif kind=='ref':
   picture,path,callback,name,anchor,x,y,auto=f;read=latest_reads.get((picture,path,name,anchor));id=read['instance_id'] if read else None
   if not id or id not in instances or not _same_point([x,y],read['point_pt']):failures.append({'reason':'semantic_reference_has_no_matching_actual_instance_read','sequence':sequence,'name':name,'anchor':anchor,'read':read})
   else:
    cloned['fields'][3]=id;ownership.append({'reference_sequence':sequence,'anchor_read_sequence':read['sequence'],'picture':picture,'path':path,'source_name':name,'anchor':anchor,'point_pt':[x,y],'instance_id':id,'definition_sequence':instances[id]['definition_sequence'],'name_generation':instances[id]['name_generation']})
  elif kind=='anchor':
   picture,path,name,anchor=f;pending_dependencies[(picture,path,name,anchor)].append(cloned)
  if kind in v1.ARITY:event_map[sequence]=len(projected);projected.append(cloned)
 node_count=sum(e['kind']=='node' for e in events)
 if len(instances)!=node_count or len(links)!=node_count or any('serial' not in n for n in instances.values()):failures.append({'reason':'instance_node_event_coverage_incomplete','instances':len(instances),'links':len(links),'node_events':node_count})
 # TikZ `edge` and pin machinery leaves empty cursor-only parent paths. No
 # softpath means no painted connector. Account for them explicitly rather than
 # pretending a move operation itself is a visible semantic edge.
 paths=collections.defaultdict(list)
 for event in projected:
  if event['kind'] not in ('header','complete','picture'):paths[tuple(event['fields'][:2])].append(event)
 cursor=[];remove=set()
 for key,items in paths.items():
  finishes=[e for e in items if e['kind']=='finish'];ops=[e for e in items if e['kind']=='operation']
  if len(finishes)==1 and not finishes[0]['fields'][-1].strip() and ops and all(e['fields'][2]=='move' for e in ops):
   cursor.append({'picture':key[0],'path':key[1],'operations':len(ops),'named_reference_reads':sum(e['kind']=='ref' for e in items),'source_has_no_painted_softpath':True});remove.update(builtins.id(e) for e in items if e['kind'] in ('operation','ref'))
 projected=[e for e in projected if builtins.id(e) not in remove];graph=v1.graph_from_events(projected)
 for node in graph['nodes']:
  if node['name'] in instances:node.update(source_name=instances[node['name']]['source_name'],instance_id=node['name'],name_generation=instances[node['name']]['name_generation'],definition_sequence=instances[node['name']]['definition_sequence'])
 duplicates=[{'picture':picture,'source_name':name,'instances':[n['instance_id'] for n in instances.values() if n['picture']==picture and n['source_name']==name]} for (picture,name),count in generations.items() if name and count>1]
 graph.update(version=VERSION,ok=graph['ok'] and not failures,identity_ok=not failures,node_instances=list(instances.values()),reference_instance_ownership=ownership,alias_instance_events=alias_events,duplicate_name_generations=duplicates,nonpainted_cursor_paths=cursor,untracked_informational_anchor_reads=unknown_reads,instance_identity_failures=failures,source_bytes_or_names_modified=False,limitations=graph['limitations']+['Numeric/anonymous painted terminals remain unsupported. Empty cursor-only paths are explicitly accounted without inventing a visible edge.'])
 graph['failures']=failures+graph['failures'];return graph


def compile_execution_graph(data,directory,extra_hooks=(),extra_arity=None):
 from tectonic_compile import compile_case,RUNTIME
 from native_worker import W,now
 import sys
 sys.path.append(str(W/'runtime/python_packages'));import pymupdf
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);hooks={name:Path(__file__).with_name(name).read_bytes() for name in ('tikz_execution_graph_hooks.tex','tikz_execution_graph_hooks_v2.tex',*extra_hooks)};wrappers={'baseline':b'\\input{original_source.tex}\n','instrumented':('\\AtBeginDocument{'+''.join('\\input{'+name+'}' for name in hooks)+'}\n\\input{original_source.tex}\n').encode()};out={'version':VERSION,'at':now(),'source_sha256':sha(data),'engine_file':str(RUNTIME/'tectonic'),'engine_sha256':sha((RUNTIME/'tectonic').read_bytes()),'hooks':{n:sha(b) for n,b in hooks.items()},'runs':{},'source_bytes_unchanged':True,'source_names_modified':False,'published':False,'instrumentation_ok':False}
 out['pgf_core_files']={}
 for name in ('tikz.code.tex','pgfmoduleshapes.code.tex','pgfcorearrows.code.tex'):
  path=next((RUNTIME/'cache/bundles/data').glob('*/'+name));out['pgf_core_files'][name]={'file':str(path),'sha256':sha(path.read_bytes())}
 try:
  for mode,wrapper in wrappers.items():
   work=directory/mode;work.mkdir();(work/'original_source.tex').write_bytes(data);(work/'source.tex').write_bytes(wrapper)
   if mode=='instrumented':
    for name,blob in hooks.items():(work/name).write_bytes(blob)
   run,attempts=compile_case(work,max_rounds=2);(work/'stdout.log').write_text(run.stdout);(work/'stderr.log').write_text(run.stderr);out['runs'][mode]={'returncode':run.returncode,'wrapper_sha256':sha(wrapper),'compile_attempts':attempts}
   if run.returncode:raise ValueError(mode+' compile failed: '+run.stderr[-2400:])
   if (work/'original_source.tex').read_bytes()!=data:raise ValueError('Original source bytes changed')
   out['runs'][mode]['pdf_sha256']=sha((work/'source.pdf').read_bytes())
  pages=[]
  with pymupdf.open(directory/'baseline/source.pdf') as a,pymupdf.open(directory/'instrumented/source.pdf') as b:
   if len(a)!=len(b):raise ValueError('v2 instrumentation changed PDF page count')
   for index,(x,y) in enumerate(zip(a,b)):
    px=x.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);py=y.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);same=(x.rect,px.width,px.height,px.samples)==(y.rect,py.width,py.height,py.samples);pages.append({'page':index,'pixel_identical':same,'baseline_pixel_sha256':sha(px.samples),'instrumented_pixel_sha256':sha(py.samples),'size':[px.width,px.height]})
  out['instrumentation_pdf_pixel_equivalence']=pages
  if not pages or not all(p['pixel_identical'] for p in pages):raise ValueError('v2 instrumentation changes actual PDF pixels')
  trace=(directory/'instrumented/source.iic').read_bytes();out['execution_trace_sha256']=sha(trace);events=parse_events(trace.decode(),extra_arity);out['graph']=graph_from_events(events);out['instrumentation_ok']=True;out['ok']=out['graph']['ok']
 except Exception as exc:out['ok']=False;out['error']=repr(exc)
 (directory/'execution_graph.json').write_text(json.dumps(out,indent=2)+'\n');return out
