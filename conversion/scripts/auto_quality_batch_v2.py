"""Fixed-program quality routing and automatic release of verified current revisions."""
import argparse,concurrent.futures,fcntl,signal,hashlib,io,json,os,sqlite3,time,traceback,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from native_worker import R,W,now,native,pair
from durable_sqlite import begin,commit
from auto_quality_common_v2 import POLICY,checked,sha,structure_checks,resource_checks,image_quality,native_source_profile,require_rendered_text,registration_record
from strict_canvas_gate import require_declared_page
from auto_quality_dispatch_v2 import initialize as initialize_dispatch,route_failure

DEPENDENCIES=('auto_quality_batch_v2.py','auto_quality_dispatch_v2.py','auto_quality_common.py','auto_quality_common_v2.py','auto_quality_source_graph.py','auto_quality_source_vector.py','auto_quality_source_vector_v2.py','html_range_extractor_v2.py','html_source_repair_v2.py','auto_quality_canvas_repair.py','auto_quality_font_repair.py','native_font_embedding_batch.py','native_text_clip.py','native_clip_reference_box.py','auto_quality_move.py','tikz_literal_graph.py','tikz_literal_connectivity.py','svg_source_coverage_v2.py','mermaid_semantic_v4.py','svg_dom_pdf.js','svg_dom_v6.js','html_dom_clip.js','strict_canvas_gate.py','native_worker.py')
IMPLEMENTATION={name:sha((Path(__file__).parent/name).read_bytes()) for name in DEPENDENCIES if (Path(__file__).parent/name).exists()}
for path in (W/'rendering_paintbounds_strict/remote_render.py',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'):
 if path.exists():IMPLEMENTATION[str(path)]=sha(path.read_bytes())
POLICY=POLICY+':'+sha(json.dumps(IMPLEMENTATION,sort_keys=True).encode())[:16]

def ensure_pinned():
 for name,digest in IMPLEMENTATION.items():
  path=Path(name) if Path(name).is_absolute() else Path(__file__).parent/name
  assert sha(path.read_bytes())==digest,'Pinned quality implementation changed: '+name

IDLE=('rendered','needs_quality_repair','harness_review_pending')
RENDERER=W/'rendering_paintbounds_strict/remote_render.py'

def atomic(path,data):
 tmp=path.with_name(path.name+'.autoquality.tmp');tmp.write_bytes(data);tmp.replace(path)

def profile(record,xml,source):
 fmt=record['source_format']
 if fmt in ('drawio','tikz') and record.get('auto_quality_canvas_repair'):
  contract=record['_verified_reference_registration'];baseline=checked(R,contract['baseline_code'],contract['baseline_code_sha256']).decode();before=json.loads(checked(R,contract['baseline_record'],contract['baseline_record_sha256']))
  if fmt=='drawio':result=native_source_profile(before,baseline,source)
  else:
   from auto_quality_source_graph import check_graph_profile
   result=check_graph_profile(before,baseline)
  result['evidence']['current_code_sha256']=sha(xml.encode());result['evidence']['canvas_only_transformation_independently_verified']=True
  return result
 if fmt=='drawio':return native_source_profile(record,xml,source)
 if fmt in ('mermaid','tikz'):
  from auto_quality_source_graph import check_graph_profile
  return check_graph_profile(record,xml)
 from auto_quality_source_vector_v2 import check_vector_profile
 return check_vector_profile(record,xml)

def verify(item):
 ensure_pinned()
 id,state,raw,input_raw,route=item;started=time.monotonic();r=json.loads(raw);digest=r['code_sha256'];work=W/'auto_quality_v2'/id/(digest+'_'+r['image_sha256'][:16])/POLICY.rsplit(':',1)[-1];work.mkdir(parents=True,exist_ok=True)
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
  try:coverage=profile(r,xml,source)
  finally:
   # An active Playwright Sync context cannot nest the independent movement runtime.
   if r['source_format'] in ('tikz','mermaid'):
    from auto_quality_source_graph import close_worker_runtime
    close_worker_runtime()
  report['checks']['source']=coverage
  if not coverage['supported']:raise ValueError('source_profile_not_implemented: '+json.dumps(coverage['failures'],ensure_ascii=False))
  if not coverage['ok']:raise ValueError('source_coverage_failure: '+json.dumps(coverage['failures'],ensure_ascii=False))
  model=E.fromstring(xml).find('.//mxGraphModel');width=int(round(float(model.get('pageWidth',0))));height=int(round(float(model.get('pageHeight',0))))
  if not(0<width<=8192 and 0<height<=8192):raise ValueError('unsupported_native_canvas')
  rendered=native.native_job(xml,width,height,180,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json')
  if not rendered['ok']:raise ValueError('fresh_native_render_failed: '+str({k:v for k,v in rendered.items() if k!='png'})[:1200])
  freshpng=rendered.pop('png');info=rendered['native_render'];require_declared_page(info,width,height);report['checks']['render']={'code_sha256':digest,'image_sha256':sha(freshpng),'strict_outside_page_pixels':0,'renderer_sha256':sha(RENDERER.read_bytes()),'canvas':[width,height],'actual_text_cells':len(info.get('actual_text_positions',[]))}
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
   from auto_quality_move import audit
   moves=audit(xml)
   if len(moves['moves'])!=2*report['checks']['structure']['edges']:raise ValueError('incomplete_native_endpoint_movement_proof')
   for move in moves['moves']:
    if abs(move['delta']['x']-17)>.05 or abs(move['delta']['y']-11)>.05:raise ValueError('native_endpoint_does_not_follow_node')
    if any(abs(c['x']-17)>.05 or abs(c['y']-11)>.05 for c in move.get('child_deltas',[])):raise ValueError('node_label_does_not_follow_node')
    for group in move.get('label_member_deltas',[]):
     members=group['members']
     if any(abs(c['x']-members[0]['x'])>.05 or abs(c['y']-members[0]['y'])>.05 for c in members):raise ValueError('edge_label_background_or_text_moves_independently')
   (work/'movement.json').write_text(json.dumps(moves,indent=2)+'\n');report['checks']['native_editing']={'endpoint_moves':len(moves['moves']),'ok':True,'evidence':str((work/'movement.json').relative_to(R))}
  else:report['checks']['native_editing']={'endpoint_moves':0,'ok':True,'source_profile_proves_no_semantic_edges':True}
  # Recheck the payload after expensive browser work, before publication CAS.
  checked(R,r['code_file'],digest);checked(R,r['image_file'],r['image_sha256'])
  verified_png=(R/r['image_file']).with_name('image.native.'+sha(freshpng)[:20]+'.png')
  r={k:v for k,v in r.items() if not k.startswith('_verified_')}
  out={**r,'image_file':str(verified_png.relative_to(R)),'image_sha256':sha(freshpng),'render':info,'quality_state':'accepted_automatic_source_and_native_quality_v2','automatic_quality_policy':POLICY,'automatic_quality_audit':str((work/'audit.json').relative_to(R)),'source_coverage_automatic':coverage,'accepted_at_utc':now(),'metrics':{**r.get('metrics',{}),'automatic_visual_quality':visual}}
  report['state']='qualified';report['new_png_sha256']=sha(freshpng)
 except Exception as exc:
  report['state']='repair_required';report['failures'].append(str(exc)[:2500]);report['exception_type']=type(exc).__name__
 report['seconds']=round(time.monotonic()-started,3);(work/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 if out:atomic(work/'fresh.png',freshpng);atomic(work/'candidate_record.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
 return item,report,out,work

def publish(db,item,report,out,work,enabled):
 id,state,raw,input_raw,route=item;r=json.loads(raw);begin(db)
 current=db.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()
 if current!=(state,raw,None):report['state']='stale_revision';out=None
 elif out and enabled:
  # All writers claim via SQLite; holding this short transaction prevents races.
  checked(R,r['code_file'],r['code_sha256']);checked(R,r['image_file'],r['image_sha256'])
  archive=work/'before';archive.mkdir(exist_ok=True);atomic(archive/'conversion.json',raw.encode());atomic(archive/'image.png',(R/r['image_file']).read_bytes())
  # A versioned native PNG preserves the prior candidate even on interrupted publication.
  atomic(R/out['image_file'],(work/'fresh.png').read_bytes());atomic((R/out['code_file']).parent/'conversion.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
  db.execute("update auto_quality_exceptions_v1 set state='resolved_by_verified_revision',updated_at=? where id=? and state in ('pending','repaired_pending_batch_qa')",(now(),id))
  db.execute('update jobs set state="accepted",output_record=?,error=NULL,worker_pid=NULL,updated_at=? where id=?',(json.dumps(out,ensure_ascii=False),now(),id));report['accepted']=True;report['state']='accepted'
  # Quiesce only idle model entries for this newly accepted revision.
  if db.execute("select 1 from sqlite_master where name='harness_queue_v3'").fetchone():db.execute("update harness_queue_v3 set state='resolved',heartbeat=?,worker_pid=NULL,error=NULL where id=? and state!='running'",(now(),id))
 elif current==(state,raw,None) and enabled and report['state']=='repair_required':
  reason='; '.join(report['failures'])
  source_failures=report.get('checks',{}).get('source',{}).get('failures') or []
  source_reasons=[x.get('reason','') if isinstance(x,dict) else str(x) for x in source_failures]
  if 'source_profile_not_implemented' in reason or source_reasons and all(x.startswith('unsupported') for x in source_reasons):repair_route='source_profile_extension'
  elif any(x in ('source_profile_validation_error','source_graph_validation_error') for x in source_reasons):repair_route='resource_or_runtime_repair'
  elif 'font_portability' in reason:repair_route='deterministic_font_embedding'
  elif 'source_coverage_failure' in reason or 'raster_anomaly' in reason:repair_route='source_geometry_or_harness'
  elif 'Native content' in reason or 'outside' in reason or 'canvas' in reason:repair_route='deterministic_canvas_repair'
  else:repair_route='resource_or_runtime_repair'
  db.execute('insert or replace into auto_quality_exceptions_v1 values(?,?,?,?,?,?,?,?)',(id,r['code_sha256'],r['image_sha256'],POLICY,repair_route,'pending',reason,now()))
  updated=r
  if repair_route=='source_geometry_or_harness' and db.execute('select input_manifest from jobs where id=?',(id,)).fetchone()[0]:
   updated,dispatch=route_failure(db,r,report,root=R);report['model_dispatch']=dispatch
  if updated!=r:atomic((R/r['code_file']).parent/'conversion.json',(json.dumps(updated,ensure_ascii=False,indent=2)+'\n').encode())
  # The existing remote pool consumes needs_quality_repair, including failures
  # first observed on a model result that used to wait for individual review.
  target='needs_quality_repair' if repair_route!='source_profile_extension' else state
  db.execute('update jobs set state=?,output_record=?,error=?,updated_at=? where id=?',(target,json.dumps(updated,ensure_ascii=False),reason[:2500],now(),id))
 db.execute('insert or replace into auto_quality_audits_v1 values(?,?,?,?,?,?,?)',(id,r['code_sha256'],r['image_sha256'],POLICY,report['state'],json.dumps(report,ensure_ascii=False),now()));commit(db);(work/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

def write_index(db):
 index=R/'release/drawio_manifest.inprogress.jsonl';tmp=index.with_name(index.name+'.autoquality.tmp')
 reader=sqlite3.connect(W/'jobs.sqlite',timeout=60);reader.execute('begin')
 with tmp.open('w') as f:
  for raw, in reader.execute('select output_record from jobs where state="accepted" order by id'):f.write(raw+'\n')
 tmp.replace(index);reader.rollback();reader.close()

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
  selection=(' and c.id in ('+','.join('?' for _ in a.ids)+')') if a.ids else ''
  rows=db.execute('''with chosen as materialized(select c.* from auto_quality_candidates_v1 c where c.route in ('graph','vector','native') and not exists(select 1 from auto_quality_audits_v1 q where q.id=c.id and q.code_hash=c.code_hash and q.image_hash=c.image_hash and q.policy=?)'''+selection+''' order by c.priority desc,c.id limit ?) select j.id,j.state,j.output_record,j.input_record,c.route from chosen c join jobs j on j.id=c.id where j.state in ('rendered','needs_quality_repair','harness_review_pending') and j.worker_pid is NULL and json_extract(j.output_record,'$.code_sha256')=c.code_hash and json_extract(j.output_record,'$.image_sha256')=c.image_hash''',[POLICY,*a.ids,a.chunk]).fetchall()
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
