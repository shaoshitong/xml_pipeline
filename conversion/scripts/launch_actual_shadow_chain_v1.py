"""Finite actual dispatch preflight followed by the immutable full-scope chain."""
from pathlib import Path
import argparse,json,os,subprocess,sys

R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts'
sys.path.insert(0,str(S))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);args=parser.parse_args();work=args.work.resolve()
    assert work.is_relative_to(R/'conversion/svg_actual_shadow_chain_launcher_v1')
    def state(value):(work/'state.json').write_text(json.dumps(value))
    state(dict(stage='actual_once_safe_runtime_preflight',goal_complete=False))
    with(work/'preflight.log').open('xb')as log:
        result=subprocess.run([sys.executable,'-B',str(S/'svg_analytic_iteration_chain_v4.py'),'preflight'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'})
    if result.returncode:
        state(dict(stage='preflight_failed_requires_repair',exit=result.returncode,goal_complete=False));raise SystemExit(result.returncode)
    state(dict(stage='preflight_passed_launching_fixed_chain',goal_complete=False))
    import svg_analytic_iteration_chain_v4 as chain
    receipt=chain.launch();(work/'chain_launch.json').write_text(json.dumps(receipt));state(dict(stage='fixed_full_scope_source_audit_launched',chain=receipt,goal_complete=False));print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
