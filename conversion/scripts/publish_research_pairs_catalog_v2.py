"""One immutable catalogue, preserving distinct evidence profiles and aliases."""
from pathlib import Path
import collections,datetime,hashlib,io,json,os,struct
from PIL import Image
R=Path('/backup/shaoshitong/img2code_20261029');C=R/'clean/complexity_curation_20261102T054553Z_v1'
M=R/'clean/matplotlib_plot_pipeline_20261102_v1';A=R/'clean/arxiv_research_figures_v1'
ROOT=R/'clean/research_pairs_catalog';ROOT.mkdir(exist_ok=True)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ROOT/('snapshot_'+stamp+'_v2');OUT.mkdir(exist_ok=False);(OUT/'input_manifests').mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
def raw(x):return (json.dumps(x,ensure_ascii=True,sort_keys=True,indent=2)+'\n').encode()
def atomic(path,x):
 t=path.with_name(path.name+'.tmp');t.write_bytes(raw(x));os.replace(t,path)
def read_stable(path):
 for _ in range(3):
  a=path.stat();b=path.read_bytes();c=path.stat()
  if (a.st_ino,a.st_size,a.st_mtime_ns)==(c.st_ino,c.st_size,c.st_mtime_ns):return b
 raise ValueError('changing_input_manifest:'+str(path))
cache={};pixels={}
def asset(name,digest,image=False):
 p=Path(name);p=p if p.is_absolute() else R/p;p=p.resolve(strict=True)
 assert p.is_relative_to((R/'clean').resolve()) and p.is_file(),('not_clean_payload',str(p))
 st=p.stat();key=(str(p),st.st_ino,st.st_size,st.st_mtime_ns)
 if key not in cache:
  data=p.read_bytes();after=p.stat();assert key[1:]==(after.st_ino,after.st_size,after.st_mtime_ns)
  cache[key]=sha(data)
  if image:
   with Image.open(io.BytesIO(data)) as im:
    assert im.format=='PNG',('not_PNG',str(p))
    rgba=im.convert('RGBA');rgba.load()
    pixels[key]={'width':rgba.width,'height':rgba.height,
      'rgba_sha256':sha(struct.pack('>QQ',rgba.width,rgba.height)+rgba.tobytes())}
 assert cache[key]==digest,('payload_hash_mismatch',str(p))
 return str(p.relative_to(R)),pixels.get(key) if image else None
cur=json.loads((C/'current.json').read_text());mainfile=R/cur['views']['paired_priority_complex']['file']
assert sha(read_stable(mainfile))==cur['views']['paired_priority_complex']['sha256']
inputs=[('paper_diagrams_and_posters_full8',mainfile),
 ('scientific_chart_provider_original',M/'provider_original_reference_aligned.jsonl'),
 ('scientific_chart_source_replay',M/'source_replay_aligned.jsonl'),
 ('scientific_chart_source_replay_repaired',M/'published_repair_pairs_v3/source_replay_aligned.jsonl'),
 ('arxiv_registered_original_PDF_visual_v2',A/'original_PDF_reference_audit_v2/paired_registered_original_PDF.jsonl'),
 ('arxiv_author_native_source_replay',A/'author_native_source_replay_v1/published_source_replay_v2/source_replay_aligned.jsonl')]
pairs={};manifests=[];byview=collections.Counter();aliases=0
for view,path in inputs:
 data=read_stable(path);rows=[json.loads(l) for l in data.splitlines() if l.strip()]
 snapshot=OUT/'input_manifests'/(view+'.jsonl');snapshot.write_bytes(data)
 manifests.append({'view':view,'source':str(path.relative_to(R)),'immutable_copy':str(snapshot.relative_to(R)),
                   'sha256':sha(data),'rows':len(rows)})
 for line,row in enumerate(rows,1):
  code,_=asset(row['code_file'],row['code_sha256']);image,pixel=asset(row['image_file'],row['image_sha256'],image=True)
  if row.get('whole_figure_wrapper'):raise ValueError('whole_figure_wrapper_not_allowed')
  key=sha((row['code_sha256']+pixel['rgba_sha256']).encode());byview[view]+=1
  if key not in pairs:
   pairs[key]={'id':key,'format':'drawio','code_file':code,'code_sha256':row['code_sha256'],
      'image_file':image,'image_sha256':row['image_sha256'],'image_pixels':pixel,'quality_views':[],
      'source_records':[],'evidence_profiles_are_not_interchangeable':True}
  else:aliases+=1
  pair=pairs[key]
  if view not in pair['quality_views']:pair['quality_views'].append(view)
  pointer={'manifest':str(snapshot.relative_to(R)),'line':line,'source_id':row.get('id'),
    'code_file':code,'code_sha256':row['code_sha256'],'image_file':image,'image_sha256':row['image_sha256'],
    'raw_source_pair_id':row.get('raw_source_pair_id',row.get('source_pair_sha256')),
    'source':row.get('source'),'source_format':row.get('source_format'),
    'quality_profile':row.get('profile',row.get('quality_profile',row.get('quality_state'))),
    'original_reference':row.get('original_reference'),'original_source_code':row.get('original_source_code')}
  if row.get('curation'):pointer['source_curation']=row['curation']
  if row.get('source_aliases'):pointer['original_PDF_aliases']=row['source_aliases']
  pair['source_records'].append(pointer)
index=OUT/'pairs.jsonl'
with index.open('xb') as f:
 for key in sorted(pairs):f.write((json.dumps(pairs[key],ensure_ascii=True,sort_keys=True)+'\n').encode())
summary={'schema':'research_pair_catalogue_v2','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'unique_code_PNG_pairs':len(pairs),'input_rows':sum(byview.values()),'exact_code_RGBA_alias_rows':aliases,
 'deduplication':'Exact drawio file SHA256 plus exact RGBA PNG pixels including dimensions; PNG encoding differences merge, no crop/resize/visual tolerance.',
 'by_evidence_view':dict(byview),'verified_unique_payload_files':len({x[0] for x in cache}),
 'all_primary_payloads_actual_clean_files':True,'input_manifests':manifests,
 'index':{'file':str(index.relative_to(R)),'sha256':sha(index.read_bytes()),'rows':len(pairs)},
 'quality_notes':{
  'paper_diagrams_and_posters_full8':'Source complexity selection plus existing full8 qualification; RAP uses reconstructed HTML template references, original poster is auxiliary.',
  'scientific_chart_provider_original':'Full scientific-plot checks including dataset-provided image correspondence.',
  'scientific_chart_source_replay':'Release-exact source execution produces a new recorded source scene; original dataset image remains auxiliary.',
  'arxiv_registered_original_PDF_visual_v2':'Actual author XML + official PNG; geometry-registered original PDF raster checks passed. This is not the legacy full8/font-portability profile.',
  'arxiv_author_native_source_replay':'Actual cold document replay/edit/restore and assets verified; physical font files bundled for the pinned runtime, standalone font portability unproved, original PDF fidelity separately recorded.'},
 'semantic_complexity_is_source_screened_not_individually_model_rated':True,'new_conversions':0,'new_QA':0,
 'external_models':0,'all_data_on_HKUST':True,'goal_complete':False}
(OUT/'summary.json').write_bytes(raw(summary))
pointer={'schema':'research_pairs_catalogue_pointer_v2','at_utc':summary['at_utc'],
 'snapshot':str(OUT.relative_to(R)),'summary':{'file':str((OUT/'summary.json').relative_to(R)),
 'sha256':sha((OUT/'summary.json').read_bytes())},'index':summary['index'],
 'unique_code_PNG_pairs':len(pairs),'by_evidence_view':dict(byview),'goal_complete':False}
atomic(ROOT/'current.json',pointer)
for p in OUT.rglob('*'):
 if p.is_file():p.chmod(0o444)
print(json.dumps({'current':str(ROOT/'current.json'),'summary':str(OUT/'summary.json'),
 'unique_code_PNG_pairs':len(pairs),'by_view':dict(byview),'alias_rows':aliases,
 'verified_payload_files':summary['verified_unique_payload_files'],'goal_complete':False},ensure_ascii=True))
