import collections,html,re,xml.etree.ElementTree as E
from mermaid_semantic_audit import text
from svg_convert_v3 import unpack

def check(ast,xml,metadata):
 root=E.fromstring(xml);cells={c.get('id'):c for c in root.iter('mxCell')};vertices=dict(ast['vertices']);mapping={g['sourceId']:'node_'+g['uid'] for g in metadata['groups']};issues=[];compact=lambda s:re.sub(r'\s+','',text(s));children=collections.defaultdict(list)
 for c in cells.values():children[c.get('parent')].append(c)
 for sid,source in vertices.items():
  cid=mapping.get(sid);c=cells.get(cid)
  if c is None or c.get('mermaidId')!='n:'+sid:issues.append({'reason':'source_node_identity_missing','source':sid});continue
  label=' '.join(html.unescape(x.get('value','')) for x in children[cid] if x.get('value'))
  if compact(label)!=compact(source.get('text') or sid):issues.append({'reason':'source_node_label_changed','source':sid,'expected':source.get('text'),'actual':label})
 expected=collections.Counter((e['start'],e['end'],compact(e.get('text',''))) for e in ast['edges']);inverse={v:k for k,v in mapping.items()};found=collections.Counter();markers=0
 for c in cells.values():
  if c.get('edge')!='1':continue
  label=' '.join(html.unescape(x.get('value','')) for x in children[c.get('id')] if x.get('value'));key=(inverse.get(c.get('source')),inverse.get(c.get('target')),compact(label));found[key]+=1;s=unpack(c.get('style',''));markers+=sum(s.get(side+'Arrow','none')!='none' for side in ['start','end'])
 if found!=expected:issues.append({'reason':'source_edge_endpoints_or_labels_changed','missing':list((expected-found).elements()),'extra':list((found-expected).elements())})
 expected_markers=sum(2 if e.get('type','').startswith('double_arrow_point') else 1 if e.get('type')=='arrow_point' else 0 for e in ast['edges']);unsupported=[e.get('type') for e in ast['edges'] if e.get('type') not in ('arrow_point','arrow_open','double_arrow_point')]
 if unsupported:issues.append({'reason':'source_arrow_type_requires_separate_verification','types':unsupported})
 if markers!=expected_markers:issues.append({'reason':'native_arrow_marker_count_mismatch','expected':expected_markers,'actual':markers})
 if ast.get('groups'):issues.append({'reason':'source_groups_not_validated'})
 return {'ok':not issues,'source_nodes':len(vertices),'source_edges':sum(expected.values()),'native_markers':markers,'expected_markers':expected_markers,'errors':issues,'scope':'Independent source AST node identity/label and directed edge/label/marker count versus actual XML; visual fidelity separate.'}
