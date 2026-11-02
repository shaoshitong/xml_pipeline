"""Metadata-only final hard-component closure, no source reads or re-sampling."""
from pathlib import Path
import json,hashlib,collections
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'release/compiler_types_audit_v1/source_only_20261101_v1'
def raw(x):return (json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
a=rows(P/'compiler_types_audited_candidates.jsonl');d=rows(P/'compiler_types_development_audit.jsonl');edges=rows(P/'compiler_types_cluster_edges.jsonl');byid={r['id']:r for r in d+a};parent={i:i for i in byid}
def find(x):
 while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
 return x
def union(x,y):
 x,y=find(x),find(y)
 if x!=y:parent[max(x,y)]=min(x,y)
for e in edges:union(e['left'],e['right'])
components=collections.defaultdict(list)
for r in d+a:components[find(r['id'])].append(r)
devcomp={find(r['id']) for r in d};uncertain={find(r['id']) for r in a if r['audit_disposition'] not in ('eligible_operational_cluster','duplicate_actual_source_semantic_family')};selected=[];reserve=[];stats={};seen=set();eligible=[]
for r in sorted(a,key=lambda r:r['pool_rank']):
 c=find(r['id'])
 if r['audit_disposition']!='eligible_operational_cluster' or c in devcomp or c in uncertain or c in seen:continue
 seen.add(c);members=components[c];stable=sorted({k for m in members for k in m.get('cluster_keys',[]) if k.startswith(('semantic:','old_family:','document:','provenance:'))});semantic=sorted(k for k in stable if k.startswith('semantic:'))
 if not semantic:continue
 eligible.append({**r,'audit_cluster':semantic[0],'cluster_keys':sorted(set(r['cluster_keys']+stable)),'hard_component_closure_verified':True,'ready_for_validation':False})
for u in sorted({r['support_unit'] for r in a}):
 rs=sorted([r for r in eligible if r['support_unit']==u],key=lambda r:r['pool_rank']);first=rs[:30] if len(rs)>=30 else [];res=rs[30:60] if len(rs)>=60 else [];selected += [dict(r,sample_order_within_unit=i+1) for i,r in enumerate(first)];reserve += [dict(r,reserve_order=i+1,eligible_rank=i+31) for i,r in enumerate(res)];stats[u]={'eligible_closed_hard_and_semantic_components':len(rs),'selected':len(first),'repair_reserve':len(res),'ready':False}
assert len({find(r['id']) for r in selected+reserve})==len(selected+reserve)
assert not({find(r['id']) for r in selected+reserve}&devcomp)
files=[]
for n,rs in [('compiler_types_selected_manifest_closure_verified.jsonl',selected),('compiler_types_repair_reserve_closure_verified.jsonl',reserve)]:
 b=b''.join(raw(r) for r in rs);p=P/n
 with p.open('xb') as f:f.write(b)
 p.chmod(0o444);files.append({'file':str(p),'sha256':sha(b),'bytes':len(b)})
s={'metadata_integrity_passed':True,'no_source_payload_or_QA_read':True,'pool_unchanged':True,'registry_unmodified':True,'component_development_overlap':0,'selected_reserve_hard_component_overlap':0,'unit_statistics':stats,'files':files,'use_these_closure_verified_manifests_for_future_seal':True,'original_aggregate_manifest_is_superseded_for_sealing':True,'ready_for_validation':False,'new_conversion_or_QA':False};(P/'compiler_types_integrity.json').write_bytes(raw(s));print(json.dumps(s))
