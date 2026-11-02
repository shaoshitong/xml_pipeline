import json,sqlite3,uuid,copy,xml.etree.ElementTree as E
from PIL import Image
from native_worker import R,W,native,now,sha
from durable_sqlite import begin,commit
from harness_context_v5 import build_context,compact_xml,hydrate
from strict_canvas_gate import require_declared_page

ID='0b8e6086486b77fdc223c81e902f2927af8f9a3be730f9f2133c68479b637fdb';OLD='743ffc5ceaa21bd2777ed555c0bca13c88dc8b318d6cf4d86a22ebfcc6ce9b97';NEW='c59c1e915943993defa7b6c6172867207c75d6d6df31b32c0747c88ed635ab97'
D=sqlite3.connect(W/'jobs.sqlite',timeout=2);state,raw,source,inp=D.execute('select state,output_record,input_record,input_manifest from jobs where id=?',(ID,)).fetchone();r=json.loads(raw);assert state=='harness_review_pending' and r['code_sha256']==NEW
snapshot=W/'root_candidate_snapshots'/ID/OLD;old=(snapshot/'diagram.drawio').read_text();xml=(R/r['code_file']).read_text();png=(R/r['image_file']).read_bytes();assert sha(xml.encode())==NEW and png==(snapshot/'native.png').read_bytes();before=json.loads((snapshot/'record.json').read_text())
def normalized(s):
 root=E.fromstring(s)
 for c in root.iter('mxCell'):
  if c.get('id') in ('0','1'):
   assert not c.get('vertex') and not c.get('edge') and not c.get('value') and len(c)==0
   assert not c.get('style','').replace(';','').strip()
   c.attrib.pop('style',None)
 return E.canonicalize(E.tostring(root,encoding='unicode'))
assert normalized(old)==normalized(xml),'Graph, model, fonts or metadata differ beyond empty root/layer styles'
audit=json.loads((W/'mermaid_compound_node_release_audit.json').read_text());a=next(x for x in audit['results'] if x['id']==ID);assert audit['ok'] and a['code_sha256']==OLD and a['source_nodes']==12 and a['source_edges']==9
review=json.loads((W/'compound_node_root_acceptance'/ID/OLD/'root_visual_review.json').read_text());assert review['code_sha256']==OLD
B=W/'harness_sessions'/('equivalent_compound_acceptance_'+uuid.uuid4().hex[:12]);B.mkdir();ctx=build_context(json.loads(source),json.loads(inp),r,B);roundtrip,_=hydrate(compact_xml(xml,ctx),ctx);w,h=Image.open(R/r['original_reference']).size;fresh=native.native_job(roundtrip,w,h,120,W/'rendering_paintbounds_strict/remote_render.py',8192,R/'evaluation/assets/drawio-runtime-v32.6.1/manifest.json');assert fresh['ok'] and fresh['png']==png;require_declared_page(fresh['native_render'],w,h)
for row in fresh['native_render']['actual_platform_font_usage']:assert row['fonts'] and all(f['isCustomFont'] for f in row['fonts'] if f['glyphCount'])
proof={'at':now(),'id':ID,'reviewed_code_sha256':OLD,'current_code_sha256':NEW,'current_image_sha256':r['image_sha256'],'all_graph_geometry_text_styles_fonts_and_page_attributes_identical':True,'only_xml_change':'empty style=";" added on nonvisual root/layer cells 0 and 1','png_identical_to_root_viewed_snapshot':True,'fresh_native_roundtrip_png_identical':True,'review':review,'accepted':True};(B/'equivalence_acceptance.json').write_text(json.dumps(proof,indent=2));(B/'before_record.json').write_text(raw)
begin(D);assert D.execute('select state,output_record from jobs where id=?',(ID,)).fetchone()==(state,raw);assert D.execute('select state from harness_queue_v3 where id=?',(ID,)).fetchone()[0]!='running';assert sha((R/r['code_file']).read_bytes())==NEW
r['root_review']={**review,'code_sha256':NEW,'equivalence_audit':str((B/'equivalence_acceptance.json').relative_to(R))};r['root_acceptance']=str((B/'equivalence_acceptance.json').relative_to(R));r['accepted_at_utc']=now();r['quality_state']='accepted_equivalent_native_graph_after_source_and_root_visual_review';r['validation_pending']=[];r['native_embedded_fonts']=before['native_embedded_fonts'];r['deterministic_source_equivalence']={'reviewed_code_sha256':OLD,'source_geometry':before['native_source_geometry_repair'],'proof':r['root_acceptance']}
meta=(R/r['code_file']).parent/'conversion.json';temp=meta.with_suffix('.equivalent-accept.tmp');temp.write_text(json.dumps(r,ensure_ascii=False,indent=2));temp.replace(meta);D.execute('update jobs set state="accepted",output_record=?,error=NULL,worker_pid=NULL,updated_at=? where id=?',(json.dumps(r,ensure_ascii=False),now(),ID));D.execute('update harness_queue_v3 set state="resolved_by_deterministic_acceptance",error=NULL,worker_pid=NULL where id=?',(ID,));commit(D);(W/'compound_harness_equivalence_acceptance.json').write_text(json.dumps(proof,indent=2));print(json.dumps(proof))
