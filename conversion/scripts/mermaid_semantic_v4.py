"""Independent official Mermaid AST coverage, including subgraph titles and native membership."""
import re,collections,xml.etree.ElementTree as E
from mermaid_semantic_audit import PARSE,text
compact=lambda s:re.sub(r"\s+","",s)

def check(ast,xml):
 if not ast.get('vertices') or ast.get('edges') is None:return {'status':'unsupported_diagram_type','type':ast['type'],'accepted':False}
 source_vertices=dict(ast['vertices']) if isinstance(ast['vertices'],list) else ast['vertices'];groups={g['id']:g for g in ast.get('groups') or []};expected={id:text(v.get('text') or id) for id,v in source_vertices.items() if id not in groups};expected_groups={id:text(g.get('title') or id) for id,g in groups.items()};root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p};cells={};metadata={};duplicates=[]
 for c in root.iter('mxCell'):
  p=parents.get(c);id=c.get('id') or (p.get('id') if p is not None else None)
  if id in cells:duplicates.append(id)
  cells[id]=c;metadata[id]={'label':text(c.get('value') if c.get('value') is not None else p.get('label','') if p is not None else ''),'tag':c.get('mermaidId') or (p.get('mermaidId') if p is not None else None)}
 vertices={id:c for id,c in cells.items() if c.get('vertex')=='1'};edges={id:c for id,c in cells.items() if c.get('edge')=='1'};childverts=collections.defaultdict(list)
 for id,c in vertices.items():childverts[c.get('parent')].append(id)
 # Geometry converters retain editable text runs as direct child vertices.
 # Only reconstruct an explicitly tagged source node with no own visible label.
 reconstructed={}
 for cid,c in vertices.items():
  tag=metadata[cid]['tag']
  if tag and tag.startswith('n:') and not metadata[cid]['label']:
   fragments=[metadata[k]['label'] for k in childverts[cid] if metadata[k]['label'] and not metadata[k]['tag'] and 'shape=text;' in (cells[k].get('style') or '')]
   if fragments:metadata[cid]['label']=' '.join(fragments);reconstructed[cid]=fragments

 def ancestors(id):
  out=[];seen={id};p=cells[id].get('parent')
  while p in cells:
   if p in seen:raise ValueError('cyclic native parent hierarchy')
   seen.add(p);out.append(p);p=cells[p].get('parent')
  return out
 ancestry={id:ancestors(id) for id in vertices};mapped={};group_cells={};group_errors=[];used=set()
 # Explicit AST group IDs, otherwise unique title + actual native container.
 for gid,title in expected_groups.items():
  exact=[id for id in vertices if metadata[id]['tag']=='n:'+gid]
  candidates=exact or [id for id in vertices if metadata[id]['label']==title and (childverts[id] or not groups[gid].get('nodes'))]
  if len(candidates)!=1 or candidates[0] in used:group_errors.append({'group':gid,'reason':'missing_or_ambiguous_group','candidates':candidates});continue
  cid=candidates[0];mapped[cid]=gid;group_cells[gid]=cid;used.add(cid)
  if compact(metadata[cid]['label'])!=compact(title):group_errors.append({'group':gid,'reason':'group_title_mismatch','expected':title,'actual':metadata[cid]['label']})
 # Explicit source-node IDs retain mismatches; label inference is only unique exact matching.
 node_cells=collections.defaultdict(list);actual={}
 for cid in vertices:
  if cid in used:continue
  tag=metadata[cid]['tag']
  if tag and tag.startswith('n:'):
   sid=tag[2:];mapped[cid]=sid;node_cells[sid].append(cid);actual[sid]=metadata[cid]['label']
 labels=collections.defaultdict(list)
 for sid,label in expected.items():labels[compact(label)].append(sid)
 for label,sids in labels.items():
  candidates=[cid for cid in vertices if cid not in mapped and compact(metadata[cid]['label'])==label]
  if len(sids)==1 and len(candidates)==1 and sids[0] not in node_cells:
   sid=sids[0];cid=candidates[0];mapped[cid]=sid;node_cells[sid].append(cid);actual[sid]=label
 def descendants(gid,seen=None):
  seen=set() if seen is None else seen
  if gid in seen:raise ValueError('cyclic source subgraphs')
  seen=seen|{gid};out=set()
  for member in groups[gid].get('nodes') or []:
   out.add(member)
   if member in groups:out.update(descendants(member,seen))
  return out
 membership=[]
 for gid,cid in group_cells.items():
  wanted=descendants(gid);found={mapped[v] for v in vertices if v in mapped and cid in ancestry[v]};missing=sorted(wanted-found);extra=sorted(found-wanted)
  if missing or extra:group_errors.append({'group':gid,'reason':'group_membership_mismatch','missing':missing,'extra':extra})
  membership.append({'group':gid,'title':expected_groups[gid],'cell':cid,'expected_members':sorted(wanted),'actual_members':sorted(found)})
 expected_edges=collections.Counter((e['start'],e['end'],compact(text(e.get('text','')))) for e in ast['edges']);actual_edges=collections.Counter();unmapped=[]
 for cid,c in edges.items():
  label=metadata[cid]['label']
  if not label:
   children=[metadata[v]['label'] for v in childverts[cid] if metadata[v]['label']]
   if children:label=' '.join(children)
  src=mapped.get(c.get('source'));tgt=mapped.get(c.get('target'))
  if src is None or tgt is None:unmapped.append({'cell':cid,'source':c.get('source'),'target':c.get('target'),'label':label})
  actual_edges[(src,tgt,compact(label))]+=1
 mismatched=[{'node':sid,'expected':label,'actual':actual.get(sid)} for sid,label in expected.items() if compact(actual.get(sid) or '')!=compact(label)];extra_nodes=sorted(set(actual)-set(expected));missing_edges=list((expected_edges-actual_edges).elements());extra_edges=list((actual_edges-expected_edges).elements());duplicate_nodes={k:v for k,v in node_cells.items() if len(v)>1};ok=not any([mismatched,extra_nodes,missing_edges,extra_edges,unmapped,group_errors,duplicates,duplicate_nodes])
 return {'status':'node_edge_text_match' if ok else 'source_content_mismatch','type':ast['type'],'expected_nodes':len(expected),'expected_edges':sum(expected_edges.values()),'actual_nodes':len(actual),'actual_edges':len(edges),'reconstructed_native_text_runs':reconstructed,'expected_groups':len(groups),'matched_groups':len(group_cells),'group_membership':membership,'group_errors':group_errors,'node_text_mismatches':mismatched,'extra_nodes':extra_nodes,'missing_or_changed_edges':missing_edges,'extra_or_changed_edges':extra_edges,'unmapped_bound_nodes':unmapped,'duplicate_cell_ids':duplicates,'duplicate_source_nodes':duplicate_nodes,'limitations':['Text run whitespace is normalized; typography, whitespace spacing, shape/style/pixel-layout and visible content clipping are separate gates.','Non-flowchart source types remain unsupported.'],'accepted':False}
