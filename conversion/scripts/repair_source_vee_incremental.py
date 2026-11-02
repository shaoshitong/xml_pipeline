"""Apply and verify source VEE markers without discarding current native font repairs."""
import argparse,hashlib,json,os,shutil,sqlite3,traceback,io
from pathlib import Path
from PIL import Image
from native_worker import R,W,native,now
from durable_sqlite import begin,commit
from source_vee_incremental import patch
from native_vee_move_audit import audit as move_audit
from native_marker_tail_audit import audit as tail_audit
from marker_pixel_audit import audit as pixel_audit
from svg_source_coverage_v2 import audit as coverage_audit
from harness_graphviz_gate import check as graphviz_check
from harness_context_v4 import verify_source_fullname_faces,structure
from repair_svg_fullname_font_v2 import check_font_files
from source_svg_snapshot import auxiliary_hashes
from strict_canvas_gate import require_declared_page
from svg_pilot import metrics
sha=lambda b:hashlib.sha256(b).hexdigest()

def main(id):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists source_vee_repairs (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');row=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert row and row[0] in ('rendered','needs_quality_repair'),'Candidate not idle';state,raw=row;old=json.loads(raw);oldhash=old['code_sha256'];assert not D.execute('select 1 from source_vee_repairs where id=? and input_code_sha256=?',(id,oldhash)).fetchone(),'Revision already attempted';D.execute('insert into source_vee_repairs values (?,?,"running",NULL,?)',(id,oldhash,now()));D.execute('update jobs set state="source_vee_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(D)
 B=W/'source_vee_repairs'/id/oldhash;B.mkdir(parents=True,exist_ok=True);(B/'before_record.json').write_text(raw);report={'at':now(),'id':id,'input_code_sha256':oldhash,'accepted':False,'published':False};out=None
 try:
  assert old['native_font_validation']['output_code_sha256']==oldhash
  for key,hkey in [('code_file','code_sha256'),('image_file','image_sha256'),('original_reference','source_image_sha256'),('original_source_code','source_code_sha256')]:
   p=R/old[key];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==old[hkey],key
  check_font_files(old['native_embedded_fonts']);aux=auxiliary_hashes(old);xml=(R/old['code_file']).read_text();png=(R/old['image_file']).read_bytes();ref=(R/old['original_reference']).read_bytes();verified=old
  if not old.get('native_source_font_repair'):
   archive=(R/old['source_font_recovery_archive']).resolve();assert archive.is_relative_to(R/'conversion/harness_sessions');verified=json.loads((archive/'conversion.json').read_text())
   assert all(verified[k]==old[k] for k in ('id','source_code_sha256','source_image_sha256'))
   assert sha((archive/'diagram.drawio').read_bytes())==verified['code_sha256'];assert auxiliary_hashes(verified)==verified['native_source_font_repair']['source_auxiliary_hashes'];report['recovered_source_font_proof']={'archive':old['source_font_recovery_archive'],'original_verified_code_sha256':verified['code_sha256'],'current_base_code_sha256':oldhash}
  repair=verified['native_source_font_repair'];domfile=R/repair['source_after_dom_file'];assert domfile.resolve().is_relative_to(R/'clean') and sha(domfile.read_bytes())==repair['source_after_dom_sha256'];dom=json.loads(domfile.read_text());w,h=Image.open(io.BytesIO(ref)).size
  (B/'before.drawio').write_text(xml);(B/'before.png').write_bytes(png);new,proof=patch(xml,dom,w,h);assert all(m['side']=='end' and m['arrow']=='open' for m in proof['markers']);(B/'candidate.drawio').write_text(new);(B/'changes.json').write_text(json.dumps(proof,indent=2));coverage=coverage_audit(dom,new,proof['source_stats_after']);assert coverage['ok'],coverage;gate=graphviz_check(verified,new);assert gate['ok'],gate;struct=structure(new,{});assert struct['ok'],struct['errors']
  before=native.native_job(xml,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');after=native.native_job(new,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert before['ok'] and after['ok'];assert before['png']==png,'Stored baseline native PNG differs';require_declared_page(before['native_render'],w,h);require_declared_page(after['native_render'],w,h)
  for field in ('actual_platform_font_usage','actual_text_positions'):assert before['native_render'][field]==after['native_render'][field],field+' changed'
  verify_source_fullname_faces(verified,before['native_render']);verify_source_fullname_faces(verified,after['native_render'])
  for label,data in [('before_render',before['native_render']),('after_render',after['native_render'])]:(B/(label+'.json')).write_text(json.dumps(data,indent=2))
  (B/'candidate.png').write_bytes(after['png']);moves=move_audit(new,proof['markers']);tails=tail_audit(xml,new,proof['markers']);pixels=pixel_audit(png,after['png'],dom,proof['markers'],tails);assert pixels['ok'],pixels
  for label,data in [('moves',moves),('tails',tails),('pixels',pixels),('coverage',coverage),('source_editability',gate)]:(B/(label+'.json')).write_text(json.dumps(data,indent=2))
  assert aux==auxiliary_hashes(old);check_font_files(old['native_embedded_fonts']);assert sha(domfile.read_bytes())==repair['source_after_dom_sha256']
  before_score=metrics(ref,png)['ssim_512'];after_score=metrics(ref,after['png'])['ssim_512'];source_png=(R/repair['audit']).parent/'source_after.png';source_score=metrics(source_png.read_bytes(),after['png'])['ssim_512'];newhash=sha(new.encode());auditpath=str((B/'report.json').relative_to(R));stats=proof['source_stats_after'];stats['source_coverage']=coverage
  validation={**old['native_font_validation'],'method':'source_vee_marker_delta_preserving_verified_native_fonts_and_actual_text_positions','output_code_sha256':newhash,'base_verified_code_sha256':oldhash,'native_pixels_unchanged':False,'all_actual_fonts_and_text_positions_unchanged':True,'audit':auditpath}
  out={**old,'vertices':struct['vertices'],'edges':struct['edges'],'bound_edges':struct['bound_edges'],'code_sha256':newhash,'image_sha256':sha(after['png']),'render':{k:v for k,v in after['native_render'].items() if k!='actual_text_positions'},'native_font_validation':validation,'native_source_font_repair':{**repair,'original_font_repair_verified_code_sha256':repair.get('original_font_repair_verified_code_sha256',verified['code_sha256']),'subsequent_marker_repair_audit':auditpath},'svg_conversion':stats,'metrics':{**old.get('metrics',{}),'original_reference_ssim_512':after_score,'source_render_vs_drawio_ssim_512':source_score},'native_source_marker_repair':{'method':'source_parameterized_vee_native_marker_incremental','input_code_sha256':oldhash,'output_code_sha256':newhash,'native_markers_added':len(proof['markers']),'actual_terminal_moves':len(moves['moves']),'source_coverage':coverage,'source_editability':gate,'contour_approximation':True,'requires_visual_acceptance':True,'audit':auditpath},'quality_state':'native_markers_verified_pending_visual_acceptance'}
  for key in ['source_render_svg','source_render_svg_sha256','source_render_dot','original_source_data','source_data_sha256','source_data_locator']:
   if verified.get(key):
    if out.get(key):assert out[key]==verified[key],'Current source provenance conflicts with verified archive: '+key
    else:out[key]=verified[key]
  assert auxiliary_hashes(out)==repair['source_auxiliary_hashes']
  if out.get('native_canvas_refresh'):out['native_canvas_refresh']={**out['native_canvas_refresh'],'verified_code_sha256':oldhash,'verified_image_sha256':old['image_sha256']}
  report.update(published=True,output_code_sha256=newhash,output_image_sha256=out['image_sha256'],native_markers_added=len(proof['markers']),actual_endpoint_moves=len(moves['moves']),maximum_original_tip_error_px=max(x['source_tip_error'] for x in moves['moves']),pixel_audit=pixels,source_coverage=coverage,source_editability=gate,actual_fonts_and_text_positions_unchanged=True,reference_ssim_before=before_score,reference_ssim_after=after_score,source_render_ssim_after=source_score,contour_approximation=True,acceptance_status='Candidate only; native open marker differs slightly from filled source VEE, requires visual review. No SSIM-only acceptance.')
  (B/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 except Exception as e:
  out=None;report.update(published=False,error=repr(e));(B/'traceback.txt').write_text(traceback.format_exc())
 (B/'report.json').write_text(json.dumps(report,indent=2));begin(D);assert D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('source_vee_repairing',os.getpid(),raw),'Owned revision changed'
 if out:
  assert sha((R/old['code_file']).read_bytes())==oldhash and sha((R/old['image_file']).read_bytes())==old['image_sha256'],'Payload changed outside owned job'
  for src,dest in [(B/'candidate.drawio',R/out['code_file']),(B/'candidate.png',R/out['image_file']),(B/'candidate_record.json',(R/out['code_file']).parent/'conversion.json')]:
   tmp=dest.with_suffix(dest.suffix+'.vee.tmp');shutil.copyfile(src,tmp);tmp.replace(dest)
 D.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',('needs_quality_repair' if out else state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));D.execute('update source_vee_repairs set state=?,record=?,updated_at=? where id=? and input_code_sha256=?',('published' if out else 'pending_source_vee_repair',json.dumps(report),now(),id,oldhash));commit(D)
 if out:(B/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256']}))
 print(json.dumps(report),flush=True);return out is not None
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('id');a=p.parse_args();raise SystemExit(0 if main(a.id) else 1)
