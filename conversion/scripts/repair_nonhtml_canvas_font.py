"""Refresh a legacy false-overflow canvas only with exact fresh native baseline proof."""
import argparse,base64,hashlib,json,mimetypes,os,shutil,sqlite3,urllib.parse
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from durable_sqlite import begin,commit
from portable_native_fonts_v2 import ready_page,capture,embed
from fontmix_native_stack import native_stack_variant
from fontmix_validation import verify_graph,verify_fonts,zero_lineboxes
from svg_pilot import metrics
from source_svg_snapshot import snapshot,auxiliary_hashes
from strict_canvas_gate import require_declared_page
sha=lambda b:hashlib.sha256(b).hexdigest()


def main(id):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists nonhtml_canvas_font_repairs (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');row=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert row and row[0] in ['rendered','needs_quality_repair'],row;before_state,raw=row;old=json.loads(raw);oldhash=old['code_sha256'];assert not D.execute('select 1 from nonhtml_canvas_font_repairs where id=? and input_code_sha256=?',(id,oldhash)).fetchone();D.execute('insert into nonhtml_canvas_font_repairs values (?,?,"running",NULL,?)',(id,oldhash,now()));D.execute('update jobs set state="nonhtml_canvas_font_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(D)
 work=W/'nonhtml_canvas_font_repair'/id/oldhash;work.mkdir(parents=True,exist_ok=True);report={'id':id,'at':now(),'input_code_sha256':oldhash,'accepted':False};out=None
 try:
  assert old['source_format'] in ['python','svg'] and old['render']['selected_image']=='complete_tight_graph';xml=(R/old['code_file']).read_text();oldpng=(R/old['image_file']).read_bytes();reference=(R/old['original_reference']).read_bytes();assert sha(xml.encode())==oldhash and sha(oldpng)==old['image_sha256'];assert sha(reference)==old['source_image_sha256'];assert sha((R/old['original_source_code']).read_bytes())==old['source_code_sha256'];assert 'extFonts=' not in xml;(work/'before.drawio').write_text(xml);(work/'before.png').write_bytes(oldpng);(work/'before_record.json').write_text(raw);width,height=Image.open(R/old['original_reference']).size;aux=auxiliary_hashes(old);(work/'auxiliary_hashes.json').write_text(json.dumps(aux,indent=2))
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser);observed=capture(page,xml);new,fonts,details=embed(xml,observed,work/'fonts',page);assert not details['issues'],details['issues'];new,details=native_stack_variant(xml,zero_lineboxes(new,details),details,fonts);verify_graph(xml,new,details);sourcepng=snapshot(browser,old,width,height);browser.close()
  (work/'source_svg_render.png').write_bytes(sourcepng);(work/'observed_fonts.json').write_text(json.dumps(observed,indent=2));(work/'font_details.json').write_text(json.dumps(details,indent=2));baseline=native.native_job(xml,width,height,120,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');fresh=native.native_job(new,width,height,120,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert baseline['ok'] and fresh['ok'];(work/'candidate.drawio').write_text(new);(work/'candidate.png').write_bytes(fresh['png']);(work/'candidate_render.json').write_text(json.dumps(fresh['native_render'],indent=2));(work/'fresh_baseline.png').write_bytes(baseline['png']);(work/'fresh_baseline_render.json').write_text(json.dumps(baseline['native_render'],indent=2));assert baseline['png']==fresh['png'],'Embedded fonts changed fresh native baseline';verify_fonts(observed,fresh['native_render'],details)
  for render in [baseline['native_render'],fresh['native_render']]:
   require_declared_page(render,width,height)
  assert baseline['native_render']['graphBounds']==fresh['native_render']['graphBounds'];assert fresh['png']!=oldpng,'No legacy canvas change to repair';(work/'fresh_baseline.png').write_bytes(baseline['png']);(work/'fresh_baseline_render.json').write_text(json.dumps(baseline['native_render'],indent=2));before_score=metrics(reference,oldpng)['ssim_512'];after_score=metrics(reference,fresh['png'])['ssim_512'];assert after_score>=before_score,'Reference fidelity metric regressed';records=[];fontroot=R/'clean/font_assets'
  for f in fonts.values():
   src=Path(f['file']);dest=fontroot/src.name;orig=Path(f['original_file']);odest=fontroot/(f['original_sha256']+orig.suffix.lower())
   for source,target,digest in [(src,dest,f['sha256']),(orig,odest,f['original_sha256'])]:
    if not target.exists():tmp=target.with_suffix(target.suffix+'.'+str(os.getpid())+'.tmp');shutil.copyfile(source,tmp);tmp.replace(target)
    assert sha(target.read_bytes())==digest
   records.append({**{k:v for k,v in f.items() if k not in ['uri','file','original_file']},'file':str(dest.relative_to(R)),'original_file':str(odest.relative_to(R)),'source_system_font_path':str(orig)})
  proof={'ok':True,'method':'physical_font_native_stacks_strict_nonhtml_canvas_refresh_v1','output_code_sha256':sha(new.encode()),'actual_custom_font_text_cells':len(details['changes']),'physical_font_glyph_counts_preserved':True,'editable_text_exact':True,'fresh_native_baseline_pixels_identical':True,'native_pixels_unchanged':False,'font_files':len(records),'font_details':{k:v for k,v in details.items() if k not in ['grapheme_probes','primary_font_probes']},'audit':str((work/'report.json').relative_to(R))};assert auxiliary_hashes(old)==aux,'Source auxiliary files changed during repair'
  refresh={'at':now(),'source_auxiliary_hashes':aux,'previous_native_image_sha256':old['image_sha256'],'previous_native_image_size':old['render']['output_size'],'native_image_size':[width,height],'original_reference_size':[width,height],'old_selection':'complete_tight_graph','new_selection':'declared_first_page','strict_no_nonwhite_pixels_outside_page':True,'graph_bounds_and_nonfont_geometry_unchanged':True,'fresh_baseline_and_embedded_render_identical':True,'reference_ssim_before':before_score,'reference_ssim_after':after_score,'audit':str((work/'report.json').relative_to(R))};out={**old,'code_sha256':sha(new.encode()),'image_sha256':sha(fresh['png']),'render':fresh['native_render'],'native_embedded_fonts':records,'native_font_validation':proof,'native_canvas_refresh':refresh,'metrics':{'original_reference_ssim_512':after_score,'original_source_render_ssim_512':metrics(reference,sourcepng)['ssim_512'],'source_render_vs_drawio_ssim_512':metrics(sourcepng,fresh['png'])['ssim_512']}};report.update(published=True,canvas_refresh=refresh,font_files=len(records),text_cells=len(details['changes']),original_source_assets_unchanged=True);(work/'candidate.drawio').write_text(new);(work/'candidate.png').write_bytes(fresh['png']);(work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 except Exception as e:
  import traceback
  out=None;report.update(published=False,error=repr(e));(work/'traceback.txt').write_text(traceback.format_exc())
 (work/'report.json').write_text(json.dumps(report,indent=2));begin(D);assert D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('nonhtml_canvas_font_repairing',os.getpid(),raw),'Ownership changed'
 if out:
  for source,target in [(work/'candidate.drawio',R/out['code_file']),(work/'candidate.png',R/out['image_file']),(work/'candidate_record.json',(R/out['code_file']).parent/'conversion.json')]:tmp=target.with_suffix(target.suffix+'.canvasfont.tmp');shutil.copyfile(source,tmp);tmp.replace(target)
 D.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',(before_state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));D.execute('update nonhtml_canvas_font_repairs set state=?,record=?,updated_at=? where id=? and input_code_sha256=?',('published' if out else 'pending_canvas_repair',json.dumps(report),now(),id,oldhash));commit(D)
 if out:(work/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256']}))
 print(json.dumps(report),flush=True);assert out,report
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('id');main(parser.parse_args().id)
