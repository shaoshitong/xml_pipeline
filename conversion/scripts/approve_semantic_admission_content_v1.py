"""Persist actual PNG inspection; preserve all technical qualifications."""
from pathlib import Path
import hashlib
import json
import uuid

R=Path('/backup/shaoshitong/img2code_20261029')
C=R/'clean/complexity_curation_20261102T054553Z_v1'
INPUT=C/'value_reviews/semantic_admission_round_5da6d1a3ec994b68ad271cf01e4f2905'
NOTES=[
    (True,'Complete graph-library tool/function management and LLM execution/return workflow with JSON calls and chain-of-thought output panels.'),
    (True,'Complete three-panel causal-cloze bidirectional transformer, transformer block and context-flow architecture.'),
    (True,'Complete convolutional encoder/decoder architecture with layer operations, skip connections and output path.'),
    (False,'Hold source content visibility: DICT2H label is covered in the source memory/IO training pipeline; source hit-stack flags six graphemes.'),
    (True,'Complete feature generation and preprocessing workflow with original/transformed tables and downstream random-forest metric comparison.'),
    (False,'Hold source layout: PTDA original/augmented image legend crosses the lower training-grid boxes; actual full-size PNG confirms overlap.'),
    (True,'Complete sparse GEMM tile diagram: weights/input, bitmap representation, PE state and ten annotated computation steps.'),
    (True,'Complete convolutional feature encoder with bidirectional recurrent context processor and distinct lower/upper-bound decoder heads.'),
    (True,'Complete LLM hardware configuration, task/thread/weight/cache pipeline and CPU/DRAM/GPU/VRAM hardware dataflow.'),
    (True,'Complete three-panel accelerator kernel fusion, stream dataflow and scheduled-module comparison.'),
    (True,'Complete cluster resource allocation, worker placement, inference migration and per-worker GPU/parameter-prefetch architecture.'),
    (False,'Deprioritize simple repetitive source: long sequential layer/shape summary; repeated boxes do not establish a complex research diagram.'),
    (True,'Complete agency-theory and LLM-alignment conceptual workflow, including signaling/screening branches and research notes.'),
    (True,'Complete MapReduce/SNARK proof pipeline with input blocks, mapped keys, shuffle/sort, reduce and final client verification.'),
]


def asset(p):
    data=p.read_bytes()
    return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))


def main():
    summary=json.loads((INPUT/'summary.json').read_bytes())
    for ref in (summary['pairs'],summary['occlusion']):
        assert asset(R/ref['file'])==ref
    rows=[json.loads(line)for line in(INPUT/'reviewed_pairs.jsonl').read_text().splitlines()]
    assert len(rows)==len(NOTES)==14
    for row,(approved,note)in zip(rows,NOTES):
        assert row['full_eight_quality_reverified']
        assert not approved or row['source_content_visibility']['potential_occluded_labels']==0
        row.update(approved_for_strict_main=approved,direct_native_PNG_visual_inspection=True,
                   visual_value_status='approved_complete_complex_research_content'if approved else'hold_source_value_or_layout',
                   visual_note='Actual native PNG inspected: '+note)
    output=C/'value_reviews'/('semantic_admission_actual_PNG_'+uuid.uuid4().hex)
    output.mkdir()
    pairs=output/'reviewed_pairs.jsonl'
    pairs.write_text(''.join(json.dumps(row,sort_keys=True)+'\n'for row in rows))
    result=dict(root=str(output),pairs=asset(pairs),occlusion=summary['occlusion'],
                actual_native_PNG_inspected_ids=[r['id']for r in rows],
                approved_ids=[r['id']for r in rows if r['approved_for_strict_main']],
                held_ids=[r['id']for r in rows if not r['approved_for_strict_main']],
                technical_qualifications_unchanged=True,new_normal_calls=0,new_QA_calls=0,
                model_calls=0,main_pointer_changed=False,input_summary=asset(INPUT/'summary.json'))
    (output/'summary.json').write_text(json.dumps(result,indent=2))
    for p in output.iterdir():p.chmod(0o444)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
