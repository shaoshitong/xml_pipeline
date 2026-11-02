"""Finite HTML compilation: fonts -> source words -> canvas -> source glyphs.

All layout parameters come from fresh source/browser Ranges. Full original
reference, assets, source paint-order and native QA remain mandatory. Mixed
physical face sets may align only when identical and every grapheme agrees.
"""
import contextlib,hashlib,json,uuid
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029')
VERSION='html_source_ranges_fontconfig_primary_strut_v4'

def sha(b):return hashlib.sha256(b).hexdigest()
def configuration():
 names=['html_compiler_v4.py','native_html_font_compiler_v3.py','native_font_order_probe_v3.py','native_html_font_quality_v3.py','native_html_compiler_v2.py','native_html_quality_v2.py','auto_quality_glyph_candidate_generate_v3b.py','html_text_layout_candidate_v5.py','html_actual_text_alignment.py','html_actual_text_registration.py','html_text_layout_registration_v5.py','html_text_whitespace_advance_v5.py']
 return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n).read_bytes()) for n in names}
def mixed_analyze(original,dom,info,xml,offset=(0.,0.)):
 result=original(dom,info,xml,offset)
 import xml.etree.ElementTree as E
 cells={c.get('id'):c for c in E.fromstring(xml).iter('mxCell')};objects={str(o['id']+1):o for o in dom['objects'] if o.get('type')=='text'}
 for row in result['objects']:
  if row['category']!='mixed_or_unresolved_physical_faces':continue
  source,native=row.get('source_faces'),row.get('native_faces')
  if not source or len(source)<2 or source!=native or row.get('source_font_basis')!='actual_text_node':continue
  if len(row.get('native_font_sizes',[]))!=1 or abs(row['native_font_sizes'][0]-row.get('source_font_size',0))>.001:continue
  if row.get('maximum_glyph_size_difference',float('inf'))>.08 or row.get('maximum_residual_from_translation',float('inf'))>.08:continue
  if any(g.get('rectCount',1)!=1 and g.get('width',0)>0 for g in objects[row['cell']].get('actualSourceGlyphs',[])):continue
  dx,dy=row['translation']['dx'],row['translation']['dy']
  if max(abs(dx),abs(dy))<=.08:row['category']='actual_glyphs_aligned';continue
  cell=cells[row['cell']];style={p.split('=',1)[0]:p.split('=',1)[1] for p in cell.get('style','').split(';') if '=' in p}
  if 'clip-path' in cell.get('value','') or objects[row['cell']].get('sourceClip',{}).get('partial'):
   row['category']='uniform_translation_requires_fixed_clip';continue
  if style.get('rotation','0') not in ('0','0.0'):continue
  row.update(category='uniform_baseline_translation',safe_translation=True,mixed_identical_source_native_physical_face_set_verified=True)
 import collections
 result['categories']=dict(collections.Counter(r['category'] for r in result['objects']));result['safe_translation_objects']=sum(r.get('safe_translation',False) for r in result['objects']);return result
@contextlib.contextmanager
def source_scope():
 import html_actual_text_alignment as glyph
 import round2_font_canvas_registration_v1 as round2_registration
 import html_actual_text_clip_alignment_v4 as clip
 from auto_quality_common_v4 import registration_record as current_html_registration
 original=glyph.analyze;original_clip=clip.analyze;original_registration=round2_registration.registration_record
 glyph.analyze=lambda dom,info,xml,offset=(0.,0.):mixed_analyze(original,dom,info,xml,offset)
 clip.analyze=glyph.analyze
 def registration(record,reference,xml):
  # Current measured-layout lineage describes a successor of the earlier font
  # and canvas revisions. Replay that complete chain before stale font-only
  # metadata; every historical delta remains independently verified.
  if record.get('source_format')=='html' and (record.get('html_actual_text_alignment') or record.get('html_text_layout_v5')):
   return current_html_registration(record,reference,xml)
  return original_registration(record,reference,xml)
 round2_registration.registration_record=registration
 try:yield
 finally:glyph.analyze=original;clip.analyze=original_clip;round2_registration.registration_record=original_registration

def _publish(out,folder):
 from fixed_batch_case_v1 import save
 folder=Path(folder)
 for field,name,digest in [('code_file','candidate.drawio','code_sha256'),('image_file','candidate.png','image_sha256')]:
  target=(R/out[field]).resolve();require=target.is_relative_to((R/'clean').resolve())
  if not require:raise ValueError('html_v3_candidate_payload_outside_clean')
  data=(folder/name).read_bytes()
  if sha(data)!=out[digest]:raise ValueError('html_v3_candidate_payload_hash_mismatch')
  save(target,data)

def repair(record,job,work):
 from fixed_batch_case_v1 import save,raw
 from native_html_font_compiler_v3 import repair_fonts,repair_html_source
 from round2_canvas_repair_v1 import repair as canvas_repair
 from auto_quality_glyph_candidate_generate_v3b import generate
 from html_text_layout_candidate_v5 import build
 if record.get('source_format')!='html':return {'ok':False,'reason':'html_v3_only_html_supported'}
 work=Path(work);work.mkdir(parents=True,exist_ok=True);steps=[];pins=configuration();policy=VERSION+':'+sha(raw(pins))[:20]
 candidate=record
 with source_scope():
  for kind,fn in [('fonts',repair_fonts),('source',repair_html_source),('canvas',canvas_repair)]:
   step=work/kind;step.mkdir(parents=True,exist_ok=True)
   a=fn(candidate,job,step);steps.append({'stage':kind,'ok':a.get('ok') is True,'reason':a.get('reason'),'detail':a.get('detail') or a.get('error')})
   if a.get('ok'):candidate=a['record'];save(step/'candidate_record.json',raw(candidate))
   elif kind=='fonts':return {'ok':False,'reason':'html_v3_font_compilation_failed','detail':a,'steps':steps}
  for kind in ('glyph_ranges','space_and_clip_layout'):
   try:
    if kind=='glyph_ranges':
     if candidate.get('html_actual_text_alignment') or candidate.get('html_text_layout_v5'):
      steps.append({'stage':kind,'ok':False,'reason':'existing_layout_requires_successor_source_profile'});continue
     folder,out,evidence=generate({'prior_snapshot':['rendered',json.dumps(candidate)]},policy,pins)
    else:folder,out,evidence=build(candidate,policy,pins)
    steps.append({'stage':kind,'ok':bool(out),'reason':evidence.get('state'),'evidence':str(folder)})
    if out:_publish(out,folder);candidate=out
   except (ImportError,ModuleNotFoundError):raise
   except Exception as exc:steps.append({'stage':kind,'ok':False,'error_type':type(exc).__name__,'detail':str(exc)[:3000]})
 if any(sha(Path(p).read_bytes())!=h for p,h in pins.items()):raise RuntimeError('infrastructure_html_v3_implementation_changed')
 save(work/'candidate_record.json',raw(candidate));save(work/'steps.json',raw(steps));return {'ok':True,'record':candidate,'steps':steps,'version':VERSION,'model_calls':0}

def verify(record,job,work,index):
 import auto_quality_batch_v4b as qa
 from native_html_quality_v2 import verify as complete_verify
 from fixed_batch_case_v1 import raw,save
 from native_html_font_quality_v3 import verify as font_verify
 font_check=None
 proof=record.get('round2_font_repair') or {}
 if proof.get('font_compiler'):
  try:
   folder=(R/proof['audit']).resolve(strict=True)
   owner=R/'conversion/auto_quality_font_repair_v1/round2_v1'/record['id']
   if folder.name!='report.json' or not folder.is_relative_to(owner.resolve()):raise ValueError('html_v4_unowned_frozen_font_revision')
   frozen=json.loads((folder.parent/'candidate_record.json').read_bytes())
   identity=('id','source_pair_sha256','source_code_sha256','source_image_sha256','source_format','category','source','original_source_code','original_reference')
   if any(frozen.get(k)!=record.get(k) for k in identity) or frozen.get('round2_font_repair')!=proof:raise ValueError('html_v4_font_successor_identity_mismatch')
   font_check=font_verify(frozen,Path(work)/'independent_font_v3')
   if not font_check.get('ok'):raise ValueError('html_v4_independent_font_delta_failed:'+str(font_check.get('reason')))
  except Exception as exc:
   folder=Path(work)/('qa_font_v3_'+str(index))/uuid.uuid4().hex;folder.mkdir(parents=True)
   report={'id':record['id'],'state':'repair_required','accepted':False,'checks':{'fonts':{'ok':False,'independent_font_delta_v3':font_check}},'failures':[str(exc)],'policy':VERSION+':'+sha(raw(configuration()))}
   save(folder/'audit.json',raw(report));return report,None,folder
 prior=getattr(qa,'_round2_frozen_policy',qa.POLICY);qa._round2_frozen_policy=prior+':'+VERSION+':'+sha(raw(configuration()))
 try:
  with source_scope():report,out,folder=complete_verify(record,job,work,index)
  if font_check:
   link={k:font_check[k] for k in ('report_file','report_sha256','schema','ok')}
   report.setdefault('checks',{}).setdefault('fonts',{})['independent_font_delta_v3']=link
   if out:out={**out,'independent_font_delta_v3':link}
   save(folder/'audit.json',raw(report))
  return report,out,folder
 finally:qa._round2_frozen_policy=prior
