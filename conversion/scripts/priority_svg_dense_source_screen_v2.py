"""Select rich SVG research layouts without inventing logical graph nodes.

This is source selection, not conversion qualification. Original source hashes,
conversion fidelity gates, and scientific provenance remain independent.
"""
from pathlib import Path
import collections,concurrent.futures,datetime,hashlib,html,json,os,re,sys,time,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean/complexity_curation_20261102T054553Z_v1'
D=R/'clean/priority_svg_dense_source_screen_v2'
sys.path[:0]=[str(R/'conversion/scripts'),str(R/'env')]
import pyarrow.parquet as pq
from priority_source_complexity_filter_v1 import svg_features
SEED='20261102-source-layout-unseen-v2'
EXCLUDED={'b21f0ddad39441d9b70ff57c0750bc61752485fa23c9f04ea9b4dc6f52d046f1','fdde92d0d175ef8920afd72e79104930b1c5be509f56c4b61b3c962e62a81c82'}
sha=lambda b:hashlib.sha256(b).hexdigest()
def raw(x):return (json.dumps(x,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode()
def atomic(p,x):
 q=p.with_name(p.name+'.tmp');q.write_bytes(raw(x));os.replace(q,p)
def local(e):return e.tag.rsplit('}',1)[-1]
def features(blob):
 root=ET.fromstring(blob);labels=[];active=[];hidden=0
 def visit(e):
  nonlocal hidden
  tag=local(e);s=dict(x.split(':',1) for x in e.get('style','').split(';') if ':' in x)
  s={k.strip().lower():v.strip().lower() for k,v in s.items()}
  if tag in {'defs','symbol','marker','clipPath','mask','pattern','linearGradient','radialGradient'}:return
  if s.get('display',e.get('display'))=='none' or s.get('visibility',e.get('visibility')) in {'hidden','collapse'}:
   hidden+=1;return
  try:
   if float(s.get('opacity',e.get('opacity','1')))==0:hidden+=1;return
  except ValueError:pass
  active.append(e)
  if tag in {'text','foreignObject'}:
   label=' '.join(' '.join(e.itertext()).split())
   if label:labels.append(label)
  for child in e:visit(child)
 visit(root);distinct=sorted(set(labels));tokens=set()
 for label in distinct:
  tokens.update(t.casefold() for t in re.findall(r'[A-Za-z][A-Za-z0-9_\-]{2,}',label))
  tokens.update(re.findall(r'[\u3400-\u9fff]{2,}',label))
 active_ids={id(e) for e in active};groups=sum(sum(id(c) in active_ids and local(c) in {'text','foreignObject','image'} for c in e)>=2 for e in active if local(e)=='g')
 panels=set()
 for label in distinct:
  m=re.match(r'^\s*\(?([a-lA-L])\)?[.)\s:]?(?:$|\s)',label)
  if m and len(label)<100 and (len(label)>1 or label.lower() in 'abcdef'):panels.add(m.group(1).lower())
 return {'distinct_labels':len(distinct),'label_characters':sum(map(len,distinct)),
  'unique_word_tokens':len(tokens),'source_label_groups':groups,'panel_label_clues':len(panels),
  'source_shape_units':sum(local(e) in {'rect','circle','ellipse','polygon','polyline','line','foreignObject','image'} for e in active),
  'path_or_use_present':any(local(e) in {'path','use'} for e in active),
  'image_units':sum(local(e)=='image' for e in active),'ignored_hidden_subtrees':hidden,
  'stylesheet_visibility_requires_render':any(re.search(r'\b(display|visibility|opacity)\s*:', ''.join(e.itertext()),re.I) for e in root.iter() if local(e)=='style'),
  'logical_graph_nodes_inferred':False,'geometry_or_path_segments_counted_as_nodes':False}
def select(f):
 if f['stylesheet_visibility_requires_render'] or f['unique_word_tokens']<10:return []
 n=f['distinct_labels'];chars=f['label_characters'];g=f['source_label_groups'];o=f['source_shape_units'];panels=f['panel_label_clues'];rules=[]
 if n>=18 and chars>=250 and g>=4 and o>=25:rules.append('rich_grouped_research_layout')
 if n>=30 and chars>=350 and o>=40:rules.append('dense_labeled_research_drawing')
 if panels>=3 and n>=14 and chars>=200 and g>=3 and o>=30:rules.append('labeled_multi_panel_research_layout')
 if g>=6 and n>=24 and chars>=350 and f['path_or_use_present']:rules.append('rich_grouped_label_and_vector_layout')
 return rules
def direct(row):
 loc=row['source_locator']
 for k in ['resolved_source_code','code_file']:
  if loc.get(k):
   p=R/loc[k]
   if p.is_file():return p
 return None
def blobs(rows):
 groups=collections.defaultdict(list)
 for row in rows:
  p=direct(row);key=('file',str(p)) if p else ('parquet',row['source_locator']['clean_file'],row['source_locator']['code_key'])
  groups[key].append(row)
 def group(task):
  key,items=task
  if key[0]=='file':
   blob=Path(key[1]).read_bytes();return [(r,blob) for r in items]
  table=pq.read_table(R/key[1],columns=[key[2]])
  out=[]
  for r in items:
   v=table.column(0)[r['source_locator']['clean_row']].as_py()
   if isinstance(v,str):v=v.encode()
   assert isinstance(v,bytes),'unexpected_SVG_cell_type'
   out.append((r,v))
  return out
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for result in pool.map(group,groups.items()):
   for item in result:yield item
def inspect(item):
 row,blob=item
 assert sha(blob)==row['code_sha256_manifest']==row['source_code_sha256_observed'],('source_hash_mismatch',row['id'])
 f=features(blob);rules=select(f)
 return {**row,'prior_curation_status':row['status'],'source_layout_features_v2':f,
  'source_layout_rules_v2':rules,'source_layout_selected_v2':bool(rules) and row['id'] not in EXCLUDED,
  'selection_does_not_assert_conversion_or_scientific_merit':True}
def selftest():
 simple='<svg><image href="data:image/png;base64,AA=="/><text>Research figure</text></svg>'
 rich='<svg>'+''.join('<g>'+''.join('<rect/><text>Research module '+str(g)+' layer '+str(i)+' attention channel token'+str(g*10+i)+'</text>' for i in range(5))+'</g>' for g in range(8))+'</svg>'
 assert select(features(rich.encode()))
 for doc in [simple,'<svg>'+('<path d="M0 0 L1 1"/>'*5000)+'</svg>',
  '<svg>'+('<text>Repeated label</text><rect/>'*100)+'</svg>',
  '<svg><g visibility="hidden">'+rich+'</g></svg>',
  '<svg><defs>'+rich+'</defs></svg>']:
  assert not select(features(doc.encode()))
 print(json.dumps({'real_source_selection_fixture_controls':6,'defs_hidden_duplicates_glyph_fragments_or_wrapper_cannot_promote':True,'conversion_quality_thresholds_changed':False}))
def run():
 D.mkdir(parents=True,exist_ok=True);assert not (D/'summary.json').exists(),'already completed; use frozen result'
 index=C/'priority_sources/index.jsonl';data=index.read_bytes();allrows=[json.loads(l) for l in data.splitlines() if l.strip()]
 eligible=[r for r in allrows if r['source_format']=='svg' and r['status']=='structure_review' and r.get('source_hash_matches_manifest') and r.get('provenance',{}).get('structurally_complete') is not False and r.get('read_status')=='read_code_only' and r.get('features',{}).get('distinct_owner_labels',0)>=14 and r.get('features',{}).get('label_characters',0)>=200]
 policy={'schema':'rich_SVG_research_layout_selection_v2','source_index_sha256':sha(data),'producer_sha256':sha(Path(__file__).read_bytes()),'legacy_metric_helper_sha256':sha((R/'conversion/scripts/priority_source_complexity_filter_v1.py').read_bytes()),'random_validation_seed':SEED,
  'selection_basis':'Visible-by-static-attributes distinct labels, lexical variety, grouped or dense drawing layout; explicit graph metadata is not required.',
  'quality_thresholds_or_existing_source_statuses_modified':False,'source_completeness_further_checked_by_conversion_QA':True,
  'limits':'Static source preselection does not certify scientific merit, actual paint or conversion fidelity; unresolved CSS visibility stays unselected. No image payloads/models used.'}
 (D/'policy.json').write_bytes(raw(policy));start=time.monotonic()
 sample=sorted(eligible,key=lambda r:sha((SEED+r['id']).encode()))[:32]
 validation=[]
 for row,blob in blobs(sample):
  old=svg_features(blob.decode());assert old==row['features'],('source_feature_replay_drift',row['id'])
  new=inspect((row,blob));validation.append({'id':row['id'],'source_sha256':sha(blob),'old_feature_replay_exact':True,'selected':new['source_layout_selected_v2'],'rules':new['source_layout_rules_v2']})
 assert len(validation)==min(32,len(eligible))
 (D/'unseen_source_validation.json').write_bytes(raw({'source_only_unseen_samples':validation,'source_hash_and_original_feature_replay_all_exact':True,'conversion_or_QA_calls':0}))
 selected=[];count=0
 with (D/'screened_index.jsonl').open('x') as f,concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  # Input source bytes are released per four-worker wave, never all held in RAM.
  pending=[]
  for item in blobs(eligible):
   pending.append(pool.submit(inspect,item))
   if len(pending)>=16:
    for future in pending:
     r=future.result();f.write(json.dumps(r,ensure_ascii=True,sort_keys=True)+'\n');count+=1
     if r['source_layout_selected_v2']:selected.append(r)
    pending=[];f.flush();atomic(D/'progress.json',{'finished':False,'processed':count,'eligible':len(eligible),'new_source_selected':len(selected),'elapsed_seconds':time.monotonic()-start})
  for future in pending:
   r=future.result();f.write(json.dumps(r,ensure_ascii=True,sort_keys=True)+'\n');count+=1
   if r['source_layout_selected_v2']:selected.append(r)
 with (D/'new_complex_candidates.jsonl').open('x') as f:
  for r in sorted(selected,key=lambda r:r['id']):f.write(json.dumps(r,ensure_ascii=True,sort_keys=True)+'\n')
 summary={'schema':'rich_SVG_source_selection_summary_v2','finished':True,'eligible_previously_review_SVGs':len(eligible),'screened':count,
  'new_structurally_complex_source_candidates':len(selected),'by_source':dict(collections.Counter(r['source'] for r in selected)),
  'rule_counts':dict(collections.Counter(v for r in selected for v in r['source_layout_rules_v2'])),
  'elapsed_seconds':time.monotonic()-start,'source_SVGs_per_second':count/max(.001,time.monotonic()-start),
  'source_only_unseen_validation_cases':len(validation),'source_code_image_or_existing_curation_modified':False,
  'new_conversion_or_QA_or_model_calls':0,'goal_complete':False}
 atomic(D/'summary.json',summary);print(json.dumps(summary))
if __name__=='__main__':
 {'selftest':selftest,'run':run}[sys.argv[1]]()
