"""Preserve five real development normals across three immutable source cores."""
from pathlib import Path
import hashlib
import json
import sys
import uuid

R=Path('/backup/shaoshitong/img2code_20261029')
sys.path.insert(0,str(R/'conversion/scripts'))
PARENTS=[
 'compiler_svg_scene_frontend_v16/normal_development_v1/07b98ad7a60d4d3ea4349ff9c485cb70',
 'compiler_svg_scene_frontend_v16/normal_development_v1/87ba4b263d7d4cc695a11612455f09c4',
 'compiler_svg_scene_frontend_v17/normal_development_v1/56a5ff51a1a5486ca6403bbd83360674',
 'compiler_svg_scene_frontend_v18/normal_development_v1/7005595f162b4de697c00e3e1cf95c02',
 'compiler_svg_scene_frontend_v18/normal_development_v1/f847142b9e954f1a9eb941e9c42639e6',
]


def asset(p):
    b=p.read_bytes()
    return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(b).hexdigest())


def main():
    parent=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_edge_layers_untouched_use_20261102_v8.json'
    original=parent.read_bytes();document=json.loads(original)
    output=R/'conversion/source_core_manual_background_catalog_v1'/uuid.uuid4().hex
    output.mkdir(parents=True)
    rows=[];frontends=[]
    for relative in PARENTS:
        p=R/'conversion'/relative
        paths=list(p.glob('*/summary.json'))
        assert len(paths)==1
        row=json.loads(paths[0].read_bytes())
        assert row['normal_frontend_calls']==1 and row['canonical_unchanged']
        assert row['source']['pair_sha256']==row['id']
        rows.append(row);frontends.append(asset(paths[0].parent/'frontend_result.json'))
    receipt=output/'normal_receipts.json'
    receipt.write_text(json.dumps(dict(results=rows,source_summary_files=[str((R/'conversion'/p))for p in PARENTS]),indent=2))
    declarations=[]
    for index,(row,frontend)in enumerate(zip(rows,frontends)):
        declarations.append(dict(id=row['id'],source_core_key=row['source_core']['key'],
            receipt=asset(receipt),rows_key='results',row_index=index,
            normal_count_key='normal_frontend_calls',requires_unchanged_canonical=True,
            frontend=frontend,source=row['source']))
    target=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_background_rotation_20261102_v9.json'
    assert not target.exists()
    result={**document,'entries':document['entries']+declarations,
            'preserved_parent':asset(parent),'producer':asset(Path(__file__)),
            'QA_only_reviews_are_not_extra_normals':True}
    target.write_text(json.dumps(result,indent=2))
    for p in [receipt,target]:p.chmod(0o444)
    assert parent.read_bytes()==original
    from compiler_source_core_attempts_v3 import collect,validate,guard
    import compiler_svg_general_guard_v14 as core
    config=core.configuration();events=collect(config,root=R,catalog=str(target.relative_to(R)))
    validate(events,config,root=R)
    assert {e['id']for e in events}=={rows[-1]['id'],rows[-2]['id']}
    for row in rows[-2:]:
        assert guard(row['id'],row['source'],config,root=R,catalog=str(target.relative_to(R)))['already_attempted']
    proof=dict(catalog=asset(target),normal_receipts=asset(receipt),
               preserved_new_normals=len(rows),current_core_preserved_normals=len(events),
               all_current_core_reexecution_blocked=True,old_catalog_unchanged=True,
               normal_calls=0,QA_calls=0,model_calls=0)
    (output/'proof.json').write_text(json.dumps(proof,indent=2))
    print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
