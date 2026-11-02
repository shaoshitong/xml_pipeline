"""Compare source DOM content against actual XML cells, independently of build counts."""
import collections,html,re,xml.etree.ElementTree as E

def audit(dom,xml,stats):
 cells=list(E.fromstring(xml).iter('mxCell'));by={c.get('id'):c for c in cells};text=lambda x:html.unescape(x);expected=collections.Counter(o['text'] for o in dom['objects'] if o['type']=='text');actual=collections.Counter(text(c.get('value','')) for c in cells if c.get('value'));errors=[]
 if expected!=actual:errors.append({'reason':'source_text_coverage_mismatch','missing':list((expected-actual).elements())[:20],'extra':list((actual-expected).elements())[:20]})
 node_titles={v['title']:'node_'+k for k,v in dom['nodes'].items()};expected_paths=[]
 for obj in dom['objects']:
  if obj.get('edge') and obj.get('tag')=='path' and obj['style']['fill']=='none':
   expected_paths.append(obj);c=by.get(obj['id']);parts=re.split(r'->|--',obj['edge']['title'] or '')
   if c is None or c.get('edge')!='1':errors.append({'reason':'source_connector_missing_native_edge','id':obj['id'],'title':obj['edge']['title']});continue
   if len(parts)!=2 or any(p not in node_titles for p in parts) or c.get('source')!=node_titles.get(parts[0]) or c.get('target')!=node_titles.get(parts[1]):errors.append({'reason':'source_connector_terminal_mismatch','id':obj['id'],'title':obj['edge']['title']})
 for name in node_titles.values():
  c=by.get(name)
  if c is None or c.get('vertex')!='1':errors.append({'reason':'source_node_group_missing','id':name})
 mapped_arrows={a['source_arrow_object'] for a in stats.get('native_graphviz_arrowheads',[])};missing_objects=[o['id'] for o in dom['objects'] if o['id'] not in by and o['id'] not in mapped_arrows]
 if missing_objects:errors.append({'reason':'source_visible_objects_missing','ids':missing_objects[:30],'count':len(missing_objects)})
 return {'ok':not errors,'source_text_runs':sum(expected.values()),'native_text_runs':sum(actual.values()),'source_node_groups':len(node_titles),'source_edge_paths':len(expected_paths),'native_edges':sum(c.get('edge')=='1' for c in cells),'native_arrowheads':len(mapped_arrows),'errors':errors,'scope':'Exact visible DOM text/object representation and Graphviz source title terminal relationships; original-image fidelity remains separately required.'}
