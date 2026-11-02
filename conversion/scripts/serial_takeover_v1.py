"""Finite, reviewed takeover of this img2code dataset's legacy process families.

Default is read-only. --execute requests known drains, terminates undrainable
whole families, then performs bounded TERM/KILL cleanup of the captured births.
No SQLite/source/assets/history/claim/model-budget mutation is performed.
"""
import argparse, collections, datetime, hashlib, json, os
from pathlib import Path
import signal, time, uuid, re
try:
 from initial_conversion_process_v1 import pidfd_open,pidfd_send_signal
except ModuleNotFoundError:
 # Local control tests use the same unchanged implementation in this directory.
 from drawio_conversion.initial_conversion_process_v1 import pidfd_open,pidfd_send_signal

ROOT = Path('/backup/shaoshitong/img2code_20261029')
WORK = ROOT/'conversion'
ALLOWED = set('''mermaid_reference_fit_batch_v10.py svg_program_terminal_finite_cohort_v1.py
tikz_render_batch.py auto_quality_batch_v4b.py auto_quality_fastlane_v4b.py
auto_quality_inventory_watch.py tex_dependency_repair.py tex_dependency_repair_v2.py
svg_fullname_font_batch_v2.py initial_conversion_supervisor_v1b.py html_batch_v3.py
visual_failure_certificate_v1.py repair_nonhtml_canvas_font.py tikz_execution_candidate_batch_v1.py
text_batch.py auto_quality_html_repair_batch_v3.py tikz_execution_candidate_watch_v1.py
tex_xcolor_repair_batch.py native_canvas_font_batch.py tikz_binary_capture_repair.py
auto_quality_font_repair.py tikz_ligature_repair_v2.py tikz_rotation_repair.py
tikz_execution_parallel_supervisor_v1.py native_page_padding_batch.py
native_text_clip_batch_v4.py native_page_padding_capture_retry.py native_font_embedding_batch.py
plantuml_repair_batch.py tikz_drawio_batch.py nonhtml_canvas_font_batch.py
auto_quality_canvas_repair.py auto_quality_html_repair_batch_v2.py visual_failure_finite_v1.py
plantuml_repair_batch_v3.py source_vee_batch.py plantuml_alignment_batch.py
tikz_literal_binding_batch_v2.py mermaid_reference_fit_batch_v9.py
native_font_embedding_v3_batch.py auto_quality_glyph_alignment_batch_v3c.py
plantuml_style_repair.py native_font_embedding_v4_batch.py python_render_batch.py
python_drawio_batch.py python_drawio_durable.py svg_batch.py svg_batch_durable.py
svg_v3_repair_batch.py svg_v5_repair_batch.py mermaid_geometry_batch.py
native_worker.py initial_conversion_supervisor_v1.py html_batch.py html_batch_v2.py
native_font_embedding_v2_batch.py svg_fullname_font_batch.py'''.split())
DRAIN = {
 'auto_quality_batch_v4b.py': 'auto_quality_control.json',
 'initial_conversion_supervisor_v1b.py': 'initial_conversion_supervisor_v1b_control.json',
 'tikz_execution_candidate_watch_v1.py': 'tikz_execution_candidate_watch_v1_control.json',
 'tikz_execution_parallel_supervisor_v1.py': 'tikz_execution_parallel_supervisor_v1_control.json',
 'auto_quality_glyph_alignment_batch_v3c.py': 'auto_quality_glyph_alignment_v3c_control.json',
 'svg_program_terminal_finite_cohort_v1.py': 'svg_program_terminal_finite_cohort_v1_control.json',
}
USR1 = set(DRAIN)-{'svg_program_terminal_finite_cohort_v1.py'}

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(raw): return hashlib.sha256(raw).hexdigest()

def atomic(path, value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
 tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 with tmp.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 tmp.replace(path)
 fd=os.open(str(path.parent),os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)

def read_process(pid, proc=Path('/proc')):
 try:
  p=proc/str(pid);raw=(p/'stat').read_text();f=raw[raw.rindex(')')+2:].split()
  argv=[a.decode(errors='replace') for a in (p/'cmdline').read_bytes().split(b'\0') if a]
  return {'pid':int(pid),'ppid':int(f[1]),'birth':int(f[19]),'state':f[0],
          'uid':p.stat().st_uid,'argv':argv}
 except (OSError,ValueError,IndexError):return None

def processes(proc=Path('/proc')):
 return {int(p.name):x for p in proc.iterdir() if p.name.isdigit()
         for x in [read_process(int(p.name),proc)] if x}

def protected_ancestors(rows, own_pid):
 result={own_pid};current=rows.get(own_pid)
 while current and current['ppid'] not in result and current['ppid']>0:
  result.add(current['ppid']);current=rows.get(current['ppid'])
 return result

def script_name(row, root=ROOT):
 # Only an actual argv path token, never a shell/-c substring, establishes ownership.
 argv=row['argv']
 if not argv or not Path(argv[0]).name.startswith(('python','pypy')):return None
 prefix=str(root/'conversion/scripts')+'/'
 return next((a[len(prefix):] for a in argv[1:]
              if a.startswith(prefix) and '/' not in a[len(prefix):] and a.endswith('.py')),None)

def task_paths(row,root=ROOT):
 prefix=str(root)+'/'
 return [a.split('=',1)[-1] for a in row['argv']
         if a.split('=',1)[-1].startswith(prefix)]

def known_orphan_helper(row,root=ROOT):
 argv=row['argv'];paths=task_paths(row,root)
 if str(root/'scripts/curate_derived.py') in paths and '--render-native-only' in argv:
  return 'exact_task_native_render_helper'
 for path in paths:
  rel=Path(path).relative_to(root).as_posix()
  if re.fullmatch(r'conversion/rendering[^/]*/remote_render\.py',rel):return 'exact_task_renderer_helper'
 # These programs are task-local copies, not a shared system/GPU runtime.
 if argv and str(root/'conversion/runtime')+'/' in argv[0]:return 'exact_task_local_runtime_helper'
 return None

def plan(rows, own_pid=None, uid=None, root=ROOT, allow=(), excluded=()):
 own_pid=os.getpid() if own_pid is None else own_pid
 uid=os.getuid() if uid is None else uid
 protected=protected_ancestors(rows,own_pid)|set(excluded)
 allowed=ALLOWED|set(allow);selected={};unknown=[]
 for pid,row in rows.items():
  if pid in protected or row['uid']!=uid:continue
  name=script_name(row,root)
  if name in allowed:selected[pid]={**row,'ownership':'exact_task_python_script','script':name}
  elif known_orphan_helper(row,root):selected[pid]={**row,'ownership':known_orphan_helper(row,root),'script':None}
 # Include complete families even when workers use spawn_main, Node, Chrome, bwrap,
 # tectonic, or a per-run script snapshot without dataset paths in argv.
 changed=True
 while changed:
  changed=False
  for pid,row in rows.items():
   if pid in selected or pid in protected or row['uid']!=uid:continue
   if row['ppid'] in selected:
    selected[pid]={**row,'ownership':'descendant_of_task_birth','via_pid':row['ppid'],
                   'script':script_name(row,root)};changed=True
 # An independent unknown task script blocks execution. Descendant helpers are
 # already justified by the recorded family, so no executable-name guess is used.
 for pid,row in rows.items():
  if pid in selected or pid in protected or row['uid']!=uid:continue
  name=script_name(row,root)
  if name or task_paths(row,root):unknown.append({**row,'reason':'unknown_independent_task_script_or_helper','script':name})
 roots=[pid for pid,row in selected.items() if row['ppid'] not in selected]
 return {'at':now(),'protected_pids':sorted(protected),'roots':sorted(roots),
         'selected':list(sorted(selected.values(),key=lambda x:x['pid'])),
         'unknown':unknown,'allowed_extra_scripts':list(allow),'excluded_pids':list(excluded),
         'root_scripts':dict(collections.Counter(selected[p].get('script') or selected[p]['ownership'] for p in roots))}

def same_birth(row):
 current=read_process(row['pid'])
 return current if current and current['birth']==row['birth'] else None

def signal_capability_preflight():
 """Harmless signal0 to self, before any control-file or process mutation."""
 before=read_process(os.getpid())
 if before is None:raise RuntimeError('Cannot establish takeover process birth')
 fd=pidfd_open(os.getpid(),0)
 try:
  if same_birth(before) is None:raise RuntimeError('Takeover process birth changed')
  pidfd_send_signal(fd,0,None,0)
 finally:os.close(fd)
 helper=Path(pidfd_open.__code__.co_filename).resolve()
 return {'ok':True,'self_pid':os.getpid(),'self_birth':before['birth'],'signal':0,
         'python_native_pidfd_open':hasattr(os,'pidfd_open'),
         'python_native_pidfd_send_signal':hasattr(signal,'pidfd_send_signal'),
         'helper':str(helper),'helper_sha256':digest(helper.read_bytes())}

def send(row, signum, events):
 current=same_birth(row)
 if not current or current['state']=='Z':return
 # pidfd binds the signal to the checked kernel process rather than a reusable PID.
 try:fd=pidfd_open(row['pid'],0)
 except ProcessLookupError:return
 try:
  current=same_birth(row)
  if not current or current['state']=='Z':return
  pidfd_send_signal(fd,signum,None,0)
  events.append({'at':now(),'pid':row['pid'],'birth':row['birth'],'signal':int(signum)})
 except ProcessLookupError:pass
 finally:os.close(fd)

def surviving(rows):
 live=[];zombies=[]
 for row in rows.values():
  current=same_birth(row)
  if current:
   (zombies if current['state']=='Z' else live).append(current)
 return live,zombies

def collect_new_descendants(known, all_rows):
 # Re-snapshot before every escalation to capture newly spawned children while
 # their live parent's birth still matches. Persist their original ancestry.
 changed=True
 while changed:
  changed=False
  for pid,row in all_rows.items():
   if pid in known:continue
   parent=known.get(row['ppid']);actual_parent=all_rows.get(row['ppid'])
   if parent and actual_parent and parent['birth']==actual_parent['birth'] and row['uid']==parent['uid']:
    known[pid]={**row,'ownership':'late_descendant_of_task_birth','via_pid':row['ppid']};changed=True

def wait_for_exit(known, seconds):
 end=time.monotonic()+seconds
 while True:
  all_rows=processes();collect_new_descendants(known,all_rows)
  live,zombies=surviving(known)
  if not live or time.monotonic()>=end:return live,zombies
  time.sleep(min(.5,max(.01,end-time.monotonic())))

def execute(prepared, out, grace_seconds=120, term_seconds=30, kill_seconds=10, kill=False):
 if prepared['unknown']:raise RuntimeError('Unknown task commands require explicit review before execution')
 capability=signal_capability_preflight()
 policy_path=WORK/'model_usage_policy_v2.json';policy_raw=policy_path.read_bytes();policy=json.loads(policy_raw)
 if not (policy.get('legacy_sdk_disabled') is True and policy.get('legacy_batch_generation_disabled') is True
         and policy.get('automatic_model_critics_disabled') is True
         and policy.get('new_gateway_enabled') is False and policy.get('authorized_model_sample_ids')==[]):
  raise RuntimeError('Frozen no-new-model policy is not in force; takeover refuses to proceed')
 known={x['pid']:x for x in prepared['selected']};events=[]
 result={'at':now(),'requested':'stop legacy task families for fixed finite pipeline',
         'before':prepared,'signals':events,'controls':[],
         'source_database_claims_histories_and_model_budgets_modified':False,'model_calls':0,
         'model_policy_sha256':digest(policy_raw),'legacy_and_new_model_dispatch_disabled':True,
         'signal_capability_preflight':capability}
 out=Path(out);atomic(out,result)
 active={x.get('script') for x in known.values()}
 for name,control in DRAIN.items():
  if name not in active:continue
  path=WORK/control;prior=path.read_bytes() if path.exists() else None
  if prior:
   value=json.loads(prior)
   if not isinstance(value,dict):raise RuntimeError('Unknown drain control shape: '+str(path))
  else:value={}
  result['controls'].append({'file':str(path),'prior_utf8':prior.decode() if prior else None,
                              'prior_sha256':digest(prior) if prior else None})
  value.update(drain=True,requested_at=now(),reason='User requested finite fixed pipeline takeover')
  atomic(path,value)
 # Known signal handlers finish the current bounded case. Non-drainable original
 # pools receive TERM as a whole captured family, never one arbitrary worker.
 drained_roots=[];undrainable=[]
 for pid in prepared['roots']:
  row=known[pid]
  if row.get('script') in DRAIN:
   drained_roots.append(pid)
   if row.get('script') in USR1:send(row,signal.SIGUSR1,events)
  else:undrainable.append(pid)
 def root_of(pid):
  seen=set()
  while pid in known and known[pid]['ppid'] in known and pid not in seen:
   seen.add(pid);pid=known[pid]['ppid']
  return pid
 for row in list(known.values()):
  if root_of(row['pid']) in undrainable:send(row,signal.SIGTERM,events)
 atomic(out,result)
 live,zombies=wait_for_exit(known,grace_seconds)
 if live:
  # Parent first stops new dispatch; all captured births are then signalled.
  for row in sorted(live,key=lambda x:(x['ppid'] not in (1,0),x['pid'])):send(row,signal.SIGTERM,events)
  live,zombies=wait_for_exit(known,term_seconds)
 if live and kill:
  for row in live:send(row,signal.SIGKILL,events)
  live,zombies=wait_for_exit(known,kill_seconds)
 # A final independent census catches surviving/new independent legacy roots.
 after=plan(processes(),allow=prepared.get('allowed_extra_scripts',()),excluded=prepared.get('excluded_pids',()))
 remaining=[x for x in after['selected'] if x['state']!='Z']
 result.update(finished_at=now(),after=after,all_captured_processes=list(known.values()),
               surviving_captured_births=live,zombie_births=zombies,
               remaining_task_processes=remaining,
               complete=not live and not remaining and not after['unknown'])
 result['model_policy_unchanged']=digest(policy_path.read_bytes())==digest(policy_raw)
 result['complete']=result['complete'] and result['model_policy_unchanged']
 atomic(out,result);return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--execute',action='store_true');p.add_argument('--allow-script',action='append',default=[])
 p.add_argument('--exclude-pid',type=int,action='append',default=[])
 p.add_argument('--grace-seconds',type=float,default=120);p.add_argument('--term-seconds',type=float,default=30)
 p.add_argument('--kill-seconds',type=float,default=10);p.add_argument('--kill-after-timeout',action='store_true')
 p.add_argument('--output');a=p.parse_args()
 if any(not 0<=n<=600 for n in (a.grace_seconds,a.term_seconds,a.kill_seconds)):p.error('Wait budgets must be0..600s')
 prepared=plan(processes(),allow=a.allow_script,excluded=a.exclude_pid)
 path=Path(a.output) if a.output else WORK/'serial_takeover_v1'/('inventory_'+uuid.uuid4().hex+'.json')
 if not path.resolve().is_relative_to((WORK/'serial_takeover_v1').resolve()):p.error('Output must be inside conversion/serial_takeover_v1/')
 if a.execute:
  result=execute(prepared,path,a.grace_seconds,a.term_seconds,a.kill_seconds,a.kill_after_timeout)
 else:
  result={'dry_run':True,'inventory':prepared,'model_calls':0,'no_signals_sent':True};atomic(path,result)
 print(json.dumps({'output':str(path),'dry_run':not a.execute,'root_scripts':prepared['root_scripts'],
                   'selected_count':len(prepared['selected']),'unknown':prepared['unknown'],
                   'complete':result.get('complete'),'remaining':len(result.get('remaining_task_processes',[]))}))
 return 0 if not a.execute or result['complete'] else 2

if __name__=='__main__':raise SystemExit(main())
