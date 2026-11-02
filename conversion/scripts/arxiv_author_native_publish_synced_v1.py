"""Fixed native-author replay cohort -> separately named clean source-replay view."""
from pathlib import Path
import collections,concurrent.futures,datetime,hashlib,json,os,sys,time,zipfile
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/author_native_source_replay_v1';sys.path.insert(0,str(R/'conversion/scripts'))
from arxiv_author_native_assets_v1 import dependencies,sha
from arxiv_author_native_asset_package_v1 import package
from arxiv_author_native_synced_replay_v1 import Synced,POLICY,pixels
from arxiv_sourceonly_bulk_200_v1_1 import facts
from arxiv_bulk_official_xml_png_v1 import WAR
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def worker(row):
 case=D/'cases'/row['id'];out=case/'source_replay_publication_record_v1.json'
 if out.exists():return json.loads(out.read_text())
 tick=time.monotonic();record={'raw_source_pair_id':row['id'],'status':'typed_pending_source_replay','new_PDF_import_calls':0,'new_normal_calls':0,'new_model_calls':0,'stage_seconds':{}};renderer=None
 try:
  author=R/row['author_xml_file'];xml=author.read_bytes();raw_png=R/row['image_file'];assert sha(xml)==row['author_xml_sha256'] and sha(raw_png.read_bytes())==row['image_sha256'];structure=facts(xml.decode());assert structure['complexity_match'] and not structure['all_single_image_wrapper'] and structure['pages']==1
  t=time.monotonic()
  with zipfile.ZipFile(WAR) as archive:dep=dependencies(xml.decode(),author,R/row['pdf_file'],archive)
  record['stage_seconds']['decoded_models_and_asset_inventory']=time.monotonic()-t;code=author;asset_map=dep['asset_map'];asset_package=None
  if dep['issues']:
   code,asset_map,asset_package=package(xml,dep,case/'standalone_asset_package_v1')
  cached=case/'synced_cold_controls_v1/cold_0/synced_replay_proof.json'
  t=time.monotonic()
  if cached.exists() and code==author:
   proof=json.loads(cached.read_text());folder=cached.parent;record['existing_identical_fixed_protocol_control_reused']=True
  else:
   folder=case/'synced_source_replay_v1';renderer=Synced(asset_map);proof=renderer.replay(code.read_bytes(),folder)
  record['stage_seconds']['cold_official_render_actual_fonts_and_native_edit_restore']=time.monotonic()-t;assert proof['ok'],'uniform_source_native_edit_restore_failed';assert proof['source_XML_sha256']==sha(code.read_bytes());assert proof['font_observations']['all_physical_font_bytes_pinned'],'physical_font_bytes_pending'
  image=folder/'official.png';assert sha(image.read_bytes())==proof['source_official_PNG_sha256'];raw_equal=pixels(image.read_bytes())==pixels(raw_png.read_bytes());padding=None
  pad=case/'canvas_padding_equivalence_probe_v1.json'
  if pad.exists():
   padding=json.loads(pad.read_text());assert padding['union_RGBA_exact'] and padding['union_changed_pixels']==0
  for f in proof['font_observations']['font_assets']:
   assert sha((R/f['file']).read_bytes())==f['sha256']
  oldproof=R/row['render_edit_evidence'];old=json.loads(oldproof.read_text());assert old['edit_probe']['mutation_actual_PNG_changed'] and old['edit_probe']['restored_actual_PNG_exact'];assert sha(author.read_bytes())==row['author_xml_sha256'] and sha(raw_png.read_bytes())==row['image_sha256'];code_sha=sha(code.read_bytes());image_sha=sha(image.read_bytes());pairid=sha(json.dumps({'profile':'author_native_source_replay','author_XML_sha256':row['author_xml_sha256'],'current_code_sha256':code_sha,'current_official_PNG_sha256':image_sha,'renderer_protocol':POLICY},sort_keys=True).encode());pdf=raw_png.parent/'source.pdf';pdf=pdf if pdf.exists() else R/row['pdf_file'];assert sha(pdf.read_bytes())==row['pdf_sha256'];p={'id':pairid,'raw_source_pair_id':row['id'],'source':'arxiv_author_native_drawio','paper':row['paper'],'source_once_databases':row['source_once_databases'],'profile':'author_native_source_replay','format':'drawio','source_format':'author_drawio_XML_embedded_in_PDF','category':'scientific_diagram','quality_state':'verified_under_declared_author_native_source_replay_contract','code_file':str(code.relative_to(R)),'code_sha256':code_sha,'image_file':str(image.relative_to(R)),'image_sha256':image_sha,'source_code_sha256':row['author_xml_sha256'],'source_image_sha256':image_sha,'source_image_origin':'fresh_source_only_official_drawio_32.6.1_full_Editor_Graph.getSvg_PNG_uniform_synced_cold_context','original_author_XML':row['author_xml_file'],'original_author_XML_sha256':row['author_xml_sha256'],'author_XML_original_file_unmodified':True,'paired_code_XML_bytes_equal_original_author_XML':code_sha==row['author_xml_sha256'],'auxiliary_preexisting_native_PNG':row['image_file'],'auxiliary_preexisting_native_PNG_sha256':row['image_sha256'],'fresh_RGBA_equals_preexisting_native_PNG':raw_equal,'native_canvas_padding_equivalence':{'evidence':str(pad.relative_to(R)),'evidence_sha256':sha(pad.read_bytes()),'union_RGBA_exact':True,'pixel_tolerance':0} if padding else None,'original_PDF_file':str(pdf.relative_to(R)),'original_PDF_sha256':row['pdf_sha256'],'original_PDF_fidelity':'review_not_certified','provider_original_reference_aligned':False,'legacy_full8_qualified':False,'historical_author_OS_fonts_exact':False,'standalone_image_assets_complete':True,'standalone_font_portability_certified':False,'font_portability_state':'runtime_bound_current_actual_physical_faces_bundled; author font styles not rewritten','font_dependencies':proof['font_observations']['font_assets'],'actual_painted_Text_backend_nodes':proof['font_observations']['Text_nodes'],'actual_Unicode_characters':proof['font_observations']['Unicode_characters'],'native_replay_proof':str((folder/'synced_replay_proof.json').relative_to(R)),'native_replay_proof_sha256':sha((folder/'synced_replay_proof.json').read_bytes()),'old_native_render_edit_proof':row['render_edit_evidence'],'old_native_render_edit_proof_sha256':sha(oldproof.read_bytes()),'asset_audit':str((case/'static_asset_audit.json').relative_to(R)),'asset_audit_sha256':sha((case/'static_asset_audit.json').read_bytes()),'asset_package':asset_package,'structural_complexity':structure,'drawing_object_counts_are_not_semantic_quality_labels':True,'whole_figure_wrapper':False,'new_PDF_import_calls':0,'new_normal_calls':0,'new_model_calls':0,'renderer_policy':POLICY,'source_geometry_or_pixel_fitting':False,'official_WAR_sha256':sha(WAR.read_bytes())};record.update(status='verified_author_native_source_replay',pair=p)
 except Exception as e:record['reason']=type(e).__name__+':'+str(e)[:1400]
 finally:
  if renderer:renderer.close()
  record['seconds']=time.monotonic()-tick;record['finished_utc']=now();out.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 return record
def publish(records,finished):
 pairs=[r['pair'] for r in records if r.get('pair')];by={p['id']:p for p in pairs};file=D/'source_replay_aligned.jsonl';tmp=file.with_suffix('.tmp');tmp.write_text(''.join(json.dumps(p,ensure_ascii=False,sort_keys=True)+'\n' for p in sorted(by.values(),key=lambda p:p['id'])));os.replace(tmp,file);summary={'at_utc':now(),'profile':'author_native_source_replay','input_rows':26,'finished_rows':len(records),'finished':finished,'states':dict(collections.Counter(r['status'] for r in records)),'verified_pairs':len(by),'file':str(file),'sha256':sha(file.read_bytes()),'runtime_bound_fonts_not_full8_or_provider_original':True,'source_XML_and_preexisting_PNGs_unchanged':True,'new_PDF_import_calls':0,'new_normal_calls':0,'new_models':0,'stage_seconds':{name:round(sum(r['stage_seconds'].get(name,0) for r in records),3) for name in ['decoded_models_and_asset_inventory','cold_official_render_actual_fonts_and_native_edit_restore']}};(D/'source_replay_manifest.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
if __name__=='__main__':
 controls=json.loads((D/'synced_cold_controls_summary_v1.json').read_text());assert len(controls)==3 and all(r['all_init_move_restore_exact'] and r['two_independent_cold_context_source_RGBA_exact'] for r in controls);assert json.loads((D/'controls/asset_contract_v1/result.json').read_text())['ok'];rows=list(map(json.loads,(D/'input_snapshot.jsonl').read_text().splitlines()));records=[];begin=time.monotonic()
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:
  futures=[ex.submit(worker,row) for row in rows]
  for future in concurrent.futures.as_completed(futures):
   r=future.result();records.append(r);publish(records,False);print(json.dumps({'id':r['raw_source_pair_id'],'status':r['status'],'reason':r.get('reason'),'seconds':r['seconds']}),flush=True)
 summary=publish(records,True);summary.update(elapsed_seconds=time.monotonic()-begin,cases_per_minute=len(records)/max(1,time.monotonic()-begin)*60);O=D/'published_source_replay_v1';O.mkdir(exist_ok=False);(O/'source_replay_aligned.jsonl').write_bytes((D/'source_replay_aligned.jsonl').read_bytes());(O/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n');(D/'source_replay_manifest.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
