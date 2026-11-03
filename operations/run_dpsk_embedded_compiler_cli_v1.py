"""One isolated, user-authorized DeepSeek CLI coding session; no per-image LLM."""
from pathlib import Path
import datetime,fcntl,json,os,subprocess
R=Path('/backup/shaoshitong/img2code_20261029')
W=R/'conversion/dpsk_svg_png_compiler_20261103'
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def put(v):
 p=W/'launcher_status.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');os.replace(t,p)
def run():
 os.umask(0o077);lock=(W/'launcher.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 patch=W/'headless.patch.yml'
 patch.write_text('''- id: credentials
  disabled: false
  config:
    path: /backup/shaoshitong/img2code_20261029/conversion/private/credentials.yaml
    watch: false
- id: deepseek-account
  disabled: false
- id: agent-default-model
  config:
    provider: deepseek-account
    model: deepseek-flash
    reasoningEffort: high
- id: sandbox-policy
  config:
    mode: workspace-write
    workspaceRoot: /backup/shaoshitong/img2code_20261029
- id: approval
  config:
    policy: never
- id: permission
  config:
    defaultPreset: workspace-write
    presets:
      workspace-write:
        sandbox: workspace-write
        approval: never
        name: Workspace Write
        description: Authorized project workspace only
- id: session-title-llm
  disabled: true
- id: session-telemetry-otel
  disabled: true
- id: tool-subagent
  disabled: true
- id: tool-subagent-fork
  disabled: true
- id: tool-subagent-control
  disabled: true
- id: tool-subagent-list-agents
  disabled: true
- id: tool-workflow
  disabled: true
- id: tool-web
  disabled: true
''')
 env=dict(os.environ,DSH_HOME=str(W/'dsh_home'),DSH_PERMISSION_MODE='workspace-write',DSH_TELEMETRY_DISABLED='1')
 cmd=['/usr/bin/node',str(R/'conversion/runtime/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js'),'--profile','headless','--patch',str(patch),'--json','Read TASK.md in the working directory and execute its implementation, regression tests, bounded real pilot and durable batch. Write machine-readable status immediately.']
 state=dict(started_utc=now(),launcher_pid=os.getpid(),command=cmd,workspace=str(W),transport='remote_existing_dsh_headless_CLI',per_image_model_calls=False)
 with (W/'events.jsonl').open('ab') as out,(W/'stderr.log').open('ab') as err:
  proc=subprocess.Popen(cmd,cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
  state.update(state='running',child_pid=proc.pid);put(state);exitcode=proc.wait()
 state.update(state='exited',exit_code=exitcode,finished_utc=now());put(state)
if __name__=='__main__':run()
