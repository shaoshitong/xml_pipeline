"""Finite once-safe dispatch check, sealed metadata reuse, B/C and gated mass."""
from pathlib import Path
import argparse,json,sys,time,traceback
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);a=p.parse_args();work=a.work;assert work.resolve().is_relative_to(R/'conversion/symbol_validation_launch_v1')
 def state(stage,**kw):(work/'state.json').write_text(json.dumps(dict(stage=stage,goal_complete=False,**kw),indent=2))
 try:
  import svg_analytic_iteration_chain_v5 as chain
  import derive_symbol_complex_source_pool_v1 as source
  import svg_analytic_iteration_program_v4 as program
  t=time.monotonic();state('real_once_safe_runtime_dispatch_preflight');proof=chain.preflight();(work/'runtime_controls.json').write_text(json.dumps(proof));state('reuse_complex_source_metadata',preflight_seconds=time.monotonic()-t)
  pool=source.prepare();(work/'pool.json').write_text(json.dumps(pool));state('reserve_fresh_unseen_families',pool=pool)
  prepared=program.prepare(Path(pool['pool']),pool['run_id']);(work/'prepared.json').write_text(json.dumps(prepared));launch=program.launch(Path(prepared['program_dir']),12,900);(work/'program_launch.json').write_text(json.dumps(launch));state('fixed_validation_then_gated_mass_running',program=launch,validation_samples=pool['selected'],total_setup_seconds=time.monotonic()-t);print(json.dumps(dict(pool=pool,program=launch)),flush=True)
 except BaseException as e:
  state('requires_repair',reason=str(e),traceback=traceback.format_exc());raise
if __name__=='__main__':main()
