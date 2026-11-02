"""Separate technical qualification from source completeness and research value."""
from pathlib import Path
import hashlib,io,json,sqlite3,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def asset(p):return dict(file=str(p.relative_to(R)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size)
def main():
 from priority_svg_dense_source_screen_v2 import features,select
 from priority_source_complexity_filter_v1 import native,classify
 from svg_source_text_occlusion_review_v1 import inspect
 from playwright.sync_api import sync_playwright
 from PIL import Image
 with sqlite3.connect((R/'release/compiler_iterations/runs/svg_complex_symbol_viewport_unseen100_20261102_v7_C/status.sqlite').as_uri()+'?mode=ro',uri=True)as d:results=[dict(json.loads(r[0]),kind='v13')for r in d.execute("select result from samples where status='qualified'")]
 normal=json.loads((R/'conversion/compiler_svg_scene_frontend_v14/normal_development_v1/f4b4a0d4f06844aeb240ab0eea1b1d1e/6c1c25a290c58f50b7affe778c2f52dba94ffae8f91ac0172547cdbc186d74bb/summary.json').read_bytes());assert normal['quality_ok'];results.append(dict(id=normal['id'],manifest=normal['qualified_manifest'],quality_report=normal['quality_report'],kind='v14'))
 output=R/'clean/complexity_curation_20261102T054553Z_v1/value_reviews'/('symbol_round_edge_normal_'+uuid.uuid4().hex);output.mkdir(parents=True);rows=[];occlusions=[]
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu']);context=browser.new_context(viewport=dict(width=1200,height=750),device_scale_factor=1,java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:route.abort());page=context.new_page()
  try:
   for result in results:
    pair=result['manifest']
    for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:assert sha((R/pair[field]).read_bytes())==pair[digest]
    record=json.loads((R/pair['metadata_file']).read_bytes());qa=Path(result['quality_report']);qa=qa if qa.is_absolute()else R/qa;report=json.loads(qa.read_bytes())
    if result['kind']=='v13':
     import compiler_svg_general_guard_v9 as core
     import svg_analytic_iteration_controls_v5 as verifier
    else:
     import compiler_svg_general_guard_v10 as core
     import svg_edge_layers_quality_contract_v1 as verifier
    verifier.full_quality(report,record,core.configuration(),asset(qa.parent/'native_render.json'))
    source=(R/pair['original_source_code']).read_bytes();size=Image.open(io.BytesIO((R/pair['original_reference']).read_bytes())).size;page.set_viewport_size(dict(width=size[0],height=size[1]));occlusion=inspect(page,source.decode('utf-8-sig'),size);occlusions.append(dict(id=pair['id'],source_sha256=pair['source_code_sha256'],**occlusion))
    dense=features(source);structure=native((R/pair['code_file']).read_text());status,rules=classify(structure,'drawio',{})
    visually_approved=pair['id']=='66710413a814b9d85d1efbf1a163c6cfc4a7bcbb3e26541c71d18914b6a08a84';approve=visually_approved and not occlusion['labels']
    rows.append(dict(id=pair['id'],pair=pair,full_eight_quality_reverified=True,quality_report=asset(qa),dense_source_features=dense,dense_source_rules=select(dense),native_structure=structure,native_complexity_status=status,native_rules=rules,source_content_visibility=occlusion,approved_for_strict_main=approve,direct_native_PNG_visual_inspection=True,visual_value_status='approved_complex_research_comparison'if approve else'hold_source_content_completeness',visual_note='Actual PNG: complete two-panel DA/DG/SSL versus few-shot learning comparison with source/target domains, labelled/unlabelled data, meta-train/meta-test and prediction/update paths.'if visually_approved else'Actual PNG: detailed inferred/blueprint parameters, cross-validation, ensembling and prediction pipeline. Central fingerprints label is partly obscured by source chart boxes; retain outside strict main despite all eight converter checks passing.'))
  finally:context.close();browser.close()
 pairs=output/'reviewed_pairs.jsonl';pairs.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in rows));occ=output/'source_text_occlusion_reviews.jsonl';occ.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in occlusions));summary=dict(root=str(output),pairs=asset(pairs),occlusion=asset(occ),reviewed=len(rows),approved_ids=[r['id']for r in rows if r['approved_for_strict_main']],held_ids=[r['id']for r in rows if not r['approved_for_strict_main']],source_occlusion=[dict(id=r['id'],labels=[dict(text=x['text'],covered_graphemes=x['covered_graphemes'])for x in r['labels']])for r in occlusions],new_normal_calls=0,new_QA_calls=0,main_pointer_changed=False);(output/'summary.json').write_text(json.dumps(summary,indent=2))
 for p in output.iterdir():p.chmod(0o444)
 print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
