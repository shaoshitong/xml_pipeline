#!/usr/bin/env python3
"""Stream strict img/code curation on the HKUST destination. Never executes dataset code.
Raw parquet fields are preserved; manifests record the pairing and rejection reasons.
An accepted row is structurally complete, not a claim that its code was executed.
"""
import argparse, ast, base64, collections, functools, hashlib, html, io, json, os, re, shutil, sqlite3, tarfile, time, urllib.parse, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path


def within(path,root):
    try: path.relative_to(root);return True
    except ValueError:return False


@functools.lru_cache(maxsize=1)
def asymptote_support():
    import importlib.util
    spec=importlib.util.spec_from_file_location('img2code_asymptote',Path(__file__).with_name('asymptote_support.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def text_content(value):
    if isinstance(value, str): return value
    if isinstance(value, bytes):
        try: return value.decode('utf-8')
        except UnicodeDecodeError: return ''
    if isinstance(value, list): return '\n'.join(text_content(x) for x in value)
    if isinstance(value, dict): return text_content(value.get('text',value.get('content','')))
    return ''


def code_value(row):
    for key in ('restored_xml','target_xml','assistant_content','completion','code','svg','Svg','output','response','answer','target_code','ground_truth','tikz_code','html','html_code','svg_code','annotation'):
        value=text_content(row.get(key))
        if value.strip(): return value, key
    for key in ('messages','conversations','conversation'):
        messages=row.get(key) or []
        if isinstance(messages,str):
            try: messages=json.loads(messages)
            except Exception: continue
        if not isinstance(messages,list): continue
        for message in reversed(messages):
            if not isinstance(message,dict): continue
            if str(message.get('role',message.get('from',''))).lower() in ('assistant','gpt'):
                value=text_content(message.get('content',message.get('value','')))
                if value.strip(): return value,key
    return '', ''


def unwrap_code(value):
    value=re.sub(r'<think>.*?</think>','',value,flags=re.S).strip()
    blocks=re.findall(r'```[^\n]*\n(.*?)```',value,flags=re.S)
    return (blocks[-1] if blocks else value).strip()


def image_bytes(value, raw_root):
    if value is None: return None
    if isinstance(value,(bytes,bytearray,memoryview)): return bytes(value)
    if isinstance(value,list):
        if value and all(isinstance(x,int) and 0<=x<=255 for x in value): return bytes(value)
        # A single image is unambiguous; multi-image edit tasks are excluded.
        if len(value)!=1: return None
        return image_bytes(value[0],raw_root)
    if isinstance(value,dict):
        b=value.get('bytes')
        if b is not None:
            data=image_bytes(b,raw_root)
            if data: return data
        return image_bytes(value.get('path',value.get('image',value.get('url'))),raw_root)
    if isinstance(value,str):
        v=value.strip()
        if v.startswith('data:image/'):
            try: return base64.b64decode(v.split(',',1)[1],validate=True)
            except Exception: return None
        if len(v)>100:
            try:
                b=base64.b64decode(v,validate=True)
                if b.startswith((b'\x89PNG',b'\xff\xd8',b'RIFF',b'GIF8',b'BM')): return b
            except Exception: pass
        if '://' in v or v.startswith('/'): return None
        p=(raw_root/v).resolve()
        if within(p,raw_root.resolve()) and p.is_file(): return p.read_bytes()
    return None


def get_image(row,raw_root):
    for key in ('image','images','png','image_bytes','img','target_image','reference_image','original_image','png_image'):
        data=image_bytes(row.get(key),raw_root)
        if data: return data,key
    return None,''


def image_info(data):
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as im:
            width,height=im.size;fmt=im.format; im.verify()
        if width<=0 or height<=0: return None
        return {'width':width,'height':height,'format':fmt}
    except Exception: return None


@functools.lru_cache(maxsize=8)
def python_tree(code):
    return ast.parse(code)


def python_call_name(node,aliases=None):
    if isinstance(node,ast.Name):return (aliases or {}).get(node.id,node.id)
    if isinstance(node,ast.Attribute):return python_call_name(node.value,aliases)+'.'+node.attr
    if isinstance(node,ast.Call):return python_call_name(node.func,aliases)+'()'
    return ''


@functools.lru_cache(maxsize=8)
def python_visual_facts(code):
    try:tree=python_tree(code)
    except SyntaxError:return {'chart':False,'substantial':False}
    calls=[];aliases={}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for item in node.names:aliases[item.asname or item.name.split('.')[0]]=item.name
        elif isinstance(node,ast.ImportFrom):
            for item in node.names:aliases[item.asname or item.name]=(node.module or '')+'.'+item.name
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):calls.append(python_call_name(node.func,aliases).rsplit('.',1)[-1].lower())
    primitives={'plot','plot3d','scatter','scatter3d','bar','bar3d','barh','broken_barh','hist','hist2d','hexbin','imshow','matshow','contour','contourf','pcolormesh','pcolor','boxplot','violinplot','pie','errorbar','fill_between','stackplot','stem','step','quiver','streamplot','eventplot','plot_surface','plot_wireframe','plot_trisurf','tricontour','tricontourf','tripcolor','loglog','semilogx','semilogy','heatmap','kdeplot','jointplot','pairplot','regplot','displot','clustermap','line','area','mark_line','mark_point','mark_bar','mark_area','mark_rect','surface','box','violin','add_trace','add_traces','draw_networkx','plot_ly'}
    actual=set(calls)&primitives;strong=actual-{'imshow','matshow'}
    graph=bool(set(calls)&{'edge','add_edge','edges','add_edges_from'}) and bool(set(calls)&{'node','add_node','add_nodes_from','nodes'})
    return {'chart':bool(actual),'substantial':bool(strong or graph),'actual_plot_calls':sorted(actual),'graph':graph}


def tikz_visual_facts(code):
    text=re.sub(r'(?<!\\)%[^\n]*','',code)
    plots=bool(re.search(r'\\addplot(?:3)?\b|\\draw\b[^;]*\bplot\s*(?:\[|\(|coordinates)',text,re.S))
    nodes=len(re.findall(r'\\(?:node|coordinate)\b',text));draws=len(re.findall(r'\\(?:draw|path)\b',text))
    edges=len(re.findall(r'\bedge\b|(?:--|to\s*\[)',text))
    graph=(nodes>=3 or '\\matrix' in text) and draws>=2 and edges>=2
    return {'chart':plots,'substantial':bool(plots or graph),'nodes':nodes,'draws':draws,'edges':edges}


@functools.lru_cache(maxsize=8)
def svg_visual_facts(code):
    try:tree=ET.fromstring(code)
    except ET.ParseError:return {'chart':False,'substantial':False}
    nodes=list(tree.iter());tag=lambda n:n.tag.rsplit('}',1)[-1]
    texts=[' '.join(n.itertext()).strip() for n in nodes if tag(n) in ('text','foreignObject')]
    counts=collections.Counter(tag(n) for n in nodes);ids=' '.join(n.get('id','')+' '+n.get('class','') for n in nodes).lower()
    arcs=sum(bool(re.search(r'[Aa]\s*[-+]?\d',n.get('d',''))) and bool(re.search(r'[Zz]\s*$',n.get('d',''))) for n in nodes if tag(n)=='path')
    percentages=sum(bool(re.search(r'\d\s*%',t)) for t in texts)
    horizontal=vertical=0
    for n in nodes:
        if tag(n)!='line':continue
        try:x1,x2,y1,y2=(float(n.get(k,0)) for k in ('x1','x2','y1','y2'))
        except ValueError:continue
        horizontal+=abs(y1-y2)<1e-6 and abs(x1-x2)>1;vertical+=abs(x1-x2)<1e-6 and abs(y1-y2)>1
    ticks=sum(bool(re.fullmatch(r'[-+]?\d[\d.,]*(?:%|s)?',t)) for t in texts)
    rotated=any('rotate' in n.get('transform','') for n in nodes if tag(n)=='text')
    traces=counts['polyline']>=1 or counts['circle']>=3 or counts['rect']>=3 or counts['path']>=2
    exported_axes=bool(re.search(r'xtick_|ytick_|axes_[0-9]|plotly|cartesianlayer',ids)) and traces
    pie=arcs>=2 and percentages>=2
    axes=horizontal>=1 and vertical>=1 and traces and (ticks>=2 or rotated)
    connectors=sum(bool(n.get('marker-end') or n.get('marker-start')) for n in nodes)
    framework=counts['text']+counts['foreignObject']>=3 and connectors>=2
    return {'chart':bool(exported_axes or pie or axes),'substantial':bool(exported_axes or pie or axes or framework),'pie_slices':arcs,'tick_labels':ticks}


def actual_chart_evidence(code,fmt):
    if fmt=='asymptote':return asymptote_support().visual_facts(code)['chart']
    if fmt=='python':return python_visual_facts(code)['chart']
    if fmt=='tikz':return tikz_visual_facts(code)['chart']
    if fmt=='svg':return svg_visual_facts(code)['chart']
    if fmt=='mermaid':return bool(re.search(r'(?m)^\s*(xychart|pie\s)',code))
    if fmt=='vegalite':
        try:value=json.loads(code);return isinstance(value,dict) and any(k in value for k in ('mark','layer','encoding'))
        except Exception:return False
    if fmt=='html':return bool(re.search(r'Plotly\.newPlot\s*\(|echarts\.init\s*\(|new\s+Chart\s*\(',code))
    return False


def dummy_content_reason(code,fmt):
    if not re.search(r'\\(?:lipsum|blindtext)\b|lorem\s+ipsum|dummy text|placeholder function|return a blank image|tikz placeholder|your text here',code,re.I):return None
    if fmt=='python':substantial=python_visual_facts(code)['substantial']
    elif fmt=='tikz':substantial=tikz_visual_facts(code)['substantial']
    elif fmt=='svg':substantial=svg_visual_facts(code)['substantial']
    elif fmt=='drawio':
        try:
            tree=ET.fromstring(code);substantial=sum(n.get('vertex')=='1' for n in tree.iter('mxCell'))>=3 and sum(n.get('edge')=='1' for n in tree.iter('mxCell'))>=2
        except ET.ParseError:substantial=False
    else:substantial=actual_chart_evidence(code,fmt)
    return None if substantial else 'dummy_placeholder_without_substantial_visual_structure'


def infer_format(code):
    stripped=code.lstrip();head=re.sub(r'^(?:<\?xml[^>]*>\s*|<!--.*?-->\s*)+','',stripped,flags=re.S)
    # Root documents are classified by their actual outer language, never by
    # an XML/TikZ string contained inside an executable Python program.
    if re.match(r'<(?:mxfile|mxGraphModel)\b',head):return 'drawio'
    if re.match(r'<!doctype\s+html|<(?:html|body)\b',head,re.I):return 'html'
    if re.match(r'<svg\b',head):return 'svg'
    if ';' in code and asymptote_support().is_asymptote(code):return 'asymptote'
    first='\n'.join(line for line in stripped.splitlines() if line.strip() and not line.lstrip().startswith('#'))
    if re.match(r'(?:import\s|from\s|def\s|async\s+def\s|class\s|with\s|for\s|while\s|try\s*:|if\s+|[A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*\s*=)',first):return 'python'
    if re.match(r'\\(?:documentclass|begin|tikzset|pgfplotsset|usetikzlibrary|usepackage)\b',stripped):return 'tikz'
    if re.search(r'(?m)^(?:import|from|def|class)\s',code):return 'python'
    try:
        tree=python_tree(code)
        if any(isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.AnnAssign,ast.FunctionDef,ast.ClassDef,ast.For,ast.While,ast.If,ast.With,ast.Try)) or (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)) for n in tree.body):return 'python'
    except SyntaxError:pass
    if re.search(r'\\begin\{tikzpicture\}|\\documentclass|\\begin\{axis\}',code):return 'tikz'
    if re.search(r'(?m)^\s*@start(?:uml|mindmap|wbs)',code):return 'plantuml'
    if re.search(r'(?m)^\s*(graph\s|flowchart\s|sequenceDiagram|classDiagram|erDiagram|xychart|pie\s|gantt|mindmap)',code):return 'mermaid'
    if code.lstrip().startswith(('{','[')):
        try:
            obj=json.loads(code)
            if isinstance(obj,dict) and any(k in obj for k in ('$schema','mark','encoding','data','layer')):return 'vegalite'
        except Exception:pass
    return 'unknown'


def validate_code(code,fmt,allowed_svg_assets=None):
    if not code.strip(): return 'missing_code'
    dummy=dummy_content_reason(code,fmt)
    if dummy:return dummy
    if fmt in ('drawio','svg'):
        if '<!DOCTYPE' in code.upper() or '<!ENTITY' in code.upper(): return 'xml_external_entity_or_doctype'
        # Explanatory text may surround model-produced XML; retain original row but validate XML segment.
        tag='svg' if fmt=='svg' else ('mxfile' if '<mxfile' in code else 'mxGraphModel')
        start=code.find('<'+tag); end=code.rfind('</'+tag+'>')
        xml=code[start:end+len(tag)+3] if start>=0 and end>=0 else code
        try: root=ET.fromstring(xml)
        except ET.ParseError: return 'invalid_xml'
        if fmt=='svg':
            allowed_svg_assets=set(allowed_svg_assets or ())
            def available(reference):
                value=urllib.parse.unquote(reference).split('?',1)[0].split('#',1)[0]
                while value.startswith('./'):value=value[2:]
                return value in allowed_svg_assets and '://' not in value and not value.startswith('/')
            for node in root.iter():
                if node.tag.rsplit('}',1)[-1] in ('image','img','use','feImage'):
                    for k,v in node.attrib.items():
                        if k.rsplit('}',1)[-1] in ('href','src') and v and not v.startswith(('#','data:')) and not available(v): return 'external_svg_asset'
            for reference in re.findall(r'url\(\s*[\'"]?([^\s)\'";]+)',xml,re.I):
                if not reference.startswith(('#','data:')) and not available(reference):return 'external_svg_asset'
        elif root.tag not in ('mxfile','mxGraphModel'): return 'wrong_xml_root'
        else:
            for node in root.iter():
                for reference in re.findall(r'(?:^|;)image=([^;]+)',node.get('style','')):
                    reference=urllib.parse.unquote(reference)
                    if reference and not reference.startswith(('data:','img/lib/','/img/lib/')):
                        return 'external_drawio_asset'
                value=node.get('value','')
                for reference in re.findall(r'<img\b[^>]*\bsrc=[\'"]([^\'"]+)',value,re.I):
                    if not reference.startswith('data:'):return 'external_drawio_asset'
    elif fmt=='python':
        try: python_tree(code)
        except SyntaxError: return 'invalid_python_syntax'
    elif fmt=='asymptote':return asymptote_support().syntax_issue(code)
    elif fmt=='vegalite':
        try: json.loads(code)
        except Exception: return 'invalid_json'
    elif fmt=='unknown': return 'unknown_code_format'
    return None


_PY_UNKNOWN=object()
_PY_MEMORY=object()
_PY_PROVIDED=object()
_PY_GRAPHVIZ=object()


class _StaticPythonInputs:
    """Bounded symbolic constants only: never eval/exec source expressions."""
    def __init__(self,tree,row,graphviz_candidate=True):
        self.graphviz_candidate=graphviz_candidate
        self.tree=tree;self.row=row;self.aliases={};self.constructor_imports=collections.defaultdict(set);self.defined_names=set();self.has_graphviz_import=False;self.unhandled_bindings=set();self.class_import_nodes=set();self.graphviz_context_calls=set();self.graphviz_context_names=set();self.bindings=collections.defaultdict(list);self.scopes={};self.params={};self.user_functions=set();self.outputs=[]
        def walk(node,scope=()):
            self.scopes[id(node)]=scope
            if graphviz_candidate:
                if isinstance(node,ast.ClassDef):self.class_import_nodes.update(id(child) for child in ast.walk(node) if isinstance(child,(ast.Import,ast.ImportFrom)))
                unsupported=[]
                if isinstance(node,(ast.For,ast.AsyncFor,ast.comprehension)):unsupported=[node.target]
                elif isinstance(node,ast.With):
                    for item in node.items:
                        call=item.context_expr;target=item.optional_vars
                        standard=isinstance(target,ast.Name) and isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='subgraph' and not call.args and all(kw.arg in {'name','comment','graph_attr','node_attr','edge_attr','body'} for kw in call.keywords)
                        if standard:
                            # Only a real with-statement can give the context's
                            # yielded child graph a type. Receiver proof is
                            # still required whenever this binding is used.
                            self.graphviz_context_calls.add(id(call));self.graphviz_context_names.add(target.id);self.bindings[(scope,target.id)].append((call.lineno,call))
                        elif target is not None:unsupported.append(target)
                elif isinstance(node,ast.AsyncWith):unsupported=[item.optional_vars for item in node.items if item.optional_vars is not None]
                elif isinstance(node,ast.NamedExpr):unsupported=[node.target]
                elif isinstance(node,ast.AugAssign):unsupported=[node.target]
                elif isinstance(node,ast.Delete):unsupported=node.targets
                if isinstance(node,ast.ExceptHandler) and node.name:self.unhandled_bindings.add(node.name)
                if isinstance(node,(ast.Global,ast.Nonlocal)):self.unhandled_bindings.update(node.names)
                for target in unsupported:self.unhandled_bindings.update(item.id for item in ast.walk(target) if isinstance(item,ast.Name) and isinstance(item.ctx,(ast.Store,ast.Del)))
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):self.defined_names.add(node.name)
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                self.user_functions.add(node.name);scope=scope+(node.lineno,);args=node.args.posonlyargs+node.args.args;defaults=[None]*(len(args)-len(node.args.defaults))+node.args.defaults;self.params[scope]={a.arg:d for a,d in zip(args,defaults)}
            if isinstance(node,ast.Import):
                if graphviz_candidate and any(item.name=='graphviz' or item.name.startswith('graphviz.') for item in node.names):self.has_graphviz_import=True
                for item in node.names:
                    root=item.asname or item.name.split('.')[0];self.aliases[root]=item.name
                    if graphviz_candidate:self.constructor_imports[root].add((scope+(-node.lineno,) if id(node) in self.class_import_nodes else scope,item.name if item.asname else item.name.split('.')[0],node.lineno))
            elif isinstance(node,ast.ImportFrom):
                if graphviz_candidate and (node.module=='graphviz' or (node.module or '').startswith('graphviz.')):self.has_graphviz_import=True
                for item in node.names:
                    root=item.asname or item.name;canonical=(node.module or '')+'.'+item.name;self.aliases[root]=canonical
                    if graphviz_candidate:self.constructor_imports[root].add((scope+(-node.lineno,) if id(node) in self.class_import_nodes else scope,canonical,node.lineno))
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target,ast.Name):self.bindings[(scope,target.id)].append((node.lineno,node.value))
            for child in ast.iter_child_nodes(node):walk(child,scope)
        walk(tree)
        for values in self.bindings.values():values.sort(key=lambda x:x[0])
        self.calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
        for node in self.calls:
            name=self.name(node.func);last=name.rsplit('.',1)[-1]
            if last in {'savefig','imsave','save','savez','savez_compressed','savetxt','savemat','to_csv','to_excel','to_json','to_parquet','to_pickle','write_text','write_bytes'}:
                target=node.func.value if last in {'write_text','write_bytes'} and isinstance(node.func,ast.Attribute) else self.argument(node,('fname','filename','file','path','path_or_buf','fp'))
                path=self.value(target,node)
                if isinstance(path,str):self.outputs.append((path,node.lineno))
            if last=='open' and self.write_mode(node):
                path=self.value(self.input_argument(node,last),node)
                if isinstance(path,str):self.outputs.append((path,node.lineno))
    def name(self,node):return python_call_name(node,self.aliases)
    def argument(self,node,keys):
        for key in keys:
            for kw in node.keywords:
                if kw.arg==key:return kw.value
        return node.args[0] if node.args else None
    def write_mode(self,node):
        mode=next((kw.value for kw in node.keywords if kw.arg=='mode'),None)
        if mode is None and isinstance(node.func,ast.Attribute) and isinstance(self.value(node.func.value,node),str) and node.args:mode=node.args[0]
        elif mode is None and len(node.args)>1:mode=node.args[1]
        mode=self.value(mode,node) if mode is not None else 'r'
        return isinstance(mode,str) and any(x in mode for x in 'wax')
    def input_argument(self,node,last):
        if last in {'read_text','read_bytes'} and isinstance(node.func,ast.Attribute):return node.func.value
        if last=='open' and isinstance(node.func,ast.Attribute):
            receiver=self.value(node.func.value,node)
            if isinstance(receiver,str):return node.func.value
        return self.argument(node,('filepath_or_buffer','path_or_buf','io','file','filename','fname','path','uri','url','fp'))
    def graphviz_constructor(self,expr,at):
        if not self.has_graphviz_import:return False
        if not isinstance(expr,ast.Call):return False
        root=expr.func;parts=[]
        while isinstance(root,ast.Attribute):parts.insert(0,root.attr);root=root.value
        if not isinstance(root,ast.Name) or root.id in self.defined_names or root.id in self.unhandled_bindings:return False
        proofs=self.constructor_imports.get(root.id,set())
        # Alias reuse across import scopes is intentionally unsupported. In
        # particular an unused function's local import cannot prove a module
        # object's type through the legacy global aliases dictionary.
        if len(proofs)!=1:return False
        imported_scope,canonical,import_line=next(iter(proofs));scope=self.scopes.get(id(at),())
        if scope[:len(imported_scope)]!=imported_scope or import_line>=getattr(at,'lineno',0):return False
        if '.'.join([canonical]+parts) not in {'graphviz.Graph','graphviz.Digraph','graphviz.Source'}:return False
        while True:
            if root.id in self.params.get(scope,{}):return False
            if any(line<=getattr(at,'lineno',10**9) for line,_ in self.bindings.get((scope,root.id),[])):return False
            if not scope:break
            scope=scope[:-1]
        return True
    def graphviz_receiver(self,expr,at,depth=0):
        if depth>10:return False
        if isinstance(expr,ast.Call):
            if self.graphviz_constructor(expr,expr):return True
            if id(expr) in self.graphviz_context_calls and isinstance(expr.func,ast.Attribute):return self.graphviz_receiver(expr.func.value,expr,depth+1)
            return False
        if not isinstance(expr,ast.Name) or expr.id in self.unhandled_bindings:return False
        scope=self.scopes.get(id(at),());position=(getattr(at,'lineno',10**9),getattr(at,'col_offset',10**9))
        while True:
            candidates=[(line,value) for line,value in self.bindings.get((scope,expr.id),[]) if (line,getattr(value,'col_offset',0))<=position]
            if candidates:
                value=max(candidates,key=lambda item:(item[0],getattr(item[1],'col_offset',0)))[1];return self.graphviz_receiver(value,value,depth+1)
            if expr.id in self.params.get(scope,{}):return False
            if not scope:break
            scope=scope[:-1]
        return False
    def value(self,expr,at,depth=0,scope=None):
        if expr is None or depth>10:return _PY_UNKNOWN
        scope=self.scopes.get(id(at),()) if scope is None else scope
        rec=lambda x:self.value(x,at,depth+1,scope)
        if isinstance(expr,ast.Constant):return expr.value
        if isinstance(expr,ast.Name):
            if expr.id in self.graphviz_context_names and self.graphviz_receiver(expr,at):return _PY_GRAPHVIZ
            context=scope
            while True:
                candidates=[x for x in self.bindings.get((context,expr.id),[]) if x[0]<=getattr(at,'lineno',10**9)]
                if candidates:
                    value=self.value(candidates[-1][1],at,depth+1,context)
                    return (_PY_GRAPHVIZ if self.graphviz_receiver(expr,at) else _PY_UNKNOWN) if value is _PY_GRAPHVIZ else value
                if expr.id in self.params.get(context,{}):
                    default=self.params[context][expr.id]
                    if expr.id=='data' and self.row.get('data') is not None:return _PY_PROVIDED
                    return self.value(default,at,depth+1,context[:-1]) if default is not None else _PY_UNKNOWN
                if not context:break
                context=context[:-1]
            return _PY_UNKNOWN
        if isinstance(expr,ast.BinOp):
            left=rec(expr.left);right=rec(expr.right)
            if isinstance(left,str) and isinstance(right,str) and isinstance(expr.op,(ast.Add,ast.Div)):return left+right if isinstance(expr.op,ast.Add) else str(Path(left)/right)
        if isinstance(expr,ast.JoinedStr):
            values=[]
            for value in expr.values:
                part=rec(value.value) if isinstance(value,ast.FormattedValue) else rec(value)
                if not isinstance(part,(str,int,float)):return _PY_UNKNOWN
                values.append(str(part))
            return ''.join(values)
        if isinstance(expr,ast.Dict) and len(expr.keys)<=128:
            keys=[rec(x) for x in expr.keys];values=[rec(x) for x in expr.values]
            if all(isinstance(x,(str,int,float)) for x in keys):return dict(zip(keys,values))
        if isinstance(expr,(ast.List,ast.Tuple)) and len(expr.elts)<=128:return [rec(x) for x in expr.elts]
        if isinstance(expr,ast.Subscript):
            container=rec(expr.value);key=rec(expr.slice)
            try:
                if isinstance(container,(dict,list,tuple)) and isinstance(key,(str,int)):return container[key]
            except (KeyError,IndexError,TypeError):pass
        if isinstance(expr,ast.Call):
            name=self.name(expr.func);last=name.rsplit('.',1)[-1]
            if self.graphviz_constructor(expr,expr):return _PY_GRAPHVIZ
            if id(expr) in self.graphviz_context_calls and self.graphviz_receiver(expr,expr):return _PY_GRAPHVIZ
            if last=='pipe' and isinstance(expr.func,ast.Attribute) and self.value(expr.func.value,expr,depth+1,self.scopes.get(id(expr),scope)) is _PY_GRAPHVIZ:return _PY_MEMORY
            if last in {'StringIO','BytesIO'}:
                value=rec(expr.args[0]) if expr.args else _PY_MEMORY
                return _PY_UNKNOWN if value is _PY_UNKNOWN else _PY_MEMORY
            if last in {'b64decode','standard_b64decode','urlsafe_b64decode'}:
                return _PY_MEMORY if expr.args and rec(expr.args[0]) is not _PY_UNKNOWN else _PY_UNKNOWN
            if last in {'Path','PurePath','PosixPath','PurePosixPath','join','joinpath'}:
                parts=[rec(x) for x in expr.args]
                if last=='joinpath' and isinstance(expr.func,ast.Attribute):parts.insert(0,rec(expr.func.value))
                if parts and all(isinstance(x,str) for x in parts):return str(Path(*parts))
            if last=='str' and expr.args:
                value=rec(expr.args[0])
                if isinstance(value,(str,int,float)):return str(value)
            if last in {'encode','getvalue','getbuffer'} and isinstance(expr.func,ast.Attribute):
                value=rec(expr.func.value)
                if isinstance(value,(str,bytes)) or value in (_PY_MEMORY,_PY_PROVIDED):return _PY_MEMORY
        return _PY_UNKNOWN


def graphviz_dependency_issue(context,raw_root,available_assets=None):
    """Only permit typed Graphviz .pipe bytes after a static asset/attribute audit.

    Does not execute Graphviz. Dynamic attribute dictionaries/raw DOT remain
    quarantined, as do missing/external native image/stylesheet resources.
    """
    if not context.has_graphviz_import:return None
    pipes=[node for node in context.calls if isinstance(node.func,ast.Attribute) and node.func.attr=='pipe' and context.value(node.func.value,node) is _PY_GRAPHVIZ]
    if not pipes:return None
    provided=context.row.get('data')
    has_provided_data=provided is not None and (not isinstance(provided,str) or bool(provided.strip()))
    # Generated bytes are complete only when their required function inputs
    # are also present. A .pipe return value must not bypass missing row data.
    functions={node.lineno:node for node in ast.walk(context.tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    owners={line for pipe in pipes for line in context.scopes.get(id(pipe),())}
    for line in owners:
        function=functions[line];positional=function.args.posonlyargs+function.args.args
        defaults=[None]*(len(positional)-len(function.args.defaults))+list(function.args.defaults)
        parameters=[(arg.arg,index,default) for index,(arg,default) in enumerate(zip(positional,defaults))]
        parameters.extend((arg.arg,None,default) for arg,default in zip(function.args.kwonlyargs,function.args.kw_defaults))
        required=[item for item in parameters if item[2] is None]
        for name,_,default in parameters:
            if name=='data' and default is not None and context.value(default,function) is _PY_UNKNOWN:return 'unresolved_graphviz_structured_data_dependency'
        if not required:continue
        calls=[call for call in context.calls if isinstance(call.func,ast.Name) and call.func.id==function.name and line not in context.scopes.get(id(call),())]
        if not calls:
            if all(name=='data' for name,_,_ in required) and has_provided_data:continue
            return 'missing_structured_data_dependency'
        for call in calls:
            if any(isinstance(arg,ast.Starred) for arg in call.args) or any(kw.arg is None for kw in call.keywords):return 'unresolved_graphviz_structured_data_dependency'
            for name,index,_ in required:
                argument=next((kw.value for kw in call.keywords if kw.arg==name),None)
                if argument is None and index is not None and len(call.args)>index:argument=call.args[index]
                if argument is None:return 'missing_structured_data_dependency'
                value=context.value(argument,call)
                if value is _PY_PROVIDED and not has_provided_data:return 'missing_structured_data_dependency'
                if value is _PY_UNKNOWN:
                    if name=='data' and isinstance(argument,ast.Name) and argument.id=='data' and has_provided_data:continue
                    return 'unresolved_graphviz_structured_data_dependency'
    raw_root=Path(raw_root).resolve();available_assets=available_assets or {}
    asset_keys={'image','shapefile','stylesheet','imagepath','fontpath'}
    def resource(value):
        if not isinstance(value,str):return 'unresolved_graphviz_asset_dependency'
        value=html.unescape(value).strip()
        if not value:return None
        if re.match(r'^(?:https?|file|ftp)://|^//',value,re.I):return 'external_graphviz_asset_dependency'
        mapped=available_assets.get(value)
        try:
            if mapped and Path(mapped).is_file():return None
            path=(raw_root/value).resolve()
            if within(path,raw_root) and path.is_file():return None
        except (OSError,ValueError):return 'unresolved_graphviz_asset_dependency'
        return 'missing_local_graphviz_asset_dependency'
    def text_issue(value,raw_dot=False):
        if not isinstance(value,str):return 'unresolved_graphviz_attribute_dependency' if raw_dot else None
        # HTML IMG syntax is special to Graphviz labels; ordinary label text
        # (including URLs) is not interpreted as an external file reference.
        for image in re.findall(r'<img\b[^>]*>',value,re.I|re.S):
            match=re.search(r'\bsrc\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27|([^\s>]+))',image,re.I)
            if not match:return 'unresolved_graphviz_asset_dependency'
            issue=resource(next(x for x in match.groups() if x is not None))
            if issue:return issue
        if re.search(r'<img\b',value,re.I) and not re.search(r'<img\b[^>]*>',value,re.I|re.S):return 'unresolved_graphviz_asset_dependency'
        if raw_dot:
            key=r'(?:"(?:image|shapefile|stylesheet|imagepath|fontpath)"|\b(?:image|shapefile|stylesheet|imagepath|fontpath))\s*='
            pattern=key+r'\s*(?:"((?:\\.|[^"\\])*)"|\x27([^\x27]*)\x27|([^\s,;\]]+))'
            matches=list(re.finditer(pattern,value,re.I))
            if len(matches)!=len(re.findall(key,value,re.I)):return 'unresolved_graphviz_asset_dependency'
            for match in matches:
                reference=next(x for x in match.groups() if x is not None)
                if re.match(r'\s*\+',value[match.end():]):return 'unresolved_graphviz_asset_dependency'
                if '\\' in reference:return 'unresolved_graphviz_asset_dependency'
                issue=resource(reference)
                if issue:return issue
        return None
    label_keys={'label','xlabel','headlabel','taillabel'}
    def attributes(value):
        if value is None:return None
        if not isinstance(value,dict) or not all(isinstance(key,str) for key in value):return 'unresolved_graphviz_attribute_dependency'
        for key,item in value.items():
            issue=resource(item) if key.lower() in asset_keys else ('unresolved_graphviz_attribute_dependency' if key.lower() in label_keys and not isinstance(item,str) else text_issue(item))
            if issue:return issue
        return None
    # Labels can be produced from the provided data. Inspect their known text
    # for the one native HTML form that can introduce an image dependency.
    strings=[node.value for node in ast.walk(context.tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)]
    data=context.row.get('data')
    if isinstance(data,str):strings.append(data)
    elif isinstance(data,(dict,list)):
        try:strings.append(json.dumps(data))
        except TypeError:return 'unresolved_graphviz_attribute_dependency'
    for value in strings:
        issue=text_issue(value)
        if issue:return issue
    def container_kind(expr,at,depth=0):
        if depth>10:return None
        if isinstance(expr,ast.Attribute) and expr.attr in {'body','graph_attr','node_attr','edge_attr'} and context.value(expr.value,at) is _PY_GRAPHVIZ:return expr.attr
        if not isinstance(expr,ast.Name):return None
        scope=context.scopes.get(id(at),());position=(getattr(at,'lineno',10**9),getattr(at,'col_offset',10**9))
        while True:
            candidates=[(line,value) for line,value in context.bindings.get((scope,expr.id),[]) if (line,getattr(value,'col_offset',0))<=position]
            if candidates:
                value=candidates[-1][1];return container_kind(value,value,depth+1)
            if expr.id in context.params.get(scope,{}):return None
            if not scope:break
            scope=scope[:-1]
        return None
    def native_or_module(expr,at):
        return context.value(expr,at) is _PY_GRAPHVIZ or bool(container_kind(expr,at)) or context.name(expr)=='graphviz'
    def label_issue(expr,at,depth=0):
        if depth>10:return 'unresolved_graphviz_attribute_dependency'
        value=context.value(expr,at)
        if isinstance(value,str):return text_issue(value)
        if isinstance(expr,ast.Name):
            scope=context.scopes.get(id(at),())
            while True:
                values=[(line,item) for line,item in context.bindings.get((scope,expr.id),[]) if (line,getattr(item,'col_offset',0))<=(getattr(at,'lineno',10**9),getattr(at,'col_offset',10**9))]
                if values:
                    item=values[-1][1];return label_issue(item,item,depth+1)
                if expr.id in context.params.get(scope,{}):break
                if not scope:break
                scope=scope[:-1]
        if isinstance(expr,ast.Call):
            if context.name(expr.func)=='str' and len(expr.args)==1:return label_issue(expr.args[0],expr,depth+1)
            return 'unresolved_graphviz_attribute_dependency'
        if isinstance(expr,(ast.JoinedStr,ast.BinOp)) and any(isinstance(item,ast.Constant) and isinstance(item.value,str) and ('<' in item.value or '>' in item.value) for item in ast.walk(expr)):return 'unresolved_graphviz_attribute_dependency'
        # Plain data/loop labels cannot by themselves introduce an HTML IMG;
        # known code/data strings were checked above. Do not inline helpers.
        return None
    parents={id(child):parent for parent in ast.walk(context.tree) for child in ast.iter_child_nodes(parent)}
    # Unsupported native mutation/dynamic access cannot be certified by the
    # narrow .pipe exception. This includes aliases of native containers.
    for statement in ast.walk(context.tree):
        if isinstance(statement,(ast.With,ast.AsyncWith)):
            for item in statement.items:
                call=item.context_expr
                if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and call.func.attr=='subgraph' and id(call) not in context.graphviz_context_calls:return 'unresolved_graphviz_attribute_dependency'
        if isinstance(statement,ast.Attribute) and statement.attr.startswith('__') and native_or_module(statement.value,statement):return 'unresolved_graphviz_attribute_dependency'
        if isinstance(statement,(ast.Name,ast.Attribute)):
            parent=parents.get(id(statement));direct_call=isinstance(parent,ast.Call) and parent.func is statement
            canonical=context.name(statement)
            if canonical.startswith('graphviz.') and not direct_call:return 'unresolved_graphviz_attribute_dependency'
            if isinstance(statement,ast.Name) and canonical=='graphviz' and not (isinstance(parent,ast.Attribute) and parent.value is statement):return 'unresolved_graphviz_attribute_dependency'
            if isinstance(parent,ast.Call) and not direct_call and (context.value(statement,parent) is _PY_GRAPHVIZ or container_kind(statement,parent)):
                function=parent.func
                safe_subgraph=isinstance(function,ast.Attribute) and function.attr=='subgraph' and context.value(function.value,parent) is _PY_GRAPHVIZ
                if not safe_subgraph:return 'unresolved_graphviz_attribute_dependency'
        if isinstance(statement,ast.Attribute):
            parent=parents.get(id(statement));direct_call=isinstance(parent,ast.Call) and parent.func is statement
            native=context.value(statement.value,statement) is _PY_GRAPHVIZ
            container=container_kind(statement.value,statement)
            if ((native and statement.attr not in {'body','graph_attr','node_attr','edge_attr','format','engine','encoding'}) or container) and not direct_call:return 'unresolved_graphviz_attribute_dependency'
        if not isinstance(statement,(ast.Assign,ast.AnnAssign,ast.AugAssign,ast.Delete)):continue
        targets=statement.targets if isinstance(statement,(ast.Assign,ast.Delete)) else [statement.target]
        for target in targets:
            if isinstance(target,ast.Attribute):
                name=context.name(target)
                if name.startswith(('graphviz.Graph.','graphviz.Digraph.','graphviz.Source.')) or (context.name(target.value)=='graphviz' and target.attr in {'Graph','Digraph','Source'}):return 'unresolved_graphviz_attribute_dependency'
                if context.value(target.value,statement) is _PY_GRAPHVIZ:
                    if target.attr not in {'format','engine','encoding'} or not isinstance(context.value(getattr(statement,'value',None),statement),str):return 'unresolved_graphviz_attribute_dependency'
            if isinstance(target,ast.Subscript) and (container_kind(target.value,statement) or native_or_module(target.value,statement)):return 'unresolved_graphviz_attribute_dependency'
            if isinstance(statement,ast.AugAssign) and container_kind(target,statement):return 'unresolved_graphviz_attribute_dependency'
    for node in context.calls:
        name=context.name(node.func);last=name.rsplit('.',1)[-1];constructor=context.graphviz_constructor(node,node)
        if last in {'getattr','setattr','delattr','vars'} and node.args and native_or_module(node.args[0],node):return 'unresolved_graphviz_attribute_dependency'
        if name.startswith('graphviz.') and not constructor and name not in {'graphviz.escape','graphviz.nohtml'}:return 'unresolved_graphviz_asset_dependency'
        receiver=node.func.value if isinstance(node.func,ast.Attribute) else None
        native_receiver=receiver is not None and context.value(receiver,node) is _PY_GRAPHVIZ
        native_container=container_kind(receiver,node) if receiver is not None else None
        if native_receiver and last not in {'node','edge','edges','attr','subgraph','pipe'}:return 'unresolved_graphviz_attribute_dependency'
        if native_container and not ((native_container=='body' and last in {'append','extend'}) or (native_container!='body' and last=='update')):return 'unresolved_graphviz_attribute_dependency'
        mutator=last in {'attr','node','edge','subgraph','edges'}
        body_method=native_container=='body' and last in {'append','extend'}
        dict_method=native_container in {'graph_attr','node_attr','edge_attr'} and last=='update'
        if not (constructor or mutator or body_method or dict_method):continue
        if any(kw.arg is None for kw in node.keywords) or any(isinstance(arg,ast.Starred) for arg in node.args):return 'unresolved_graphviz_attribute_dependency'
        for kw in node.keywords:
            value=context.value(kw.value,node)
            if kw.arg.lower() in asset_keys:issue=resource(value)
            elif kw.arg in {'graph_attr','node_attr','edge_attr','_attributes'}:issue=attributes(value)
            elif kw.arg.lower() in label_keys:issue=label_issue(kw.value,node)
            elif kw.arg=='body':
                issue=None
                if not isinstance(value,(list,tuple)) or not all(isinstance(x,str) for x in value):issue='unresolved_graphviz_attribute_dependency'
                else:
                    for item in value:
                        issue=text_issue(item,True)
                        if issue:break
            else:issue=text_issue(value)
            if issue:return issue
        if constructor and name=='graphviz.Source':
            value=context.value(context.argument(node,('source',)),node)
            issue=text_issue(value,True)
            if issue:return issue
        if constructor:
            # Positional attribute/body arguments are deliberately unsupported;
            # ordinary name/comment/output/format arguments are not file inputs.
            if name in {'graphviz.Graph','graphviz.Digraph'} and len(node.args)>7:return 'unresolved_graphviz_attribute_dependency'
        if mutator:
            position={'attr':1,'node':2,'edge':3}.get(last)
            if position is not None and len(node.args)>position:
                issue=attributes(context.value(node.args[position],node))
                if issue:return issue
            if last=='subgraph':
                graph=context.argument(node,('graph',))
                if graph is None:
                    if id(node) not in context.graphviz_context_calls or not context.graphviz_receiver(node,node):return 'unresolved_graphviz_attribute_dependency'
                elif context.value(graph,node) is not _PY_GRAPHVIZ:return 'unresolved_graphviz_attribute_dependency'
            if last in {'node','edge'}:
                # Node names and edge tail/head IDs are ordinary strings,
                # even when their syntax resembles HTML. Only the actual
                # positional label can load native HTML IMG resources.
                for argument in node.args[1:2] if last=='node' else node.args[2:3]:
                    issue=label_issue(argument,node)
                    if issue:return issue
        if body_method:
            value=context.value(node.args[0],node) if node.args else _PY_UNKNOWN
            values=[value] if last=='append' else value
            if not isinstance(values,(list,tuple)) or not all(isinstance(x,str) for x in values):return 'unresolved_graphviz_attribute_dependency'
            for item in values:
                issue=text_issue(item,True)
                if issue:return issue
        if dict_method:
            if node.args:
                issue=attributes(context.value(node.args[0],node))
                if issue:return issue
    for node in ast.walk(context.tree):
        if not isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):continue
        targets=node.targets if isinstance(node,ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target,ast.Attribute) and target.attr in {'body','source','graph_attr','node_attr','edge_attr'}:return 'unresolved_graphviz_attribute_dependency'
            if isinstance(target,ast.Subscript) and isinstance(target.value,ast.Attribute) and target.value.attr in {'graph_attr','node_attr','edge_attr'}:return 'unresolved_graphviz_attribute_dependency'
    context.graphviz_validated_input_scopes=owners
    return None


def python_dependency_issue(code,row,raw_root,available_assets=None):
    """Conservative static input audit; available_assets maps proven refs to files."""
    try:tree=python_tree(code)
    except SyntaxError:return 'invalid_python_syntax'
    context=_StaticPythonInputs(tree,row or {},graphviz_candidate='graphviz' in code);available_assets=available_assets or {};raw_root=Path(raw_root)
    graphviz_issue=graphviz_dependency_issue(context,raw_root,available_assets)
    if graphviz_issue:return graphviz_issue
    readers={'read_csv','read_excel','read_json','read_parquet','read_table','read_fwf','read_feather','read_hdf','read_pickle','read_orc','read_stata','ExcelFile','loadtxt','genfromtxt','fromfile','memmap','imread','open','read_text','read_bytes','read_html','read_clipboard','loadmat','readsav','load_npz'}
    for node in context.calls:
        name=context.name(node.func);last=name.rsplit('.',1)[-1]
        network=name.startswith(('requests.','httpx.','aiohttp.','pandas_datareader.','yfinance.','pooch.','socket.','boto3.','botocore.','fsspec.')) or name.startswith(('urllib.request.','urllib2.'))
        dataset=last=='load_dataset' and ('.' in name or last not in context.user_functions)
        dataset=dataset or (last.startswith('fetch_') and name.startswith(('sklearn.','datasets.')))
        if network:return 'external_network_client_or_data_dependency'
        if dataset:return 'external_dataset_loader_dependency'
        if last.startswith('read_sql'):return 'external_database_data_dependency'
        is_load=last=='load' and name.startswith(('np.','numpy.','pickle.','joblib.','torch.','scipy.io.'))
        if last not in readers and not is_load:continue
        if last=='open' and context.write_mode(node):continue
        argument=context.input_argument(node,last);value=context.value(argument,node)
        if value is _PY_MEMORY or value is _PY_PROVIDED:continue
        if not isinstance(value,str):return 'unresolved_python_input_dependency'
        if value.startswith('data:'):continue
        if last=='read_html' and value.lstrip().startswith('<'):continue
        if last=='read_json' and value.lstrip().startswith(('{','[')):
            try:json.loads(value);continue
            except ValueError:pass
        if re.match(r'^(?:https?|ftp|s3|gs|hdfs|file)://',value,re.I) or value.startswith('//'):return 'external_data_dependency'
        mapped=available_assets.get(value)
        if mapped and Path(mapped).is_file():continue
        path=(raw_root/value).resolve()
        if within(path,raw_root.resolve()) and path.is_file():continue
        if any(reference==value and line<node.lineno for reference,line in context.outputs):continue
        return 'missing_local_data_dependency'
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='generate_plot' and any(a.arg=='data' for a in node.args.args):
            if node.lineno in getattr(context,'graphviz_validated_input_scopes',set()):continue
            invoked=any(isinstance(call.func,ast.Name) and call.func.id==node.name for call in context.calls)
            if not invoked and (row or {}).get('data') is None:return 'missing_structured_data_dependency'
    return None


def tex_dependency_issue(code,raw_root):
    text=re.sub(r'(?<!\\)%[^\n]*','',code);generated=set();tables=set();raw_root=Path(raw_root)
    for match in re.finditer(r'\\begin\{filecontents\*?\}\s*\{([^}]+)\}.*?\\end\{filecontents\*?\}',text,re.S):
        name=match.group(1).strip()
        if '\\' not in name:generated.add(name)
    def group(position):
        while position<len(text) and text[position].isspace():position+=1
        while position<len(text) and text[position]=='[':
            end=text.find(']',position+1)
            if end<0:return None,position
            position=end+1
            while position<len(text) and text[position].isspace():position+=1
        if position>=len(text):return None,position
        if text[position]!='{':
            match=re.match(r'[^\s;]+',text[position:]);return (match.group(0),position+len(match.group(0))) if match else (None,position)
        start=position+1;depth=1;position=start
        while position<len(text):
            if text[position]=='{' and (position==0 or text[position-1]!='\\'):depth+=1
            elif text[position]=='}' and (position==0 or text[position-1]!='\\'):
                depth-=1
                if depth==0:return text[start:position],position+1
            position+=1
        return None,position
    def resource(value,kind):
        if value is None:return 'unresolved_tex_input_dependency'
        value=value.strip().strip('"\'')
        if kind=='table':
            number=r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?'
            # PGFPlots histogram tables can be one whitespace-delimited line.
            # Only unambiguous numeric payloads (at least three tokens) receive
            # this exception; include/input/graphics files never do.
            if re.fullmatch(r'\s*'+number+r'(?:\s+'+number+r'){2,}\s*',value):return None
        if kind=='table' and ('\n' in value or '\\\\' in value) and len(value.split())>=3:return None
        if kind=='table' and value in tables:return None
        if value in generated:return None
        if re.match(r'^(?:https?|ftp|file)://',value,re.I):return 'external_tex_data_dependency'
        if '\\' in value or re.search(r'[#{}]',value):return 'unresolved_tex_input_dependency'
        if not value:return 'unresolved_tex_input_dependency'
        try:
            resolved_root=raw_root.resolve();path=(resolved_root/value).resolve();candidates=[path]
            if not path.suffix:
                candidates.extend(path.with_suffix(ext) for ext in ('.tex','.csv','.dat','.png','.jpg','.jpeg','.pdf','.eps','.svg'))
            if any(within(p,resolved_root) and p.is_file() for p in candidates):return None
        except (OSError,ValueError):
            # Dataset text is untrusted input, not necessarily a valid path.
            # ENAMETOOLONG/invalid filenames must quarantine one pair, never
            # abort an entire curation pass.
            return 'unresolved_tex_input_dependency'
        return 'missing_local_tex_dependency'
    commands=re.compile(r'\\(?:includegraphics|input|include|pgfplotstableread)\b\*?|\\addplot(?:3)?\+?\s*(?:\[[^\]]*\]\s*)*(?:table|graphics)\b')
    for match in commands.finditer(text):
        command=match.group(0);value,end=group(match.end());kind='table' if 'table' in command else 'file'
        issue=resource(value,kind)
        if issue:return issue
        if 'pgfplotstableread' in command:
            alias=re.match(r'\s*(\\[A-Za-z@]+)',text[end:])
            if alias:tables.add(alias.group(1))
    return None


def dependency_reason(code,fmt,row,raw_root):
    if fmt=='python':return python_dependency_issue(code,row,raw_root)
    if fmt=='tikz':return tex_dependency_issue(code,raw_root)
    if fmt=='asymptote':return asymptote_support().dependency_issue(code,raw_root)
    if fmt=='html':return html_dependency_reason(code,raw_root)
    if fmt=='vegalite' and re.search(r'"url"\s*:',code):return 'external_data_dependency'
    return None


def revision_panel_assets(row,raw_root):
    names=set();metadata=[];seen={}
    for index,panel in enumerate(row.get('panels') or []):
        if not isinstance(panel,dict):return names,metadata,'invalid_revision_panel_record'
        filename=str(panel.get('file_name',''));path=Path(filename)
        if not filename or path.is_absolute() or '..' in path.parts or '://' in filename:return names,metadata,'unsafe_revision_panel_filename'
        data=image_bytes(panel.get('image'),raw_root);info=image_info(data) if data else None
        if not info:return names,metadata,'missing_or_invalid_revision_panel_image'
        sha=hashlib.sha256(data).hexdigest();aliases={filename,path.name,'panels/'+path.name}
        for alias in aliases:
            if alias in seen and seen[alias]!=sha:return names,metadata,'ambiguous_revision_panel_name'
            seen[alias]=sha;names.add(alias)
        metadata.append({'file_name':filename,'image_key':'panels['+str(index)+'].image','image_sha256':sha,'allowed_svg_references':sorted(aliases),'image_info':info})
    return names,metadata,None


def profile_for(repo):
    s=repo.lower()
    if s.endswith('--rap') or s=='rap':return 'rap'
    if 'brokenxml' in s or 'baustex--drawio-to-xml' in s:return 'broken_drawio'
    if 'scidiagramrevision' in s:return 'revision'
    if 'slide2svg' in s:return 'slide_aux'
    if 'vcg-bench' in s:return 'vcg'
    if 'svg_basic_benchmark' in s:return 'generic_svg_auxiliary'
    if 'omnidiagram' in s:return 'omni'
    if 'vincicoder' in s:return 'vinci'
    if 'cosyn' in s:return 'cosyn'
    if 'plot2code' in s:return 'plot2code'
    if 'chartmimic' in s or 'chart2code' in s or 'chartcoder' in s:return 'chart'
    if 'vfig' in s:return 'vfig'
    if 'datikz' in s or 'daeditikz' in s:return 'datikz'
    return 'unknown'


def file_scope_reason(profile,rel):
    """Only exclusions whose existing domain_reason is independent of row data.

    This does not decide VCG, TikZ, VFIG or CoSyn metadata-dependent domains.
    Rejection priority may change to the domain exclusion; accepted set cannot.
    """
    path=str(rel).lower()
    if profile=='unknown':return 'unknown_source_profile'
    if profile=='generic_svg_auxiliary':return 'generic_svg_features_not_verified_poster_diagram_or_chart'
    if profile=='slide_aux':return 'slide2svg_raw_only_editability_unverified'
    if profile=='vinci':
        if any(x in path for x in ('web2html','table','chem','molecule','circuit')):return 'excluded_web_table_chemistry_circuit'
        if 'img2svg' in path:return 'svg_domain_not_established'
    if profile=='omni' and 'dia2code' not in path:return 'not_dia2code_target_pair'
    if profile=='cosyn' and any(x in path for x in ('webpagepipeline','tablepipeline')):return 'excluded_web_table_domain'
    return None


def domain_reason(profile,row,rel,code,fmt):
    path=str(rel).lower()
    meta=' '.join(str(row.get(k,'')) for k in ('domain_l1','domain_l2','category','type','figure_type','metadata','source','dataset','caption','vlm_description')).lower()
    if profile=='vcg':
        if 'academic' not in str(row.get('domain_l1','')).lower():return None,'out_of_scope_domain'
        sub=str(row.get('domain_l2','')).lower()
        if any(x in sub for x in ('architecture','neural','dataviz','scientific','flowchart')):
            return ('chart' if 'dataviz' in sub else 'scientific_diagram'),None
        return None,'out_of_scope_domain'
    if profile=='generic_svg_auxiliary':return None,'generic_svg_features_not_verified_poster_diagram_or_chart'
    if profile=='poster':return 'poster',None
    if profile=='slide_aux':return None,'slide2svg_raw_only_editability_unverified'
    if profile=='revision':return ('chart' if actual_chart_evidence(code,fmt) else 'scientific_diagram'),None
    if profile=='broken_drawio':
        if re.search(r'mxgraph\.mockup|wireframe|landing.?page|login.?page|login.?form|navbar|navigation.?bar|shopping.?cart|checkout|ecommerce',code,re.I):return None,'web_ui_content'
        try:tree=ET.fromstring(code)
        except ET.ParseError:return None,'invalid_drawio_xml'
        vertices=sum(n.get('vertex')=='1' for n in tree.iter('mxCell'));edges=sum(n.get('edge')=='1' for n in tree.iter('mxCell'));labels=[re.sub('<[^>]+>',' ',html.unescape(n.get('value',''))) for n in tree.iter('mxCell') if n.get('value')]
        if vertices>=4 and len(labels)>=2 and re.search(r'chart|scatter|histogram|bar plot|x.axis|y.axis|accuracy|learning curve',' '.join(labels),re.I):return 'chart',None
        if vertices>=3 and edges>=2 and len(labels)>=2:return 'scientific_diagram',None
        return None,'broken_drawio_framework_domain_not_established'
    if profile=='omni':
        if 'dia2code' not in path:return None,'not_dia2code_target_pair'
    if profile=='vinci':
        if any(x in path for x in ('web2html','table','chem','molecule','circuit')):return None,'excluded_web_table_chemistry_circuit'
        if 'img2svg' in path:return None,'svg_domain_not_established'
    if profile=='cosyn':
        if any(x in path or x in meta for x in ('webpagepipeline','tablepipeline')):return None,'excluded_web_table_domain'
        if not path.startswith('chart/') and any(x in path or x in meta for x in ('molecule','circuit','chemical')):return None,'excluded_nonchart_molecular_or_circuit_diagram'
        if not any(x in path or x in meta for x in ('chart','diagram','poster','infographic')) and not (fmt=='asymptote' and actual_chart_evidence(code,fmt)):return None,'domain_not_established'
    if profile=='unknown':return None,'unknown_source_profile'
    if actual_chart_evidence(code,fmt):return 'chart',None
    if profile=='cosyn' and path.startswith('diagram/') and fmt=='python' and python_visual_facts(code).get('graph'):return 'scientific_diagram',None
    if profile=='datikz':
        # arXiv TikZ collections include much pure mathematics and geometry.
        # A TikZ language label alone does not establish the requested domain.
        description=meta+' '+str(row.get('description','')).lower()
        chart_terms=r'line chart|line plot|scatter|bar chart|bar plot|histogram|box plot|boxplot|heatmap|data visual|time series|experimental results|performance curve|learning curve|accuracy curve|error bar|distribution plot|roc curve|function plot|graph of (?:the )?function|trigonometric (?:plot|curve)'
        if re.search(chart_terms,description) and tikz_visual_facts(code)['draws']>=3:return 'chart',None
        excluded=r'commutative|geometr(?:y|ic|ical)|euclidean|polyhedr|triangle|triangulation|tetrahedr|torus|knot diagram|graph theor|complete graph|cayley|proof|derivation|algebraic'
        if re.search(excluded,description):return None,'math_geometry_or_graph_theory_domain'
        framework_terms=r'flow.?chart|pipeline|(?:model|system|network|neural|transformer|encoder|decoder|cnn|rnn|computational|software) architecture|neural network|convolutional network|framework|data.?flow|workflow|block diagram|processing stages|feature extraction|encoder.decoder|attention mechanism'
        if re.search(framework_terms,description+' '+code.lower()):return 'scientific_diagram',None
        return None,'datikz_domain_not_established'
    if re.search(r'circuitikz|chemfig|mhchem|\\molecule',code,re.I):return None,'excluded_web_or_chemistry_circuit'
    if fmt=='html':
        if re.search(r'login|sign.?in|landing.page|navbar|navigation.bar|ecommerce|webpage|website|dashboard',meta):return None,'web_ui_content'
        if 'poster' in meta or 'infographic' in meta:return 'poster',None
        if 'chart' in path or 'chart' in meta or re.search(r'plotly|vega(?:lite)?|echarts|chart\.js',code,re.I):return 'chart',None
        return None,'html_visual_domain_not_established'
    if fmt=='mermaid':
        if re.search(r'(?m)^\s*(graph\s|flowchart\s)',code):return 'scientific_diagram',None
        if re.search(r'(?m)^\s*(xychart|pie\s)',code):return 'chart',None
        return None,'non_framework_mermaid_domain'
    if fmt=='plantuml':
        if re.search(r'(?m)^\s*(class\s|entity\s|database\s|actor\s|participant\s)',code):return None,'non_framework_uml_domain'
        return 'scientific_diagram',None
    if fmt=='tikz' and re.search(r'\\begin\{(?:tabular|table|longtable)|circuitikz|chemfig',code):return None,'excluded_table_chemistry_circuit'
    if fmt in ('tikz','drawio'):return 'scientific_diagram',None
    if fmt in ('python','vegalite') and (profile in ('chart','plot2code','vinci','cosyn') or re.search(r'matplotlib|plotly|seaborn|plt\.|ax\.|altair',code)):
        return 'chart',None
    if profile=='vfig' and ('complex' in path or 'bench' in path):return 'scientific_diagram',None
    if profile=='vinci' and fmt=='svg':
        try:
            tree=ET.fromstring(code)
            labels=[' '.join(n.itertext()).strip() for n in tree.iter() if n.tag.rsplit('}',1)[-1] in ('text','foreignObject')]
            label_text=' '.join(labels).lower()
            if len(labels)>=3 and re.search(r'encoder|decoder|attention|neural|transformer|embedding|feature extraction|gradient|backprop|pipeline|framework',label_text):return 'scientific_diagram',None
            if len(labels)>=4 and re.search(r'accuracy|epoch|probability|frequency|learning curve|performance|time\s*\(|x.axis|y.axis',label_text):return 'chart',None
        except ET.ParseError:pass
    if fmt=='svg' and any(x in meta for x in ('poster','scientific','flowchart','architecture','diagram','chart','infographic')):
        return ('poster' if 'poster' in meta else 'scientific_diagram'),None
    return None,'domain_not_established'


class ResourceParser(HTMLParser):
    def __init__(self):super().__init__();self.resources=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        for key in ('src','poster'):
            if attrs.get(key):self.resources.append(attrs[key])
        if tag=='link' and attrs.get('rel','').lower() in ('stylesheet','preload') and attrs.get('href'):self.resources.append(attrs['href'])
        if tag=='object' and attrs.get('data'):self.resources.append(attrs['data'])


def html_dependency_reason(code,folder):
    parser=ResourceParser()
    try:parser.feed(code)
    except Exception:return 'invalid_html_structure'
    refs=parser.resources+re.findall(r'url\(\s*[\'"]?([^\s\)\'";]+)',code,flags=re.I)
    for ref in refs:
        if ref.startswith(('data:','#','about:','javascript:')):continue
        if ref.startswith(('http:','https:','//','file:')):return 'external_html_asset'
        value=urllib.parse.unquote(ref.split('?',1)[0].split('#',1)[0])
        p=(folder/value).resolve()
        if not within(p,folder.resolve()) or not p.is_file():return 'missing_html_asset'
    return None


def safe_extract_template(tf,members,prefix,destination):
    prefix=prefix.strip('/')+'/'
    selected=[]
    for member in members:
        if not member.name.startswith(prefix):continue
        suffix=member.name[len(prefix):]
        if not suffix:continue
        p=Path(suffix)
        if p.is_absolute() or '..' in p.parts or member.issym() or member.islnk() or not (member.isdir() or member.isfile()):return 'unsafe_template_member'
        selected.append((member,destination/p))
    if not selected:return 'template_directory_missing'
    for member,target in selected:
        if not within(target.resolve(),destination.resolve()):return 'unsafe_template_member'
        if member.isdir():target.mkdir(parents=True,exist_ok=True)
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            stream=tf.extractfile(member)
            if stream is None:return 'unreadable_template_member'
            with stream,target.open('wb') as output:shutil.copyfileobj(stream,output,length=1024*1024)
    return None


def curate_rap(root,source,db,case_counts,case_targets):
    annotations=source/'annotations'/'all.jsonl'
    stats={'profile':'rap','raw_rows':0,'accepted':0,'rejected':0,'reasons':collections.Counter(),'formats':{'html':0},'categories':{'poster':0},'archives':0,'pairing_provenance':'provided rendered.png corresponds to generated.html and assets; original conference poster is auxiliary approximate-reference, never mislabeled as exact template render'}
    if not annotations.is_file():stats['error']='annotations_not_downloaded';stats['reasons']=dict(stats['reasons']);return stats
    groups=collections.defaultdict(list)
    with annotations.open() as stream:
        for index,line in enumerate(stream):
            if line.strip():groups[json.loads(line).get('template_archive','')].append((index,json.loads(line)))
    outdir=root/'clean'/source.name;outdir.mkdir(parents=True,exist_ok=True)
    with (root/'manifests'/(source.name+'.jsonl')).open('w') as mf,(root/'manifests'/(source.name+'.rejected.jsonl')).open('w') as rf:
        for archive,rows in sorted(groups.items()):
            archive_path=(source/archive).resolve();tf=None;members=[]
            if within(archive_path,source.resolve()) and archive_path.is_file():
                try:tf=tarfile.open(archive_path,'r:*');members=tf.getmembers();stats['archives']+=1
                except (OSError,tarfile.TarError):pass
            try:
                for row_index,row in rows:
                    stats['raw_rows']+=1;record={'source':source.name,'raw_file':'annotations/all.jsonl','raw_row':row_index,'annotation':row,'category':'poster','format':'html'};reason=None
                    paper=str(row.get('paper_id',''))
                    if not re.fullmatch(r'[A-Za-z0-9._-]+',paper):reason='invalid_paper_id'
                    if tf is None:reason=reason or 'template_archive_not_downloaded'
                    destination=outdir/'templates'/(paper if re.fullmatch(r'[A-Za-z0-9._-]+',paper) else '_invalid_'+hashlib.sha256(paper.encode()).hexdigest()[:16]);extracted=False
                    if not reason:
                        extracted=True;reason=safe_extract_template(tf,members,str(row.get('template_dir',paper+'/')),destination)
                    html=destination/'generated.html';render=destination/'rendered.png';code='';image=None;info=None
                    if not reason and (not html.is_file() or not render.is_file()):reason='missing_html_or_rendered_image'
                    if not reason:
                        try:code=html.read_text();image=render.read_bytes();info=image_info(image)
                        except (OSError,UnicodeError):reason='unreadable_template_pair'
                    if not reason and (not code.strip() or not info):reason='invalid_template_pair'
                    if not reason:reason=html_dependency_reason(code,destination)
                    if not reason:
                        image_sha=hashlib.sha256(image).hexdigest();code_sha=hashlib.sha256(code.encode()).hexdigest();pair_sha=hashlib.sha256((image_sha+code_sha).encode()).hexdigest()
                        try:db.execute('INSERT INTO pairs VALUES (?)',(pair_sha,))
                        except sqlite3.IntegrityError:reason='duplicate_exact_pair'
                    if reason:
                        stats['rejected']+=1;stats['reasons'][reason]+=1;record['reason']=reason;rf.write(json.dumps(record,ensure_ascii=False)+'\n')
                        # This directory was created only by this curation; discard rejected products.
                        if extracted and destination.exists() and within(destination.resolve(),outdir.resolve()):shutil.rmtree(destination)
                        continue
                    original=(source/str(row.get('poster_file',''))).resolve()
                    record.update({'pairing':'provided_template_render_and_code','provenance':'reconstructed_poster_template','reference_image':str(render.relative_to(root)),'code_file':str(html.relative_to(root)),'asset_root':str(destination.relative_to(root)),'original_poster':str(original.relative_to(root)) if within(original,root.resolve()) and original.is_file() else None,'image_sha256':image_sha,'code_sha256':code_sha,'image_info':info,'structurally_complete':True,'code_execution_checked':False})
                    stats['accepted']+=1;stats['formats']['html']+=1;stats['categories']['poster']+=1;mf.write(json.dumps(record,ensure_ascii=False)+'\n')
                    if case_counts['poster']<case_targets['poster']:
                        case_counts['poster']+=1;cd=root/'curation_cases'/f"poster_{case_counts['poster']:02d}";cd.mkdir(parents=True,exist_ok=True)
                        shutil.copyfile(render,cd/'reference.png');shutil.copyfile(html,cd/'ground_truth.html')
                        # Keep relative dependencies rooted alongside the HTML.
                        if (destination/'assets').is_dir():shutil.copytree(destination/'assets',cd/'assets',dirs_exist_ok=True)
                        write_json(cd/'case.json',record)
                db.commit();print(json.dumps({'event':'curated_rap_archive','archive':archive,'accepted':stats['accepted'],'rejected':stats['rejected']}),flush=True)
            finally:
                if tf is not None:tf.close()
    stats['reasons']=dict(stats['reasons']);return stats


def write_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2));tmp.replace(path)


def curate(root,only=None,batch_size=16):
    import pyarrow as pa
    import pyarrow.parquet as pq
    raw=root/'raw';clean=root/'clean';manifests=root/'manifests';reports=root/'reports';cases=root/'curation_cases'
    for p in (clean,manifests,reports,cases):p.mkdir(parents=True,exist_ok=True)
    summary={'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'root':str(root),'sources':{},'validation':'image decode + nonempty parsable code + domain + local/external asset checks; no arbitrary code execution','paired_image_code':0,'derived_code_only_rows':0,'case_targets':{'vcg':2,'chart':2,'poster':1}}
    db=sqlite3.connect(str(manifests/'dedup.sqlite'))
    db.execute('CREATE TABLE IF NOT EXISTS pairs (pair_sha TEXT PRIMARY KEY)')
    # A fresh invocation rebuilds compact clean products; raw assets stay untouched.
    db.execute('DELETE FROM pairs');db.commit()
    case_counts=collections.Counter()
    source_dirs=sorted(p for p in raw.iterdir() if p.is_dir())
    for source in source_dirs:
        if only and not any(x.lower() in source.name.lower() for x in only):continue
        profile=profile_for(source.name); stats={'profile':profile,'raw_rows':0,'accepted':0,'rejected':0,'derived_code_only':0,'reasons':collections.Counter(),'formats':collections.Counter(),'categories':collections.Counter(),'files':[]}
        outdir=clean/source.name;outdir.mkdir(parents=True,exist_ok=True)
        (manifests/(source.name+'.derived.jsonl')).write_text('')
        if profile=='rap':
            stats=curate_rap(root,source,db,case_counts,summary['case_targets']);summary['sources'][source.name]=stats;summary['paired_image_code']+=stats['accepted'];write_json(reports/'summary.json',summary);continue
        manifest_path=manifests/(source.name+'.jsonl');reject_path=manifests/(source.name+'.rejected.jsonl')
        with manifest_path.open('w') as mf,reject_path.open('w') as rf:
            for file_index,pf in enumerate(sorted(source.rglob('*.parquet'))):
                rel=pf.relative_to(source); file_stat={'raw':str(pf),'accepted':0,'rows':0};stats['files'].append(file_stat)
                try:reader=pq.ParquetFile(pf)
                except Exception as e:
                    stats['reasons']['unreadable_parquet']+=1;file_stat['error']=type(e).__name__;continue
                output=outdir/f'part{file_index:05d}.parquet';writer=None;row_index=0
                output.unlink(missing_ok=True)
                scope_reason=file_scope_reason(profile,rel)
                # The general row loop can emit two variant rejections when both
                # TikZ sides are nonempty. Footer row count alone cannot prove
                # that cardinality, so retain its original behavior for that schema.
                paired_schema={'tikz_code_i','tikz_code_j'}.issubset(reader.schema_arrow.names)
                if scope_reason and not paired_schema:
                    count=reader.metadata.num_rows;raw_bytes=pf.stat().st_size
                    stats['raw_rows']+=count;stats['rejected']+=count
                    if count:stats['reasons'][scope_reason]+=count
                    stats['file_scope_skipped_rows']=stats.get('file_scope_skipped_rows',0)+count
                    stats['file_scope_skipped_raw_bytes']=stats.get('file_scope_skipped_raw_bytes',0)+raw_bytes
                    file_stat.update({'rows':count,'scope_fast_reject_reason':scope_reason,'scope_fast_rejected_rows':count,'scope_skipped_raw_file_bytes':raw_bytes})
                    for raw_row in range(count):
                        record={'source':source.name,'raw_file':str(rel),'raw_row':raw_row,'profile':profile,'reason':scope_reason,'rejection_stage':'file_scope','scope_fast_reject':True}
                        rf.write(json.dumps(record,ensure_ascii=False)+'\n')
                    print(json.dumps({'event':'curated_file','source':source.name,**file_stat}),flush=True)
                    for key in ('reasons','formats','categories'):stats[key]=dict(stats[key])
                    summary['sources'][source.name]=stats;write_json(reports/'summary.json',summary)
                    for key in ('reasons','formats','categories'):stats[key]=collections.Counter(stats[key])
                    continue
                try:
                    for batch in reader.iter_batches(batch_size=batch_size):
                        selected=[]
                        original_rows=batch.to_pylist()
                        variants=[]
                        for original_index,original in enumerate(original_rows):
                            stats['raw_rows']+=1;file_stat['rows']+=1
                            if original.get('tikz_code_i') and original.get('tikz_code_j'):
                                for side in ('i','j'):
                                    variant=dict(original);variant['code']=original['tikz_code_'+side];variant['image']=original.get('image_'+side);variant['_pair_side']=side;variants.append((original_index,variant))
                            else:variants.append((original_index,original))
                        for i,row in variants:
                            record={'source':source.name,'raw_file':str(rel),'raw_row':row_index+i,'profile':profile}
                            if row.get('_pair_side'):record['pair_side']=row['_pair_side']
                            panel_metadata=[];panel_error=None;allowed_panels=None
                            if profile=='revision':
                                value=text_content(row.get('input_svg'));code_key='input_svg';allowed_panels,panel_metadata,panel_error=revision_panel_assets(row,source)
                            else:value,code_key=code_value(row)
                            code=unwrap_code(value);fmt=infer_format(code);reason=panel_error or validate_code(code,fmt,allowed_panels)
                            category,domain_error=domain_reason(profile,row,rel,code,fmt)
                            reason=reason or domain_error
                            if profile=='revision':image=image_bytes(row.get('input_image'),source);image_key='input_image'
                            else:image,image_key=get_image(row,source)
                            if row.get('_pair_side'):code_key='tikz_code_'+row['_pair_side'];image_key='image_'+row['_pair_side']
                            if not reason and not image:
                                if profile=='vfig' and fmt=='svg':
                                    stats['derived_code_only']+=1;summary['derived_code_only_rows']+=1
                                    record.update({'pairing':'code_only_can_render_derived_image','format':fmt,'category':category,'code_key':code_key})
                                    with (manifests/(source.name+'.derived.jsonl')).open('a') as df:df.write(json.dumps(record,ensure_ascii=False)+'\n')
                                    reason='missing_independent_image_svg_only'
                                else:reason='missing_or_ambiguous_image'
                            info=image_info(image) if not reason else None
                            if not reason and not info:reason='invalid_image'
                            if not reason:reason=dependency_reason(code,fmt,row,source)
                            if not reason:
                                image_sha=hashlib.sha256(image).hexdigest();code_sha=hashlib.sha256(code.encode()).hexdigest();pair_sha=hashlib.sha256((image_sha+code_sha).encode()).hexdigest()
                                try:db.execute('INSERT INTO pairs VALUES (?)',(pair_sha,))
                                except sqlite3.IntegrityError:reason='duplicate_exact_pair'
                            if reason:
                                stats['rejected']+=1;stats['reasons'][reason]+=1;record['reason']=reason;rf.write(json.dumps(record,ensure_ascii=False)+'\n');continue
                            selected.append(i);stats['accepted']+=1;file_stat['accepted']+=1;stats['formats'][fmt]+=1;stats['categories'][category]+=1;summary['paired_image_code']+=1
                            image_provenance={'poster':'synthetic_render_provided_by_dataset','vcg':'paper_or_open_repository_reference_image','cosyn':'synthetic_render_provided_by_dataset','datikz':'arxiv_or_synthetic_tikz_render_provided_by_dataset','revision':'dataset_provided_before_edit_render','broken_drawio':'dataset_provided_reference_image','omni':'mixed_collected_or_synthetic_diagram_provided_by_dataset','vinci':'aggregated_dataset_render_or_reference_image'}.get(profile,'dataset_provided_image')
                            code_provenance={'poster':'dataset_svg_template_source','vcg':'reconstructed_mxgraph_xml','cosyn':'synthetic_generation_source','datikz':'arxiv_or_synthetic_tikz_source','revision':'dataset_input_svg_before_edit','broken_drawio':'dataset_target_or_annotation_xml_unverified','omni':'dataset_provided_or_generated_diagram_code','vinci':'aggregated_or_refined_generation_source'}.get(profile,'dataset_provided_code')
                            record.update({'image_provenance':image_provenance,'gold_code_provenance':code_provenance,'clean_file':str(output.relative_to(root)),'clean_row':file_stat['accepted']-1,'pairing':'provided_image_and_code','format':fmt,'category':category,'code_key':code_key,'image_key':image_key,'image_sha256':image_sha,'code_sha256':code_sha,'image_info':info,'structurally_complete':True,'code_execution_checked':False})
                            if fmt=='asymptote':record['syntax_validation_backend']=asymptote_support().RUNTIME_VERSION
                            if profile=='revision':record.update({'alignment_role':'before_edit_input','asset_key':'panels','panel_assets':panel_metadata})
                            mf.write(json.dumps(record,ensure_ascii=False)+'\n')
                            case_group='vcg' if profile=='vcg' else ('poster' if category=='poster' else ('chart' if category=='chart' else None))
                            if case_group and case_counts[case_group]<summary['case_targets'][case_group]:
                                case_counts[case_group]+=1;cd=cases/f'{case_group}_{case_counts[case_group]:02d}';cd.mkdir(exist_ok=True)
                                suffix={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp','GIF':'.gif'}.get(info['format'],'.img');(cd/('reference'+suffix)).write_bytes(image)
                                extension={'drawio':'.drawio','svg':'.svg','python':'.py','tikz':'.tex','asymptote':'.asy','mermaid':'.mmd','plantuml':'.puml','vegalite':'.json','html':'.html'}[fmt]
                                (cd/('ground_truth'+extension)).write_text(code)
                                # Runtime data is part of the code pair; keep it with test cases.
                                for key in ('data','metadata'):
                                    if row.get(key) is not None:
                                        try:write_json(cd/(key+'.json'),row[key])
                                        except TypeError:pass
                                write_json(cd/'case.json',record)
                        row_index+=len(original_rows)
                        if selected:
                            table=pa.Table.from_batches([batch]).take(pa.array(selected,type=pa.int64()))
                            if writer is None:writer=pq.ParquetWriter(output,table.schema,compression='zstd')
                            writer.write_table(table)
                        db.commit()
                finally:
                    if writer is not None:writer.close()
                print(json.dumps({'event':'curated_file','source':source.name,**file_stat}),flush=True)
                for key in ('reasons','formats','categories'):stats[key]=dict(stats[key])
                summary['sources'][source.name]=stats;write_json(reports/'summary.json',summary)
                for key in ('reasons','formats','categories'):stats[key]=collections.Counter(stats[key])
        for key in ('reasons','formats','categories'):stats[key]=dict(stats[key])
        summary['sources'][source.name]=stats;write_json(reports/'summary.json',summary)
    summary['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());summary['case_counts']=dict(case_counts);write_json(reports/'summary.json',summary)
    db.close();print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--only',nargs='*');p.add_argument('--batch-size',type=int,default=16);a=p.parse_args();curate(a.root,a.only,a.batch_size)
