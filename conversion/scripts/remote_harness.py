import json,os,queue,re,subprocess,threading,time
from pathlib import Path
ROOT=Path('/backup/shaoshitong/img2code_20261029/conversion')
CLI=ROOT/'runtime/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js'
MASKED_TOOLS=['tool-working-directory', 'tool-bash', 'tool-pwsh', 'tool-jobs', 'tool-fs', 'tool-fs-search', 'tool-skill', 'tool-subagent-control', 'tool-subagent-list-agents', 'tool-subagent', 'tool-subagent-fork', 'tool-workflow', 'tool-result-pruner', 'tool-todo', 'tool-goal', 'tool-web', 'plan-mode']
def require_legacy_sdk_allowed():
    policy=ROOT/'model_usage_policy_v2.json'
    if not policy.exists() or json.loads(policy.read_text()).get('legacy_sdk_disabled',True):
        raise RuntimeError('Legacy model SDK disabled by user policy. Use the budgeted patch-only gateway; lifetime maximum is two calls per original sample including history.')
def safe_text(text):
    text=re.sub(r'(?i)(bearer\s+|x-dsh-auth-token[\s:=]+)\S+',r'\1[REDACTED]',text)
    return re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[REDACTED]',text)


def make_patch(path,full_tools=False):
    lines=['- id: credentials','  config:',
           '    path: /backup/shaoshitong/img2code_20261029/conversion/private/credentials.yaml','    watch: false',
           '- id: sdk-jsonrpc-server','  config:','    maxTokensAsSuccess: false',
           '- id: agent-default-model','  config:','    provider: deepseek-account',
           '    model: deepseek-flash','    reasoningEffort: max',
           '- id: agent-instructions','  disabled: true',
           '- id: skill-filesystem','  disabled: true',
           '- id: session-telemetry-otel','  disabled: true']
    masked = MASKED_TOOLS if not full_tools else [name for name in MASKED_TOOLS
        if name not in ('tool-fs','tool-result-pruner')]
    for tool in masked:lines+=['- id: '+tool,'  disabled: true']
    path.write_text('\n'.join(lines)+'\n')


class SDK:
    def __init__(self,directory,proxy=None,full_tools=False,extra_patch=None,max_tool_calls=None):
        require_legacy_sdk_allowed()
        self.directory=directory
        self.home=directory/'sdk_home'
        self.home.mkdir(parents=True,exist_ok=False)
        self.patch=directory/'controlled.patch.yml'; make_patch(self.patch,full_tools)
        self.events=[]; self.stderr=[]; self.pending={}; self.counter=0
        self.max_tool_calls=max_tool_calls
        env=dict(os.environ,DSH_HOME=str(self.home),ELECTRON_RUN_AS_NODE='1',
                 DSH_PERMISSION_MODE='workspace-write',DSH_TELEMETRY_DISABLED='1')
        # Preserve the installed app's credentials by reference, never a copy.
        if proxy:
            env.update(HTTPS_PROXY=proxy,HTTP_PROXY=proxy,https_proxy=proxy,http_proxy=proxy)
        command=['/usr/bin/node',str(CLI),'--profile','sdk','--patch',str(self.patch)]
        if extra_patch:command+=['--patch',str(extra_patch)]
        self.proc=subprocess.Popen(command,
            cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,bufsize=1)
        self.out_thread=threading.Thread(target=self._read,daemon=True); self.out_thread.start()
        self.err_thread=threading.Thread(target=self._read_err,daemon=True); self.err_thread.start()
    def _read(self):
        for line in self.proc.stdout:
            try: frame=json.loads(line)
            except ValueError:
                self.stderr.append('nonprotocol stdout: '+safe_text(line));continue
            if 'method' in frame:
                self.events.append(frame)
            elif frame.get('id') in self.pending:
                self.pending[frame['id']].put(frame)
    def _read_err(self):
        for line in self.proc.stderr:self.stderr.append(safe_text(line))
    def request(self,method,params=None,timeout=120):
        self.counter+=1; rid=self.counter
        mailbox=queue.Queue(); self.pending[rid]=mailbox
        frame={'jsonrpc':'2.0','id':rid,'method':method}
        if params is not None:frame['params']=params
        self.proc.stdin.write(json.dumps(frame,ensure_ascii=False)+'\n');self.proc.stdin.flush()
        end=time.monotonic()+timeout
        try:
            while True:
                try:response=mailbox.get(timeout=1)
                except queue.Empty:
                    if self.max_tool_calls is not None:
                        count=sum(e.get('params',{}).get('event',{}).get('type')=='tool/call' for e in self.events)
                        if count>=self.max_tool_calls:
                            self.proc.terminate()
                            raise RuntimeError('SDK stopped after tool budget exceeded: '+str(count))
                    if self.proc.poll() is not None:
                        raise RuntimeError('SDK exited: '+''.join(self.stderr)[-4000:])
                    if time.monotonic()>end:raise TimeoutError('SDK '+method+' timed out')
                    continue
                if 'error' in response:raise RuntimeError('SDK '+method+': '+str(response['error']))
                return response.get('result')
        finally:self.pending.pop(rid,None)
    def initialize(self,model,reasoning,max_tokens):
        return self.request('initialize',{'cwd':str(self.directory),'provider':'deepseek-account',
            'model':model,'reasoningEffort':reasoning,'maxTokens':max_tokens},timeout=120)
    def turn(self,session,blocks,timeout):
        require_legacy_sdk_allowed()
        before=len(self.events); start=time.monotonic()
        ack=self.request('session/prompt',{'sessionId':session,'contentBlocks':blocks},timeout=120)
        self.request('session/wait',{'sessionId':session},timeout=timeout)
        events=self.events[before:]
        texts=[]; usages=[]; calls=[]; reasons=[]; finish_reasons=[]
        for frame in events:
            ev=frame.get('params',{}).get('event',{})
            data=ev.get('data',{})
            if ev.get('type')=='assistant/message':
                text=''.join(b.get('text','') for b in data.get('message',{}).get('content',[])
                             if b.get('type')=='text')
                if text:texts.append(text)
                if data.get('usage'):usages.append(data['usage'])
                for record in data.get('stream',[]):
                    chunk=record.get('chunk',{}) if isinstance(record,dict) else {}
                    if chunk.get('type')=='finish':finish_reasons.append(chunk.get('reason'))
            elif ev.get('type')=='tool/call':calls.append({'name':data.get('name')})
            elif ev.get('type')=='turn/end':reasons.append(data.get('reason'))
        usage={k:sum(x.get(k,0) or 0 for x in usages) for k in
               ['inputTokens','outputTokens','cacheReadTokens','cacheWriteTokens','totalTokens']}
        return {'response':'\n\n'.join(texts),'events':events,'usage':usage,
                'tool_calls':calls,'reasons':reasons,'finish_reasons':finish_reasons,
                'token_limit_reached':any(isinstance(r,dict) and r.get('kind') in
                  ('max-tokens','max_tokens','length') for r in reasons+finish_reasons),
                'message_id':ack.get('messageId'),
                'seconds':round(time.monotonic()-start,3)}
    def close(self):
        if self.proc.poll() is None:
            try:self.request('shutdown',timeout=30)
            except Exception:self.proc.terminate()
        try:self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.out_thread.join(timeout=2);self.err_thread.join(timeout=2)

