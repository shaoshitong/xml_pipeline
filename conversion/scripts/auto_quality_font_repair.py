"""Bundle actual missing physical faces, including pending model/native results."""
import argparse,concurrent.futures,hashlib,io,json,os,shutil,sqlite3,time,xml.etree.ElementTree as E
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright
from native_worker import R,W,native,now
from portable_native_fonts import capture,embed,ready_page
from native_font_embedding_batch import canonical
from durable_sqlite import begin,commit

sha=lambda b:hashlib.sha256(b).hexdigest()
STATE='auto_quality_font_repairing'
TABLE='auto_quality_font_repairs_v2'
RENDERER=W/'rendering_paintbounds_strict/remote_render.py'

def atomic(path,data):
 tmp=path.with_name(path.name+'.'+str(os.getpid())+'.fontqa.tmp');tmp.write_bytes(data);tmp.replace(path)

def pixels(blob):
 im=Image.open(io.BytesIO(blob)).convert('RGBA');return im.size,im.tobytes()

def merge_fonts(xml,old_ext):
 root=E.fromstring(xml);model=root.find('.//mxGraphModel');entries={}
 for value in (old_ext or '').split('|')+(model.get('extFonts') or '').split('|'):
  if not value:continue
  family=value.split('^',1)[0]
  if family in entries:assert entries[family]==value,'Conflicting embedded face payload'
  entries[family]=value
 if entries:model.set('extFonts','|'.join(entries.values()))
 return E.tostring(root,encoding='unicode')

def preserve_named_styles(before,after,changed):
 a=E.fromstring(before);b=E.fromstring(after);pa={c:p for p in a.iter() for c in p};pb={c:p for p in b.iter() for c in p}
 old={c.get('id') or pa[c].get('id'):c for c in a.iter('mxCell')};new={c.get('id') or pb[c].get('id'):c for c in b.iter('mxCell')};fontkeys={'fontFamily','fontStyle','fontSource'}
 for cid in changed:
  original=old[cid].get('style','').split(';');proposed=new[cid].get('style','').split(';')
  kv=lambda parts:{x.split('=',1)[0]:x.split('=',1)[1] for x in parts if '=' in x and x.split('=',1)[0] not in fontkeys}
  assert kv(original)==kv(proposed),'Embedding altered a non-font style property'
  # Preserve named stylesheet tokens and their ordering exactly. Physical face
  # overrides are explicit final tokens, so a named style cannot undo embedding.
  kept=[x for x in original if x and x.split('=',1)[0] not in fontkeys];fonts=[x for x in proposed if '=' in x and x.split('=',1)[0] in fontkeys]
  new[cid].set('style',';'.join(kept+fonts)+';')
 return E.tostring(b,encoding='unicode')

def check_faces(before,after,changed):
 a={r['cell']:r['actual_fonts'] for r in before};b={r['cell']:r['fonts'] for r in after['actual_platform_font_usage']}
 def counts(rows):
  result={}
  for f in rows:
   if f['glyphCount']:result[f['postScriptName']]=result.get(f['postScriptName'],0)+f['glyphCount']
  return result
 for cid in changed:
  rows=[r for r in b.get(cid,[]) if r['glyphCount']]
  assert rows and all(r['isCustomFont'] for r in rows),'A repaired glyph still uses a system fallback'
  assert counts(a[cid])==counts(rows),'Physical face or glyph count changed'
 assert all(f['isCustomFont'] for row in after['actual_platform_font_usage'] for f in row['fonts'] if f['glyphCount']),'A non-target text cell still uses a system fallback'

def proposal(id,raw,page):
 old=json.loads(raw);digest=old['code_sha256'];xml=(R/old['code_file']).read_text();png=(R/old['image_file']).read_bytes();assert sha(xml.encode())==digest and sha(png)==old['image_sha256']
 work=W/'auto_quality_font_repair_v1'/id/digest;work.mkdir(parents=True,exist_ok=True);atomic(work/'before.drawio',xml.encode());atomic(work/'before_record.json',raw.encode())
 # These cases have actually observed system faces. Already-custom siblings and
 # unused original face resources remain intact, rather than being flattened.
 observations=capture(page,xml);targets=[r for r in observations if any(f['glyphCount'] and not f['isCustomFont'] for f in r['actual_fonts'])];assert targets,'No current unembedded text glyphs'
 old_ext=E.fromstring(xml).find('.//mxGraphModel').get('extFonts');new,fonts,details=embed(xml,targets,work/'fonts');assert not details['issues'],str(details['issues'])[:2500];assert details['changes'];new=merge_fonts(new,old_ext);changed={r['cell'] for r in details['changes']};new=preserve_named_styles(xml,new,changed);atomic(work/'proposed.drawio',new.encode());atomic(work/'font_details.json',(json.dumps(details,indent=2)+'\n').encode())
 assert canonical(xml,changed)==canonical(new,changed),'Non-font graph/text/geometry was changed'
 w,h=Image.open(io.BytesIO(png)).size;baseline=native.native_job(xml,w,h,150,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');fresh=native.native_job(new,w,h,150,RENDERER,8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert baseline['ok'] and fresh['ok'],'Actual native render failed'
 assert pixels(baseline['png'])==pixels(png),'Current candidate PNG does not match its fresh native render'
 assert pixels(baseline['png'])==pixels(fresh['png']),'Embedding changes actual native pixels'
 check_faces(observations,fresh['native_render'],changed)
 records=list(old.get('native_embedded_fonts') or []);fontroot=R/'clean/font_assets';fontroot.mkdir(exist_ok=True)
 for font in fonts.values():
  src=Path(font['file']);target=fontroot/src.name
  if not target.exists():atomic(target,src.read_bytes())
  assert sha(target.read_bytes())==font['sha256'];original=Path(font['original_file']);originaltarget=fontroot/(font['original_sha256']+original.suffix.lower())
  if not originaltarget.exists():atomic(originaltarget,original.read_bytes())
  assert sha(originaltarget.read_bytes())==font['original_sha256'];records.append({**{k:v for k,v in font.items() if k not in ('uri','file','original_file')},'file':str(target.relative_to(R)),'original_file':str(originaltarget.relative_to(R)),'source_system_font_path':str(original)})
 archive=W/'harness_sessions'/('auto_font_'+id+'_'+digest)/'baseline';archive.mkdir(parents=True,exist_ok=True);atomic(archive/'conversion.json',raw.encode());atomic(archive/'diagram.drawio',xml.encode());atomic(archive/'image.png',png)
 targetpng=(R/old['image_file']).with_name('image.font.'+sha(new.encode())[:20]+'.png');targetcode=(R/old['code_file']).with_name('diagram.font.'+sha(new.encode())[:20]+'.drawio');proof={'ok':True,'at':now(),'input_code_sha256':digest,'output_code_sha256':sha(new.encode()),'input_image_sha256':old['image_sha256'],'output_image_sha256':sha(fresh['png']),'native_pixels_unchanged':True,'physical_faces_and_glyph_counts_preserved':True,'all_actual_fonts_custom':True,'original_unused_font_payloads_preserved':True,'text_cells':len(changed),'audit':str((work/'report.json').relative_to(R)),'accepted':False}
 out={**old,'code_file':str(targetcode.relative_to(R)),'code_sha256':sha(new.encode()),'image_file':str(targetpng.relative_to(R)),'image_sha256':sha(fresh['png']),'render':fresh['native_render'],'native_embedded_fonts':records,'native_font_validation':proof,'previous_candidate_archive':str(archive.relative_to(R)),'quality_state':'pending_automatic_quality_recheck'}
 atomic(work/'candidate.drawio',new.encode());atomic(work/'candidate.png',fresh['png']);atomic(work/'candidate_record.json',(json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode());atomic(work/'observations.json',(json.dumps(observations,indent=2)+'\n').encode());return work,out,proof

def worker(index,limit):
 db=sqlite3.connect(W/'jobs.sqlite',timeout=2);n=0;counts={}
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage']);page=ready_page(browser)
  while not limit or n<limit:
   row=db.execute('''select j.id,j.state,j.output_record from jobs j where j.state in ('rendered','needs_quality_repair','harness_review_pending') and j.worker_pid is NULL and exists(select 1 from auto_quality_exceptions_v1 q where q.id=j.id and q.route='deterministic_font_embedding' and q.code_hash=json_extract(j.output_record,'$.code_sha256')) and not exists(select 1 from auto_quality_font_repairs_v2 f where f.id=j.id and f.input_hash=json_extract(j.output_record,'$.code_sha256')) order by j.id limit 1''').fetchone()
   if not row:
    if limit:break
    time.sleep(20);continue
   id,state,raw=row;digest=json.loads(raw)['code_sha256'];begin(db)
   if db.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()!=(state,raw,None) or db.execute('select 1 from '+TABLE+' where id=? and input_hash=?',(id,digest)).fetchone():db.rollback();continue
   db.execute('insert into '+TABLE+' values(?,?,"running",NULL,?)',(id,digest,now()));db.execute('update jobs set state=?,worker_pid=?,updated_at=? where id=?',(STATE,os.getpid(),now(),id));commit(db);out=None
   try:work,out,report=proposal(id,raw,page)
   except Exception as exc:report={'id':id,'at':now(),'input_hash':digest,'error':repr(exc),'previous_candidate_retained':True,'accepted':False}
   begin(db);assert db.execute('select state,output_record,worker_pid from jobs where id=?',(id,)).fetchone()==(STATE,raw,os.getpid()),'Repair ownership changed'
   stage='published' if out else 'retained_prior_candidate'
   if out:
    atomic(R/out['image_file'],(work/'candidate.png').read_bytes());atomic(R/out['code_file'],(work/'candidate.drawio').read_bytes());atomic((R/out['code_file']).parent/'conversion.json',(work/'candidate_record.json').read_bytes())
   db.execute('update jobs set state=?,output_record=?,worker_pid=NULL,updated_at=? where id=?',(state,json.dumps(out,ensure_ascii=False) if out else raw,now(),id));db.execute('update '+TABLE+' set state=?,record=?,updated_at=? where id=? and input_hash=?',(stage,json.dumps(report),now(),id,digest));commit(db)
   if out:atomic(work/'report.json',(json.dumps(report,indent=2)+'\n').encode())
   n+=1;counts[stage]=counts.get(stage,0)+1;print(json.dumps({'at':now(),'id':id,'stage':stage,'worker':index,'error':report.get('error')}),flush=True)
  browser.close()
 return {'worker':index,'processed':n,'counts':counts}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=2);p.add_argument('--limit',type=int,default=0);a=p.parse_args();db=sqlite3.connect(W/'jobs.sqlite',timeout=2);begin(db);db.execute('create table if not exists '+TABLE+'(id TEXT,input_hash TEXT,state TEXT,record TEXT,updated_at TEXT,primary key(id,input_hash))');commit(db);db.close();(W/'auto_quality_font_owner.json').write_text(json.dumps({'pid':os.getpid(),'workers':a.workers,'at':now(),'limit':a.limit}))
 with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers) as pool:results=list(pool.map(worker,range(a.workers),[a.limit]*a.workers))
 print(json.dumps({'at':now(),'workers':results,'goal_complete':False}),flush=True)
