"""Per-case physical-font bundling; no DB writes, watcher, model or acceptance.

Only system fonts observed in the actual native runtime may be embedded. Text,
geometry, named styles, source identity, PS names, glyph counts and native
pixels must remain unchanged. Full source/native/visual QA remains independent.
"""
import hashlib, io, json, os, re, uuid, xml.etree.ElementTree as E
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion'
VERSION='observed_physical_font_only_round2_v1'
COMPILER_VERSION='native_single_observed_face_rich_label_v2'
def sha(blob):return hashlib.sha256(blob).hexdigest()
def save(path,blob):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():
  if path.read_bytes()!=blob:raise ValueError('immutable_font_artifact_changed')
  return
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 with tmp.open('xb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
 tmp.replace(path)
def dump(path,value):save(path,(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
def checked(locator,digest):
 p=(R/locator).resolve(strict=True)
 if not p.is_relative_to(R.resolve()):raise ValueError('font_input_outside_root')
 blob=p.read_bytes()
 if sha(blob)!=digest:raise ValueError('font_input_sha_mismatch')
 return blob
def job_dict(job):
 if isinstance(job,dict):return job
 cols=('id','category','format','source','input_record','state','route','attempts','updated_at','output_record','error','input_manifest','worker_pid')
 return dict(zip(cols,job))
def compatible(record):return record.get('source_format') in ('drawio','html','svg','python','plantuml','mermaid','tikz')
def repair_fonts(record,job,work):
 """Return {ok,record,evidence} or a typed refusal; never publish/qualify."""
 work=Path(work).resolve();job=job_dict(job);before=dict(record)
 result={'ok':False,'id':before.get('id'),'version':VERSION,'model_calls':0,'canonical_db_written':False}
 try:
  if not work.is_relative_to(W.resolve()):raise ValueError('font_work_outside_conversion')
  work.mkdir(parents=True,exist_ok=True)
  requested=work
  source=json.loads(job['input_record']) if isinstance(job['input_record'],str) else job['input_record']
  if (record.get('id'),record.get('source_pair_sha256'),record.get('source_code_sha256'),record.get('source_image_sha256'))!=(job['id'],job['id'],source['code_sha256'],source['image_sha256']):raise ValueError('font_source_identity_mismatch')
  if record.get('source_format')!=source['format'] or not compatible(record):raise ValueError('font_format_identity_mismatch')
  if not re.fullmatch('[0-9a-f]{64}',str(record['id'])):raise ValueError('font_invalid_original_id')
  # Additive round2 subtree under the frozen font-delta validator's owned
  # namespace. No historical per-ID directory or old proof is replaced.
  work=W/'auto_quality_font_repair_v1/round2_v1'/record['id']/uuid.uuid4().hex
  work.mkdir(parents=True,exist_ok=False)
  xml=checked(record['code_file'],record['code_sha256']).decode();png=checked(record['image_file'],record['image_sha256'])
  from PIL import Image
  size=Image.open(io.BytesIO(png)).size
  from playwright.sync_api import sync_playwright
  from portable_native_fonts import capture,ready_page
  from auto_quality_font_repair import merge_fonts,preserve_named_styles,check_faces,pixels
  from native_source_font_profile_v4 import canonical_font_only
  from native_worker import native
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage'])
   try:
    observations=capture(ready_page(browser),xml)
    targets=[row for row in observations if any(f.get('glyphCount',0)>0 and not f.get('isCustomFont') for f in row['actual_fonts'])]
    dump(work/'observations.json',observations)
    if not targets:
     return {**result,'ok':True,'record':record,'no_op':True,'evidence':{'reason':'all_observed_glyphs_already_custom_or_no_text','observed_text_cells':len(observations)}}
    new,fonts,details=embed(xml,targets,work/'fonts')
   finally:browser.close()
  dump(work/'font_details.json',details)
  if details['issues']:raise ValueError('font_embedding_requires_unsupported_text_run:'+json.dumps(details['issues'],ensure_ascii=False)[:2500])
  changed={r['cell'] for r in details['changes']}
  if not changed:raise ValueError('font_no_actual_changes')
  old_ext=E.fromstring(xml).find('.//mxGraphModel').get('extFonts')
  new=preserve_named_styles(xml,merge_fonts(new,old_ext),changed)
  if canonical_font_only(xml,changed)!=canonical_font_only(new,changed):raise ValueError('font_nonfont_graph_or_text_changed')
  renderer=W/'rendering_paintbounds_strict/remote_render.py';runtime=R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json'
  baseline=native.native_job(xml,*size,150,renderer,8192,runtime);fresh=native.native_job(new,*size,150,renderer,8192,runtime)
  if not baseline.get('ok') or not fresh.get('ok'):raise ValueError('font_fresh_native_render_failed')
  stored_matches_fresh=pixels(baseline['png'])==pixels(png)
  if pixels(baseline['png'])!=pixels(fresh['png']):raise ValueError('font_embedding_changes_native_pixels')
  check_faces(observations,fresh['native_render'],changed)
  dest=R/'clean/round2_font_repair_v1'/record['id'][:2]/record['id']/uuid.uuid4().hex;dest.mkdir(parents=True)
  assets=list(record.get('native_embedded_fonts') or [])
  for font in fonts.values():
   src=Path(font['file']);fontblob=src.read_bytes();original=Path(font['original_file']);originalblob=original.read_bytes()
   if sha(fontblob)!=font['sha256'] or sha(originalblob)!=font['original_sha256']:raise ValueError('font_asset_changed_before_copy')
   target=dest/'fonts'/src.name;origin=dest/'fonts'/(font['original_sha256']+original.suffix.lower());save(target,fontblob);save(origin,originalblob)
   assets.append({**{k:v for k,v in font.items() if k not in ('uri','file','original_file')},'file':str(target.relative_to(R)),'original_file':str(origin.relative_to(R))})
  codefile=dest/'diagram.drawio';imagefile=dest/'image.png';save(codefile,new.encode());save(imagefile,fresh['png'])
  proof={'version':VERSION,'ok':True,'input_code_sha256':record['code_sha256'],'input_image_sha256':record['image_sha256'],'output_code_sha256':sha(new.encode()),'output_image_sha256':sha(fresh['png']),
   'source_code_sha256':record['source_code_sha256'],'source_image_sha256':record['source_image_sha256'],'changed_cells':sorted(changed),'native_pixels_unchanged':True,
   'physical_postscript_and_glyph_counts_unchanged':True,'all_actual_fonts_custom':True,'source_graph_text_and_nonfont_styles_unchanged':True,'accepted':False,
   'physical_faces_and_glyph_counts_preserved':True,'audit':str((work/'report.json').relative_to(R)),
   'stored_candidate_png_equal_fresh_baseline':stored_matches_fresh,'pixel_comparison_scope':'fresh native baseline before embedding versus fresh native after embedding; original reference fidelity remains independent',
   'renderer_sha256':sha(renderer.read_bytes()),'runtime_sha256':sha(runtime.read_bytes()),'observations':str((work/'observations.json').relative_to(R)),'details':str((work/'font_details.json').relative_to(R))}
  out={**record,'code_file':str(codefile.relative_to(R)),'code_sha256':proof['output_code_sha256'],'image_file':str(imagefile.relative_to(R)),'image_sha256':proof['output_image_sha256'],
       'native_embedded_fonts':assets,'render':fresh['native_render'],'round2_font_repair':proof,'quality_state':'pending_full_round2_source_native_visual_quality'}
  if record.get('source_format')!='drawio':out['native_font_validation']=proof
  dump(work/'before_record.json',record);save(work/'before.drawio',xml.encode());save(work/'before.png',png);save(work/'candidate.drawio',new.encode());save(work/'candidate.png',fresh['png']);dump(work/'candidate_record.json',out);dump(work/'report.json',proof)
  dump(requested/'round2_font_result.json',{'ok':True,'audit':proof['audit'],'code_file':out['code_file'],'image_file':out['image_file'],'model_calls':0})
  checked(record['code_file'],record['code_sha256']);checked(record['image_file'],record['image_sha256'])
  return {**result,'ok':True,'record':out,'evidence':proof,'no_op':False}
 except Exception as e:
  result.update(reason=str(e).split(':',1)[0],error_type=type(e).__name__,error=str(e)[:4000])
  if work.is_relative_to(W.resolve()) and work.exists():dump(work/'failure.json',result)
  return result


def embed(xml,observations,directory):
 """Preserve original rich labels while embedding observed physical families.

 Single-face rich labels and same-style fallback stacks need no text rewriting.
 Faces are ordered by the original CSS family preference, then actual observed
 fallback order. Exact same-renderer pixels/PS counts remain mandatory, so a
 context-dependent fallback or explicit inline override cannot slip through.
 """
 from portable_native_fonts import embed as original_embed
 from pdf_to_native import attach_fonts
 root=E.fromstring(xml);parents={c:p for p in root.iter() for c in p}
 cells={c.get('id') or parents[c].get('id'):c for c in root.iter('mxCell')}
 fake=E.Element('mxfile');cr=E.SubElement(E.SubElement(E.SubElement(fake,'diagram'),'mxGraphModel'),'root')
 fakeobs=[];mapping={};issues=[]
 for row in observations:
  for face in row.get('actual_fonts',[]):
   if not face.get('glyphCount',0):continue
   key=(face['postScriptName'],int(row['style'].get('fontStyle',0)))
   if key in mapping:continue
   cid='face'+str(len(mapping));mapping[key]=cid
   E.SubElement(cr,'mxCell',id=cid,vertex='1',value='probe',style='fontStyle='+str(key[1])+';')
   fakeobs.append({'cell':cid,'label':'physical-face-probe','style':row['style'],'actual_fonts':[face]})
 _,fonts,report=original_embed(E.tostring(fake,encoding='unicode'),fakeobs,directory)
 issues.extend(report['issues']);converted={ch['cell']:ch for ch in report['changes']};changes=[]
 for row in observations:
  actual=[f for f in row.get('actual_fonts',[]) if f.get('glyphCount',0)>0]
  flags=int(row['style'].get('fontStyle',0));keys=[mapping.get((f['postScriptName'],flags)) for f in actual]
  if not actual or any(k not in converted for k in keys):continue
  faces=[converted[k] for k in keys];physical={(fonts[f['family']]['physical_bold'],fonts[f['family']]['physical_italic']) for f in faces}
  if len(physical)!=1:
   issues.append({'cell':row['cell'],'reason':'inline_mixed_physical_styles_require_per_run_embedding'});continue
  families=[f.strip(' \"\'') for f in str(row['style'].get('fontFamily','Arial')).split(',')]
  preference={name.lower():i for i,name in enumerate(families)}
  paired=list(zip(actual,faces));paired.sort(key=lambda pair:preference.get(pair[0].get('familyName','').lower(),len(preference)))
  ordered=[f['family'] for _,f in paired];primary=paired[0][1]
  c=cells[row['cell']];style={part.split('=',1)[0]:part.split('=',1)[1] for part in c.get('style','').split(';') if '=' in part}
  style['fontFamily']=','.join(ordered);style['fontStyle']=str(primary['after_flags'])
  c.set('style',';'.join(k+'='+v for k,v in style.items())+';')
  changes.append({**primary,'cell':row['cell'],'before_family':row['style'].get('fontFamily'),'before_flags':flags,'actual_fonts':actual,'families':ordered,'actual_font':actual[0] if len(actual)==1 else None})
 out=attach_fonts(E.tostring(root,encoding='unicode'),fonts) if fonts else xml
 return out,fonts,{'changes':changes,'issues':issues,'text_cells_observed':len(observations),'font_files':len(fonts),'compiler_version':COMPILER_VERSION,'original_label_markup_untouched':True}

def repair_html_source(record,job,work):
 """Run missing wrapped-fragment/paint-order recovery AFTER donor fonts exist."""
 from round2_html_repair_v1 import repair as source_repair
 work=Path(work);work.mkdir(parents=True,exist_ok=True)
 return source_repair(record,job,work)

def repair(record,job,work):
 result=repair_fonts(record,job,Path(work)/'font')
 if not result.get('ok'):return result
 if record.get('source_format')=='html':
  source_result=repair_html_source(result['record'],job,Path(work)/'html_source')
  if source_result.get('ok'):return {**result,'record':source_result['record'],'html_source_evidence':source_result.get('evidence')}
  return {**result,'html_source_refusal':{k:v for k,v in source_result.items() if k!='record'}}
 if record.get('source_format')!='drawio':return result
 from native_export_reference_v3 import repair as export_repair
 exported=export_repair(result['record'],job,Path(work)/'export')
 if exported.get('ok'):return {**result,'record':exported['record'],'export_evidence':exported.get('evidence')}
 return {**result,'export_refusal':{k:v for k,v in exported.items() if k!='record'}}

convert=repair
