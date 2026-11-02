"""Finite runtime-control completion -> atomic unseen validation -> gated mass."""
from pathlib import Path
import argparse,hashlib,json,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def main():
    p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--runtime-launch',type=Path,required=True);p.add_argument('--pool',type=Path,required=True);p.add_argument('--run-id',required=True);a=p.parse_args()
    work=a.work.resolve();assert work.is_relative_to(R/'conversion/compound_linear_validation_launch_v1')
    work.mkdir(parents=True,exist_ok=False);h=json.loads(a.runtime_launch.read_bytes())
    def state(**value):
        tmp=work/'state.tmp';tmp.write_text(json.dumps(dict(goal_complete=False,**value),indent=2));tmp.replace(work/'state.json')
    proof=R/'release/compiler_iterations/controls/svg_compound_linear_runtime_controls_20261102_v1/proof.json'
    try:
        state(stage='waiting_birth_verified_runtime_preflight',runtime=h)
        started=time.monotonic()
        while not proof.exists():
            stat=Path('/proc',str(h['pid']),'stat')
            live=stat.exists()and stat.read_text().rsplit(') ',1)[1].split()[19]==h['birth_ticks']
            if not live:raise RuntimeError('Runtime preflight is terminal without a proof: '+(Path(h['parent'])/'output.log').read_text()[-1800:])
            if time.monotonic()-started>900:raise RuntimeError('Runtime observation bound reached while the original process remains live; do not restart it.')
            time.sleep(2)
        import svg_analytic_iteration_program_v7 as program
        program.runtime_controls();state(stage='prepare_atomic_fresh_unseen_cohort',pool=str(a.pool))
        ready=program.prepare(a.pool,a.run_id);(work/'prepared.json').write_text(json.dumps(ready,indent=2))
        state(stage='launch_fixed_validation_then_gated_mass',prepared=ready)
        launch=program.launch(Path(ready['program_dir']),12,900);(work/'program_launch.json').write_text(json.dumps(launch,indent=2))
        state(stage='fixed_validation_then_gated_mass_launched',program=launch)
        print(json.dumps(dict(prepared=ready,program=launch,model_calls=0,goal_complete=False)))
    except BaseException as error:
        state(stage='requires_repair',reason=str(error),exception=type(error).__name__);raise
if __name__=='__main__':main()
