"""Pure typed cached-DOT audit graph. Does not execute source, layout or render."""
import collections,decimal,hashlib,json,re,signal
from html.parser import HTMLParser
import networkx as nx
VERSION='compiler_dot_semantic_cluster_v2'
MAX_IR_NODES=20000
MAX_ISO_SECONDS=3
TEXT_KEYS={'label','xlabel','headlabel','taillabel','tooltip','headtooltip','tailtooltip','edgetooltip','comment'}
DROP={'_gvid','name','id','URL','href','target','class','edgeURL','headURL','tailURL','labelURL','edgehref','headhref','tailhref','labelhref'}
ALIASES={'rect':'box','rectangle':'box'}
DEFAULT_NODE={'shape':'ellipse','fontname':'Times-Roman','fontsize':'14','color':'black','fontcolor':'black','penwidth':'1','width':'0.75','height':'0.5','style':''}
DEFAULT_EDGE={'fontname':'Times-Roman','fontsize':'14','color':'black','fontcolor':'black','penwidth':'1','arrowsize':'1','arrowhead':'normal','arrowtail':'normal','style':''}
COMPASS={'n','ne','e','se','s','sw','w','nw','c','_'}
def raw(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def sha(v):return hashlib.sha256(v).hexdigest()
def scalar(v):
 s=str(v).strip()
 if re.fullmatch(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?',s):
  n=decimal.Decimal(s)
  if not n.is_finite():raise ValueError('nonfinite_semantic_attribute')
  return format(n.normalize(),'f')
 return re.sub(r'\s+',' ',s)
class HtmlLabel(HTMLParser):
 def __init__(self):super().__init__();self.events=[];self.ports={}
 def handle_starttag(self,tag,attrs):
  arr=[]
  for k,v in attrs:
   if k.lower()=='port':v=self.ports.setdefault(v,'p'+str(len(self.ports)))
   elif k.lower() in ('href','src'):v='<ASSET>'
   else:v=scalar(v) if v is not None else None
   arr.append((k, v))
  self.events.append(['start',tag,sorted(arr)])
 def handle_endtag(self,tag):self.events.append(['end',tag])
 def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
 def handle_data(self,data):
  if data.strip():self.events.append(['text'])
def label_structure(o):
 text=str(o.get('label','\\N'));shape=ALIASES.get(o.get('shape'),o.get('shape','ellipse'))
 if text.startswith('<') and text.endswith('>'):
  p=HtmlLabel();p.feed(text[1:-1]);p.close();return ['html',p.events],p.ports
 if shape in ('record','Mrecord'):
  ports={};clean=re.sub(r'<([A-Za-z_][\w]*)>',lambda m:'<'+ports.setdefault(m[1],'p'+str(len(ports)))+'>',text)
  parts=re.split(r'([{}|]|<p\d+>)',clean)
  return ['record',[p if re.fullmatch(r'[{}|]|<p\d+>',p) else 'TEXT' for p in parts if p.strip()]],ports
 return ['plain','nonempty' if text else 'empty'],{}
def attrs(o,kind,directed=True):
 values=dict(DEFAULT_NODE if kind=='node' else DEFAULT_EDGE if kind=='edge' else {})
 if kind=='edge':values['dir']='forward' if directed else 'none'
 for k,v in o.items():
  if k in DROP or k in ('objects','edges','nodes','subgraphs','directed','strict','_subgraph_cnt','tail','head','tailport','headport','lhead','ltail','group'):continue
  if k.startswith('_'):raise ValueError('unhandled_xdot_source_attribute:'+k)
  if k in TEXT_KEYS:
   if k!='label':values[k]='<TEXT>' if str(v) else '<EMPTY>'
   elif kind!='node':values[k]='<TEXT>' if str(v) else '<EMPTY>'
   continue
  if isinstance(v,(dict,list)):raise ValueError('unhandled_nested_DOT_attribute:'+k)
  if k=='style':v=','.join(sorted(set(p.strip() for p in str(v).split(',') if p.strip())))
  if k=='shape':v=ALIASES.get(str(v),str(v))
  values[k]=scalar(v)
 return sorted(values.items())
def normalized_port(value,ports):
 if not value:return None
 parts=str(value).split(':')
 if len(parts)>2:raise ValueError('unparsed_port_syntax')
 if parts[0] in ports:first=ports[parts[0]]
 elif parts[0] in COMPASS:first='compass:'+parts[0]
 else:raise ValueError('unknown_named_port_reference')
 if len(parts)==2:
  if parts[1] not in COMPASS:raise ValueError('unknown_port_compass')
  return first+':'+parts[1]
 return first

def typed_graph(document):
 objects=document.get('objects',[]);subcount=int(document.get('_subgraph_cnt',0));directed=bool(document.get('directed'));g=nx.MultiDiGraph()
 if len(objects)+len(document.get('edges',[]))>MAX_IR_NODES:raise ValueError('typed_IR_node_budget')
 def add(n,kind,a):g.add_node(n,signature=sha(raw([kind,a])))
 def link(a,b,kind):g.add_edge(a,b,signature=kind)
 add(('root',0),'graph_root',{'directed':directed,'strict':bool(document.get('strict')),'attrs':attrs(document,'graph',directed)})
 containers={o['_gvid']:o for o in objects if o['_gvid']<subcount or 'nodes' in o or 'subgraphs' in o or 'edges' in o}
 nodes={o['_gvid']:o for o in objects if o['_gvid'] not in containers};ports={};names={o['name']:('cluster',i) for i,o in containers.items() if 'name' in o}
 for i,o in containers.items():add(('cluster',i),'cluster' if o.get('name','').startswith('cluster') else 'subgraph',attrs(o,'graph',directed))
 groups={}
 for i,o in nodes.items():
  ls,ps=label_structure(o);ports[i]=ps;add(('node',i),'node',[attrs(o,'node',directed),ls]);link(('root',0),('node',i),'root_node')
  if o.get('group'):
   name=o['group']
   if name not in groups:groups[name]=('layout_group',len(groups));add(groups[name],'layout_group',{})
   link(('node',i),groups[name],'layout_group_member')
 edgeids={}
 for e in document.get('edges',[]):
  ei=('edge',e['_gvid']);edgeids[e['_gvid']]=ei
  if e.get('tail') not in nodes or e.get('head') not in nodes:raise ValueError('unresolved_DOT_endpoint')
  add(ei,'edge',attrs(e,'edge',directed))
  tp=normalized_port(e.get('tailport'),ports[e['tail']]);hp=normalized_port(e.get('headport'),ports[e['head']])
  link(('node',e['tail']),ei,('tail:' if directed else 'endpoint:')+str(tp));link(ei,('node',e['head']),('head:' if directed else 'endpoint:')+str(hp))
  for key in ('lhead','ltail'):
   if e.get(key):
    if e[key] not in names:raise ValueError('unknown_cluster_endpoint_reference')
    link(ei,names[e[key]],key)
 children=set()
 for i,o in containers.items():
  ci=('cluster',i)
  for n in o.get('nodes',[]):
   if n not in nodes:raise ValueError('unresolved_cluster_node')
   link(ci,('node',n),'node_member')
  for c in o.get('subgraphs',[]):
   if c not in containers:raise ValueError('unresolved_cluster_child')
   link(ci,('cluster',c),'subgraph_member');children.add(c)
  for e in o.get('edges',[]):
   if e not in edgeids:raise ValueError('unresolved_cluster_edge')
   link(ci,edgeids[e],'edge_member')
 for i in containers:
  if i not in children:link(('root',0),('cluster',i),'root_subgraph')
 return g

def invariant(g):
 colors={n:a['signature'] for n,a in g.nodes(data=True)};history=[]
 for step in range(6):
  history.append(sorted(collections.Counter(colors.values()).items()))
  new={}
  for n in g:
   incoming=sorted((a['signature'],colors[u]) for u,_,a in g.in_edges(n,data=True));outgoing=sorted((a['signature'],colors[v]) for _,v,a in g.out_edges(n,data=True));new[n]=sha(raw([colors[n],incoming,outgoing]))
  colors=new
 return sha(raw([g.number_of_nodes(),g.number_of_edges(),history]))
class IsoUnknown(Exception):pass
def _alarm(signum,frame):raise IsoUnknown('typed_isomorphism_timeout')
def equivalent(a,b):
 if invariant(a)!=invariant(b):return False
 old=signal.signal(signal.SIGALRM,_alarm);signal.alarm(MAX_ISO_SECONDS)
 try:return nx.is_isomorphic(a,b,node_match=nx.algorithms.isomorphism.categorical_node_match('signature',''),edge_match=nx.algorithms.isomorphism.categorical_multiedge_match('signature',''))
 finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)
