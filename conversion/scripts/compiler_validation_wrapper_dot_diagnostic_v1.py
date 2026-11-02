"""Finite5-pair method diagnostic; cached DOT syntax only, no layout/conversion.
All raw source/parsed DOT JSON stays on HKUST. Export only structural metadata.
"""
import collections,hashlib,json,os,signal,sqlite3,subprocess,time
from pathlib import Path
import networkx as nx
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_validation_v1/python_graphviz_reservoir_20261101_v1';D=R/'release/compiler_validation_v1/cluster_audit_20261101_v1';O=R/'release/compiler_validation_v1/python_wrapper_dot_method_diagnostic_20261101_v1';DOT=R/'conversion/runtime/graphviz/bin/dot'
SEED='hkust-compiler-wrapper-dot-diagnostic-20261101-v1'
SHAPE={'shape','sides','peripheries','fixedsize','orientation','regular','skew','distortion','width','height','rects'}
STYLE={'style','color','fillcolor','pencolor','fontcolor','fontname','fontsize','penwidth','margin','gradientangle','colorscheme','xlabel','labelloc','labeljust','imagescale'}
PORTS={'tailport','headport','tailclip','headclip','lhead','ltail'}
EDGE_STYLE=STYLE|PORTS|{'arrowhead','arrowtail','arrowsize','dir','constraint','weight','minlen','decorate'}
GRAPH_STYLE={'rankdir','ranksep','nodesep','splines','concentrate','compound','overlap','pack','packmode','ordering','outputorder','newrank','dpi','size','ratio','sep','esep','pad','margin','bgcolor','fontname','fontsize','fontcolor','style','color','pencolor','fillcolor','penwidth','labeljust','labelloc'}
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(x):return (json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
def val(v):return str(v)
def fields(o,keys):return {k:val(o[k]) for k in sorted(keys) if k in o}
def style_vector(o,kind):
 return blob(fields(o,SHAPE|STYLE if kind=='node' else EDGE_STYLE)).decode().strip()
def degree_hist(g):return dict(collections.Counter(str((g.in_degree(n),g.out_degree(n))) for n in g))
def parse(record,identifier,out):
 for key in ('source_render_dot','source_render_svg','execution_audit'):
  if not isinstance(record.get(key),str):raise ValueError('missing_cached_source_field:'+key)
 dotpath=(R/record['source_render_dot']).resolve(strict=True)
 if not dotpath.is_relative_to(R/'clean'):raise ValueError('dot_not_in_clean')
 b=dotpath.read_bytes()
 if len(b)>4*1024*1024:raise ValueError('dot_source_budget')
 proc=subprocess.run([str(DOT),'-Tdot_json'],input=b,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
 if proc.returncode:raise ValueError('dot_json_parse_failed:'+proc.stderr.decode(errors='replace')[:200])
 if len(proc.stdout)>16*1024*1024:raise ValueError('dot_json_output_budget')
 document=json.loads(proc.stdout);(out/(identifier+'.dot_json.json')).write_bytes(proc.stdout)
 objects=document.get('objects',[]);nodeobjs=[o for o in objects if not ('nodes' in o or 'subgraphs' in o or 'edges' in o)];ids={o['_gvid'] for o in nodeobjs}
 g=nx.MultiDiGraph() if document.get('directed') else nx.MultiGraph()
 for o in nodeobjs:g.add_node(o['_gvid'],signature=style_vector(o,'node'))
 edges=document.get('edges',[])
 for e in edges:
  if e.get('tail') not in ids or e.get('head') not in ids:raise ValueError('edge_endpoint_not_semantic_node')
  g.add_edge(e['tail'],e['head'],signature=style_vector(e,'edge'))
 index={o['_gvid']:i for i,o in enumerate(nodeobjs)}
 sem={'directed':document.get('directed'),'strict':document.get('strict'),'graph_style':fields(document,GRAPH_STYLE),'nodes':[{'index':index[o['_gvid']],'shape_and_style':fields(o,SHAPE|STYLE),'label_sha256':sha(str(o.get('label',o.get('name',''))).encode()),'label_kind':'html' if str(o.get('label','')).startswith('<') else 'text'} for o in nodeobjs],'edges':[{'tail':index[e['tail']],'head':index[e['head']],'ports_style':fields(e,EDGE_STYLE),'label_sha256':sha(str(e.get('label','')).encode())} for e in edges],'subgraphs':[{'node_members':sorted(index[i] for i in o.get('nodes',[]) if i in index),'style':fields(o,GRAPH_STYLE)} for o in objects if 'nodes' in o or 'subgraphs' in o]}
 info={'id':identifier,'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'source_data_sha256':record.get('source_data_sha256'),'dot_sha256':sha(b),'dot_bytes':len(b),'dot_json_sha256':sha(proc.stdout),'semantic_ordered_ir_sha256':sha(blob(sem)),'nodes':len(nodeobjs),'edges':len(edges),'subgraphs':len(sem['subgraphs']),'directed':bool(document.get('directed')),'shapes':dict(collections.Counter(o.get('shape','default') for o in nodeobjs)),'node_style_signatures':dict(collections.Counter(sha(blob(fields(o,SHAPE|STYLE))) for o in nodeobjs)),'edge_style_port_signatures':dict(collections.Counter(sha(blob(fields(e,EDGE_STYLE))) for e in edges)),'ports_present':sum(any(k in e for k in PORTS) for e in edges),'graph_style_sha256':sha(blob(sem['graph_style'])),'node_label_hash_multiset_sha256':sha(blob(sorted(n['label_sha256'] for n in sem['nodes']))),'edge_label_hash_multiset_sha256':sha(blob(sorted(e['label_sha256'] for e in sem['edges']))),'degree_histogram':degree_hist(g) if g.is_directed() else dict(collections.Counter(str(g.degree(n)) for n in g)),'layout_created':any(k in document for k in ('bb','_draw_')),'source_svg_sha256':record.get('source_render_svg_sha256')}
 return info,g,sem
class IsoBudget(Exception):pass
def alarm(signum,frame):raise IsoBudget('isomorphism_budget_5s')
def compare(a,b,ga,gb,sa,sb):
 same_shape_attrs=collections.Counter(nx.get_node_attributes(ga,'signature').values())==collections.Counter(nx.get_node_attributes(gb,'signature').values())
 result={'dot_bytes_equal':a['dot_sha256']==b['dot_sha256'],'python_source_bytes_equal':a['source_code_sha256']==b['source_code_sha256'],'source_data_sha_equal':a['source_data_sha256']==b['source_data_sha256'],'original_image_bytes_equal':a['source_image_sha256']==b['source_image_sha256'],'node_count_equal':a['nodes']==b['nodes'],'edge_count_equal':a['edges']==b['edges'],'shape_style_multiset_equal':same_shape_attrs,'edge_style_ports_multiset_equal':a['edge_style_port_signatures']==b['edge_style_port_signatures'],'graph_style_equal':sa['graph_style']==sb['graph_style'],'node_label_multiset_equal':a['node_label_hash_multiset_sha256']==b['node_label_hash_multiset_sha256'],'edge_label_multiset_equal':a['edge_label_hash_multiset_sha256']==b['edge_label_hash_multiset_sha256']}
 if ga.is_directed()!=gb.is_directed() or len(ga)!=len(gb) or ga.number_of_edges()!=gb.number_of_edges():result['topology_isomorphic_ignoring_labels']=False;result['shape_ports_style_isomorphic_ignoring_labels']=False
 else:
  old=signal.signal(signal.SIGALRM,alarm);signal.alarm(5)
  try:
   result['topology_isomorphic_ignoring_labels']=nx.is_isomorphic(ga,gb)
   result['shape_ports_style_isomorphic_ignoring_labels']=nx.is_isomorphic(ga,gb,node_match=nx.algorithms.isomorphism.categorical_node_match('signature',''),edge_match=nx.algorithms.isomorphism.categorical_multiedge_match('signature',''))
  except IsoBudget:result['isomorphism_status']='unknown_budget'
  finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)
 return result

def main():
 O.mkdir(parents=True,exist_ok=False)
 cand=rows(P/'compiler_validation_audited_reservoir.jsonl');dev=rows(D/'compiler_validation_development_ids.jsonl');devmap={r['id']:r for r in dev};cmap={r['id']:r for r in cand};neighbors=collections.defaultdict(lambda:collections.defaultdict(list))
 for e in rows(P/'compiler_validation_cluster_edges.jsonl'):
  x,y=e['left'],e['right']
  if x in devmap and y in cmap:neighbors[y][x].append({k:v for k,v in e.items() if k not in ('left','right')})
  elif y in devmap and x in cmap:neighbors[x][y].append({k:v for k,v in e.items() if k not in ('left','right')})
 pairs=[]
 for c in sorted(cand,key=lambda r:r['reservoir_rank']):
  if c['audit_disposition']!='development_cluster_overlap' or not neighbors.get(c['id']):continue
  d=min(neighbors[c['id']],key=lambda d:sha(blob([SEED,'direct_development_neighbor',c['id'],d])))
  pairs.append((c,devmap[d],neighbors[c['id']][d]))
  if len(pairs)==5:break
 if len(pairs)!=5:raise ValueError('not_enough_direct_development_pairs')
 selection=[{'candidate_id':c['id'],'development_id':d['id'],'candidate_reservoir_rank':c['reservoir_rank'],'pair_evidence':ev} for c,d,ev in pairs]
 (O/'compiler_validation_diagnostic_pairs_frozen.json').write_bytes(blob({'seed':SEED,'selection_rule':'first5 reservoir-ranked development-connected candidates with a direct dev edge; per candidate choose dev neighbor by fixed hash; no DOT comparison consulted','pairs':selection}))
 db=sqlite3.connect('file:'+str(R/'conversion/jobs.sqlite')+'?mode=ro',uri=True,timeout=30);results=[];cache={}
 try:
  for c,d,ev in pairs:
   entries=[]
   for x in (c,d):
    ident=x['id'];rec=json.loads(db.execute('select output_record from jobs where id=?',(ident,)).fetchone()[0])
    if (rec['id'],rec['source_code_sha256'],rec['source_image_sha256'])!=(ident,x['code_sha256'],x['image_sha256']):raise ValueError('indexed_record_original_identity_mismatch')
    if ident not in cache:cache[ident]=parse(rec,ident,O)
    entries.append(cache[ident])
   ia,ga,sa=entries[0];ib,gb,sb=entries[1]
   comparisons=compare(ia,ib,ga,gb,sa,sb)
   results.append({'candidate':ia,'development':ib,'pair_connection_evidence':ev,'all_candidate_direct_development_evidence_counts':dict(collections.Counter(e['evidence'] for es in neighbors[c['id']].values() for e in es)),'candidate_direct_development_neighbors':len(neighbors[c['id']]),'provenance_keys_intersection':sorted(set(c.get('provenance_keys',[]))&set(d.get('provenance_keys',[]))),'comparisons':comparisons})
 finally:db.close()
 summary={'diagnostic_only':True,'frozen_pool':str(P),'seed':SEED,'selected_pairs':selection,'pair_results':results,'dot_parser':{'path':str(DOT),'sha256':sha(DOT.read_bytes()),'args':['-Tdot_json'],'mode':'native syntax/semantic parse only, no layout/render/drawio conversion'},'rule_changes':False,'reservoir_refilled':False,'threshold_changes':False,'heldout_conversion_executions':0,'new_QA_results_viewed':False,'model_calls':0,'all_raw_DOT_and_JSON_remain_HKUST':True,'method_limit':'5 deterministic edge diagnostics, not a population prevalence estimate or an independence proof.'}
 (O/'compiler_validation_method_diagnostic.json').write_bytes(blob(summary));print(json.dumps(summary))
if __name__=='__main__':main()
