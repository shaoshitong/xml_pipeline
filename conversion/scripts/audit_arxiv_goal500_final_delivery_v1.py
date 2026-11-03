"""Final read-only payload/proof audit on HKUST3, no imports or model calls."""
from pathlib import Path
import collections,concurrent.futures as cf,datetime,hashlib,json,sqlite3,sys
from arxiv_goal500_progress_v1 import BASELINE_SHA,pixels
from arxiv_pair_identity_admission_v1 import admit_unique
from arxiv_author_native_synced_replay_v1 import canonical
from arxiv_math_source_repair_v1 import native,classify,valuable
import arxiv_goal500_automatic_admission_v2 as automatic
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'goal500_final_delivery_v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def filecheck(item):
 file,expected=item;p=R/file
 if not p.resolve().is_relative_to(R):return dict(file=file,error='path_outside_project')
 try:
  actual=sha(p.read_bytes())
  return None if actual==expected else dict(file=file,expected=expected,actual=actual)
 except OSError as error:return dict(file=file,error=str(error))
def main():
 receipt=json.loads((D/'frozen_receipt.json').read_text());baseline_raw=(R/'clean/accepted_3759_v1/pairs.jsonl').read_bytes();assert sha(baseline_raw)==BASELINE_SHA==receipt['baseline_SHA256'];baseline=[json.loads(x) for x in baseline_raw.splitlines()]
 new_raw=(D/'accepted_new_pairs.jsonl').read_bytes();all_raw=(D/'baseline_plus_accepted_new.jsonl').read_bytes();assert sha(new_raw)==receipt['new_index_SHA256'] and sha(all_raw)==receipt['unified_index_SHA256'];new=[json.loads(x) for x in new_raw.splitlines()];all_rows=[json.loads(x) for x in all_raw.splitlines()]
 assert len(baseline)==3759 and len(new)>=500 and all_rows==baseline+new
 assert new[:190]==[json.loads(x) for x in (P/'goal500_automatic_admission_v2/retained_reviewed_190.jsonl').read_text().splitlines()]
 identities,rejected=admit_unique(baseline,new);assert len(identities)==len(new) and not rejected,'independent_code_OR_RGBA_duplicates'
 tasks={(r['code_file'],r['code_sha256']) for r in all_rows}|{(r['image_file'],r['image_sha256']) for r in all_rows}
 with cf.ThreadPoolExecutor(max_workers=8) as pool:payload_errors=[r for r in pool.map(filecheck,sorted(tasks)) if r]
 assert not payload_errors,str(payload_errors[:8]);print(json.dumps(dict(payload_files_checked=len(tasks),payload_errors=0)),flush=True)
 sys.path.insert(0,str(automatic.W/'scripts'));import embedded_xml_compiler_v1 as C
 errors=[];proof_count=0;metadata=collections.Counter();quality=collections.Counter();papers={};databases=[]
 for name in ['recent_ai_source_expansion_v2','new_bulk_200_v1']:
  db=sqlite3.connect((P/name/'once.sqlite').as_uri()+'?mode=ro',uri=True);databases.append(db)
 for i,row in enumerate(new):
  try:
   raw=(R/row['code_file']).read_bytes();image=(R/row['image_file']).read_bytes();assert pixels(image)==row['image_pixels'];features=native(raw.decode('utf-8-sig'));kind,_=classify(features,'drawio',{});assert kind=='complex_candidate' and features['native_pages']==1 and valuable(features)
   path=R/row['native_replay_proof'];proof_bytes=path.read_bytes();assert sha(proof_bytes)==row['native_replay_proof_sha256'];proof=json.loads(proof_bytes)
   for key in ['ok','normalized_model_exact_restore','mutation_normalized_model_changed','mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact']:assert proof[key] is True,key
   assert proof['source_XML_sha256']==row['code_sha256'] and proof['source_official_PNG_sha256']==row['image_sha256'];assert proof['source_geometry_topology_style_inventory_sha256']==proof['restored_geometry_topology_style_inventory_sha256'];assert (path.parent/'restored.png').read_bytes()==image and pixels((path.parent/'mutated.png').read_bytes())!=pixels(image)
   svg=(path.parent/'official.svg').read_text();assert sha(svg.encode())==proof['source_official_SVG_sha256'];assert canonical(svg)==canonical((path.parent/'restored.svg').read_text())
   assert not proof['resource_closure']['failed'] and proof['font_observations']['all_physical_font_bytes_pinned']
   for font in proof['font_observations']['font_assets']:assert sha((R/font['file']).read_bytes())==font['sha256']
   if not row.get('scientific_value_individually_certified'):
    evidence=(R/row['automatic_admission_proof']).read_bytes();assert sha(evidence)==row['automatic_admission_proof_sha256'];result=automatic.audit(row,C);assert result['code_sha256']==row['code_sha256'] and result['image_sha256']==row['image_sha256']
   paper=row['paper']
   if paper not in papers:
    found=None
    for db in databases:
     r=db.execute('select record from papers where id=?',(paper,)).fetchone()
     if r:found=json.loads(r[0]).get('metadata');break
    papers[paper]=found
   meta=papers[paper]
   if meta and meta.get('publication_date') and meta.get('categories'):
    day=datetime.datetime.fromisoformat(meta['publication_date'].replace('Z','+00:00')).date();metadata['dated_AI_2023plus' if day>=datetime.date(2023,1,1) and set(meta['categories'])&{'cs.AI','cs.CL','cs.CV','cs.LG'} else 'other_existing_reviewed_context']+=1
   else:metadata['existing_reviewed_metadata_context_missing']+=1
   quality.update(row.get('quality_views',[]));proof_count+=1
  except Exception as error:errors.append(dict(id=row.get('id'),paper=row.get('paper'),error=type(error).__name__+':'+str(error)[:1400]))
  if (i+1)%50==0:print(json.dumps(dict(pairs_checked=i+1,errors=len(errors))),flush=True)
 out=dict(at_utc=now(),ok=not errors,baseline_rows=3759,new_pairs=len(new),unified_rows=len(all_rows),payload_files_checked=len(tasks),all_payload_hashes_match=True,new_code_OR_RGBA_unique_against_baseline=True,original_baseline_SHA256=BASELINE_SHA,prior190_preserved=True,new_index_SHA256=sha(new_raw),unified_index_SHA256=sha(all_raw),strict_native_replay_packets_checked=proof_count,metadata_context=dict(metadata),quality_views=dict(quality),quality_views_overlap=True,original_PDF_fidelity_not_inferred=True,errors=errors,CPU_host='HKUST3',new_PDF_import_calls=0,new_model_calls=0,new_source_downloads=0)
 (D/'final_audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out),flush=True);return not out['ok']
if __name__=='__main__':raise SystemExit(main())
