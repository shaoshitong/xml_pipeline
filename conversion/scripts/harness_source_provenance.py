"""Carry immutable, source-identity-checked provenance through repeated model revisions."""
import copy,json,hashlib
from pathlib import Path
from native_worker import R
sha=lambda data:hashlib.sha256(data).hexdigest()
IDENTITY=('id','source_code_sha256','source_image_sha256')
SOURCE_FIELDS=('source_render_svg','source_render_svg_sha256','source_render_dot','source_render_pdf','source_render_pdf_sha256','original_source_data','source_data_sha256','source_data_locator')

def archive_record(relative,identity):
 p=(R/relative).resolve();assert p.is_relative_to(R/'conversion/harness_sessions'),'Archive outside owned Harness sessions';raw=(p/'conversion.json').read_bytes();r=json.loads(raw);assert all(r[k]==identity[k] for k in IDENTITY),'Archive source identity mismatch';xml=(p/'diagram.drawio').read_bytes();assert sha(xml)==r['code_sha256'],'Archived code hash mismatch';return r,xml,raw,p

def resolve(previous):
 if not previous:return None
 initial=copy.deepcopy(previous);r=initial;origin=None;visited=set()
 for _ in range(32):
  if r.get('native_source_font_repair'):break
  link=r.get('source_font_recovery_archive') or r.get('previous_candidate_archive')
  if not link:break
  assert link not in visited,'Source archive cycle';visited.add(link);r,xml,raw,origin=archive_record(link,initial)
 else:raise AssertionError('Source archive chain too deep')
 # If no historical source font proof exists, snapshot current available source metadata.
 if not r.get('native_source_font_repair'):r=initial;origin=None
 if origin is None:
  p=(R/r['code_file']).resolve();assert p.is_relative_to(R/'clean');xml=p.read_bytes();assert sha(xml)==r['code_sha256'],'Current candidate changed before provenance snapshot'
 return r,xml,str(origin.relative_to(R)) if origin else None

def validate_source_record(r):
 checks={}
 for key,digest in [('original_reference','source_image_sha256'),('original_source_code','source_code_sha256'),('original_source_data','source_data_sha256'),('source_render_svg','source_render_svg_sha256'),('source_render_dot',None),('source_render_pdf','source_render_pdf_sha256')]:
  if not r.get(key):continue
  p=(R/r[key]).resolve();assert p.is_relative_to(R/'clean'),'Source resource outside clean';h=sha(p.read_bytes())
  if digest:assert h==r[digest],'Source hash mismatch: '+key
  checks[key]={'file':r[key],'sha256':h}
 proof=r.get('native_source_font_repair',{})
 if proof.get('mappings'):
  for prefix in ['source_before_dom','source_after_dom']:
   p=(R/proof[prefix+'_file']).resolve();assert p.is_relative_to(R/'clean');h=sha(p.read_bytes());assert h==proof[prefix+'_sha256'],'Source font DOM hash mismatch';checks[prefix]={'file':proof[prefix+'_file'],'sha256':h}
 return checks

def freeze(previous,work):
 if not previous:return None
 resolved,xml,origin=resolve(previous);checks=validate_source_record(resolved);folder=work/'source_provenance';folder.mkdir(exist_ok=False);raw=(json.dumps(resolved,ensure_ascii=False,indent=2)+'\n').encode();(folder/'conversion.json').write_bytes(raw);(folder/'diagram.drawio').write_bytes(xml)
 audit={'version':1,'archive':str(folder.relative_to(R)),'record_sha256':sha(raw),'archived_code_sha256':sha(xml),'identity':{k:resolved[k] for k in IDENTITY},'recovered_from':origin,'source_hash_checks':checks,'scope':'Original-source/font provenance only. Archived whole-XML validation is historical; each new model candidate needs fresh source, font, geometry and render checks.'};(folder/'proof.json').write_text(json.dumps(audit,indent=2));return audit

def validate_frozen(proof):
 r,xml,raw,p=archive_record(proof['archive'],proof['identity']);assert sha(raw)==proof['record_sha256'],'Frozen source record modified';assert sha(xml)==proof['archived_code_sha256'];assert validate_source_record(r)==proof['source_hash_checks'];return r

def attach(out,ctx):
 proof=ctx.get('source_provenance')
 if proof is None:return out
 r=validate_frozen(proof);assert all(out[k]==r[k] for k in IDENTITY),'New output changed original source identity'
 result={**out,'source_font_recovery_archive':proof['archive'],'source_provenance':proof}
 for key in SOURCE_FIELDS:
  if r.get(key):
   if result.get(key):assert result[key]==r[key],'Conflicting source locator: '+key
   else:result[key]=r[key]
 return result
