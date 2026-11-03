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
 from native_text_layout_review_v1 import inspect as inspect_native_layout
 from playwright.sync_api import sync_playwright
 from PIL import Image
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['C','mass'],required=True);parser.add_argument('--limit',type=int,default=8);args=parser.parse_args();assert 1<=args.limit<=64;run=R/('release/compiler_iterations/runs/svg_complex_source_whitespace_cached_unseen_20261103_v12_'+args.phase)
 with sqlite3.connect((run/'status.sqlite').as_uri()+'?mode=ro',uri=True)as d:results=[dict(json.loads(r[0]),kind='v24')for r in d.execute("select result from samples where status='qualified' order by seq")]
 ledger_root=R/'clean/complexity_curation_20261102T054553Z_v1/value_review_registry_v1';ledger_root.mkdir(exist_ok=True);ledger=sqlite3.connect(ledger_root/'status.sqlite');ledger.execute('create table if not exists reviews(id text,code_sha256 text,image_sha256 text,review_root text,status text,primary key(id,code_sha256,image_sha256))')
 pointer=json.loads((R/'clean/complexity_curation_20261102T054553Z_v1/current.json').read_bytes());main_ids={json.loads(x)['id']for x in(R/pointer['views']['paired_priority_complex']['file']).read_text().splitlines()};seen=set(ledger.execute('select id,code_sha256,image_sha256 from reviews'))
 results=[r for r in results if r['id']not in main_ids and(r['id'],r['manifest']['code_sha256'],r['manifest']['image_sha256'])not in seen][:args.limit]
 if not results:print(json.dumps(dict(reviewed=0,already_staged_or_published=True)));ledger.close();return
 output=R/'clean/complexity_curation_20261102T054553Z_v1/value_reviews'/('background_incremental_'+args.phase+'_' +uuid.uuid4().hex);output.mkdir(parents=True);rows=[];occlusions=[]
 with sync_playwright()as p:
  browser=p.chromium.launch(executable_path='/home/shaoshitong/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome',args=['--disable-dev-shm-usage','--disable-gpu']);context=browser.new_context(viewport=dict(width=1200,height=750),device_scale_factor=1,java_script_enabled=False,service_workers='block');context.route('**/*',lambda route:route.abort());page=context.new_page()
  try:
   for result in results:
    pair=result['manifest']
    for field,digest in [('code_file','code_sha256'),('image_file','image_sha256'),('metadata_file','metadata_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256')]:assert sha((R/pair[field]).read_bytes())==pair[digest]
    record=json.loads((R/pair['metadata_file']).read_bytes());qa=Path(result['quality_report']);qa=qa if qa.is_absolute()else R/qa;report=json.loads(qa.read_bytes())
    import compiler_svg_general_guard_v20 as core
    import svg_source_whitespace_quality_contract_v1 as verifier
    verifier.full_quality(report,record,core.configuration(),asset(qa.parent/'native_render.json'));native_layout=dict(native_render=asset(qa.parent/'native_render.json'),**inspect_native_layout(json.loads((qa.parent/'native_render.json').read_bytes()),report['checks']['render']['canvas']))
    source=(R/pair['original_source_code']).read_bytes();size=Image.open(io.BytesIO((R/pair['original_reference']).read_bytes())).size;page.set_viewport_size(dict(width=size[0],height=size[1]));occlusion=inspect(page,source.decode('utf-8-sig'),size);occlusions.append(dict(id=pair['id'],source_sha256=pair['source_code_sha256'],**occlusion))
    dense=features(source);structure=native((R/pair['code_file']).read_text());status,rules=classify(structure,'drawio',{})
    rows.append(dict(id=pair['id'],pair=pair,full_eight_quality_reverified=True,quality_report=asset(qa),dense_source_features=dense,dense_source_rules=select(dense),native_structure=structure,native_complexity_status=status,native_rules=rules,source_content_visibility=occlusion,paired_native_text_layout=native_layout,approved_for_strict_main=False,direct_native_PNG_visual_inspection=False,visual_value_status='await_actual_PNG_value_review',visual_note='Pending actual native PNG scientific content inspection.'))
  finally:context.close();browser.close()
 pairs=output/'reviewed_pairs.jsonl';pairs.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in rows));occ=output/'source_text_occlusion_reviews.jsonl';occ.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in occlusions));summary=dict(source_run=str(run),source_phase=args.phase,source_generation_core='190048fb8bc0e6eee862b0e0f43b55cda78c9820355151c76e8000e0657fd774',source_and_actual_paired_native_layout_review=True,candidate_qualification_unchanged=True,root=str(output),pairs=asset(pairs),occlusion=asset(occ),reviewed=len(rows),approved_ids=[r['id']for r in rows if r['approved_for_strict_main']],held_ids=[r['id']for r in rows if not r['approved_for_strict_main']],source_occlusion=[dict(id=r['id'],labels=[dict(text=x['text'],covered_graphemes=x['covered_graphemes'])for x in r['labels']])for r in occlusions],new_normal_calls=0,new_QA_calls=0,main_pointer_changed=False);(output/'summary.json').write_text(json.dumps(summary,indent=2))
 for p in output.iterdir():p.chmod(0o444)
 for row in rows:ledger.execute('insert into reviews values(?,?,?,?,?)',(row['id'],row['pair']['code_sha256'],row['pair']['image_sha256'],str(output),'await_actual_PNG_review'))
 ledger.commit();ledger.close();print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
