"""Actual PNG value review plus immutable native-glyph layout evidence."""
from pathlib import Path
import hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
INPUT=R/'clean/complexity_curation_20261102T054553Z_v1/value_reviews/background_fixed_C_434ab16be69a4616a93d33262ff6f5de'
NOTES=[
 ('3dad888e4d4b',False,'Hold source layout: ESN/attractor/excitable-connection workflow has an overcrowded effective-FNA caption and graph at the large arrow; actual full PNG is not suitable for the strict main.'),
 ('53971523afc9',False,'Hold incomplete source layout: AGN emission-line/stellar-kinematics labels stack over one another while multiple process boxes are blank. Actual paired glyphs confirm thirteen overlapping label pairs.'),
 ('159fd1abaf2d',True,'Complete NVFlare training/fine-tuning system pipeline, provisioning, secure server/client communication and parameter aggregation/distribution loop.'),
 ('b30f4138e734',False,'Deprioritize generic layer graph: mainly repeated Conv/Dense/Concatenate layer names and dimensions, with limited research-specific explanation.'),
 ('f1b59b4f1146',True,'Complete model overview with direct DeBERTa/LLM classification, pseudo-gold processing and multiple ensemble strategies across three panels.'),
 ('92ffcab5ce5c',True,'Complete document-analysis system: heterogeneous loaders, conversion/font repair, layout analysis, table/figure/OCR elements and reading-order/relation/hierarchy reconstruction.'),
]
def asset(p):return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
def main():
 from native_text_layout_review_v1 import inspect,controls
 summary=json.loads((INPUT/'summary.json').read_bytes())
 for ref in [summary['pairs'],summary['occlusion']]:assert asset(R/ref['file'])==ref
 rows=[json.loads(x)for x in(INPUT/'reviewed_pairs.jsonl').read_text().splitlines()];assert len(rows)==len(NOTES)==6
 layouts=[]
 for row,(prefix,approved,note)in zip(rows,NOTES):
  assert row['id'].startswith(prefix)and row['full_eight_quality_reverified']
  qa=R/row['quality_report']['file'];assert asset(qa)==row['quality_report'];report=json.loads(qa.read_bytes());info=qa.parent/'native_render.json'
  layout=dict(id=row['id'],native_render=asset(info),**inspect(json.loads(info.read_bytes()),report['checks']['render']['canvas']));layouts.append(layout)
  assert not approved or(not layout['needs_content_review']and not row['source_content_visibility']['labels'])
  row.update(paired_native_text_layout=layout,approved_for_strict_main=approved,direct_native_PNG_visual_inspection=True,
   visual_value_status='approved_complete_complex_research_content'if approved else'hold_source_value_or_layout',visual_note='Actual native PNG inspected: '+note)
 output=INPUT.parent/('unseen27_actual_PNG_'+uuid.uuid4().hex);output.mkdir();pairs=output/'reviewed_pairs.jsonl';pairs.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in rows));native=output/'paired_native_layout_reviews.jsonl';native.write_text(''.join(json.dumps(r,sort_keys=True)+'\n'for r in layouts))
 result=dict(root=str(output),pairs=asset(pairs),occlusion=summary['occlusion'],paired_native_layout=asset(native),
  approved_ids=[r['id']for r in rows if r['approved_for_strict_main']],held_ids=[r['id']for r in rows if not r['approved_for_strict_main']],
  actual_native_PNG_inspected_ids=[r['id']for r in rows],layout_observer_controls=controls(),technical_qualifications_unchanged=True,
  new_normal_calls=0,new_QA_calls=0,model_calls=0,main_pointer_changed=False)
 (output/'summary.json').write_text(json.dumps(result,indent=2))
 for p in output.iterdir():p.chmod(0o444)
 print(json.dumps(result),flush=True)
if __name__=='__main__':main()
