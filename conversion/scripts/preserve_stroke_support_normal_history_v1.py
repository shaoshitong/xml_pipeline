"""Conservatively preserve the consumed invocation, including its owner failure."""
from pathlib import Path
import hashlib,json,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');sys.path.insert(0,str(R/'conversion/scripts'))
def asset(p):return dict(file=str(p.relative_to(R)),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 parent=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_background_rotation_20261102_v9.json';original=parent.read_bytes();document=json.loads(original)
 work=R/'conversion/background_stroke_support_normal_development_v1/a0ab875affa74dbab2ccee65fc242e3c/e99263f5c4b6270d48ae6892ef8440c3f3bb6a6280f13094d188f4327b5d6c84'
 row=json.loads((work/'summary.json').read_bytes());frontend=json.loads((work/'frontend_result.json').read_bytes())
 assert row['normal_frontend_calls']==1 and row['canonical_unchanged'] and frontend['reason']=='compiler_work_outside_owner'
 assert not(work/'compiler').exists(),'owner rejection unexpectedly emitted work'
 output=R/'conversion/source_core_manual_stroke_support_catalog_v1'/uuid.uuid4().hex;output.mkdir(parents=True)
 receipt=output/'normal_receipts.json';receipt.write_text(json.dumps(dict(results=[row],source_summary=asset(work/'summary.json'),owner_rejected_before_source_preparation=True,nevertheless_block_reexecution=True),indent=2))
 declaration=dict(id=row['id'],source_core_key=row['source_core']['key'],receipt=asset(receipt),rows_key='results',row_index=0,normal_count_key='normal_frontend_calls',requires_unchanged_canonical=True,frontend=asset(work/'frontend_result.json'),source=row['source'])
 target=R/'release/compiler_iterations/source_core_attempts/manual_catalog_svg_background_stroke_support_20261102_v10.json';assert not target.exists()
 target.write_text(json.dumps({**document,'entries':document['entries']+[declaration],'preserved_parent':asset(parent),'producer':asset(Path(__file__))},indent=2))
 for p in [target,receipt]:p.chmod(0o444)
 from compiler_source_core_attempts_v3 import collect,validate,guard
 import compiler_svg_general_guard_v15 as core
 config=core.configuration();events=collect(config,root=R,catalog=str(target.relative_to(R)));validate(events,config,root=R)
 assert len(events)==1 and events[0]['id']==row['id'];assert guard(row['id'],row['source'],config,root=R,catalog=str(target.relative_to(R)))['already_attempted'];assert parent.read_bytes()==original
 result=dict(catalog=asset(target),normal_receipts=asset(receipt),current_core_preserved_invocations=1,owner_rejected_before_source_preparation=True,source_or_native_candidate_emissions=0,all_current_core_reexecution_blocked=True,old_catalog_unchanged=True,new_normal_calls=0,QA_calls=0,model_calls=0)
 (output/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
