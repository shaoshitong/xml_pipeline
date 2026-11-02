"""Finite metadata retarget, fresh anti-leakage reservation and fixed dispatch."""
from pathlib import Path
import argparse,json,sys
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);args=parser.parse_args();work=args.work.resolve();assert work.is_relative_to(R/'conversion/complex_target_queue_launch_v1')
    def state(value):(work/'state.json').write_text(json.dumps(value))
    try:
        import derive_complex_source_pool_v1 as source
        import svg_analytic_iteration_program_v3 as program
        state(dict(stage='reuse_full_scope_audit_filter_complex_sources',goal_complete=False));pool=source.prepare();(work/'pool.json').write_text(json.dumps(pool));state(dict(stage='reserve_independent_complex_source_families',pool=pool,goal_complete=False))
        ready=program.prepare(Path(pool['pool']),pool['run_id']);(work/'prepared.json').write_text(json.dumps(ready));receipt=program.launch(Path(ready['program_dir']),12,900);(work/'program_launch.json').write_text(json.dumps(receipt));state(dict(stage='complex_source_validation_then_gated_mass_launched',program=receipt,scope=pool['policy'],goal_complete=False));print(json.dumps(dict(pool=pool,prepared=ready,program=receipt)),flush=True)
    except BaseException as error:
        state(dict(stage='retarget_requires_repair',reason=str(error),goal_complete=False));raise

if __name__=='__main__':main()
