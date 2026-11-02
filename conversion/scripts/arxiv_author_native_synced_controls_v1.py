from pathlib import Path
import concurrent.futures,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/author_native_source_replay_v1';sys.path.insert(0,str(R/'conversion/scripts'));from arxiv_author_native_synced_replay_v1 import Synced,pixels
ids={'f393deb9c2d3d0e9189d98b1a11496f4c66688dfadd00cc83ca05170bdcf0c17','03d5182d837740a9069a58052e0540b68df9e64bcdc7745ffe71155059f870f8','5a6eb87163138c2a3009a5f0d61422051598b2fd156cb61f374a56e8c92acccf'};rows=[r for r in map(json.loads,(D/'input_snapshot.jsonl').read_text().splitlines()) if r['id'] in ids]
def one(row):
 out=D/'cases'/row['id']/'synced_cold_controls_v1';out.mkdir();results=[]
 for attempt in range(2):
  renderer=Synced()
  try:results.append(renderer.replay((R/row['author_xml_file']).read_bytes(),out/('cold_'+str(attempt))))
  finally:renderer.close()
 result={'id':row['id'],'fixed_cold_contexts':2,'all_init_move_restore_exact':all(x['ok'] for x in results),'two_independent_cold_context_source_RGBA_exact':pixels((out/'cold_0/official.png').read_bytes())==pixels((out/'cold_1/official.png').read_bytes()),'source_body_font_count':len(results[0]['font_observations']['font_assets']),'states':[{k:r[k] for k in ['ok','normalized_model_exact_restore','mutation_actual_RGBA_changed','restored_actual_RGBA_exact','restored_PNG_bytes_exact','restored_SVG_namespace_canonical_exact','source_official_PNG_sha256','seconds']} for r in results],'old_author_XML_and_PNG_unmodified':True,'new_PDF_import_calls':0,'new_models':0};(out/'controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);return result
if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:results=list(ex.map(one,rows))
 (D/'synced_cold_controls_summary_v1.json').write_text(json.dumps(results,indent=2)+'\n')
