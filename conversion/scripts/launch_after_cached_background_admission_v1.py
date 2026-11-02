"""Finite runtime test -> wait known source audit -> reserve -> validate -> mass."""
from pathlib import Path
import argparse,json,sys,time,traceback,os
R=Path('/backup/shaoshitong/img2code_20261029');S=R/'conversion/scripts';sys.path.insert(0,str(S))
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--audit',type=Path,required=True);a=p.parse_args();assert a.work.resolve().is_relative_to(R/'conversion/background_rotation_validation_launch_v1');audit=a.audit.resolve();assert audit.is_relative_to(R/'conversion/source_cached_admission_v1')
 def state(stage,**kw):(a.work/'state.json').write_text(json.dumps(dict(stage=stage,goal_complete=False,**kw),indent=2))
 try:
  import svg_analytic_iteration_chain_v7 as chain
  import derive_cached_semantic_source_pool_v2 as source
  import svg_analytic_iteration_program_v6 as program
  t=time.monotonic();state('real_once_safe_runtime_dispatch_preflight');proof=chain.preflight();(a.work/'runtime_controls.json').write_text(json.dumps(proof));state('waiting_for_existing_source_only_admission_audit',audit=str(audit),preflight_seconds=time.monotonic()-t)
  owner=json.loads((audit/'launch.json').read_bytes())
  while True:
   summary=json.loads((audit/'summary.json').read_bytes())
   if summary.get('finished')and summary.get('files'):break
   stat=Path('/proc',str(owner['pid']),'stat')
   try:live=stat.read_text().rsplit(') ',1)[1].split()[19]==str(owner['birth_ticks'])
   except FileNotFoundError:live=False
   if not live:
    final=json.loads((audit/'summary.json').read_bytes())
    if final.get('finished')and final.get('files'):break
    raise RuntimeError('source_admission_owner_missing_before_terminal_export_do_not_restart')
   time.sleep(5)
  state('freeze_source_only_eligibility_and_fresh_family_selection');pool=source.prepare(audit);(a.work/'pool.json').write_text(json.dumps(pool))
  if not pool['selected']:state('source_family_repair_required',reason=pool['reason']);return
  ready=program.prepare(Path(pool['pool']),pool['run_id']);(a.work/'prepared.json').write_text(json.dumps(ready));launch=program.launch(Path(ready['program_dir']),12,900);(a.work/'program_launch.json').write_text(json.dumps(launch));state('fixed_source_qualified_validation_then_gated_mass_launched',program=launch,selection=pool,setup_seconds=time.monotonic()-t);print(json.dumps(dict(program=launch,pool=pool)),flush=True)
 except BaseException as e:
  state('requires_repair',reason=str(e),traceback=traceback.format_exc());raise
if __name__=='__main__':main()
