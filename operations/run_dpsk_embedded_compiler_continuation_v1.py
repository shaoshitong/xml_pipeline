"""Continue the same completed remote CLI session with versioned compiler work."""
from pathlib import Path
import datetime,fcntl,json,os,subprocess
R=Path('/backup/shaoshitong/img2code_20261029');W=R/'conversion/dpsk_svg_png_compiler_20261103'
def run():
 os.umask(0o077);lock=(W/'continuation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 previous=json.loads((W/'launcher_status.json').read_text());assert previous['state']=='exited','original coding session not terminal'
 session=None
 for line in (W/'events.jsonl').read_text().splitlines():
  try:event=json.loads(line)
  except ValueError:continue
  if event.get('type')=='session':session=event['sessionId'];break
 assert session
 env=dict(os.environ,DSH_HOME=str(W/'dsh_home'),DSH_PERMISSION_MODE='workspace-write',DSH_TELEMETRY_DISABLED='1')
 cmd=['/usr/bin/node',str(R/'conversion/runtime/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js'),'--profile','headless','--patch',str(W/'headless.patch.yml'),'--json','--session-id',session,'Read CONTINUE_TASK.md and implement the checkpointed cumulative-input and complete native-page compiler extension. Use HKUST3 CPU only; keep existing proof packets/ledgers and old compiler core untouched.']
 p=W/'continuation_status.json'
 def put(state):
  t=p.with_suffix('.tmp');t.write_text(json.dumps(state,indent=2)+'\n');os.replace(t,p)
 state=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),launcher_pid=os.getpid(),session_id=session,same_existing_harness_session=True,CPU_host='HKUST3',command=cmd,state='starting')
 with (W/'continuation_events.jsonl').open('ab') as out,(W/'continuation_stderr.log').open('ab') as err:
  child=subprocess.Popen(cmd,cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err);state.update(state='running',child_pid=child.pid);put(state);code=child.wait()
 state.update(state='exited',exit_code=code,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());put(state)
if __name__=='__main__':run()
