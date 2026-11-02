"""Revision-owned execution graph candidate producer; never accepts a job.

Default: bounded one-worker dry run. Explicit --publish stages immutable clean
versions and swaps only an owned jobs pointer. Prior pairs and model history
remain intact. A failed revision is not selected again without --retry-failed,
a new implementation policy, or a new source/code/image revision.
"""
import argparse,collections,concurrent.futures,datetime,fcntl,hashlib,io,json,os,shutil,sqlite3,time,traceback,uuid,xml.etree.ElementTree as E
from pathlib import Path
from durable_sqlite import begin,commit

R=Path(os.environ.get('IMG2CODE_ROOT','/backup/shaoshitong/img2code_20261029')).resolve();W=R/'conversion'
STATE='tikz_execution_candidate_v1_producing';TABLE='tikz_execution_candidates_v1';HISTORY='tikz_execution_candidate_history_v1'
IDLE=('rendered','needs_quality_repair','harness_review_pending')
SNAPSHOT_COLUMNS='state,output_record,worker_pid,error,updated_at,input_record,input_manifest,attempts,route,format,source,category'
KEY_COLUMNS='id,code_hash,image_hash,source_code_hash,source_image_hash,policy'
MODEL_TABLES=('harness_queue','harness_queue_v2','harness_queue_v3')
METHOD='actual_pgf_execution_named_graph_painted_native_markers_v3'
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.exec.tmp');temp.write_bytes(data);temp.replace(path)


def exists(db,name):return db.execute('select 1 from sqlite_master where type="table" and name=?',(name,)).fetchone() is not None
def model_running(db,id):return any(exists(db,t) and db.execute('select 1 from '+t+' where id=? and state="running"',(id,)).fetchone() for t in MODEL_TABLES)
def snapshot(db,id):return db.execute('select '+SNAPSHOT_COLUMNS+' from jobs where id=?',(id,)).fetchone()
def key_for(id,old,policy):return (id,old['code_sha256'],old['image_sha256'],old['source_code_sha256'],old['source_image_sha256'],policy)


def init(db):
 begin(db);db.execute('create table if not exists '+TABLE+'(id text,code_hash text,image_hash text,source_code_hash text,source_image_hash text,policy text,state text,owner_pid integer,claim_token text,run_id text,attempts integer,record text,updated_at text,primary key('+KEY_COLUMNS+'))');db.execute('create table if not exists '+HISTORY+'(id text,code_hash text,image_hash text,source_code_hash text,source_image_hash text,policy text,claim_token text,record text,updated_at text,primary key('+KEY_COLUMNS+',claim_token))');commit(db)


def eligible_record(old):
 return old.get('source_format')=='tikz' and old.get('code_sha256') and old.get('image_sha256') and old.get('source_code_sha256') and old.get('source_image_sha256') and old.get('source_render_pdf') and old.get('source_render_svg') and not old.get('edges') and not old.get('native_page_padding') and not old.get('native_canvas_contract')


def stage_eligible(db,key,run_id,publish,retry_failed):
 row=db.execute('select state,run_id,attempts from '+TABLE+' where '+ ' and '.join(c+'=?' for c in KEY_COLUMNS.split(',')),key).fetchone()
 if row is None:return True
 state,prior_run,attempts=row
 if prior_run==run_id or state in ('running','published_candidate','stale_revision_or_ownership'):return False
 return state=='deferred_model_running' or publish and state=='validated_dry_run' or retry_failed and attempts<2 and state in ('unsupported_source','failed_retained_prior','publication_failed','recovered_abandoned')


def select_candidate(db,policy,run_id,publish=False,retry_failed=False,ids=()):
 guard=''.join(' and not exists(select 1 from '+t+' h where h.id=j.id and h.state="running")' for t in MODEL_TABLES if exists(db,t));restriction=' and j.id in ('+','.join('?' for _ in ids)+')' if ids else ''
 # Skip completed/failed revision keys in SQL rather than re-walking a growing
 # Python prefix of a 15k+ cohort for every claimed item.
 audit=''' and not exists(select 1 from '''+TABLE+''' t where t.id=j.id and t.code_hash=json_extract(j.output_record,'$.code_sha256') and t.image_hash=json_extract(j.output_record,'$.image_sha256') and t.source_code_hash=json_extract(j.output_record,'$.source_code_sha256') and t.source_image_hash=json_extract(j.output_record,'$.source_image_sha256') and t.policy=? and (t.run_id=? or not(t.state='deferred_model_running' or (? and t.state='validated_dry_run') or (? and t.attempts<2 and t.state in ('unsupported_source','failed_retained_prior','publication_failed','recovered_abandoned')))))'''
 sql='''select j.id,'''+','.join('j.'+c for c in SNAPSHOT_COLUMNS.split(','))+''' from jobs j where j.format='tikz' and j.state in ('rendered','needs_quality_repair','harness_review_pending') and j.worker_pid is null and j.output_record is not null and coalesce(json_extract(j.output_record,'$.edges'),0)=0 and json_extract(j.output_record,'$.native_page_padding') is null and json_extract(j.output_record,'$.native_canvas_contract') is null'''+guard+audit+restriction+' order by j.id'
 for row in db.execute(sql,[policy,run_id,int(publish),int(retry_failed),*ids]):
  old=json.loads(row[2]);key=key_for(row[0],old,policy) if eligible_record(old) else None
  if key and stage_eligible(db,key,run_id,publish,retry_failed):return row[0],tuple(row[1:])
 return None


def claim(db,selection,policy,run_id,publish=False,retry_failed=False,pid=None):
 id,prior=selection;pid=pid or os.getpid();old=json.loads(prior[1]);key=key_for(id,old,policy);where=' and '.join(c+'=?' for c in KEY_COLUMNS.split(','));begin(db)
 try:
  if snapshot(db,id)!=prior or prior[0] not in IDLE or prior[2] is not None or model_running(db,id) or not eligible_record(old) or not stage_eligible(db,key,run_id,publish,retry_failed):db.rollback();return None
  previous=db.execute('select attempts,claim_token,record from '+TABLE+' where '+where,key).fetchone()
  if previous:db.execute('insert or replace into '+HISTORY+' values(?,?,?,?,?,?,?,?,?)',(*key,previous[1],previous[2],now()))
  token=uuid.uuid4().hex;stamp=now();record={'id':id,'key':list(key),'token':token,'pid':pid,'run_id':run_id,'prior_snapshot':list(prior),'claimed_at':stamp,'accepted':False}
  db.execute('insert or replace into '+TABLE+' values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(*key,'running',pid,token,run_id,(previous[0] if previous else 0)+1,json.dumps(record),stamp));db.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(STATE,pid,stamp,id));record['owned_snapshot']=list(snapshot(db,id));db.execute('update '+TABLE+' set record=? where '+where,(json.dumps(record),*key));commit(db);return record
 except Exception:db.rollback();raise


def _restore(db,id,prior):
 db.execute('update jobs set '+','.join(c+'=?' for c in SNAPSHOT_COLUMNS.split(','))+' where id=?',(*prior,id))


def _checked(path,digest,clean=False):
 p=Path(path).resolve()
 if clean and not p.is_relative_to((R/'clean').resolve()):raise ValueError('Dataset payload is outside clean: '+str(p))
 data=p.read_bytes()
 if sha(data)!=digest:raise ValueError('Payload/source revision changed: '+str(path))
 return data


def recheck_old(old):
 count=0
 for key,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_pdf','source_render_pdf_sha256'),('source_render_png','source_render_png_sha256')]:
  if old.get(key):_checked(R/old[key],old[digest],True);count+=1
 for font in old.get('native_embedded_fonts',[]):
  for key,digest in [('file','sha256'),('original_file','original_sha256')]:
   if font.get(key):_checked(R/font[key],font[digest],True);count+=1
 return count


def publish_artifacts(current,out,report,work):
 """Fast final check of already staged immutable files while SQL ownership holds."""
 from tikz_execution_source_profile_v3 import FIELD
 old=json.loads(current['prior_snapshot'][1]);assert report.get('candidate_checks_passed') is True and report.get('accepted') is False and out['quality_state'].startswith('pending_')
 assert report['policy']==current['key'][-1]
 for key in ('id','source_code_sha256','source_image_sha256','source_pair_sha256'):
  if key in old:assert out.get(key)==old[key],'Original source identity changed'
 assert out.get('previous_candidate_archive')==old.get('previous_candidate_archive'),'Legacy harness archive locator must remain compatible'
 recheck_old(old)
 for key,digest in [('code_file','code_sha256'),('image_file','image_sha256')]:assert out[key]!=old[key];_checked(R/out[key],out[digest],True)
 for item in out[FIELD]['files'].values():_checked(R/item['file'],item['sha256'],True)
 assert json.loads((R/out['code_file']).parent.joinpath('conversion.json').read_text())==out
 archive=R/out['execution_prior_pair_archive'];assert json.loads((archive/'conversion.json').read_text())==old
 _checked(archive/'diagram.drawio',old['code_sha256'],True);_checked(archive/'image.png',old['image_sha256'],True)


def finish(db,current,report,out=None,work=None,publish=False,artifact_writer=publish_artifacts):
 id=current['id'];key=tuple(current['key']);where=' and '.join(c+'=?' for c in KEY_COLUMNS.split(','));prior=tuple(current['prior_snapshot']);owned=tuple(current['owned_snapshot']);begin(db)
 try:
  owner=db.execute('select state,owner_pid,claim_token from '+TABLE+' where '+where,key).fetchone()
  if owner!=('running',current['pid'],current['token']) or snapshot(db,id)!=owned:report.update(state='stale_revision_or_ownership',accepted=False)
  elif model_running(db,id):_restore(db,id,prior);report.update(state='deferred_model_running',accepted=False)
  elif out is not None and publish:
   artifact_writer(current,out,report,work);db.execute('update jobs set state="needs_quality_repair",output_record=?,worker_pid=null,error=?,updated_at=? where id=?',(json.dumps(out,ensure_ascii=False),'Unaccepted PGF execution native graph candidate; QA v3 required',now(),id))
   for table in MODEL_TABLES:
    if exists(db,table):db.execute('update '+table+' set state="held_for_quality_v3",worker_pid=null,heartbeat=? where id=? and state!="running"',(now(),id))
   report.update(state='published_candidate',accepted=False)
  else:
   _restore(db,id,prior);report.update(state='validated_dry_run' if out is not None else report.get('state','failed_retained_prior'),accepted=False)
  if owner==('running',current['pid'],current['token']):db.execute('update '+TABLE+' set state=?,record=?,updated_at=? where '+where,(report['state'],json.dumps(report,ensure_ascii=False),now(),*key))
  commit(db)
 except Exception:db.rollback();raise
 if work is not None:
  try:atomic(Path(work)/'publication_result.json',(json.dumps(report,indent=2)+'\n').encode())
  except OSError:pass # The complete audit is already durable in SQL.
 return report['state']


def recover_dead(db):
 """Explicit recovery only; never terminate or take a live owner/model call."""
 recovered=[]
 for raw,pid in db.execute('select record,owner_pid from '+TABLE+' where state="running"').fetchall():
  try:os.kill(pid,0);continue
  except ProcessLookupError:pass
  except PermissionError:continue
  current=json.loads(raw);current['owned_snapshot']=current.get('owned_snapshot',[])
  if snapshot(db,current['id'])!=tuple(current['owned_snapshot']) or model_running(db,current['id']):continue
  stage=finish(db,current,{'id':current['id'],'state':'recovered_abandoned','accepted':False,'owner_was_dead':pid,'at':now()});recovered.append({'id':current['id'],'stage':stage})
 return recovered


def implementation():
 from tikz_execution_source_profile_v3 import SCRIPTS
 names=set(SCRIPTS)|{'tikz_execution_candidate_batch_v1.py','tectonic_compile.py','sandbox_runner.py','native_worker.py','durable_sqlite.py','auto_quality_move.py','harness_source_provenance.py','svg_batch.py','tikz_literal_graph.py'}
 paths=[Path(__file__).parent/name for name in sorted(names)]+[R/'scripts/curate_derived.py',R/'scripts/curate_pairs.py',W/'rendering_paintbounds_strict/remote_render.py',R/'evaluation/assets/viewer-static.min.js',R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json',W/'runtime/tectonic/tectonic']
 for name in ('tikz.code.tex','pgfmoduleshapes.code.tex','pgfcorearrows.code.tex'):paths.append(next((W/'runtime/tectonic/cache/bundles/data').glob('*/'+name)))
 files={str(p):sha(p.read_bytes()) for p in paths};return 'pgf_execution_candidate_v1:'+sha(json.dumps(files,sort_keys=True).encode())[:20],files


def ensure_implementation(policy,files):
 if implementation()!=(policy,files):raise RuntimeError('Pinned execution candidate implementation changed; start a new versioned worker')


def require_bounded_smoke(policy,publish,workers,limit):
 if not publish and workers==1 and limit<=3:return
 receipt=json.loads((W/'tikz_execution_candidate_v1_smoke.json').read_bytes())
 if not receipt.get('ok') or receipt.get('published') is not False or receipt.get('accepted')!=0 or receipt['summary']['policy']!=policy or not receipt.get('all_selected_job_snapshots_exactly_restored') or not receipt.get('all_model_queue_rows_unchanged') or not receipt.get('all_source_and_native_pair_hashes_unchanged') or not receipt.get('source_profile_v3_api_tests',{}).get('relocated_actual_proof_bundle_passed') or not receipt.get('state_and_rollback_tests',{}).get('ok'):raise ValueError('This implementation requires a passing bounded nonpublishing smoke and state/rollback/API tests before publishing or broader batching')


def _font_signature(info):
 out={}
 for cell in info.get('actual_platform_font_usage',[]):
  faces=collections.Counter()
  for font in cell.get('fonts',[]):
   if font.get('glyphCount'):
    if not font.get('isCustomFont') or not font.get('postScriptName'):raise ValueError('Native source text needs proven embedded physical fonts')
    faces[font['postScriptName']]+=font['glyphCount']
  if faces:out[cell['cell']]=dict(faces)
 return out


def generate(current,policy,files,publish=False):
 from PIL import Image
 from native_worker import native
 from harness_source_provenance import validate_source_record
 from tikz_execution_graph import compile_execution_graph,parse_events
 from tikz_execution_binding import bind_execution
 from tikz_execution_marker_paint_fit import fit_painted_markers
 import tikz_execution_source_profile as source_base
 import tikz_execution_source_profile_v3 as profile
 old=json.loads(current['prior_snapshot'][1]);validate_source_record(old);recheck_old(old);work=W/'tikz_execution_candidates_v1'/current['id']/(current['key'][1]+'_'+current['key'][2][:16])/policy.rsplit(':',1)[-1]/current['token'];work.mkdir(parents=True);proof=work/'proof';proof.mkdir();raw=current['prior_snapshot'][1];base_xml=_checked(R/old['code_file'],old['code_sha256'],True).decode();baseline_png=_checked(R/old['image_file'],old['image_sha256'],True);source=_checked(R/old['original_source_code'],old['source_code_sha256'],True);atomic(proof/'baseline_record.json',raw.encode());atomic(proof/'baseline.drawio',base_xml.encode());atomic(proof/'baseline.png',baseline_png)
 sidecar=compile_execution_graph(source,proof/'execution')
 if not sidecar.get('ok'):raise ValueError('Unsupported/incomplete actual PGF execution graph: '+json.dumps(sidecar.get('graph',{}).get('failures',sidecar.get('error'))))
 source_base._pdf_pixels((R/old['source_render_pdf']).read_bytes(),proof/'execution',sidecar);dom,matrix=source_base._capture((R/old['source_render_svg']).read_bytes(),(R/old['original_reference']).read_bytes());events=parse_events((proof/'execution/instrumented/source.iic').read_text());candidate,binding=bind_execution(base_xml,dom,sidecar,events,matrix)
 if not binding['complete']:raise ValueError('Unsupported execution/source-native binding: '+json.dumps(binding['issues']))
 if binding['binding']['native_arrowheads']:candidate,binding,fit=fit_painted_markers(candidate,dom,binding,R/'evaluation/assets/viewer-static.min.js',0)
 else:fit={'markers':[],'policy':'no_source_markers'}
 width,height=Image.open(io.BytesIO(baseline_png)).size;renderer=W/'rendering_paintbounds_strict/remote_render.py';cache=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json';before=native.native_job(base_xml,width,height,180,renderer,8192,cache);fresh=native.native_job(candidate,width,height,180,renderer,8192,cache)
 if not before['ok'] or not fresh['ok']:raise ValueError('Actual native renderer failed')
 if before['png']!=baseline_png:raise ValueError('Current baseline native PNG does not reproduce under the pinned runtime')
 font_signature=_font_signature(before['native_render'])
 if font_signature!=_font_signature(fresh['native_render']):raise ValueError('Original text physical faces/glyph counts changed')
 from auto_quality_move import audit
 moves=audit(candidate)
 if len(moves['moves'])!=2*binding['source_edges']:raise ValueError('Incomplete actual connector endpoint movement proof')
 for move in moves['moves']:
  if abs(move['delta']['x']-17)>.05 or abs(move['delta']['y']-11)>.05:raise ValueError('Actual native edge endpoint failed to follow its source node')
  if any(abs(c['x']-17)>.05 or abs(c['y']-11)>.05 for c in move.get('child_deltas',[])):raise ValueError('Native node text child did not move as a whole')
  for group in move.get('label_member_deltas',[]):
   members=group['members']
   if not members or any(abs(c['x']-members[0]['x'])>.05 or abs(c['y']-members[0]['y'])>.05 for c in members):raise ValueError('Native complete edge label group did not move together')
 code_hash=sha(candidate.encode());image_hash=sha(fresh['png']);target=(R/old['code_file']).parent/'execution_v3'/(code_hash[:24]+'_'+image_hash[:16]+'_'+current['token'][:8]);archive=target/'prior_pair';cells=list(E.fromstring(candidate).iter('mxCell'));out={**old,'code_file':str((target/'diagram.drawio').relative_to(R)),'image_file':str((target/'image.png').relative_to(R)),'code_sha256':code_hash,'image_sha256':image_hash,'conversion_method':METHOD,'connectivity':binding,'vertices':sum(c.get('vertex')=='1' for c in cells),'edges':binding['source_edges'],'bound_edges':binding['source_edges'],'render':fresh['native_render'],'quality_state':'pending_automatic_quality_v3_recheck','execution_prior_pair_archive':str(archive.relative_to(R)),'converted_at_utc':now(),'last_repair':{'method':METHOD,'model':None,'policy':policy},'native_font_validation':{'ok':True,'method':'execution_graph_reparenting_preserved_physical_faces_and_glyph_counts_v3','output_code_sha256':code_hash,'base_verified_code_sha256':old['code_sha256'],'input_image_sha256':old['image_sha256'],'output_image_sha256':image_hash,'all_actual_fonts_custom':True,'all_original_cell_physical_faces_and_glyph_counts_preserved':True,'actual_custom_font_text_cells':len(font_signature),'physical_faces_and_counts_by_cell':font_signature,'font_files':len(old.get('native_embedded_fonts',[]))}}
 for key in ('accepted_at_utc','automatic_quality_policy','automatic_quality_audit','root_review','root_acceptance'):out.pop(key,None)
 out[profile.FIELD]=profile.manifest(out,candidate,proof,0);source_qa=profile.check_execution_profile(out,candidate);marker_qa=profile.check_execution_marker_render(out,candidate,fresh['png'])
 if not source_qa['ok'] or not marker_qa['ok']:raise ValueError('Batch source/marker QA failed: '+json.dumps({'source':source_qa['failures'],'marker':marker_qa['failures']}))
 result={'id':current['id'],'at':now(),'policy':policy,'implementation':files,'input_code_sha256':old['code_sha256'],'input_image_sha256':old['image_sha256'],'source_code_sha256':old['source_code_sha256'],'source_image_sha256':old['source_image_sha256'],'output_code_sha256':code_hash,'output_image_sha256':image_hash,'candidate_checks_passed':True,'accepted':False,'source_nodes':binding['source_nodes'],'native_edges':binding['source_edges'],'actual_endpoint_moves':len(moves['moves']),'whole_edge_label_groups':len(binding['binding']['edge_child_labels']),'free_annotations':len(binding['retained_free_annotation_serials']),'work':str(work.relative_to(R)),'source_qa':source_qa,'marker_qa':marker_qa,'paint_fitting':fit}
 for name,data in [('candidate.drawio',candidate.encode()),('candidate.png',fresh['png']),('native_moves.json',(json.dumps(moves,indent=2)+'\n').encode()),('baseline_native_render.json',(json.dumps(before['native_render'],indent=2)+'\n').encode()),('candidate_native_render.json',(json.dumps(fresh['native_render'],indent=2)+'\n').encode())]:atomic(work/name,data)
 if publish:
  # Immutable clean files are staged before holding a database write lock.
  for name,item in out[profile.FIELD]['files'].items():
   path=R/item['file'];dest=target/'proof'/name;data=path.read_bytes()
   if dest.exists() and dest.read_bytes()!=data:raise ValueError('Immutable clean proof target differs')
   if not dest.exists():atomic(dest,data)
  out[profile.FIELD]=profile.relocate(out[profile.FIELD],target/'proof')
  for name,data in [('diagram.drawio',candidate.encode()),('image.png',fresh['png'])]:
   dest=target/name
   if dest.exists() and dest.read_bytes()!=data:raise ValueError('Immutable clean candidate target differs')
   if not dest.exists():atomic(dest,data)
  for name,data in [('conversion.json',raw.encode()),('diagram.drawio',base_xml.encode()),('image.png',baseline_png)]:
   dest=archive/name
   if dest.exists() and dest.read_bytes()!=data:raise ValueError('Immutable original-pair archive differs')
   if not dest.exists():atomic(dest,data)
  staged=profile.check_execution_marker_render(out,candidate,fresh['png'])
  if not staged['ok']:raise ValueError('Relocated clean execution proof failed: '+json.dumps(staged['failures']))
  atomic(target/'conversion.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode())
 atomic(work/'candidate_record.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode());atomic(work/'report.json',(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());ensure_implementation(policy,files);return work,out,result


def worker(index,limit,publish,retry_failed,ids,run_id,policy,files):
 db=sqlite3.connect(W/'jobs.sqlite',timeout=2);done=0;counts=collections.Counter()
 while done<limit:
  ensure_implementation(policy,files);selection=select_candidate(db,policy,run_id,publish,retry_failed,ids)
  if selection is None:break
  current=claim(db,selection,policy,run_id,publish,retry_failed)
  if current is None:continue
  started=time.monotonic();out=None;work=None
  try:work,out,report=generate(current,policy,files,publish)
  except Exception as error:
   report={'id':current['id'],'at':now(),'policy':policy,'state':'unsupported_source' if isinstance(error,ValueError) and ('Unsupported' in str(error) or 'unsupported' in str(error)) else 'failed_retained_prior','error':repr(error)[:4000],'accepted':False,'previous_candidate_retained':True};work=W/'tikz_execution_candidates_v1'/current['id']/(current['key'][1]+'_'+current['key'][2][:16])/policy.rsplit(':',1)[-1]/current['token'];work.mkdir(parents=True,exist_ok=True);atomic(work/'traceback.txt',traceback.format_exc().encode())
  report['seconds']=round(time.monotonic()-started,3)
  try:ensure_implementation(policy,files);stage=finish(db,current,report,out,work,publish)
  except Exception as error:stage=finish(db,current,{**report,'state':'publication_failed','error':repr(error),'accepted':False},None,work,False)
  counts[stage]+=1;done+=1;print(json.dumps({'at':now(),'worker':index,'id':current['id'],'stage':stage,'seconds':report['seconds'],'error':report.get('error'),'accepted':False}),flush=True)
 db.close();return {'worker':index,'processed':done,'counts':dict(counts),'accepted':0}


def main(args):
 if not 1<=args.workers<=4 or not 1<=args.limit<=1000:raise ValueError('Bounded worker count 1..4 and positive per-worker limit <=1000 required')
 lock=(W/'tikz_execution_candidate_batch_v1.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);policy,files=implementation();require_bounded_smoke(policy,args.publish,args.workers,args.limit);db=sqlite3.connect(W/'jobs.sqlite',timeout=2);init(db);recovered=recover_dead(db) if args.recover_dead else [];db.close();run_id=uuid.uuid4().hex;owner={'pid':os.getpid(),'at':now(),'run_id':run_id,'policy':policy,'implementation':files,'workers':args.workers,'limit_per_worker':args.limit,'publish':args.publish,'retry_failed':args.retry_failed,'accepted':0,'recovered':recovered};atomic(W/'tikz_execution_candidate_v1_owner.json',(json.dumps(owner,indent=2)+'\n').encode())
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:results=[f.result() for f in [pool.submit(worker,i,args.limit,args.publish,args.retry_failed,args.ids,run_id,policy,files) for i in range(args.workers)]]
 summary={'at':now(),'run_id':run_id,'policy':policy,'workers':results,'accepted':0,'published_only_if_explicit':args.publish};atomic(W/'tikz_execution_candidate_v1_summary.json',(json.dumps(summary,indent=2)+'\n').encode());print(json.dumps(summary),flush=True)


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=1);p.add_argument('--limit',type=int,default=3);p.add_argument('--publish',action='store_true');p.add_argument('--retry-failed',action='store_true');p.add_argument('--recover-dead',action='store_true');p.add_argument('--id',dest='ids',action='append',default=[]);main(p.parse_args())
