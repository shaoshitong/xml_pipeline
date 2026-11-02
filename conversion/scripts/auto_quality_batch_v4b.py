"""Fixed-program quality routing and automatic release of verified current revisions."""
import argparse,concurrent.futures,fcntl,signal,hashlib,io,json,os,sqlite3,time,traceback,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from native_worker import R,W,now,native,pair
from durable_sqlite import begin,commit
from auto_quality_common_v4 import POLICY,checked,sha,structure_checks,resource_checks,image_quality,native_source_profile,require_rendered_text,registration_record
from strict_canvas_gate import require_declared_page
from auto_quality_dispatch_v2 import initialize as initialize_dispatch

POLICY='bounded_deterministic_clip_canvas_and_native_quality_v4b'

DEPENDENCIES=('auto_quality_batch_v2.py','auto_quality_dispatch_v2.py','auto_quality_common.py','auto_quality_common_v2.py','auto_quality_source_graph.py','auto_quality_source_vector.py','auto_quality_source_vector_v2.py','html_range_extractor_v2.py','html_source_repair_v2.py','auto_quality_canvas_repair.py','auto_quality_font_repair.py','native_font_embedding_batch.py','native_text_clip.py','native_clip_reference_box.py','auto_quality_move.py','tikz_literal_graph.py','tikz_literal_connectivity.py','svg_source_coverage_v2.py','mermaid_semantic_v4.py','svg_dom_pdf.js','svg_dom_v6.js','html_dom_clip.js','strict_canvas_gate.py','native_worker.py')
DEPENDENCIES=tuple(dict.fromkeys(DEPENDENCIES+('auto_quality_batch_v3.py', 'auto_quality_common_v3.py', 'auto_quality_publication_v3.py', 'tikz_execution_source_profile_v3.py', 'tikz_execution_source_profile.py', 'tikz_execution_graph.py', 'tikz_execution_graph_hooks.tex', 'tikz_execution_binding.py', 'tikz_execution_binding_v2.py', 'tikz_execution_marker_paint_fit.py', 'tikz_execution_marker_quality.py', 'svg_dom_pdf_v2.js', 'svg_convert_v2.py', 'svg_convert_v3.py', 'html_actual_text_alignment.py', 'html_actual_text_registration.py', 'auto_quality_html_glyph_profile_v3.py')))
DEPENDENCIES=tuple(dict.fromkeys(DEPENDENCIES+('auto_quality_common_v2.py','harness_canvas_contract.py','portable_native_fonts.py','durable_sqlite.py')))
DEPENDENCIES=tuple(dict.fromkeys(DEPENDENCIES+('auto_quality_batch_v4.py','auto_quality_common_v4.py','auto_quality_publication_v4.py','qualified_index_v4.py','native_source_font_profile_v4.py','native_source_editing_v4.py','native_source_editing_v4.js','html_text_layout_registration_v5.py','auto_quality_html_text_layout_profile_v5.py','html_text_layout_candidate_v5.py','html_text_whitespace_advance_v5.py','html_actual_text_clip_alignment_v4.py')))
MANDATORY_NEW=('auto_quality_batch_v4.py','auto_quality_common_v4.py','auto_quality_publication_v4.py','qualified_index_v4.py','native_source_font_profile_v4.py','native_source_editing_v4.py','native_source_editing_v4.js','html_text_layout_registration_v5.py','auto_quality_html_text_layout_profile_v5.py','html_text_layout_candidate_v5.py','html_text_whitespace_advance_v5.py','html_actual_text_clip_alignment_v4.py')
for name in MANDATORY_NEW:assert (Path(__file__).parent/name).is_file(),'Missing mandatory QA4 dependency: '+name
DEPENDENCIES=tuple(dict.fromkeys(DEPENDENCIES+('auto_quality_batch_v4b.py','clip_canvas_render_v4b.py')))
for name in ('auto_quality_batch_v4b.py','clip_canvas_render_v4b.py'):assert (Path(__file__).parent/name).is_file(),'Missing QA4b dependency: '+name
IMPLEMENTATION={name:sha((Path(__file__).parent/name).read_bytes()) for name in DEPENDENCIES if (Path(__file__).parent/name).exists()}
for path in (R/'scripts/curate_derived.py',R/'scripts/curate_pairs.py',W/'rendering_paintbounds_strict/remote_render.py',W/'rendering_clipbox_strict/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'):
 if path.exists():IMPLEMENTATION[str(path)]=sha(path.read_bytes())
POLICY=POLICY+':'+sha(json.dumps(IMPLEMENTATION,sort_keys=True).encode())[:16]

def ensure_pinned():
 for name,digest in IMPLEMENTATION.items():
  path=Path(name) if Path(name).is_absolute() else Path(__file__).parent/name
  assert sha(path.read_bytes())==digest,'Pinned quality implementation changed: '+name

IDLE=('rendered','needs_quality_repair','harness_review_pending','harness_rendered','needs_fallback')
RENDERER=W/'rendering_paintbounds_strict/remote_render.py'
CLIP_RENDERER=W/'rendering_clipbox_strict/remote_render.py'

def atomic(path,data):
 tmp=path.with_name(path.name+'.autoquality.tmp');tmp.write_bytes(data);tmp.replace(path)

def source_baseline(record,xml):
 contract=record.get('_verified_reference_registration')
 if record.get('auto_quality_canvas_repair'):
  baseline=checked(R,contract['baseline_code'],contract['baseline_code_sha256']).decode()
  previous=json.loads(checked(R,contract['baseline_record'],contract['baseline_record_sha256']))
  return previous,baseline
 return record,xml

def profile(record,xml,source,native_info=None):
 fmt=record['source_format']
 if fmt=='html' and record.get('html_text_layout_v5'):
  from auto_quality_html_text_layout_profile_v5 import check_html_profile
  return check_html_profile(record,xml,native_render=native_info)
 if fmt=='html' and record.get('html_actual_text_alignment'):
  from auto_quality_html_glyph_profile_v3 import check_html_profile
  return check_html_profile(record,xml,native_render=native_info)
 before,baseline=source_baseline(record,xml) if fmt in ('drawio','tikz') else (record,xml)
 if fmt=='drawio':
  proof=before.get('native_font_validation') or {}
  if str(proof.get('audit','')).startswith('conversion/auto_quality_font_repair_v1/'):
   from native_source_font_profile_v4 import check_native_profile
   result=check_native_profile(before,baseline,source,native_info=native_info if before is record else None)
  else:result=native_source_profile(before,baseline,source)
 elif fmt=='tikz' and before.get('tikz_execution_source_v3'):
  from tikz_execution_source_profile_v3 import check_execution_profile
  result=check_execution_profile(before,baseline)
 elif fmt in ('mermaid','tikz'):
  from auto_quality_source_graph import check_graph_profile
  result=check_graph_profile(before,baseline)
 else:
  from auto_quality_source_vector_v2 import check_vector_profile
  result=check_vector_profile(record,xml)
 if before is not record:
  result['evidence']['current_code_sha256']=sha(xml.encode())
  result['evidence']['canvas_only_transformation_independently_verified']=True
 return result

def require_coverage(coverage):
 if not coverage['supported']:raise ValueError('source_profile_not_implemented: '+json.dumps(coverage['failures'],ensure_ascii=False))
 if not coverage['ok']:raise ValueError('source_coverage_failure: '+json.dumps(coverage['failures'],ensure_ascii=False))

def execution_marker_check(record,xml,png):
 before,baseline=source_baseline(record,xml)
 if record.get('source_format')!='tikz' or not before.get('tikz_execution_source_v3'):return None
 from tikz_execution_source_profile_v3 import check_execution_marker_render
 if before is not record:
  width,height=Image.open(io.BytesIO(checked(R,before['image_file'],before['image_sha256']))).size
  rendered=native.native_job(baseline,width,height,180,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
  if not rendered['ok']:raise ValueError('frozen_execution_marker_native_render_failed')
  require_declared_page(rendered['native_render'],width,height)
  png=rendered['png']
 result=check_execution_marker_render(before,baseline,png)
 if not result['supported'] or not result['ok']:raise ValueError('native_marker_paint_failure: '+json.dumps(result['failures'],ensure_ascii=False))
 return result

def verify(item):
 ensure_pinned()
 id,state,raw,input_raw,route=item;started=time.monotonic();r=json.loads(raw);digest=r['code_sha256'];work=W/'auto_quality_v4b'/id/(digest+'_'+r['image_sha256'][:16])/POLICY.rsplit(':',1)[-1];work.mkdir(parents=True,exist_ok=True)
 report={'id':id,'policy':POLICY,'at':now(),'input_code_sha256':digest,'input_image_sha256':r['image_sha256'],'record_sha256':sha(raw.encode()),'source_image_sha256':r['source_image_sha256'],'source_code_sha256':r['source_code_sha256'],'checks':{},'failures':[],'accepted':False}
 freshpng=None;out=None
 try:
  original=json.loads(input_raw);assert r['id']==id and r['source_pair_sha256']==id and r['source_image_sha256']==original['image_sha256'] and r['source_code_sha256']==original['code_sha256'],'Current output does not belong to the authoritative source pair'
  xml=checked(R,r['code_file'],digest).decode();checked(R,r['image_file'],r['image_sha256']);report['checks']['structure']=structure_checks(xml)
  # Legacy native pairs did not copy references/source out of the input Parquet.
  if not r.get('original_reference') or not r.get('original_source_code'):
   reference,source=pair(json.loads(input_raw));dest=(R/r['code_file']).parent;ext=Image.open(io.BytesIO(reference)).format.lower();ref=dest/('original_image.'+ext);code=dest/('original_source.'+r['source_format']);atomic(ref,reference);atomic(code,source.encode());r={**r,'original_reference':str(ref.relative_to(R)),'original_source_code':str(code.relative_to(R))}
  reference=checked(R,r['original_reference'],r['source_image_sha256']);source=checked(R,r['original_source_code'],r['source_code_sha256']).decode()
  r,registration=registration_record(r,reference,xml)
  if registration:report['checks']['reference_registration']=registration
  report['checks']['resources']=resource_checks(R,r,xml,reference)
  glyph_profile=bool(r.get('html_actual_text_alignment') or r.get('html_text_layout_v5'))
  renderer=CLIP_RENDERER if glyph_profile else RENDERER
  try:coverage=None if glyph_profile else profile(r,xml,source)
  finally:
   # An active Playwright Sync context cannot nest the independent movement runtime.
   if r['source_format'] in ('tikz','mermaid'):
    from auto_quality_source_graph import close_worker_runtime
    close_worker_runtime()
  if coverage is not None:
   report['checks']['source']=coverage;require_coverage(coverage)
  model=E.fromstring(xml).find('.//mxGraphModel');width=int(round(float(model.get('pageWidth',0))));height=int(round(float(model.get('pageHeight',0))))
  if not(0<width<=8192 and 0<height<=8192):raise ValueError('unsupported_native_canvas')
  from clip_canvas_render_v4b import render
  rendered=render(xml,width,height,180,renderer,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
  if not rendered['ok']:raise ValueError('fresh_native_render_failed: '+str({k:v for k,v in rendered.items() if k!='png'})[:1200])
  freshpng=rendered.pop('png');info=rendered['native_render'];require_declared_page(info,width,height)
  if glyph_profile and sha(freshpng)!=r['image_sha256']:raise ValueError('hash_bound_text_layout_fresh_png_differs_from_candidate')
  if glyph_profile:
   coverage=profile(r,xml,source,info);report['checks']['source']=coverage;require_coverage(coverage)
  marker=execution_marker_check(r,xml,freshpng)
  if marker:report['checks']['native_marker_paint']=marker
  report['checks']['render']={'code_sha256':digest,'image_sha256':sha(freshpng),'strict_outside_page_pixels':0,'renderer_sha256':sha(renderer.read_bytes()),'canvas':[width,height],'actual_text_cells':len(info.get('actual_text_positions',[])),'strict_clip_canvas_proof':info.get('clip_canvas_strict_proof_v4b')}
  if registration and registration.get('font_only_delta_verified'):
   from auto_quality_common import rgb
   frozen=(R/registration['frozen_origin_image']).read_bytes();assert rgb(freshpng).size==rgb(frozen).size and rgb(freshpng).tobytes()==rgb(frozen).tobytes(),'Fresh font revision changed registered native paint'
  usage=[f for row in info.get('actual_platform_font_usage',[]) for f in row.get('fonts',[]) if f.get('glyphCount',0)>0]
  report['checks']['text_paint']=require_rendered_text(xml,info)
  if info.get('actual_text_positions') and (not usage or not all(f.get('isCustomFont') for f in usage)):raise ValueError('actual_font_portability_requires_embedding')
  report['checks']['fonts']={'actual_custom_font_glyphs':sum(f['glyphCount'] for f in usage),'all_rendered_fonts_embedded':True}
  visual=image_quality(reference,freshpng,r,info.get('actual_text_positions'));report['checks']['visual']=visual
  if not visual['ok']:raise ValueError('raster_anomaly: '+','.join(visual['failures']))
  # Every semantic connector is actually tested in the upstream runtime.
  if report['checks']['structure']['edges']:
   if r['source_format']=='drawio':
    from native_source_editing_v4 import audit
    moves=audit(xml,record=r,source_profile=coverage)
    if not moves['ok'] or len(moves['moves'])!=2*report['checks']['structure']['edges']:raise ValueError('incomplete_original_native_constraint_intervention_proof')
   else:
    from auto_quality_move import audit
    moves=audit(xml)
    if len(moves['moves'])!=2*report['checks']['structure']['edges']:raise ValueError('incomplete_native_endpoint_movement_proof')
    for move in moves['moves']:
     if abs(move['delta']['x']-17)>.05 or abs(move['delta']['y']-11)>.05:raise ValueError('native_endpoint_does_not_follow_node')
     if any(abs(c['x']-17)>.05 or abs(c['y']-11)>.05 for c in move.get('child_deltas',[])):raise ValueError('node_label_does_not_follow_node')
     for group in move.get('label_member_deltas',[]):
      members=group['members']
      if any(abs(c['x']-members[0]['x'])>.05 or abs(c['y']-members[0]['y'])>.05 for c in members):raise ValueError('edge_label_background_or_text_moves_independently')
   (work/'movement.json').write_text(json.dumps(moves,indent=2)+'\n');report['checks']['native_editing']={'endpoint_moves':len(moves['moves']),'ok':True,'profile':moves.get('profile','fixed_connector_translation'),'evidence':str((work/'movement.json').relative_to(R))}
  else:report['checks']['native_editing']={'endpoint_moves':0,'ok':True,'source_profile_proves_no_semantic_edges':True}
  # Recheck the payload after expensive browser work, before publication CAS.
  checked(R,r['code_file'],digest);checked(R,r['image_file'],r['image_sha256'])
  verified_png=(R/r['image_file']).with_name('image.native.'+sha(freshpng)[:20]+'.png')
  r={k:v for k,v in r.items() if not k.startswith('_verified_')}
  out={**r,'image_file':str(verified_png.relative_to(R)),'image_sha256':sha(freshpng),'render':info,'quality_state':'accepted_automatic_source_and_native_quality_v4b','automatic_quality_policy':POLICY,'automatic_quality_audit':str((work/'audit.json').relative_to(R)),'source_coverage_automatic':coverage,'accepted_at_utc':now(),'metrics':{**r.get('metrics',{}),'automatic_visual_quality':visual}}
  report['state']='qualified';report['new_png_sha256']=sha(freshpng)
 except Exception as exc:
  report['state']='repair_required';report['failures'].append(str(exc)[:2500]);report['exception_type']=type(exc).__name__
 report['seconds']=round(time.monotonic()-started,3);(work/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if out:atomic(work/'fresh.png',freshpng);atomic(work/'candidate_record.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
 return item,report,out,work

def publish(db,item,report,out,work,enabled):
 from auto_quality_publication_v4 import publish as publish_revision
 return publish_revision(db,item,report,out,work,enabled,POLICY)

def write_index(db):
 from qualified_index_v4 import export
 try:return export(R)
 except AssertionError as error:
  if 'changed during qualified-index bootstrap' not in str(error):raise
  print(json.dumps({'at':now(),'stage':'qualified_index_retry_next_batch','error':str(error)}),flush=True)

# These rules change only native physical-font validation and the new HTML
# layout lineage. Reuse unchanged-family failures instead of rescanning them
# after a coordinator version bump. New revisions always remain eligible.
PREDECESSOR='source_execution_glyph_lineage_native_render_and_local_fidelity_v3:210bf4dbced804c5'
PREDECESSOR_V4='bounded_deterministic_font_text_layout_and_native_quality_v4:d2f5d9ada102865c'

def select_rows(db,ids,chunk):
 selection=(' and c.id in ('+','.join('?' for _ in ids)+')') if ids else ''
 # Reuse failed unchanged rule families. Only the missing strict-boundary
 # interface for hash-bound HTML clip/glyph revisions is repaired in v4b.
 return db.execute("""with chosen as materialized(
 select c.* from auto_quality_candidates_v1 c
 where c.route in ('graph','vector','native','repair')
 and not exists(select 1 from auto_quality_audits_v1 q where q.id=c.id and q.code_hash=c.code_hash and q.image_hash=c.image_hash and q.policy=?)
 and (not exists(select 1 from processing_outcomes_v2 o where o.id=c.id and o.status='abandoned' and json_extract(o.record,'$.code_sha256')=c.code_hash and json_extract(o.record,'$.image_sha256')=c.image_hash)
      or exists(select 1 from jobs n where n.id=c.id and json_extract(n.output_record,'$.source_format')='drawio')
      or exists(select 1 from auto_quality_audits_v1 q where q.id=c.id and q.code_hash=c.code_hash and q.image_hash=c.image_hash and q.policy=? and json_extract(q.record,'$.failures[0]')=?))
 and (not exists(select 1 from auto_quality_audits_v1 q where q.id=c.id and q.code_hash=c.code_hash and q.image_hash=c.image_hash and q.policy in (?,?) and q.state!='stale_revision')
      or exists(select 1 from jobs n where n.id=c.id and
         (json_extract(n.output_record,'$.source_format')='drawio' or json_extract(n.output_record,'$.html_text_layout_v5') is not null)
         and not exists(select 1 from auto_quality_audits_v1 q where q.id=c.id and q.code_hash=c.code_hash and q.image_hash=c.image_hash and q.policy=? and q.state!='stale_revision'))
      or exists(select 1 from jobs n where n.id=c.id and json_extract(n.output_record,'$.source_format')='html'
         and (json_extract(n.output_record,'$.html_text_layout_v5') is not null or json_extract(n.output_record,'$.html_actual_text_alignment') is not null)
         and exists(select 1 from auto_quality_audits_v1 q where q.id=c.id and q.code_hash=c.code_hash and q.image_hash=c.image_hash and q.policy=? and json_extract(q.record,'$.failures[0]')=?)))
 """+selection+""" order by c.priority desc,c.id limit ?)
 select j.id,j.state,j.output_record,j.input_record,c.route from chosen c join jobs j on j.id=c.id
 where j.state in ('rendered','needs_quality_repair','harness_review_pending','harness_rendered','needs_fallback') and j.worker_pid is NULL
 and json_extract(j.output_record,'$.code_sha256')=c.code_hash and json_extract(j.output_record,'$.image_sha256')=c.image_hash""",[POLICY,PREDECESSOR_V4,"'outside_page_pixel_audit'",PREDECESSOR,PREDECESSOR_V4,PREDECESSOR_V4,PREDECESSOR_V4,"'outside_page_pixel_audit'",*ids,chunk]).fetchall()

DRAIN=False
def request_drain(*_):
 global DRAIN
 DRAIN=True

def main(a):
 signal.signal(signal.SIGUSR1,request_drain)
 lock=(W/'auto_quality_coordinator.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 db=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(db);db.execute('create table if not exists auto_quality_audits_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy))');db.execute('create table if not exists auto_quality_exceptions_v1(id TEXT,code_hash TEXT,image_hash TEXT,policy TEXT,route TEXT,state TEXT,reason TEXT,updated_at TEXT,primary key(id,code_hash,image_hash,policy))');initialize_dispatch(db);commit(db)
 (W/'auto_quality_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'publish':a.publish,'at':now(),'policy':POLICY}))
 total=0;started=time.monotonic();counts={};default_workers=a.workers;default_chunk=a.chunk
 while True:
  if DRAIN:break
  ensure_pinned()
  control=W/'auto_quality_control.json'
  if control.exists():
   settings=json.loads(control.read_text());a.workers=int(settings.get('workers',default_workers));a.chunk=int(settings.get('chunk',default_chunk));assert 1<=a.workers<=24 and a.workers<=a.chunk<=256
   if settings.get('drain'):break
  # Inventory includes every revision. Unsupported/failing cases remain tracked for repair.
  rows=select_rows(db,a.ids,a.chunk)
  if a.limit:rows=rows[:max(0,a.limit-total)]
  if not rows:
   if not a.watch or a.limit and total>=a.limit:break
   from auto_quality_inventory_v2 import refresh
   refresh(R);time.sleep(15);continue
  with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
   pending={pool.submit(verify,row):row[0] for row in rows}
   for future in concurrent.futures.as_completed(pending):
    try:item,report,out,work=future.result();publish(db,item,report,out,work,a.publish)
    except Exception as exc:
     if db.in_transaction:db.rollback()
     print(json.dumps({'at':now(),'id':pending[future],'stage':'worker_error','error':repr(exc)}),flush=True);continue
    counts[report['state']]=counts.get(report['state'],0)+1;total+=1
    print(json.dumps({'at':now(),'id':report['id'],'stage':report['state'],'seconds':report['seconds'],'failures':report['failures']}),flush=True)
  if a.publish and any(counts.get(k,0) for k in ('accepted',)):write_index(db)
  runtime={'at':now(),'processed':total,'counts':counts,'workers':a.workers,'chunk':a.chunk,'elapsed_seconds':time.monotonic()-started,'checks_per_minute':60*total/max(1,time.monotonic()-started),'goal_complete':False,'policy':POLICY};atomic(W/'auto_quality_runtime.json',(json.dumps(runtime,indent=2)+'\n').encode())
  if a.limit and total>=a.limit:break
 if a.publish:write_index(db)
 print(json.dumps({'at':now(),'processed':total,'counts':counts,'drained':DRAIN,'goal_complete':False}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);p.add_argument('--chunk',type=int,default=64);p.add_argument('--limit',type=int,default=0);p.add_argument('--publish',action='store_true');p.add_argument('--watch',action='store_true');p.add_argument('--id',dest='ids',action='append',default=[]);main(p.parse_args())
