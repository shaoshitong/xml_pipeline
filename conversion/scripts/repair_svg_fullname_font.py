"""Correct exact source font full names and matching editable native text geometry."""
import argparse,base64,hashlib,json,os,shutil,sqlite3,traceback
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from durable_sqlite import begin,commit
from svg_fullname_fonts import capture_source,patch_native,verify_render_fonts,NoFullNameFace
from source_svg_snapshot import auxiliary_hashes
from strict_canvas_gate import require_declared_page
from svg_pilot import metrics
sha=lambda b:hashlib.sha256(b).hexdigest()

def check_font_files(fonts):
 for f in fonts:
  for key,digest in [('file','sha256'),('original_file','original_sha256')]:
   path=R/f[key];assert path.resolve().is_relative_to(R/'clean');assert sha(path.read_bytes())==f[digest]

def main(id):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists svg_fullname_font_repairs (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');row=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert row and row[0] in ['rendered','needs_quality_repair'];before_state,raw=row;old=json.loads(raw);oldhash=old['code_sha256'];assert not D.execute('select 1 from svg_fullname_font_repairs where id=? and input_code_sha256=?',(id,oldhash)).fetchone();D.execute('insert into svg_fullname_font_repairs values (?,?,"running",NULL,?)',(id,oldhash,now()));D.execute('update jobs set state="svg_fullname_font_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(D);B=W/'svg_fullname_font_repair'/id/oldhash;B.mkdir(exist_ok=True,parents=True);(B/'before_record.json').write_text(raw);report={'at':now(),'id':id,'input_code_sha256':oldhash,'accepted':False};out=None;stage='pending_source_fullname_repair'
 try:
  assert old['source_format'] in ['python','svg'];assert old['native_font_validation']['output_code_sha256']==oldhash;xml=(R/old['code_file']).read_text();png=(R/old['image_file']).read_bytes();reference=(R/old['original_reference']).read_bytes();assert sha(xml.encode())==oldhash and sha(png)==old['image_sha256'] and sha(reference)==old['source_image_sha256'];assert sha((R/old['original_source_code']).read_bytes())==old['source_code_sha256'];check_font_files(old['native_embedded_fonts']);aux=auxiliary_hashes(old);w,h=Image.open(R/old['original_reference']).size
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
   try:source_before,source_after,source_before_png,source_after_png,fonts,source_changes=capture_source(browser,old,B,w,h)
   finally:browser.close()
  (B/'before.drawio').write_text(xml);(B/'before.png').write_bytes(png);(B/'source_before.png').write_bytes(source_before_png);(B/'source_after.png').write_bytes(source_after_png)
  for name,value in [('source_before_dom',source_before),('source_after_dom',source_after),('source_font_changes',source_changes),('auxiliary_hashes',aux)]: (B/(name+'.json')).write_text(json.dumps(value,indent=2))
  new,changes=patch_native(xml,old,source_before,source_after,fonts,w,h);(B/'candidate.drawio').write_text(new);(B/'changes.json').write_text(json.dumps(changes,indent=2));(B/'fonts.json').write_text(json.dumps(fonts,indent=2));baseline=native.native_job(xml,w,h,120,W/'rendering_textproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');fresh=native.native_job(new,w,h,120,W/'rendering_textproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert baseline['ok'] and baseline['png']==png;assert fresh['ok'];require_declared_page(baseline['native_render'],w,h);require_declared_page(fresh['native_render'],w,h);(B/'candidate.png').write_bytes(fresh['png']);(B/'before_render.json').write_text(json.dumps(baseline['native_render'],indent=2));(B/'after_render.json').write_text(json.dumps(fresh['native_render'],indent=2));verify_render_fonts(baseline['native_render'],fresh['native_render'],changes,source_changes)
  before_score=metrics(reference,png)['ssim_512'];after_score=metrics(reference,fresh['png'])['ssim_512'];source_score_before=metrics(source_after_png,png)['ssim_512'];source_score_after=metrics(source_after_png,fresh['png'])['ssim_512'];assert after_score>=before_score and source_score_after>=source_score_before,'Source/reference fidelity regressed';assert aux==auxiliary_hashes(old);records=list(old['native_embedded_fonts']);fontroot=R/'clean/font_assets'
  for f in fonts.values():
   src=Path(f['file']);dest=fontroot/src.name;orig=Path(f['original_file']);odest=fontroot/(f['original_sha256']+orig.suffix.lower())
   for source,target,digest in [(src,dest,f['sha256']),(orig,odest,f['original_sha256'])]:
    if not target.exists():tmp=target.with_suffix(target.suffix+'.'+str(os.getpid())+'.tmp');shutil.copyfile(source,tmp);tmp.replace(target)
    assert sha(target.read_bytes())==digest
   assert not any(x['family']==f['family'] for x in records);records.append({**{k:v for k,v in f.items() if k not in ['uri','file','original_file']},'file':str(dest.relative_to(R)),'original_file':str(odest.relative_to(R)),'source_system_font_path':str(orig)})
  newhash=sha(new.encode());case=(R/old['code_file']).parent;proof={'ok':True,'method':'exact_source_fullname_faces_and_source_text_geometry_v1','output_code_sha256':newhash,'base_verified_code_sha256':oldhash,'native_pixels_unchanged':False,'all_changed_faces_match_exact_source_fullname':True,'unchanged_text_faces_and_positions_preserved':True,'nontext_graph_and_connectivity_unchanged':True,'source_text_content_preserved':True,'font_files':len(records),'audit':str((B/'report.json').relative_to(R))};repair={'method':'exact_font_name_table_fullname_lookup','changed_text_objects':len(changes),'mappings':[{k:v for k,v in c.items() if k!='selector'} for c in source_changes],'source_before_dom_file':str((case/'source_fullname_before_dom.json').relative_to(R)),'source_after_dom_file':str((case/'source_fullname_after_dom.json').relative_to(R)),'source_before_dom_sha256':sha((B/'source_before_dom.json').read_bytes()),'source_after_dom_sha256':sha((B/'source_after_dom.json').read_bytes()),'text_geometry_changes':changes,'source_auxiliary_hashes':aux,'reference_ssim_before':before_score,'reference_ssim_after':after_score,'audit':str((B/'report.json').relative_to(R))};out={**old,'code_sha256':newhash,'image_sha256':sha(fresh['png']),'render':{k:v for k,v in fresh['native_render'].items() if k!='actual_text_positions'},'native_embedded_fonts':records,'native_font_validation':proof,'native_source_font_repair':repair,'metrics':{'original_reference_ssim_512':after_score,'original_source_render_ssim_512':metrics(reference,source_after_png)['ssim_512'],'source_render_vs_drawio_ssim_512':source_score_after}}
  if old.get('native_canvas_refresh'):out['native_canvas_refresh']={**old['native_canvas_refresh'],'verified_code_sha256':oldhash,'verified_image_sha256':old['image_sha256']}
  report.update(published=True,changed_text_objects=len(changes),new_fonts=len(fonts),reference_ssim_before=before_score,reference_ssim_after=after_score,corrected_source_vs_native_before=source_score_before,corrected_source_vs_native_after=source_score_after,all_changed_faces_match_exact_requested_fullnames=True,nontext_graph_and_unchanged_text_preserved=True);(B/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));stage='published'
 except NoFullNameFace as e:report.update(published=False,no_change_needed=True,reason=str(e));stage='no_exact_fullname_mapping_needed'
 except Exception as e:out=None;report.update(published=False,error=repr(e));(B/'traceback.txt').write_text(traceback.format_exc())
 (B/'report.json').write_text(json.dumps(report,indent=2));begin(D);assert D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('svg_fullname_font_repairing',os.getpid(),raw),'Owned job changed'
 if out:
  for source,target in [(B/'candidate.drawio',R/out['code_file']),(B/'candidate.png',R/out['image_file']),(B/'candidate_record.json',(R/out['code_file']).parent/'conversion.json'),(B/'source_before_dom.json',R/out['native_source_font_repair']['source_before_dom_file']),(B/'source_after_dom.json',R/out['native_source_font_repair']['source_after_dom_file'])]:tmp=target.with_suffix(target.suffix+'.fullname.tmp');shutil.copyfile(source,tmp);tmp.replace(target)
 D.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',(before_state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));D.execute('update svg_fullname_font_repairs set state=?,record=?,updated_at=? where id=? and input_code_sha256=?',(stage,json.dumps(report),now(),id,oldhash));commit(D)
 if out:(B/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256']}))
 print(json.dumps(report),flush=True);return stage
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('id');s=main(p.parse_args().id);raise SystemExit(1 if s=='pending_source_fullname_repair' else 0)
