"""Run the already-approved core on disjoint pending sources without waiting.

The unchanged parent program still retains the entire source population and
waits for foreign pending work, including this independently named batch. Its
later mass pass excludes every source-core attempt recorded here. No active
implementation, release gate, canonical job or original source is rewritten.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys,uuid
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
NAME='svg_source_whitespace_disjoint_20261103_v2_mass'
P=R/'release/compiler_iterations/programs/svg_complex_source_whitespace_cached_unseen_20261103_v12'
ROOT=R/'release/compiler_iterations/disjoint_batches'/NAME
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(v):return(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
def put(p,v):
    q=p.with_name(p.name+'.tmp');q.write_bytes(raw(v));os.replace(q,p)
def execute(root):
    import svg_whitespace_iteration_program_v1 as program
    plan=json.loads((root/'plan.json').read_text());assert sha(Path(__file__).read_bytes())==plan['producer_sha256']
    put(root/'owner.json',dict(pid=os.getpid(),birth_ticks=Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]))
    put(root/'state.json',dict(stage='approved_disjoint_mass',goal_complete=False))
    try:
        outcomes=program.run_phase(Path(plan['run']),plan['workers'],900,root)
        put(root/'summary.json',dict(finished=True,targets=len(outcomes),qualified=sum(r['status']=='qualified'for r in outcomes.values()),infrastructure_errors=sum(r.get('infrastructure_failure')is True for r in outcomes.values()),normal_attempts_per_source_core=1,goal_complete=False))
        put(root/'state.json',dict(stage='disjoint_mass_finished_parent_catchup_retained',goal_complete=False))
    except BaseException as e:put(root/'failure.json',dict(reason=str(e),type=type(e).__name__,goal_complete=False));raise
def launch():
    import svg_whitespace_iteration_program_v1 as program
    import svg_whitespace_iteration_batch_v1 as controller
    import svg_whitespace_iteration_pool_v1 as sourcepool
    import svg_whitespace_source_contract_v1 as contract
    import compiler_source_core_attempts_v3 as history
    from compiler_mermaid_alpha_iteration_overlap_v2 import snapshot
    assert not ROOT.exists()and not(controller.FLOOR/NAME).exists(),'Observe existing batch; never duplicate or restart it'
    freeze=json.loads((P/'implementation.json').read_text());gate=json.loads((P/'release_gate.json').read_text());unit=contract.UNIT
    program.verify_release_gate(P/'release_gate.json',freeze,[unit]);controller.check_pins(freeze['pins'])
    selected={r['id']for r in program.readrows(P/'selected.jsonl')};population=program.readrows(P/'supported_population.jsonl')
    protected=program.preserved_qualified(P);protected.update(sourcepool.fresh_qualified(contract.configuration()))
    events=history.collect(contract.configuration(),root=R,catalog=contract.CATALOG);history.validate(events,contract.configuration(),root=R);consumed={r['id']for r in events}
    observed=snapshot(ignore_runs=(P.name,));active=set(observed['active'])
    requests=[r for r in population if r['id']not in selected|set(protected)|consumed|active and r['compiler_unit']in gate['approved_units']]
    assert requests,'No disjoint original remains; keep observing the parent program'
    program.validate_source_requests(requests)
    ROOT.mkdir(parents=True,exist_ok=False)
    for i,r in enumerate(requests,1):r['seq']=i
    payload=b''.join(program.raw(r)for r in requests);manifest=ROOT/'input.jsonl';manifest.write_bytes(payload);manifest.chmod(0o444)
    (ROOT/'live_overlap_snapshot.json').write_bytes(raw(observed));(ROOT/'source_core_history_before.jsonl').write_bytes(b''.join(program.raw(r)for r in events))
    # Preserve the exact approved implementation identity; only input and gate
    # references vary, as in the validated standard whole-batch constructor.
    config={**freeze,'input_sha256':sha(payload),'release_gate':program.asset(P/'release_gate.json')};frozen=ROOT/'freeze.json';frozen.write_bytes(program.raw(config));frozen.chmod(0o444)
    run=controller.FLOOR/NAME;controller.create(run,manifest,frozen,'batch')
    plan=dict(run=str(run),targets=len(requests),workers=12,parent_program=str(P),approved_release_gate=program.asset(P/'release_gate.json'),producer_sha256=sha(Path(__file__).read_bytes()),full_parent_population_retained=len(population),excluded_live_overlap=len({r['id']for r in population}&active),same_source_core_attempts_preserved=len(consumed),all_selected_current_validation_preserved=True,source_generation_implementation_unchanged=True,goal_complete=False)
    put(ROOT/'plan.json',plan);(ROOT/'plan.json').chmod(0o444);Path(__file__).chmod(0o444)
    with(ROOT/'output.log').open('wb')as log:p=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'execute',str(ROOT)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'))
    birth=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()[19];receipt=dict(root=str(ROOT),run=str(run),pid=p.pid,birth_ticks=birth,targets=len(requests),workers=12,excluded_foreign_pending=plan['excluded_live_overlap'],parent_full_catchup_unchanged=True,source_core_implementation_unchanged=True,model_calls=0,goal_complete=False);put(ROOT/'launch.json',receipt);return receipt
if __name__=='__main__':print(json.dumps(launch()if len(sys.argv)==1 else execute(Path(sys.argv[2]))))
