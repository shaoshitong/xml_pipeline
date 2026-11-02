#!/usr/bin/env python3
"""Semantic diagnostics for five HKUST img2code cases; no downloads or network.
Matplotlib scripts execute only in a guarded subprocess inside evaluation sandbox.
Metrics compare supplied code baselines, not independently verified image truth.
Default CLI evaluates the five selected formal cases. Historical generic SVG
controls require --mode legacy and use a separate output file.

HKUST examples:
  python evaluate_semantics.py --root /backup/shaoshitong/img2code_20261029
  python evaluate_semantics.py --root ROOT --selection evaluation/selected_results/selection.json --output FORMAL.json
  python evaluate_semantics.py --root ROOT --mode legacy --run baseline5_20261029
"""
import argparse, ast, base64, collections, html, io, itertools, json, math, os, re, subprocess, sys, time, unicodedata, urllib.parse, xml.etree.ElementTree as ET, zlib
from html.parser import HTMLParser
from pathlib import Path


class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_starttag(self,tag,attrs):
        if tag in ('br','p','div','li'):self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('p','div','li'):self.parts.append(' ')


def label(value):
    value=html.unescape(html.unescape(str(value or '')))
    parser=PlainText()
    try:parser.feed(value);value=' '.join(parser.parts)
    except Exception:value=re.sub(r'<[^>]*>',' ',value)
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())


def scores(gold,pred):
    g=collections.Counter(gold);p=collections.Counter(pred);tp=sum((g&p).values());ng=sum(g.values());np=sum(p.values())
    precision=tp/np if np else (1.0 if ng==0 else 0.0);recall=tp/ng if ng else (1.0 if np==0 else 0.0)
    return {'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.,'matched':tp,'gold_count':ng,'pred_count':np}


def label_metrics(gold,pred):
    result=scores(gold,pred);result['word_tokens']=scores(re.findall(r'\w+', ' '.join(gold)),re.findall(r'\w+', ' '.join(pred)))
    result['missing_examples']=[x[:150] for x in (collections.Counter(gold)-collections.Counter(pred)).elements()][:10]
    result['extra_examples']=[x[:150] for x in (collections.Counter(pred)-collections.Counter(gold)).elements()][:10]
    return result


def localtag(node):return node.tag.rsplit('}',1)[-1]


def xml_root(path):
    text=path.read_text()
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('XML DTD/entity is disallowed')
    root=ET.fromstring(text)
    if localtag(root)=='mxfile':
        diagram=next((x for x in root.iter() if localtag(x)=='diagram'),None)
        if diagram is not None and not list(diagram) and diagram.text:
            data=zlib.decompress(base64.b64decode(diagram.text),-15)
            if len(data)>64*1024*1024:raise ValueError('oversized compressed diagram')
            root=ET.fromstring(urllib.parse.unquote(data.decode()))
    return root


def number(value,default=0.):
    try:return float(value)
    except (ValueError,TypeError):return default


def drawio_snapshot(path):
    root=xml_root(path);parents={c:p for p in root.iter() for c in p};cells={}
    for node in root.iter():
        if localtag(node)!='mxCell' or not node.get('id'):continue
        wrapper=parents.get(node);value=node.get('value','')
        if not value and wrapper is not None:value=wrapper.get('label',wrapper.get('value',''))
        geometry=next((x for x in node if localtag(x)=='mxGeometry'),None)
        cells[node.get('id')]={'id':node.get('id'),'label':label(value),'vertex':node.get('vertex')=='1','edge':node.get('edge')=='1','parent':node.get('parent'),'source':node.get('source'),'target':node.get('target'),'style':node.get('style',''),'geometry':geometry}
    children=collections.Counter(c['parent'] for c in cells.values() if c['vertex']);positions={}
    def position(cid,seen=None):
        if cid in positions:return positions[cid]
        if cid not in cells:return (0.,0.,0.,0.)
        seen=set() if seen is None else set(seen)
        if cid in seen:return (0.,0.,0.,0.)
        seen.add(cid);c=cells[cid];g=c['geometry'];px,py,pw,ph=position(c['parent'],seen)
        if g is None:return (px,py,0.,0.)
        x=number(g.get('x'));y=number(g.get('y'));w=number(g.get('width'));h=number(g.get('height'))
        if g.get('relative')=='1':
            x=px+x*pw;y=py+y*ph
            for point in g:
                if localtag(point)=='mxPoint' and point.get('as')=='offset':x+=number(point.get('x'));y+=number(point.get('y'))
        else:x+=px;y+=py
        positions[cid]=(x,y,w,h);return positions[cid]
    vertices=[];blank_groups=0;labels=[]
    for cid,c in cells.items():
        if c['label'] and (c['vertex'] or c['edge']):labels.append(c['label'])
        if not c['vertex']:continue
        blank_group=not c['label'] and (children[cid]>0 or 'group;' in c['style'] or c['style']=='group')
        if blank_group:blank_groups+=1;continue
        vertices.append({'id':cid,'label':c['label'],'bbox':position(cid)})
    if vertices:
        xmin=min(v['bbox'][0] for v in vertices);ymin=min(v['bbox'][1] for v in vertices);xmax=max(v['bbox'][0]+v['bbox'][2] for v in vertices);ymax=max(v['bbox'][1]+v['bbox'][3] for v in vertices)
    else:xmin=ymin=0.;xmax=ymax=1.
    width=max(xmax-xmin,1e-8);height=max(ymax-ymin,1e-8)
    for v in vertices:
        x,y,w,h=v['bbox'];v['normalized_bbox']=[(x-xmin)/width,(y-ymin)/height,w/width,h/height]
    edges=[];unresolved=0;edge_count=0
    for c in cells.values():
        if not c['edge']:continue
        edge_count+=1;a=cells.get(c['source'],{}).get('label','');b=cells.get(c['target'],{}).get('label','')
        if not a or not b:unresolved+=1;continue
        style=dict(x.split('=',1) for x in c['style'].split(';') if '=' in x)
        start=style.get('startArrow','none') not in ('','none');end=style.get('endArrow','classic') not in ('','none')
        if start and not end:edges.append((b,a))
        elif start and end:edges.extend([(a,b),(b,a)])
        else:edges.append((a,b))
    missing_binding=sum(c['edge']and(not c['source']or not c['target'])for c in cells.values())
    return {'editable_vertices':sum(c['vertex'] for c in cells.values()),'scored_vertices':len(vertices),'blank_group_vertices_excluded':blank_groups,'unlabeled_leaf_vertices':sum(not v['label'] for v in vertices),'xml_edges':edge_count,'resolved_directed_edges':len(edges),'edges_missing_source_or_target':missing_binding,'edges_excluded_unlabeled_endpoint':unresolved,'labels':labels,'vertices':vertices,'edges':edges,'content_bounds':[xmin,ymin,width,height]}


def assignment(matrix):
    """Exact small assignment, greedy large assignment; matrix may be rectangular."""
    n=len(matrix);m=len(matrix[0]) if n else 0
    if not n or not m:return []
    if n>m:return [(j,i) for i,j in assignment([list(x) for x in zip(*matrix)])]
    if m<=8:
        best=min(itertools.permutations(range(m),n),key=lambda cols:sum(matrix[i][cols[i]] for i in range(n)))
        return list(enumerate(best))
    remaining=set(range(m));pairs=[]
    for i in sorted(range(n),key=lambda x:min(matrix[x])):
        j=min(remaining,key=lambda x:matrix[i][x]);pairs.append((i,j));remaining.remove(j)
    return pairs


def layout_metrics(gold,pred):
    g=collections.defaultdict(list);p=collections.defaultdict(list)
    for v in gold['vertices']:
        if v['label']:g[v['label']].append(v['normalized_bbox'])
    for v in pred['vertices']:
        if v['label']:p[v['label']].append(v['normalized_bbox'])
    center=[];size=[]
    for text in set(g)&set(p):
        def cost(a,b):return sum(abs(x-y) for x,y in zip(a,b))
        matrix=[[cost(a,b) for b in p[text]] for a in g[text]]
        for i,j in assignment(matrix):
            a=g[text][i];b=p[text][j];center.append(((a[0]+a[2]/2-b[0]-b[2]/2)**2+(a[1]+a[3]/2-b[1]-b[3]/2)**2)/2);size.append((abs(a[2]-b[2])+abs(a[3]-b[3]))/2)
    return {'matched_labeled_nodes':len(center),'center_rmse_content_normalized':math.sqrt(sum(center)/len(center)) if center else None,'size_mae_content_normalized':sum(size)/len(size) if size else None,'normalization':'Each diagram content bounding box is independently mapped to [0,1]^2; global translation/scale are intentionally removed. Blank groups excluded.'}


def compare_drawio(gold,pred):
    g=drawio_snapshot(gold);p=drawio_snapshot(pred)
    keys=('editable_vertices','scored_vertices','blank_group_vertices_excluded','unlabeled_leaf_vertices','xml_edges','resolved_directed_edges','edges_missing_source_or_target','edges_excluded_unlabeled_endpoint')
    return {'ok':True,'gold':{k:g[k] for k in keys},'prediction':{k:p[k] for k in keys},'text_labels':label_metrics(g['labels'],p['labels']),'directed_label_edges':scores(g['edges'],p['edges']),'layout':layout_metrics(g,p),'note':'Edge endpoints require nonempty exact normalized labels; unresolved/group-only endpoints are reported separately. Gold XML is VCG restored source, not independently verified image truth.'}


def svg_snapshot(path):
    root=xml_root(path)
    if localtag(root)!='svg':raise ValueError('SVG root expected')
    counts=collections.Counter(localtag(n) for n in root.iter());labels=[label(' '.join(n.itertext())) for n in root.iter() if localtag(n)=='text'];labels=[x for x in labels if x]
    return {'labels':labels,'elements':dict(counts),'total_elements':sum(counts.values()),'graphic_elements':sum(counts[k] for k in ('path','rect','circle','ellipse','polygon','polyline','line','text','image')),'text_elements':counts['text']}


def compare_svg(gold,pred):
    g=svg_snapshot(gold);p=svg_snapshot(pred)
    return {'ok':True,'gold':{k:v for k,v in g.items() if k!='labels'},'prediction':{k:v for k,v in p.items() if k!='labels'},'text_labels':label_metrics(g['labels'],p['labels']),'note':'Element counts depend on representation; matching counts do not imply visual equality. Paths/outlines cannot supply recoverable text labels.'}


ALLOWED_IMPORTS={'matplotlib','numpy','math','random','scipy','seaborn','pandas','statistics','itertools','collections'}
BANNED_NAMES={'open','exec','eval','compile','input','breakpoint','getattr','setattr','delattr','globals','locals','vars','dir','__import__','help','exit','quit'}
BANNED_ATTRS={'os','sys','socket','subprocess','ctypes','ctypeslib','f2py','distutils','DataSource','get_sample_data','get_data_path','get_cachedir','get_configdir','fromfile','fromregex','tofile','memmap','load','loadtxt','loads','load_dataset','load_npz','loadmat','read','read_csv','read_excel','read_json','read_parquet','read_pickle','read_sql','read_html','read_table','read_fwf','read_hdf','read_feather','read_stata','read_sas','read_spss','read_orc','read_clipboard','to_clipboard','to_hdf','to_feather','to_stata','open_file_cm','genfromtxt','imread','imsave','save','savez','savez_compressed','savetxt','dump','dumps','to_csv','to_excel','to_json','to_pickle','to_parquet','to_sql','system','popen','fork','spawn','unlink','remove','rmdir','mkdir','makedirs','chdir','write','write_text','write_bytes','open','urlopen','urlretrieve','request','connect','send','sendall','getattr','setattr','__subclasses__'}


def guard_source(code):
    tree=ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            names=[x.name for x in node.names] if isinstance(node,ast.Import) else [node.module or '']
            if isinstance(node,ast.ImportFrom) and node.level:raise ValueError('relative import rejected')
            if any(n.split('.')[0] not in ALLOWED_IMPORTS or any(part.startswith('_') or part in {'io','lib','testing','cbook','backends','backend_bases','ctypeslib','distutils','f2py','datasets'} for part in n.split('.')[1:]) for n in names):raise ValueError('import outside plotting allowlist')
            if isinstance(node,ast.ImportFrom) and any(x.name=='*' or x.name.startswith('_') or x.name in BANNED_ATTRS for x in node.names):raise ValueError('unsafe imported helper rejected')
        if isinstance(node,ast.Name) and node.id in BANNED_NAMES:raise ValueError('forbidden dynamic/filesystem builtin: '+node.id)
        if isinstance(node,ast.Attribute) and (node.attr.startswith('_') or node.attr in BANNED_ATTRS):raise ValueError('forbidden filesystem/network/dynamic attribute: '+node.attr)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='use':
            style_call=isinstance(node.func.value,ast.Attribute) and node.func.value.attr=='style'
            if style_call:
                try:styles=ast.literal_eval(node.args[0]);styles=[styles] if isinstance(styles,str) else styles
                except Exception:raise ValueError('plot style must be literal installed style names')
                if not isinstance(styles,(list,tuple)) or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',x) or '..' in x for x in styles):raise ValueError('external/file plot style rejected')
            elif not node.args or not isinstance(node.args[0],ast.Constant) or str(node.args[0].value).lower()!='agg':raise ValueError('only Agg plotting backend allowed')
    return tree


def capture_worker(source,output,sandbox):
    code=source.read_text();tree=guard_source(code)
    sandbox.mkdir(parents=True,exist_ok=True);os.chdir(sandbox);os.environ['MPLBACKEND']='Agg';os.environ['MPLCONFIGDIR']=str(sandbox/'mplconfig')
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.collections import PathCollection
    np.random.seed(0)
    import random;random.seed(0)
    captures={}
    def clean(values):
        try:
            arr=np.asarray(values,dtype=float).reshape(-1);return arr
        except Exception:return np.array([],dtype=float)
    def series(x,y):
        x=clean(x);y=clean(y);n=min(len(x),len(y));x=x[:n];y=y[:n];valid=np.isfinite(x)&np.isfinite(y);x=x[valid];y=y[valid];count=len(x)
        if count>4096:ids=np.linspace(0,count-1,4096).astype(int);x=x[ids];y=y[ids]
        return {'x':x.tolist(),'y':y.tolist(),'point_count':count,'sampled_points':len(x)}
    def snapshot(*args,**kwargs):
        for num in plt.get_fignums():
            fig=plt.figure(num)
            try:fig.canvas.draw()
            except Exception:pass
            axes=[]
            for ax in fig.axes:
                item={'bbox':list(ax.get_position().bounds),'xlim':list(ax.get_xlim()),'ylim':list(ax.get_ylim()),'xscale':ax.get_xscale(),'yscale':ax.get_yscale(),'title':label(ax.get_title()),'xlabel':label(ax.get_xlabel()),'ylabel':label(ax.get_ylabel()),'xticks':clean(ax.get_xticks()).tolist(),'yticks':clean(ax.get_yticks()).tolist(),'xtick_labels':[label(t.get_text()) for t in ax.get_xticklabels()],'ytick_labels':[label(t.get_text()) for t in ax.get_yticklabels()],'legend':[label(t.get_text()) for t in ax.get_legend().get_texts()] if ax.get_legend() else [],'lines':[],'scatters':[]}
                for line in ax.lines:
                    data=series(line.get_xdata(),line.get_ydata());data.update({'label':label(line.get_label()) if not str(line.get_label()).startswith('_') else '', 'linestyle':str(line.get_linestyle()),'marker':str(line.get_marker())});item['lines'].append(data)
                for coll in ax.collections:
                    if isinstance(coll,PathCollection):
                        try:points=np.asarray(coll.get_offsets(),dtype=float);data=series(points[:,0],points[:,1]);data['label']=label(coll.get_label()) if not str(coll.get_label()).startswith('_') else '';item['scatters'].append(data)
                        except Exception:pass
                axes.append(item)
            captures[str(num)]={'size_inches':list(fig.get_size_inches()),'dpi':float(fig.dpi),'axes':axes}
    plt.show=snapshot;plt.savefig=snapshot;Figure.savefig=lambda self,*a,**k:snapshot();plt.close=lambda *a,**k:None
    import socket
    def denied(*a,**k):raise RuntimeError('network/system access denied during semantic capture')
    socket.socket=denied;socket.create_connection=denied;socket.getaddrinfo=denied
    subprocess.Popen=denied;subprocess.run=denied;os.system=denied;os.popen=denied
    import builtins
    real_import=builtins.__import__
    def safe_import(name,globals=None,locals=None,fromlist=(),level=0):
        if level or name.split('.')[0] not in ALLOWED_IMPORTS:raise ImportError('capture import rejected')
        return real_import(name,globals,locals,fromlist,level)
    safe={k:v for k,v in vars(builtins).items() if k not in BANNED_NAMES and k not in ('__import__','__loader__','__spec__')};safe['__import__']=safe_import;safe['print']=lambda *a,**k:None
    exec(compile(tree,str(source),'exec'),{'__builtins__':safe,'__name__':'__main__'})
    snapshot()
    result={'ok':True,'figures':list(captures.values()),'note':'Plot objects captured with savefig/show disabled; data arrays stay in remote evaluation sandbox, not stdout.'}
    output.write_text(json.dumps(result,allow_nan=False))


def run_capture(source,sandbox):
    sandbox.mkdir(parents=True,exist_ok=True);output=sandbox/'capture.json';output.unlink(missing_ok=True);env=dict(os.environ,MPLBACKEND='Agg',MPLCONFIGDIR=str(sandbox/'mplconfig'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(45,45));resource.setrlimit(resource.RLIMIT_FSIZE,(128*1024*1024,128*1024*1024));resource.setrlimit(resource.RLIMIT_AS,(6*1024**3,6*1024**3))
    try:
        run=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--capture',str(source.resolve()),'--capture-output',str(output.resolve()),'--sandbox',str(sandbox.resolve())],cwd=sandbox,env=env,capture_output=True,text=True,timeout=65,preexec_fn=limits)
        (sandbox/'worker.stderr.txt').write_text(run.stderr)
        if output.is_file():return json.loads(output.read_text())
        return {'ok':False,'error':'capture subprocess failed','returncode':run.returncode,'stderr_log':str(sandbox/'worker.stderr.txt')}
    except Exception as e:return {'ok':False,'error':type(e).__name__+': '+str(e)[:400]}


def nearest_distance(a,b,np):
    if not len(a) or not len(b):return None
    vals=[]
    for start in range(0,len(a),256):
        delta=a[start:start+256,None,:]-b[None,:,:];vals.append(np.sqrt(np.min(np.sum(delta*delta,axis=2),axis=1)))
    return float(np.mean(np.concatenate(vals)))


def cloud_metric(g,p,axis,np):
    a=np.column_stack((g['x'],g['y']));b=np.column_stack((p['x'],p['y']));scale=np.array([max(abs(axis['xlim'][1]-axis['xlim'][0]),1e-8),max(abs(axis['ylim'][1]-axis['ylim'][0]),1e-8)])
    a=a/scale;b=b/scale;ab=nearest_distance(a,b,np);ba=nearest_distance(b,a,np)
    return {'mean_gold_to_prediction_normalized':ab,'mean_prediction_to_gold_normalized':ba,'symmetric_mean_normalized':(ab+ba)/2 if ab is not None and ba is not None else None,'gold_point_count':g['point_count'],'prediction_point_count':p['point_count'],'gold_sampled_points':g['sampled_points'],'prediction_sampled_points':p['sampled_points']}


def line_metric(g,p,axis,np):
    gx=np.asarray(g['x']);gy=np.asarray(g['y']);px=np.asarray(p['x']);py=np.asarray(p['y']);result={'gold_point_count':g['point_count'],'prediction_point_count':p['point_count']}
    if len(gx)<2 or len(px)<2:return {**result,'normalized_rmse':None,'reason':'fewer_than_two_points'}
    gi=np.argsort(gx);pi=np.argsort(px);gx,gy=gx[gi],gy[gi];px,py=px[pi],py[pi];gx,idx=np.unique(gx,return_index=True);gy=gy[idx];px,idx=np.unique(px,return_index=True);py=py[idx]
    if len(gx)<2 or len(px)<2:
        cloud=cloud_metric(g,p,axis,np);return {**result,'normalized_rmse':None,'vertical_or_duplicate_x_cloud':cloud}
    lo=max(gx.min(),px.min());hi=min(gx.max(),px.max());yrange=max(abs(axis['ylim'][1]-axis['ylim'][0]),1e-8)
    if hi<=lo:return {**result,'normalized_rmse':None,'reason':'no_common_x_domain','reference_domain_coverage':0.}
    grid=np.linspace(lo,hi,256);delta=(np.interp(grid,px,py)-np.interp(grid,gx,gy))/yrange
    return {**result,'normalized_rmse':float(np.sqrt(np.mean(delta*delta))),'reference_domain_coverage':float((hi-lo)/max(gx.max()-gx.min(),1e-8)),'common_x_domain':[float(lo),float(hi)],'normalization':'Reference y-axis span; linear interpolation on common x domain. Curves are treated as single-valued y(x); nonmonotone paths need visual review.'}


def compare_series(gold,pred,axis,kind,np):
    if not gold or not pred:return {'gold_series':len(gold),'prediction_series':len(pred),'matched_series':0,'matches':[]}
    details=[];matrix=[]
    for g in gold:
        row=[];metrics=[]
        for p in pred:
            metric=line_metric(g,p,axis,np) if kind=='line' else cloud_metric(g,p,axis,np);metrics.append(metric)
            distance=metric.get('normalized_rmse') if kind=='line' else metric.get('symmetric_mean_normalized')
            if distance is None:distance=metric.get('vertical_or_duplicate_x_cloud',{}).get('symmetric_mean_normalized',2.)
            row.append(float(distance if distance is not None else 2.)+(0.1 if g.get('label') and p.get('label') and g['label']!=p['label'] else 0.))
        matrix.append(row);details.append(metrics)
    matches=[]
    for i,j in assignment(matrix):matches.append({'gold_index':i,'prediction_index':j,'gold_label':gold[i].get('label',''),'prediction_label':pred[j].get('label',''),**details[i][j]})
    return {'gold_series':len(gold),'prediction_series':len(pred),'matched_series':len(matches),'matches':matches}


def compare_chart(gold,pred):
    import numpy as np
    if not gold.get('ok') or not pred.get('ok'):return {'ok':False,'gold_capture':{k:v for k,v in gold.items() if k!='figures'},'prediction_capture':{k:v for k,v in pred.items() if k!='figures'}}
    ga=[a for f in gold['figures'] for a in f['axes']];pa=[a for f in pred['figures'] for a in f['axes']]
    matrix=[[sum(abs(x-y) for x,y in zip(g['bbox'],p['bbox'])) for p in pa] for g in ga];axes=[]
    for gi,pi in assignment(matrix):
        g=ga[gi];p=pa[pi];xspan=max(abs(g['xlim'][1]-g['xlim'][0]),1e-8);yspan=max(abs(g['ylim'][1]-g['ylim'][0]),1e-8)
        bounds={'xlim_mae_normalized':sum(abs(a-b) for a,b in zip(g['xlim'],p['xlim']))/2/xspan,'ylim_mae_normalized':sum(abs(a-b) for a,b in zip(g['ylim'],p['ylim']))/2/yspan,'axes_bbox_mae_figure_normalized':sum(abs(a-b) for a,b in zip(g['bbox'],p['bbox']))/4,'gold_xlim':g['xlim'],'prediction_xlim':p['xlim'],'gold_ylim':g['ylim'],'prediction_ylim':p['ylim'],'gold_xscale':g['xscale'],'prediction_xscale':p['xscale'],'gold_yscale':g['yscale'],'prediction_yscale':p['yscale']}
        tick_values={}
        for key,span in [('xticks',xspan),('yticks',yspan)]:
            a=np.asarray(g[key]);b=np.asarray(p[key]);ab=nearest_distance(a.reshape(-1,1)/span,b.reshape(-1,1)/span,np);ba=nearest_distance(b.reshape(-1,1)/span,a.reshape(-1,1)/span,np);tick_values[key]={'gold_count':len(a),'prediction_count':len(b),'symmetric_nearest_normalized':(ab+ba)/2 if ab is not None and ba is not None else None}
        axes.append({'gold_axis':gi,'prediction_axis':pi,'bounds':bounds,'axis_labels':label_metrics([x for x in [g['title'],g['xlabel'],g['ylabel']] if x],[x for x in [p['title'],p['xlabel'],p['ylabel']] if x]),'tick_labels':label_metrics(g['xtick_labels']+g['ytick_labels'],p['xtick_labels']+p['ytick_labels']),'tick_values':tick_values,'legend_labels':label_metrics(g['legend'],p['legend']),'lines':compare_series(g['lines'],p['lines'],g,'line',np),'scatter':compare_series(g['scatters'],p['scatters'],g,'scatter',np)})
    line_errors=[match['normalized_rmse'] for axis in axes for match in axis['lines']['matches'] if match.get('normalized_rmse') is not None]
    scatter_errors=[match['symmetric_mean_normalized'] for axis in axes for match in axis['scatter']['matches'] if match.get('symmetric_mean_normalized') is not None]
    aggregate={'mean_matched_line_normalized_rmse':sum(line_errors)/len(line_errors) if line_errors else None,'mean_matched_scatter_symmetric_distance_normalized':sum(scatter_errors)/len(scatter_errors) if scatter_errors else None,'gold_scatter_points':sum(c['point_count'] for a in ga for c in a['scatters']),'prediction_scatter_points':sum(c['point_count'] for a in pa for c in a['scatters']),'legend_labels':label_metrics([x for a in ga for x in a['legend']],[x for a in pa for x in a['legend']])}
    return {'ok':True,'aggregate':aggregate,'gold_figures':len(gold['figures']),'prediction_figures':len(pred['figures']),'gold_axes':len(ga),'prediction_axes':len(pa),'matched_axes':len(axes),'axes':axes,'note':'Numeric comparisons use supplied plotting code as baseline. Visually inferred model data need not equal hidden original data. Captured arrays remain in the HKUST sandbox; this summary contains aggregate errors and counts only.'}


def finite_json(value):
    if isinstance(value,float):return value if math.isfinite(value) else None
    if isinstance(value,dict):return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [finite_json(v) for v in value]
    return value


def safe_compare(function,*args):
    try:return function(*args)
    except Exception as e:return {'ok':False,'error':type(e).__name__+': '+str(e)[:600]}


FORMAL_CASES={
 'line_chart':{'extension':'py','reasoning':'max','per_call_output_budget':20000,'workflow':'two_turns_one_feedback',
   'directories':['baseline_native_20261029/line_chart/pass1','baseline_native_20261029/line_chart/pass2']},
 'scatter_chart':{'extension':'py','reasoning':'max','per_call_output_budget':32768,'workflow':'two_turns_one_feedback',
   'directories':['scatter_rescue_20261029/scatter_chart/pass1','scatter_rescue_20261029/scatter_chart/pass2']},
 'framework_simple':{'extension':'drawio','reasoning':'max','per_call_output_budget':32768,'workflow':'two_turns_one_feedback',
   'directories':['baseline_xml_20261029/framework_simple/pass1','baseline_xml_20261029/framework_simple/pass2']},
 'framework_complex':{'extension':'drawio','reasoning':'high','per_call_output_budget':65536,'workflow':'file_and_render_tool_loop',
   'directories':['toolloop_high_20261029/framework_complex/iteration_01','toolloop_high_20261029/framework_complex/final']},
 'academic_poster':{'extension':'html','reasoning':'high','per_call_output_budget':65536,'workflow':'two_turns_one_feedback',
   'directories':['academic_poster_high_20261029/academic_poster/pass1','academic_poster_high_20261029/academic_poster/pass2']}}


def read_json_optional(path):
    if not path.is_file():return None
    try:return json.loads(path.read_text())
    except (OSError,ValueError)as exc:return {'read_error':type(exc).__name__+': '+str(exc)[:300]}


def task_path(root,path,base=None):
    path=Path(path)
    resolved=(path if path.is_absolute()else(base or root)/path).resolve()
    if not resolved.is_relative_to(root.resolve()):raise ValueError('selection path is outside the task root: '+str(path))
    return resolved


def write_summary(root,output,summary):
    output=Path(output).resolve()
    if output==(root/'evaluation/semantic_summary.json').resolve():
        raise ValueError('evaluation/semantic_summary.json is historical; choose a separate --output')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_suffix(output.suffix+'.tmp')
    temporary.write_text(json.dumps(finite_json(summary),ensure_ascii=False,indent=2,allow_nan=False))
    temporary.replace(output)
    return output


def evaluate_formal(root,selection=None,output=None,poster_text_diagnostics=None):
    """Use selection.json's {mapping: {case: [evaluation-relative directories]}}.

    Only the five formal case IDs are admitted. Missing formal entries fall back
    to the recorded final runs above; poster_svg remains a historical control.
    Poster DOM metrics are referenced separately rather than recomputed with a
    different tokenizer or presented as whole-image OCR accuracy.
    """
    evaluation=root/'evaluation';default_selection=evaluation/'selected_results/selection.json'
    selection_path=task_path(root,selection)if selection else default_selection
    if selection is not None and not selection_path.is_file():raise ValueError('selection file does not exist: '+str(selection_path))
    selected=read_json_optional(selection_path)if selection_path.is_file()else None
    if selection_path.is_file()and(not isinstance(selected,dict)or not isinstance(selected.get('mapping'),dict)):
        raise ValueError('selection must contain a mapping object from case IDs to directory arrays')
    mapping={}if selected is None else selected['mapping']
    summary={'mode':'formal5','created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
      'selection_file':str(selection_path)if selected is not None else None,
      'selection_source':'selection.json plus fixed fallback for absent formal IDs'if selected is not None else'fixed five formal runs',
      'excluded_selection_entries':sorted(set(mapping)-set(FORMAL_CASES)),
      'method':'Offline supplied-source structure/numeric diagnostics plus existing render metadata; no model inference or image generation.',
      'limitations':['Different budgets and workflows: these selected examples are not a uniform benchmark.',
        'Output budgets are test settings, not native model output limits. Earlier environment/configuration failures are retained separately.',
        'VCG gold is reconstructed XML, not original author source or independently verified image truth.',
        'Line RMSE uses 256 interpolated samples on the common x domain, normalized by the reference y-axis span; it does not prove analytic-function recovery.',
        'An unresolved XML edge is not automatically a visually incorrect arrow. Missing source/target bindings are reported explicitly.',
        'Poster DOM diagnostics are optional independent references; text embedded in image assets is not covered, so DOM F1 is not full-image OCR accuracy.',
        'AST/import guards and resource limits are defensive controls for these known plotting cases, not a general security sandbox.'],
      'cases':{}}
    for case,config in FORMAL_CASES.items():
        directories=mapping.get(case,config['directories'])
        if not isinstance(directories,list)or not directories or not all(isinstance(p,str)for p in directories):
            raise ValueError('selection mapping must give a nonempty directory array for '+case)
        chosen=[task_path(root,p,evaluation)for p in directories]
        gold=root/'cases'/case/('ground_truth.'+config['extension'])
        known_configuration=chosen[-1]==task_path(root,config['directories'][-1],evaluation)
        record={'format':config['extension'],'gold_code':str(gold)if gold.is_file()else None,
          'selected_final_directory':str(chosen[-1]),'outputs':[],
          'configuration':{k:config[k]if known_configuration else None for k in ('reasoning','per_call_output_budget','workflow')},
          'configuration_note':'Recorded formal test settings'if known_configuration else'Nondefault selection: budget/workflow metadata not inferred'}
        gold_capture=None
        if config['extension']=='py'and gold.is_file():
            gold_capture=run_capture(gold,evaluation/'semantic_sandbox/formal5'/case/'gold')
        for index,directory in enumerate(chosen,1):
            prediction=directory/('prediction.'+config['extension'])
            item={'source_directory':str(directory),'prediction_code':str(prediction),
              'prediction_present':prediction.is_file(),'render':read_json_optional(directory/'render.json')}
            if config['extension']=='html':
                diagnostic=task_path(root,poster_text_diagnostics)if poster_text_diagnostics and directory==chosen[-1]else directory/'text_diagnostics.json'
                item['semantic']={'ok':None,'status':'independent_dom_reference_only',
                  'text_diagnostics_path':str(diagnostic)if diagnostic.is_file()else None,
                  'text_diagnostics':read_json_optional(diagnostic),
                  'note':'Optional existing DOM-text diagnostics; missing means null, not an invented score. No raster-asset text/OCR is included.'}
            elif not prediction.is_file()or not gold.is_file():
                item['semantic']={'ok':False,'error':'missing_prediction_or_gold',
                  'prediction_present':prediction.is_file(),'gold_present':gold.is_file()}
            elif not prediction.read_text().strip():item['semantic']={'ok':False,'error':'empty_prediction_source'}
            elif config['extension']=='drawio':item['semantic']=safe_compare(compare_drawio,gold,prediction)
            else:
                capture=run_capture(prediction,evaluation/'semantic_sandbox/formal5'/case/('selected_'+str(index)))
                item['semantic']=safe_compare(compare_chart,gold_capture,capture)
            record['outputs'].append(item)
        summary['cases'][case]=record
    output=write_summary(root,output or evaluation/'formal5_semantic_summary.json',summary)
    print(json.dumps({'ok':True,'mode':'formal5','summary':str(output),'formal_cases':list(summary['cases']),
      'excluded_selection_entries':summary['excluded_selection_entries'],
      'final_semantics_ok':sum(c['outputs'][-1]['semantic'].get('ok')is True for c in summary['cases'].values()),
      'poster_dom_metrics':'separate optional reference, never implicit OCR accuracy'}),flush=True)
    return summary


def evaluate_legacy(root,run_name,output=None):
    evaluation=root/'evaluation';run=task_path(root,run_name,evaluation);summary={'mode':'legacy','run':run_name,'formal_benchmark':False,'created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'method':'Historical single-run code diagnostics; generic SVG control is not a poster case.','limitations':['VCG gold is reconstructed XML, not original author source or independently verified image truth.','Presto generic SVG background control is historical auxiliary data, never a formal academic-poster test.','Chart numeric distances compare supplied source data with visually inferred data; pixel similarity remains a separate diagnostic.','AST/import guards and resource limits reject filesystem/network code; they are defensive controls for these selected known plotting cases, not a general security sandbox.'],'cases':{}}
    specs=[('framework_simple','drawio','framework_simple'),('framework_complex','drawio','framework_complex'),('line_chart','py','line_chart'),('scatter_chart','py','scatter_chart'),('poster_svg','svg','poster_01')]
    for case,ext,gold_case in specs:
        gold_path=root/'cases'/gold_case/('ground_truth.'+ext);passes={};gold_capture=None
        if ext=='py' and gold_path.is_file():gold_capture=run_capture(gold_path,evaluation/'semantic_sandbox'/case/'gold')
        for number in (1,2):
            prediction=run/case/('pass'+str(number))/('prediction.'+ext)
            if not prediction.is_file() or not gold_path.is_file():passes['pass'+str(number)]={'ok':False,'error':'missing_prediction_or_gold','prediction_present':prediction.is_file(),'gold_present':gold_path.is_file()};continue
            if ext=='drawio':result=safe_compare(compare_drawio,gold_path,prediction)
            elif ext=='svg':result=safe_compare(compare_svg,gold_path,prediction)
            else:
                capture=run_capture(prediction,evaluation/'semantic_sandbox'/case/('pass'+str(number)));result=safe_compare(compare_chart,gold_capture,capture)
            passes['pass'+str(number)]=result
        summary['cases'][case]={'gold_code':str(gold_path),'passes':passes}
    output=write_summary(root,output or evaluation/'legacy_semantics'/(run.name+'.json'),summary)
    print(json.dumps({'ok':True,'mode':'legacy','summary':str(output),'passes_ok':sum(p.get('ok',False) for c in summary['cases'].values() for p in c['passes'].values()),'passes_total':10}),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path)
    p.add_argument('--mode',choices=('formal','legacy'),default='formal')
    p.add_argument('--selection',type=Path,help='Formal {mapping:{case:[evaluation-relative directories]}} JSON; defaults to evaluation/selected_results/selection.json when present')
    p.add_argument('--output',type=Path,help='Separate summary path; the historical evaluation/semantic_summary.json is protected')
    p.add_argument('--poster-text-diagnostics',type=Path,help='Optional existing DOM-text diagnostics JSON for the final academic poster; absent metrics stay null')
    p.add_argument('--run',help='Historical single run; requires --mode legacy')
    p.add_argument('--capture',type=Path);p.add_argument('--capture-output',type=Path);p.add_argument('--sandbox',type=Path);a=p.parse_args()
    if a.capture:
        try:capture_worker(a.capture.resolve(),a.capture_output.resolve(),a.sandbox.resolve())
        except Exception as e:
            a.capture_output.parent.mkdir(parents=True,exist_ok=True);a.capture_output.write_text(json.dumps({'ok':False,'error':type(e).__name__+': '+str(e)[:600]}))
    elif a.root:
        if a.mode=='legacy':
            if a.selection or a.poster_text_diagnostics:p.error('--selection/--poster-text-diagnostics apply only to formal mode')
            evaluate_legacy(a.root.resolve(),a.run or'baseline5_20261029',a.output)
        else:
            if a.run:p.error('--run requires explicit --mode legacy; formal mode uses --selection or the five recorded runs')
            evaluate_formal(a.root.resolve(),a.selection,a.output,a.poster_text_diagnostics)
    else:p.error('--root is required')

if __name__=='__main__':main()
