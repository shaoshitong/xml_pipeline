"""Prototype PGF execution graph sidecar, isolated from production jobs/payloads.

Compile original bytes twice under the existing offline sandbox, once with
sidecar hooks. Accept instrumentation only when every rendered PDF page is pixel
identical. Expanded names/references come from PGF callbacks, never regex macro
expansion or geometric guessing. No job/accepted-state changes are performed.
"""
from __future__ import annotations
import collections
import hashlib
import json
import re
from pathlib import Path

VERSION = "actual_pgf_execution_named_graph_prototype_v1"
sha = lambda data: hashlib.sha256(data).hexdigest()
ARITY = {"header":2,"picture":2,"path":3,"node":10,"ref":8,"operation":4,"finish":6,"complete":3,"unsupportedpaint":3,"anchor":4}
ROLES = {r"\tikz@@moveto":"move",r"\tikz@@lineto":"line",r"\tikz@@hv@lineto":"horizontal_vertical",r"\tikz@@vh@lineto":"vertical_horizontal",r"\tikz@curveC":"cubic"}


def parse_events(data: str):
    """Read the braced event format without evaluating source TeX."""
    events=[];pos=0
    while pos<len(data):
        while pos<len(data) and data[pos].isspace():pos+=1
        if pos==len(data):break
        match=re.match(r"\\IIC([A-Za-z]+)",data[pos:])
        if not match or match[1] not in ARITY:raise ValueError("Unknown or corrupt execution event near "+repr(data[pos:pos+80]))
        kind=match[1];pos+=match.end();fields=[]
        for _ in range(ARITY[kind]):
            while pos<len(data) and data[pos].isspace():pos+=1
            if pos==len(data) or data[pos]!="{":raise ValueError("Missing execution field: "+kind)
            start=pos+1;pos+=1;depth=1
            while pos<len(data) and depth:
                if data[pos]=='\\' and pos+1<len(data) and not data[pos+1].isalpha():pos+=2;continue
                if data[pos]=='{':depth+=1
                if data[pos]=='}':depth-=1
                pos+=1
            if depth:raise ValueError("Truncated execution field: "+kind)
            fields.append(data[start:pos-1])
        events.append({"kind":kind,"fields":fields})
    if not events or events[0]['kind']!='header' or events[-1]['kind']!='complete':raise ValueError("Incomplete execution trace")
    if sum(e['kind']=='header' for e in events)!=1 or sum(e['kind']=='complete' for e in events)!=1:raise ValueError("Multiple/truncated execution sessions")
    return events


def graph_from_events(events):
    pictures={};paths={};nodes={};decorative=[];failures=[];references=[]
    for sequence,event in enumerate(events):
        kind=event['kind'];f=event['fields']
        if kind not in ('header','complete','picture') and (f[0] not in pictures or pictures[f[0]]['end'] is not None):
            failures.append({'reason':'event_outside_open_picture','event_kind':kind,'picture':f[0]})
        if kind=='picture':
            picture,status=f
            if status=='begin':
                if picture in pictures:failures.append({'reason':'duplicate_picture_begin','picture':picture})
                pictures[picture]={'begin':sequence,'end':None}
            elif status=='end' and picture in pictures:pictures[picture]['end']=sequence
            else:failures.append({'reason':'unmatched_picture_event','event':event})
        elif kind=='path':
            picture,path,status=f;key=(picture,path)
            if status!='begin' or key in paths:failures.append({'reason':'duplicate_or_unknown_path_event','event':event})
            paths[key]={'picture':picture,'id':path,'references':[],'anchor_dependencies':[],'operations':[],'labels':[],'finish':[]}
        elif kind=='node':
            picture,path,serial,role,name,shape,text,x,y,segment=f
            node={'picture':picture,'path':path,'serial':serial,'role':role,'name':name,'shape':shape,'expanded_label_tex':text,'center_pt':[x,y],'operation':int(segment)}
            if not x or not y:failures.append({'reason':'executed_node_position_not_recorded','serial':serial,'name':name})
            if role=='label':
                if (picture,path) not in paths:failures.append({'reason':'label_without_path','node':node})
                else:paths[(picture,path)]['labels'].append(node)
            elif name:
                key=(picture,name)
                if key in nodes:failures.append({'reason':'duplicate_executed_node_name','picture':picture,'name':name})
                nodes[key]=node
            else:decorative.append({**node,'execution_id':'unnamed_'+picture+'_'+serial})
        elif kind=='ref':
            picture,path,callback,name,anchor,x,y,auto_border=f
            ref={'callback':callback,'name':name,'anchor':anchor,'auto_shape_border':auto_border=='1','point_pt':[x,y],'sequence':sequence}
            references.append({'picture':picture,'path':path,**ref})
            if (picture,path) in paths:paths[(picture,path)]['references'].append(ref)
            else:failures.append({'reason':'reference_without_path','reference':ref})
        elif kind=='operation':
            picture,path,operation,number=f
            if (picture,path) not in paths:failures.append({'reason':'operation_without_path','event':event})
            else:paths[(picture,path)]['operations'].append({'kind':operation,'number':int(number),'sequence':sequence})
        elif kind=='anchor':
            picture,path,name,anchor=f
            if (picture,path) not in paths:failures.append({'reason':'anchor_dependency_without_path','event':event})
            else:paths[(picture,path)]['anchor_dependencies'].append({'name':name,'anchor':anchor})
        elif kind=='finish':
            picture,path,arrows,start,end,softpath=f
            if (picture,path) not in paths:failures.append({'reason':'finish_without_path','event':event})
            else:paths[(picture,path)]['finish'].append({'arrows_tex':arrows,'start_arrow':start=='1','end_arrow':end=='1','softpath_tex':softpath})
        elif kind=='unsupportedpaint':
            failures.append({'reason':'direct_pgf_paint_outside_recorded_tikz_pipeline','picture':f[0],'path':f[1],'paint':f[2]})
    edges=[];unresolved_labels=[]
    for key,path in paths.items():
        if len(path['finish'])!=1:
            failures.append({'reason':'path_finish_coverage_incomplete','picture':key[0],'path':key[1],'finish_count':len(path['finish'])});continue
        finish=path['finish'][0];ops=path['operations'];refs=[r for r in path['references'] if r['callback'] in ROLES]
        if not finish['softpath_tex'].strip() and not ops:
            # A standalone at(...) annotation may carry a nonempty TikZ timer
            # inherited from its coordinate calculation. It has no source edge
            # operation, so preserve it separately rather than invent ownership.
            decorative.extend({**n,'role':'annotation','execution_id':'unnamed_'+n['picture']+'_'+n['serial'],'executed_anchor_dependencies':path['anchor_dependencies']} for n in path['labels'])
            continue  # standalone node-only path
        if not ops:
            failures.append({'reason':'painted_path_without_named_semantic_operations','picture':key[0],'path':key[1]});continue
        soft_operators=collections.Counter(re.findall(r'\\pgfsyssoftpath@([A-Za-z]+)token',finish['softpath_tex']))
        expected_operators=collections.Counter()
        for op in ops:
            expected_operators.update({'moveto':1} if op['kind']=='move' else {'lineto':1} if op['kind']=='line' else {'lineto':2} if op['kind'] in ('horizontal_vertical','vertical_horizontal') else {'curvetosupporta':1,'curvetosupportb':1,'curveto':1} if op['kind']=='cubic' else {'unsupported_operation':1})
        if len(ops)!=len(refs) or any(op['kind']!=ROLES[ref['callback']] for op,ref in zip(ops,refs)):
            failures.append({'reason':'numeric_or_unbound_path_terminal','picture':key[0],'path':key[1],'operations':len(ops),'named_references':len(refs)});continue
        # TikZ restarts the painted subpath at an intermediate bare node's
        # outgoing border. This is a real PGF move, not an extra semantic edge.
        expected_operators['moveto']+=sum(refs[i]['auto_shape_border'] and ops[i]['kind']!='move' and ops[i+1]['kind']!='move' for i in range(len(ops)-1))
        if soft_operators!=expected_operators:
            failures.append({'reason':'uncovered_executed_softpath_operations','picture':key[0],'path':key[1],'actual':dict(soft_operators),'expected':dict(expected_operators)});continue
        current=None;segments=[]
        for op,ref in zip(ops,refs):
            if (key[0],ref['name']) not in nodes:
                failures.append({'reason':'terminal_is_not_an_extracted_source_node','picture':key[0],'path':key[1],'node':ref['name']})
            if op['kind']=='move':current=ref;continue
            if current is None:
                failures.append({'reason':'path_segment_without_named_move','picture':key[0],'path':key[1]});continue
            labels=[n for n in path['labels'] if n['operation']==op['number']]
            segments.append({'picture':key[0],'path':key[1],'source':current['name'],'source_anchor':current['anchor'],'source_auto_border':current['auto_shape_border'],'target':ref['name'],'target_anchor':ref['anchor'],'target_auto_border':ref['auto_shape_border'],'operation':op['kind'],'expanded_labels_tex':[n['expanded_label_tex'] for n in labels],'executed_label_nodes':labels,'operation_number':op['number']})
            current=ref
        if not segments and finish['softpath_tex'].strip():failures.append({'reason':'painted_path_without_extracted_segments','picture':key[0],'path':key[1]})
        for i,edge in enumerate(segments):
            edge.update(start_arrow=bool(i==0 and finish['start_arrow']),end_arrow=bool(i==len(segments)-1 and finish['end_arrow']))
            edges.append(edge)
        unassigned=[n for n in path['labels'] if n['operation'] not in {e['operation_number'] for e in segments}]
        if unassigned:
            unresolved_labels.extend(unassigned)
            failures.append({'reason':'edge_label_operation_ambiguous','picture':key[0],'path':key[1],'labels':unassigned})
    for picture,status in pictures.items():
        if status['end'] is None:failures.append({'reason':'unfinished_picture','picture':picture})
    if not pictures:failures.append({'reason':'no_executed_picture_boundaries'})
    complete=events[-1]['fields']
    if int(complete[0])!=len(pictures) or int(complete[1])!=len(paths) or int(complete[2])!=sum(e['kind']=='node' for e in events):failures.append({'reason':'execution_counter_mismatch'})
    accounted=[n['serial'] for n in list(nodes.values())+decorative]+[n['serial'] for e in edges for n in e['executed_label_nodes']]
    expected=[e['fields'][2] for e in events if e['kind']=='node']
    if collections.Counter(accounted)!=collections.Counter(expected):failures.append({'reason':'node_or_label_event_coverage_incomplete','missing':list((collections.Counter(expected)-collections.Counter(accounted)).elements()),'extra':list((collections.Counter(accounted)-collections.Counter(expected)).elements())})
    for n in decorative:
        n.setdefault('executed_anchor_dependencies',paths.get((n['picture'],n['path']),{}).get('anchor_dependencies',[]))
    return {'version':VERSION,'ok':not failures,'nodes':list(nodes.values()),'decorative_nodes':decorative,'edges':edges,'unresolved_label_nodes':unresolved_labels,'executed_nodes_accounted':len(accounted),'pictures':len(pictures),'paths':len(paths),'failures':failures,'executed_reference_count':len(references),'reference_events':references,'limitations':['Prototype covers executed named terminal operations; unbound numeric/decorative paths remain unsupported, never guessed.','Unnamed node text and actual engine positions are preserved as separate annotations, never guessed to be named semantic terminals.','Expanded TeX label tokens are recorded; matching math/control-sequence labels to rendered PDF glyphs remains a separate task.','This sidecar does not publish drawio conversions or imply native editability.']}


def compile_execution_graph(data: bytes, directory: Path):
    from tectonic_compile import compile_case,RUNTIME
    import sys
    from native_worker import W,now
    sys.path.append(str(W/'runtime/python_packages'))
    import pymupdf
    directory.mkdir(parents=True,exist_ok=False)
    hook=Path(__file__).with_name('tikz_execution_graph_hooks.tex').read_bytes()
    wrappers={'baseline':b'\\input{original_source.tex}\n','instrumented':b'\\AtBeginDocument{\\input{tikz_execution_graph_hooks.tex}}\n\\input{original_source.tex}\n'}
    result={'version':VERSION,'at':now(),'source_sha256':sha(data),'engine_file':str(RUNTIME/'tectonic'),'engine_sha256':sha((RUNTIME/'tectonic').read_bytes()),'hook_sha256':sha(hook),'runs':{},'source_bytes_unchanged':True,'published':False}
    pgf_root=RUNTIME/'cache/bundles/data'
    result['pgf_core_files']={}
    for name in ('tikz.code.tex','pgfmoduleshapes.code.tex','pgfcorearrows.code.tex'):
        path=next(pgf_root.glob('*/'+name));result['pgf_core_files'][name]={'file':str(path),'sha256':sha(path.read_bytes())}
    try:
        for mode,wrapper in wrappers.items():
            work=directory/mode;work.mkdir();(work/'original_source.tex').write_bytes(data);(work/'source.tex').write_bytes(wrapper)
            if mode=='instrumented':(work/'tikz_execution_graph_hooks.tex').write_bytes(hook)
            run,attempts=compile_case(work,max_rounds=2)
            (work/'stdout.log').write_text(run.stdout);(work/'stderr.log').write_text(run.stderr)
            result['runs'][mode]={'returncode':run.returncode,'wrapper_sha256':sha(wrapper),'compile_attempts':attempts}
            if (work/'original_source.tex').read_bytes()!=data:raise ValueError('Source input bytes changed')
            if run.returncode:raise ValueError(mode+' compilation failed: '+run.stderr[-2200:])
            pdf=work/'source.pdf';result['runs'][mode]['pdf_sha256']=sha(pdf.read_bytes())
        with pymupdf.open(directory/'baseline/source.pdf') as original,pymupdf.open(directory/'instrumented/source.pdf') as hooked:
            if len(original)!=len(hooked):raise ValueError('Instrumentation changed page count')
            pages=[]
            for index,(a,b) in enumerate(zip(original,hooked)):
                pa=a.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False);pb=b.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
                same=(pa.width,pa.height,pa.samples)==(pb.width,pb.height,pb.samples)
                pages.append({'page':index,'pixel_identical':same,'baseline_pixel_sha256':sha(pa.samples),'instrumented_pixel_sha256':sha(pb.samples),'size':[pa.width,pa.height]})
            result['instrumentation_pdf_pixel_equivalence']=pages
            if not all(p['pixel_identical'] for p in pages):raise ValueError('Instrumentation changed actual PDF pixels')
        trace=(directory/'instrumented/source.iic').read_bytes();result['execution_trace_sha256']=sha(trace)
        graph=graph_from_events(parse_events(trace.decode()))
        result['graph']=graph;result['ok']=graph['ok']
    except Exception as exc:
        result['ok']=False;result['error']=repr(exc)
    (directory/'execution_graph.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
