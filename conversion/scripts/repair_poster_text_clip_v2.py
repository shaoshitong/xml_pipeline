import argparse,copy,hashlib,json,os,shutil,sqlite3,xml.etree.ElementTree as E
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from durable_sqlite import begin,commit
from source_html_snapshot import snapshot
from native_text_clip import apply_clips,verify_graph,verify_positions,pixel_clip_proof,plain
from svg_pilot import metrics
sha=lambda b:hashlib.sha256(b).hexdigest()
class NoSourceClip(Exception):pass

def main(id):
 D=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(D);D.execute('create table if not exists native_text_clip_repairs (id TEXT,input_code_sha256 TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_code_sha256))');row=D.execute('select state,output_record from jobs where id=?',(id,)).fetchone();assert row and row[0] in ['rendered','needs_quality_repair'];before_state,raw=row;old=json.loads(raw);oldhash=old['code_sha256'];assert not D.execute('select 1 from native_text_clip_repairs where id=? and input_code_sha256=?',(id,oldhash)).fetchone();D.execute('insert into native_text_clip_repairs values (?,?,"running",NULL,?)',(id,oldhash,now()));D.execute('update jobs set state="native_text_clip_repairing",worker_pid=?,updated_at=? where id=?',(os.getpid(),now(),id));commit(D);work=W/'native_text_clip_repair'/id/oldhash;work.mkdir(parents=True,exist_ok=True);report={'id':id,'at':now(),'input_code_sha256':oldhash,'accepted':False,'implementation':'source_text_clip_batch_v2'};out=None;stage='pending_text_clip_repair'
 try:
  assert old['source_format']=='html';assert old['native_font_validation']['output_code_sha256']==oldhash;xml=(R/old['code_file']).read_text();png=(R/old['image_file']).read_bytes();reference=(R/old['original_reference']).read_bytes();assert sha(xml.encode())==oldhash and sha(png)==old['image_sha256'] and sha(reference)==old['source_image_sha256'];w,h=Image.open(R/old['original_reference']).size;(work/'before.drawio').write_text(xml);(work/'before.png').write_bytes(png);(work/'before_record.json').write_text(raw)
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);sourcepng,dom=snapshot(browser,old,w,h);browser.close()
  (work/'source.png').write_bytes(sourcepng);(work/'source_dom.json').write_text(json.dumps(dom,indent=2));cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};text_count=0
  for o in dom['objects']:
   if o['type']!='text':continue
   c=cells[str(o['id']+1)];assert plain(c.get('value',''))==o['text'],'Source/native text mismatch';g=c.find('mxGeometry');assert all(abs(float(g.get(k,'0'))-o[v])<1e-6 for k,v in [('x','x'),('y','y'),('width','w'),('height','h')]),'Source/native geometry mismatch';text_count+=1
  if not any(o['type']=='text' and o.get('sourceClip',{}).get('partial') for o in dom['objects']):raise NoSourceClip('No partially clipped source text')
  before=native.native_job(xml,w,h,120,W/'rendering_textproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert before['ok'] and before['png']==png,'Refresh native canvas before clip repair';new,details=apply_clips(xml,dom,before['native_render']['actual_text_positions'],w,h);assert details['changes'];(work/'clip_details.json').write_text(json.dumps(details,indent=2));verify_graph(xml,new,details);after=native.native_job(new,w,h,120,W/'rendering_textproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert after['ok'];verify_positions(before['native_render']['actual_text_positions'],after['native_render']['actual_text_positions']);usage=lambda r:{x['cell']:x['fonts'] for x in r['actual_platform_font_usage']};assert usage(before['native_render'])==usage(after['native_render']),'Actual font usage changed';assert all(f['isCustomFont'] for fs in usage(after['native_render']).values() for f in fs if f['glyphCount']);assert after['native_render']['selected_image']=='declared_first_page' and not after['native_render']['content_outside_declared_canvas']
  root=E.fromstring(xml);changed={x['cell'] for x in details['changes']}
  for c in root.iter('mxCell'):
   if c.get('id') in changed:c.set('value','')
  background=native.native_job(E.tostring(root,encoding='unicode'),w,h,120,W/'rendering_fontproof_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert background['ok'];proof=pixel_clip_proof(png,after['png'],background['png'],details);assert proof['ok'],proof;negative=pixel_clip_proof(png,png,background['png'],details);assert not negative['ok'],'Missing clipping passed expected-source-pixel oracle'
  corrupt=E.fromstring(new);c=next(c for c in corrupt.iter('mxCell') if c.get('id') in changed);c.set('value',c.get('value')+'X');rejected=False
  try:verify_graph(xml,E.tostring(corrupt,encoding='unicode'),details)
  except AssertionError:rejected=True
  assert rejected;source_before=metrics(sourcepng,png)['ssim_512'];source_after=metrics(sourcepng,after['png'])['ssim_512'];ref_before=metrics(reference,png)['ssim_512'];ref_after=metrics(reference,after['png'])['ssim_512'];assert source_after>=source_before and ref_after>=ref_before
  for f in old['native_embedded_fonts']:
   for key,digest in [('file','sha256'),('original_file','original_sha256')]:p=R/f[key];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==f[digest]
  for asset in old['source_assets']:
   if asset['source']!='embedded_original_html_asset':p=R/asset['source'];assert p.resolve().is_relative_to(R/'clean') and sha(p.read_bytes())==asset['source_sha256']
  newhash=sha(new.encode());font_proof={**old['native_font_validation'],'method':'portable_physical_fonts_preserved_during_source_text_clipping','output_code_sha256':newhash,'base_verified_code_sha256':oldhash,'native_pixels_unchanged':False,'all_native_character_bounds_unchanged':True,'physical_font_glyph_counts_preserved':True,'audit':str((work/'report.json').relative_to(R))};font_proof.pop('graph_changes_limited_to_font_styles_and_verified_editable_spans',None);font_proof.pop('fresh_native_baseline_pixels_identical',None);clip={'method':'source_rectangular_overflow_native_editable_span_clip_v1','source_dom_file':str(((R/old['code_file']).parent/'source_dom_clip.json').relative_to(R)),'source_dom_sha256':sha((work/'source_dom.json').read_bytes()),'source_text_objects_verified':text_count,'clipped_text_objects':len(changed),'original_source_clips_preserved':True,'full_text_preserved':True,'all_native_character_bounds_unchanged':True,'pixel_proof':proof,'negative_missing_clip_rejected':True,'negative_text_corruption_rejected':True,'source_reference_ssim_before':ref_before,'source_reference_ssim_after':ref_after,'audit':str((work/'report.json').relative_to(R))};out={**old,'code_sha256':newhash,'image_sha256':sha(after['png']),'render':{k:v for k,v in after['native_render'].items() if k!='actual_text_positions'},'native_font_validation':font_proof,'native_text_clipping':clip,'metrics':{'original_reference_ssim_512':ref_after,'original_source_render_ssim_512':metrics(reference,sourcepng)['ssim_512'],'source_render_vs_drawio_ssim_512':source_after}}
  if old.get('native_canvas_refresh'):out['native_canvas_refresh']={**old['native_canvas_refresh'],'verified_code_sha256':oldhash,'verified_image_sha256':old['image_sha256']}
  stage='published';report.update(published=True,clipping=clip,source_html_ssim_before=source_before,source_html_ssim_after=source_after);(work/'candidate.drawio').write_text(new);(work/'candidate.png').write_bytes(after['png']);(work/'candidate_record.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(work/'clip_details.json').write_text(json.dumps(details,indent=2));(work/'background.png').write_bytes(background['png']);(work/'before_render.json').write_text(json.dumps(before['native_render'],indent=2));(work/'after_render.json').write_text(json.dumps(after['native_render'],indent=2))
 except NoSourceClip as e:stage='no_source_text_clips';report.update(published=False,no_change_required=True,reason=str(e))
 except Exception as e:
  import traceback
  out=None;report.update(published=False,error=repr(e));(work/'traceback.txt').write_text(traceback.format_exc())
 (work/'report.json').write_text(json.dumps(report,indent=2));begin(D);assert D.execute('select state,worker_pid,output_record from jobs where id=?',(id,)).fetchone()==('native_text_clip_repairing',os.getpid(),raw)
 if out:
  for source,target in [(work/'candidate.drawio',R/out['code_file']),(work/'candidate.png',R/out['image_file']),(work/'candidate_record.json',(R/out['code_file']).parent/'conversion.json'),(work/'source_dom.json',R/out['native_text_clipping']['source_dom_file'])]:tmp=target.with_suffix(target.suffix+'.textclip.tmp');shutil.copyfile(source,tmp);tmp.replace(target)
 D.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',(before_state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));D.execute('update native_text_clip_repairs set state=?,record=?,updated_at=? where id=? and input_code_sha256=?',(stage,json.dumps(report),now(),id,oldhash));commit(D)
 if out:(work/'committed.json').write_text(json.dumps({'at':now(),'code_sha256':out['code_sha256'],'image_sha256':out['image_sha256']}))
 print(json.dumps(report),flush=True);return stage
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('id');stage=main(p.parse_args().id);raise SystemExit(1 if stage=='pending_text_clip_repair' else 0)
