"""Finite dispatch proof, source admission, unseen validation and gated mass handoff."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def sha(b):return hashlib.sha256(b).hexdigest()
def put(p,v):
    q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(v,indent=2)+'\n');os.replace(q,p)
def check_owner(h):
    p=Path('/proc',str(h['pid']),'stat')
    if not p.exists():return False
    f=p.read_text().rsplit(') ',1)[1].split();return f[0]!='Z'and f[19]==str(h['birth_ticks'])
def execute(root):
    plan=json.loads((root/'plan.json').read_text());put(root/'owner.json',dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]));started=time.monotonic()
    try:
        for name,digest in plan['pins'].items():assert sha(Path(name).read_bytes())==digest
        import svg_whitespace_iteration_chain_v1 as runtime
        import svg_whitespace_iteration_program_v1 as program
        import derive_svg_whitespace_source_pool_v1 as pool
        put(root/'state.json',dict(stage='real_once_safe_runtime_preflight',normal_conversion_calls=0,goal_complete=False));proof=runtime.preflight();put(root/'runtime_proof.json',proof)
        admission=plan['admission']
        while True:
            summary=json.loads((Path(admission['root'])/'summary.json').read_text())
            put(root/'state.json',dict(stage='waiting_existing_source_admission',source_summary=summary,goal_complete=False))
            if summary['finished']:break
            if not check_owner(admission):raise RuntimeError('existing_source_admission_ended_without_terminal_summary')
            if time.monotonic()-started>3600:raise RuntimeError('finite_source_admission_wait_exhausted_preserve_handle')
            time.sleep(10)
        for name,digest in plan['pins'].items():assert sha(Path(name).read_bytes())==digest
        put(root/'state.json',dict(stage='seal_complete_source_population_and_fresh_families',goal_complete=False));scope=pool.prepare(admission['root']);put(root/'source_pool.json',scope)
        if not scope['selected']:
            put(root/'state.json',dict(stage='no_remaining_unseen_family_in_retained_scope',source_pool=scope,requires_source_family_scope_repair=True,goal_complete=False));return
        prepared=program.prepare(Path(scope['pool']),scope['run_id']);put(root/'prepared.json',prepared)
        launch=program.launch(Path(prepared['program_dir']),12,900);put(root/'program_launch.json',launch)
        put(root/'state.json',dict(stage='fixed_unseen_validation_then_gated_whole_population_launched',program=launch,source_pool=scope,foreign_live_overlap_preserved_until_completion=True,goal_complete=False))
    except BaseException as error:
        put(root/'failure.json',dict(reason=str(error),type=type(error).__name__,goal_complete=False));put(root/'state.json',dict(stage='requires_repair',reason=str(error),goal_complete=False));raise
def launch():
    screen=R/'clean/priority_svg_flat_source_screen_v1/da55c2ca71a24d7ab63d36c571ca963c';admission=json.loads((screen/'source_admission_launch_v1.json').read_text())
    import svg_whitespace_iteration_program_v1 as program
    import svg_whitespace_source_contract_v1 as contract
    program.check_controls(program.control_bundle(contract))
    receipt=screen/'whitespace_validation_chain_launch_v1.json';assert not receipt.exists(),'Observe existing chain, never restart'
    names=['svg_whitespace_source_contract_v1.py','svg_whitespace_cohort_refresh_v1.py','svg_whitespace_iteration_pool_v1.py','svg_whitespace_iteration_chain_v1.py','svg_whitespace_iteration_controls_v1.py','svg_whitespace_iteration_program_v1.py','svg_whitespace_iteration_batch_v1.py','svg_whitespace_iteration_case_v1.py','derive_svg_whitespace_source_pool_v1.py',Path(__file__).name]
    pins={}
    for name in names:
        p=S/name;p.chmod(0o444);pins[str(p)]=sha(p.read_bytes())
    root=R/'conversion/svg_whitespace_validation_chain_v1'/uuid.uuid4().hex;root.mkdir(parents=True);plan=dict(admission=admission,pins=pins,workers=12,case_timeout_seconds=900,gate=dict(minimum_fraction=.2,minimum_new_qualified=5,maximum_regressions=0,maximum_infrastructure_failures=0),normal_attempts_per_original_per_core=1,model_calls=0,goal_complete=False);put(root/'plan.json',plan);(root/'plan.json').chmod(0o444)
    with(root/'output.log').open('wb')as log:process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'execute',str(root)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
    birth=Path('/proc',str(process.pid),'stat').read_text().rsplit(') ',1)[1].split()[19];out=dict(root=str(root),pid=process.pid,birth_ticks=birth,finite=True,source_admission=admission,goal_complete=False);put(root/'launch.json',out);put(receipt,out);receipt.chmod(0o444);return out
if __name__=='__main__':print(json.dumps(launch()if len(sys.argv)==1 else execute(Path(sys.argv[2]))))
