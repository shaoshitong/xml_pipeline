from pathlib import Path
import concurrent.futures,hashlib,json,shutil,sys,time,xml.etree.ElementTree as ET
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/author_native_source_replay_v1';W=R/'conversion/arxiv_author_native_font_portable_v1';sys.path[:0]=[str(R/'conversion/scripts'),str(R/'scripts')]
from arxiv_author_native_assets_v1 import models,sha
from arxiv_sourceonly_bulk_200_v1_1 import facts
import drawio_author_version_fonts_v4 as fonts
rows=list(map(json.loads,(D/'input_snapshot.jsonl').read_text().splitlines()));eligible=[r for r in rows if facts((R/r['author_xml_file']).read_text())['image_vertices']==0];selected=sorted(eligible,key=lambda r:sha(('arxiv-author-portable-font-probe-v1-public-seed-20261102'+r['id']).encode()))[:2];assert len(selected)==2
(D/'portable_font_probe_selection_v1.json').write_text(json.dumps({'source_candidate_ids':[r['id'] for r in selected],'public_seed':'arxiv-author-portable-font-probe-v1-public-seed-20261102','source_XML_kept_unmodified':True,'new_PDF_import_calls':0,'new_models':0},indent=2)+'\n')
def one(row):
 case=D/'cases'/row['id'];out=case/'portable_font_probe_v1.json'
 if out.exists():return json.loads(out.read_text())
 t=time.monotonic();record={'id':row['id'],'status':'typed_pending_portable_fonts','new_PDF_import_calls':0,'new_models':0,'font_helper':'drawio_author_version_fonts_v4.py','author_runtime_version_is_not_asserted_reproduced':True}
 try:
  xml=(R/row['author_xml_file']).read_bytes();assert sha(xml)==row['author_xml_sha256'];_,ms=models(xml);assert len(ms)==1;source=ET.tostring(ms[0],encoding='unicode');profile={'version':'32.6.1','scale':json.loads((R/row['render_edit_evidence']).read_text())['scale'],'border':8};result=fonts.compile(source,profile,W/row['id']);dest=case/'portable_font_candidate_v1';dest.mkdir(exist_ok=False);(dest/'portable.drawio').write_text(result['xml']);(dest/'portable.official.png').write_bytes(result['png']);(dest/'font_binding_proof.json').write_text(json.dumps(result['proof'],indent=2)+'\n');(dest/'font_assets.json').write_text(json.dumps(result['assets'],indent=2)+'\n');record.update(status='verified_portable_font_derivative',portable_code_file=str((dest/'portable.drawio').relative_to(R)),portable_code_sha256=sha(result['xml'].encode()),portable_image_file=str((dest/'portable.official.png').relative_to(R)),portable_image_sha256=sha(result['png']),font_binding_proof=str((dest/'font_binding_proof.json').relative_to(R)),font_binding_proof_sha256=sha((dest/'font_binding_proof.json').read_bytes()),font_assets=result['assets'],source_official_render_profile=profile,source_normalized_model_sha256=sha(source.encode()),raw_author_XML_sha256=row['author_xml_sha256'],source_graph_geometry_topology_and_nonfont_metadata_preserved=True,source_official_RGBA_equals_portable_official_RGBA=True)
 except Exception as e:record['reason']=type(e).__name__+':'+str(e)[:1600]
 record['seconds']=time.monotonic()-t;out.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record.get(k) for k in ['id','status','reason','seconds']}),flush=True);return record
if __name__=='__main__':
 with concurrent.futures.ProcessPoolExecutor(max_workers=2) as ex:results=list(ex.map(one,selected))
 (D/'portable_font_probe_summary_v1.json').write_text(json.dumps({'results':results,'new_PDF_import_calls':0,'new_models':0},indent=2)+'\n')
