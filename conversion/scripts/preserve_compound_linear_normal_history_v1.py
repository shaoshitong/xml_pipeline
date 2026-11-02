"""Preserve the completed normal and verify that its exact source/core is consumed."""
from pathlib import Path
import hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def asset(p):return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
    work=Path(sys.argv[1]).resolve();assert work.is_relative_to(R/'conversion/compiler_svg_scene_frontend_v21')
    row=json.loads((work/'summary.json').read_bytes());assert row['normal_frontend_calls']==1 and row['canonical_unchanged']
    parent=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_outline_crossing_20261102_v11.json';original=parent.read_bytes();document=json.loads(original)
    root=R/'conversion/source_core_manual_compound_linear_catalog_v1'/uuid.uuid4().hex;root.mkdir(parents=True)
    receipt=root/'normal_receipts.json';receipt.write_text(json.dumps(dict(results=[row],source_summary=asset(work/'summary.json')),indent=2));receipt.chmod(0o444)
    declaration=dict(id=row['id'],source_core_key=row['source_core']['key'],receipt=asset(receipt),rows_key='results',row_index=0,normal_count_key='normal_frontend_calls',requires_unchanged_canonical=True,frontend=asset(work/'frontend_result.json'),source=row['source'])
    target=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_compound_linear_20261102_v12.json';assert not target.exists()
    target.write_text(json.dumps({**document,'entries':document['entries']+[declaration],'preserved_parent':asset(parent),'producer':asset(Path(__file__))},indent=2));target.chmod(0o444)
    import compiler_svg_general_guard_v17 as core
    from compiler_source_core_attempts_v3 import collect,validate,guard
    config=core.configuration();events=collect(config,root=R,catalog=str(target.relative_to(R)));validate(events,config,root=R)
    assert len(events)==1 and events[0]['id']==row['id']
    assert guard(row['id'],row['source'],config,root=R,catalog=str(target.relative_to(R)))['already_attempted']
    assert parent.read_bytes()==original
    result=dict(catalog=asset(target),normal_receipts=asset(receipt),preserved_normal_count=1,same_source_core_reexecution_blocked=True,parent_catalog_unchanged=True,new_normal_calls=0,QA_calls=0,model_calls=0)
    (root/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
