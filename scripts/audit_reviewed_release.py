import hashlib,json,datetime,itertools
from pathlib import Path
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'release'
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
review=load(R/'reports/visual_audit_final/root_visual_review.json');summary=load(D/'summary.json');content=load(R/'reports/content_audit.json');checks={};counts={}
checks['base_full_content_audit_success']=content['ok'];checks['realchart_recovery_audit_success']=load(R/'reports/realchart_recovery_final_audit.json')['ok'];checks['all_visual_sheets_reviewed']=len(review['sheets_reviewed'])==12 and review['samples_reviewed']==139 and review['strata_reviewed']==71
for kind,folder,label in [('provided','clean','clean'),('derived','derived','derived')]:
 source=R/folder/'manifest.jsonl';dest=D/(kind+'.jsonl');checks[kind+'_base_sha']=sha(source)==content['input_manifest_sha256'][label]==review['base_manifest_sha256'][label];checks[kind+'_release_sha']=sha(dest)==summary['groups'][kind]['sha256'];read=0;excluded=0;errors=0
 with source.open() as base,dest.open() as release:
  for line in base:
   row=json.loads(line);im=row['image_sha256']
   if im in review['rejected_image_hashes']:excluded+=1;continue
   actual_line=next(release,None)
   if actual_line is None:errors+=1;break
   actual=json.loads(actual_line);correction=actual.pop('visual_review_category_correction',None)
   if im in review['category_corrections_by_image_hash'] and row['category']!=review['category_corrections_by_image_hash'][im]['category']:
    target=review['category_corrections_by_image_hash'][im]
    if correction!={'kind':kind,'pair_sha256':row['pair_sha256'],'previous_category':row['category'],**target}:errors+=1
    row['category']=target['category']
   elif correction is not None:errors+=1
   if row!=actual:errors+=1
   read+=1
  if next(release,None) is not None:errors+=1
 checks[kind+'_exact_filtered_copy']=errors==0;checks[kind+'_counts']=read==summary['groups'][kind]['pairs'] and excluded==summary['groups'][kind]['excluded_pairs'];counts[kind]={'retained':read,'excluded':excluded,'record_mismatches':errors}
checks['no_media_or_code_modified']=all(checks[k+'_exact_filtered_copy'] for k in ('provided','derived'))
result={'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ok':all(checks.values()),'checks':checks,'counts':counts,'scope':'Every retained locator, image hash, code hash and provenance field is an exact copy of the full-content-audited base catalog, except explicitly reviewed category corrections. No code/media mutation or model call. Full-content coverage is inherited by verified subset equality, not asserted from a fresh rerender.','limitations':'139 visually reviewed samples across 71 strata; source quality and semantic alignment are not exhaustively verified.'}
(D/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert result['ok']
