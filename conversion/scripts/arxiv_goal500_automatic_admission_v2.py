"""Independent proof-backed admission of embedded native framework candidates.

Retains baseline3759 and earlier reviewed190 verbatim. Publishes a separate v2
index; neither a provisional marker nor the compiler's claimed status suffices.
All data, image decoding, source checks and watch work run on HKUST3.
"""
from pathlib import Path
import argparse,collections,datetime,fcntl,hashlib,json,os,signal,sqlite3,struct,sys,time,zipfile
from PIL import Image
from arxiv_author_native_assets_v1 import models,dependencies
from arxiv_native_framework_layout_gate_v1 import check as layout_check
from arxiv_pair_identity_admission_v1 import admit_unique
from arxiv_complete_native_page_identity_v1 import verify as verify_complete_page
from arxiv_goal500_progress_v1 import pixels,BASELINE_SHA,VALUE_POLICY
from arxiv_author_native_synced_replay_v1 import canonical
from arxiv_math_source_repair_v1 import native,classify,valuable
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';D=P/'goal500_automatic_admission_v2';W=R/'conversion/dpsk_svg_png_compiler_20261103';COMP=W/'results/embedded_XML_compiler_dpsk_v1';WAR=R/'evaluation/assets/drawio-runtime-v32.6.1/draw.war';WAR_SHA='44dd56958c8408963457dc98f04d2228408ac145c7aa1d8e6895d9c88d5e42aa';RETAINED_SHA='44437f4b5e86006ad896829c003ff1061aeb5f0fe499cf674cf58a15c9e1f514'
POLICY='independent_source_proof_complete_native_page_payload_font_resource_layout_code_OR_RGBA_admission_v4'
DIGESTS={};AUDITED={};PAPER_CACHE={};PINNED_CORE=None;PINNED_PAGE_CORE=None;STOP=False
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=lambda b:hashlib.sha256(b).hexdigest()
RECIPE_SHA=sha(Path(__file__).read_bytes()+Path(layout_check.__code__.co_filename).read_bytes()+Path(verify_complete_page.__code__.co_filename).read_bytes())
def put(path,obj):
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n');os.replace(tmp,path)
def safe(file):
 p=R/file;assert p.resolve().is_relative_to(R),'path_outside_remote_project';return p
def digest(p):
 s=p.stat();key=(str(p),s.st_ino,s.st_size,s.st_mtime_ns)
 if key not in DIGESTS:DIGESTS[key]=sha(p.read_bytes())
 return DIGESTS[key]
def read_proof(row,name):
 p=safe(row[name]);assert digest(p)==row[name+'_sha256'],name+'_SHA_changed';return json.loads(p.read_text())
def source_identity(row,source):
 paper=row['paper'];base=P/'recent_ai_source_expansion_v2/papers'/paper;root=base/'source';assert source.resolve().is_relative_to(root.resolve())
 with sqlite3.connect((P/'recent_ai_source_expansion_v2/once.sqlite').as_uri()+'?mode=ro',uri=True) as db:state,raw=db.execute('select status,record from papers where id=?',(paper,)).fetchone()
 meta=json.loads(raw)['metadata'];assert state=='source_completed' and meta==row['paper_metadata'] and meta['versioned_id']==paper
 day=datetime.datetime.fromisoformat(meta['publication_date'].replace('Z','+00:00')).date();assert datetime.date(2023,1,1)<=day<=datetime.date(2026,11,2) and set(meta['categories'])&{'cs.AI','cs.CL','cs.CV','cs.LG'}
 archive=base/'source.archive';receipt=base/'source_receipt.json';assert safe(row['source_archive_file'])==archive and safe(row['source_receipt_file'])==receipt
 receipt_data=json.loads(receipt.read_text());assert receipt_data['url']=='https://arxiv.org/src/'+paper and receipt_data['sha256']==digest(archive)==row['source_archive_sha256'];assert receipt_data['bytes']==archive.stat().st_size and digest(receipt)==row['source_receipt_sha256']
 return dict(source_root=str(root.relative_to(R)),source_archive_file=str(archive.relative_to(R)),source_archive_sha256=digest(archive))
def fingerprint(row):
 fields=['code_file','image_file','native_replay_proof','archive_membership_proof','original_container_file','source_archive_file','source_receipt_file']
 if row.get('source_origin_kind')=='embedded_native_complete_page':fields+=['official_full_decoder_agreement','official_page_decoder_comparison','page_selection_proof','original_author_XML','original_page_author_XML']
 else:fields+=['official_decoder_agreement']
 paths={safe(row[k]) for k in fields};folder=safe(row['native_replay_proof']).parent
 paths.update(folder/n for n in ['mutated.png','restored.png','official.svg','restored.svg']);paths.update(safe(f['file']) for f in row['font_dependencies']);paths.add(WAR)
 for asset in (row.get('asset_package') or {}).get('resource_dependencies',[]):
  for key in ['original_asset_file','portable_asset_file']:
   if asset.get(key):paths.add(safe(asset[key]))
 return [(str(p),p.stat().st_ino,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(paths)]
def audit(row,C):
 code,image=safe(row['code_file']),safe(row['image_file']);assert digest(code)==row['code_sha256'] and digest(image)==row['image_sha256'],'pair_payload_SHA_changed'
 proof=read_proof(row,'native_replay_proof');folder=safe(row['native_replay_proof']).parent
 assert proof['source_XML_sha256']==row['code_sha256'] and proof['source_official_PNG_sha256']==row['image_sha256']
 for k in ['ok','normalized_model_exact_restore','mutation_normalized_model_changed','mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact']:assert proof[k] is True,'strict_replay_'+k
 assert proof['source_geometry_topology_style_inventory_sha256']==proof['restored_geometry_topology_style_inventory_sha256']
 original=image.read_bytes();restored=(folder/'restored.png').read_bytes();mutated=(folder/'mutated.png').read_bytes();assert restored==original,'actual_restored_PNG_bytes_differ';assert pixels(mutated)!=pixels(original),'actual_mutation_did_not_change_RGBA'
 svg=(folder/'official.svg').read_text();rsvg=(folder/'restored.svg').read_text();assert sha(svg.encode())==proof['source_official_SVG_sha256'];assert canonical(svg)==canonical(rsvg),'actual_restored_SVG_differs'
 assert proof['font_observations']['all_physical_font_bytes_pinned'] and not proof['resource_closure']['failed'] and not proof.get('missing') and not proof.get('blocked')
 for font in proof['font_observations']['font_assets']:assert digest(safe(font['file']))==font['sha256'],'physical_font_SHA_changed'
 blob=code.read_bytes();f=native(blob.decode('utf-8-sig'));kind,_=classify(f,'drawio',{});assert kind=='complex_candidate' and f['native_pages']==1 and valuable(f),'existing_scientific_value_policy_failed'
 with zipfile.ZipFile(WAR) as war:closure=dependencies(blob,code,code,war)
 assert not closure['issues'],'independent_resource_closure_failed'
 layout=layout_check(blob);assert layout['ok'],'layout:'+','.join(layout['reasons'])
 assert row['static_QA']['ok'] and row['render_QA']['ok'];assert not row['static_QA']['warnings'] and not row['render_QA']['warnings'],'compiler_quality_warning_held'
 source=safe(row['original_container_file']);assert digest(source)==row['original_container_sha256'];container_kind='PNG_native_XML_marker' if source.suffix.lower()=='.png' else 'SVG_native_XML_marker';page_identity=None
 if row.get('source_origin_kind')=='embedded_native_complete_page':
  import embedded_xml_page_core_v1 as PC
  extracted=PC.extract_full_v2(source,container_kind);full=extracted['raw'];assert digest(safe(row['original_author_XML']))==row['original_author_XML_sha256']==sha(full);assert safe(row['original_author_XML']).read_bytes()==full
  assert digest(safe(row['original_page_author_XML']))==row['original_page_author_XML_sha256']==row['code_sha256']==row['selected_page_XML_sha256'];assert safe(row['original_page_author_XML']).read_bytes()==blob
  selection=read_proof(row,'page_selection_proof');assert selection['complete_selected_mxGraphModel'] and selection['every_original_cell_edge_group_style_geometry_label_preserved'];assert not selection['fragment_crop_or_subgraph_selection'] and not selection['geometry_or_scientific_content_rewritten']
  assert selection['parent_full_embedded_XML_sha256']==sha(full) and selection['selected_page_XML_sha256']==sha(blob);assert row['paired_code_XML_bytes_equal_full_embedded_XML']==(full==blob)
  assert (selection['selected_page_index'],selection['selected_page_id'],selection['selected_page_name'])==(row['selected_page_index'],row['selected_page_id'],row['selected_page_name'])
  page_identity=verify_complete_page(full,blob,row['selected_page_index'],row['selected_page_id'],row['selected_page_name'])
  agreement=read_proof(row,'official_full_decoder_agreement');assert agreement['python_xml_sha256']==sha(full) and (agreement['exact_bytes_equal'] or agreement['canonical_XML_equal'])
  page_decode=read_proof(row,'official_page_decoder_comparison');assert page_decode['exact_bytes_equal'] or page_decode['canonical_model_equal'];assert page_decode['full_embedded_XML_sha256']==sha(full) and page_decode['selected_page_XML_sha256']==sha(blob);assert page_decode['official_WAR_sha256']==WAR_SHA
  assert (page_decode['selected_page_index'],page_decode['selected_page_id'],page_decode['selected_page_name'])==(row['selected_page_index'],row['selected_page_id'],row['selected_page_name'])
 else:
  agreement=read_proof(row,'official_decoder_agreement');assert agreement['exact_bytes_equal'] or agreement['canonical_XML_equal'];assert agreement['python_xml_sha256']==row['code_sha256'];extracted=C.extract_candidate(source,container_kind);assert extracted['raw']==blob,'independent_source_extraction_differs'
 assert agreement['official_WAR_sha256']==WAR_SHA and row['official_WAR_sha256']==WAR_SHA
 identity=source_identity(row,source)
 membership=read_proof(row,'archive_membership_proof');assert membership['all_members_exact_and_safe'] and membership['members'];assets=[]
 for dep in (row.get('asset_package') or {}).get('resource_dependencies',[]):
  if dep.get('original_asset_file'):assets.append(safe(dep['original_asset_file']))
 actual_membership=C.verify_source_archive_members(identity,source,assets);assert actual_membership==membership,'independent_archive_membership_differs'
 observed=pixels(original);assert row.get('whole_figure_wrapper') is False
 result=dict(row,image_pixels=observed,goal500_pair_id=sha(json.dumps([row['code_sha256'],observed['width'],observed['height'],observed['rgba_sha256']]).encode()),quality_views=['arxiv_author_native_source_replay','automatic_native_framework_QA_v2'],scientific_value_individually_certified=False,scientific_value_review='deterministic_complexity_and_framework_layout_policy',automatic_admission_policy=POLICY,automatic_layout_proof=layout,curation_features=f,accepted_authoritative=True,authoritative_index_updated=True,quality_state='independently_verified_native_framework_source_replay')
 evidence=dict(at_utc=now(),policy=POLICY,id=row['id'],code_sha256=row['code_sha256'],image_sha256=row['image_sha256'],native_replay_proof_sha256=row['native_replay_proof_sha256'],official_decoder_agreement_sha256=row.get('official_decoder_agreement_sha256') or row.get('official_full_decoder_agreement_sha256'),archive_membership_proof_sha256=row['archive_membership_proof_sha256'],actual_RGBA_edit_changed=True,actual_PNG_restore_exact=True,actual_SVG_restore_exact=True,resources_closed=True,physical_font_bytes_pinned=True,layout=layout,source_container_unchanged=True,original_PDF_fidelity_not_claimed=True,new_PDF_import_calls=0,new_model_calls=0)
 if page_identity:
  result['quality_views'].append('arxiv_complete_native_page_source_replay');evidence.update(complete_page_identity=page_identity,page_selection_proof_sha256=row['page_selection_proof_sha256'],official_page_decoder_comparison_sha256=row['official_page_decoder_comparison_sha256'])
 proof_dir=D/'admission_proofs'/RECIPE_SHA;proof_dir.mkdir(exist_ok=True);p=proof_dir/(row['id']+'.json');evidence['recipe_SHA256']=RECIPE_SHA
 if not p.exists():put(p,evidence)
 result.update(automatic_admission_proof=str(p.relative_to(R)),automatic_admission_proof_sha256=digest(p));return result

def snapshot():
 global PINNED_CORE,PINNED_PAGE_CORE
 sys.path.insert(0,str(W/'scripts'));import embedded_xml_compiler_v1 as C
 actual_core=digest(Path(C.__file__))
 if PINNED_CORE is None:PINNED_CORE=actual_core
 assert actual_core==PINNED_CORE,'compiler_core_changed_review_before_admission'
 page_core=W/'scripts/embedded_xml_page_core_v1.py'
 if page_core.exists():
  if PINNED_PAGE_CORE is None:PINNED_PAGE_CORE=digest(page_core)
  assert digest(page_core)==PINNED_PAGE_CORE,'page_core_changed_review_before_admission'
 assert digest(WAR)==WAR_SHA
 base=(R/'clean/accepted_3759_v1/pairs.jsonl').read_bytes();assert sha(base)==BASELINE_SHA;baseline=[json.loads(x) for x in base.splitlines()];assert len(baseline)==3759
 retained_file=D/'retained_reviewed_190.jsonl'
 if not retained_file.exists():
  retained=(P/'goal500_progress_v1/accepted_new_pairs.jsonl').read_bytes();assert sha(retained)==RETAINED_SHA;retained_file.write_bytes(retained)
 retained=retained_file.read_bytes();assert sha(retained)==RETAINED_SHA;prior=[json.loads(x) for x in retained.splitlines()];assert len(prior)==190
 manifest=(COMP/'verified_candidates.jsonl').read_bytes();page_manifest=W/'results/embedded_XML_page_compiler_v1/verified_pages.jsonl';page_raw=page_manifest.read_bytes() if page_manifest.exists() else b'';rows=[json.loads(x) for x in manifest.splitlines()+page_raw.splitlines()];new=[];held=[]
 for row in rows:
  token=sha(json.dumps(row,sort_keys=True).encode())
  try:
   # Audited immutable replay packets are cached only while all their files keep
   # the same identities; font/resource/archive hashes are checked by audit().
   ids=fingerprint(row);cached=AUDITED.get(token)
   if cached and cached[0]==ids:checked=cached[1]
   else:checked=audit(row,C);AUDITED[token]=(ids,checked)
   new.append(checked)
  except Exception as error:held.append(dict(id=row.get('id'),reason=type(error).__name__+':'+str(error)[:1200]))
 admitted,rejected=admit_unique(baseline+prior,sorted(new,key=lambda r:r['goal500_pair_id']));accepted=prior+admitted
 for name,records in [('accepted_new_pairs.jsonl',accepted),('baseline_plus_accepted_new.jsonl',baseline+accepted)]:
  p=D/name;tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in records));os.replace(tmp,p)
 put(D/'held.json',held);put(D/'duplicate_rejections.json',rejected)
 current=dict(at_utc=now(),policy=POLICY,baseline_rows=3759,retained_previously_reviewed_new=190,embedded_candidates=len(rows),automatic_new=len(admitted),held=len(held),duplicates=len(rejected),accepted_new_pairs=dict(file=str((D/'accepted_new_pairs.jsonl').relative_to(R)),rows=len(accepted),sha256=digest(D/'accepted_new_pairs.jsonl')),unified_pairs=dict(file=str((D/'baseline_plus_accepted_new.jsonl').relative_to(R)),rows=3759+len(accepted),sha256=digest(D/'baseline_plus_accepted_new.jsonl')),target_new=500,goal_complete=False,original_PDF_quality_view_not_inferred=True,all_processing_CPU_host='HKUST3',source_compiler_manifest_SHA256=sha(manifest),final_random100_still_required=True)
 current['accepted_by_quality_view']=dict(collections.Counter(view for r in accepted for view in r.get('quality_views',[])));current['quality_views_overlap']=True;current['source_page_manifest_SHA256']=sha(page_raw)
 put(D/'current.json',current);print(json.dumps(current),flush=True);return current

def main(watch):
 global STOP
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda *_:globals().__setitem__('STOP',True))
 D.mkdir(exist_ok=True);(D/'admission_proofs').mkdir(exist_ok=True);lock=(D/'publisher.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 put(D/'launch.json',dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],at_utc=now(),CPU_host='HKUST3'))
 while True:
  snapshot()
  if not watch or STOP:break
  for _ in range(60):
   if STOP:break
   time.sleep(1)
  if STOP:break
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');main(p.parse_args().watch)
