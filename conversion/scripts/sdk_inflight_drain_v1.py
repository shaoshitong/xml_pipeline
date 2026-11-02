"""Deny future SDK prompts/model POSTs while existing Node streams drain.

Only explicitly supplied, source-verified SDK children of the two specified
Harness coordinators may be patched. Never reads credentials, prompts or images.
"""
import argparse
import json
import os
import re
import signal
import time
import urllib.request
from pathlib import Path

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
CLI = W / 'runtime/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js'
MODULE = W / 'runtime/dsh/node_modules/@deepseek-ai/dsh-sdk-jsonrpc-server/lib/index.js'


def patch_expression(receipt, module=MODULE):
    return '''(async()=>{
      if(globalThis.__codexModelDrainV1)return {...globalThis.__codexModelDrainV1,already_installed:true};
      const {appendFileSync}=process.getBuiltinModule('fs');
      const require=process.getBuiltinModule('module').createRequire(process.cwd()+'/__drain_guard__.cjs');
      const sdk=require(MODULE);
      const proto=sdk.HarnessSdkJsonRpcServer.prototype;
      if(typeof proto.prompt!=='function'||typeof proto.wait!=='function')throw Error('SDK cached class shape changed');
      const oldPrompt=proto.prompt,oldWait=proto.wait,oldFetch=globalThis.fetch;
      if(typeof oldFetch!=='function')throw Error('Missing global fetch');
      const state={version:1,pid:process.pid,installed_at:new Date().toISOString(),receipt:RECEIPT,
        denied_prompts:0,denied_model_posts:0,cached_class_module:MODULE,
        source_boundary:'Existing fetch Promise/SSE and session/wait remain untouched; future prompt and model POST are locally refused.'};
      const record=(kind,extra={})=>appendFileSync(RECEIPT,JSON.stringify({at:new Date().toISOString(),pid:process.pid,kind,
        upstream_send_performed:false,charged:false,...extra})+'\\n',{mode:0o600});
      proto.prompt=async function(params){state.denied_prompts++;record('blocked_prompt',{session_id:params?.sessionId??null});
        throw Error('MODEL_CALLS_STOPPED_BY_USER: new prompt blocked locally before followup; not charged');};
      globalThis.fetch=function(input,init){
        const url=typeof input==='string'?input:input instanceof URL?input.href:input?.url;
        const method=String(init?.method??input?.method??'GET').toUpperCase();
        let path;try{path=new URL(url).pathname;}catch{}
        if(method==='POST'&&path&&(/\\/messages\\/?$/.test(path)||/\\/chat\\/completions\\/?$/.test(path)||/\\/responses\\/?$/.test(path))){
          state.denied_model_posts++;record('blocked_model_POST',{method,path});
          return Promise.reject(Error('MODEL_CALLS_STOPPED_BY_USER: model POST blocked locally before fetch; not charged'));}
        return Reflect.apply(oldFetch,this,arguments);
      };
      globalThis.__codexModelDrainV1=state;
      record('guards_installed',{cached_class_confirmed:require(MODULE).HarnessSdkJsonRpcServer.prototype.prompt===proto.prompt,
        wait_function_unchanged:proto.wait===oldWait});
      return {...state,cached_class_confirmed:require(MODULE).HarnessSdkJsonRpcServer.prototype.prompt===proto.prompt,
        wait_function_unchanged:proto.wait===oldWait};
    })()'''.replace('MODULE', json.dumps(str(Path(module).resolve()))).replace('RECEIPT', json.dumps(str(receipt)))


class Inspector:
    def __init__(self, url):
        import websocket
        self.ws = websocket.create_connection(url, timeout=10, suppress_origin=True)
        self.counter = 0

    def evaluate(self, expression):
        self.counter += 1
        self.ws.send(json.dumps({'id': self.counter, 'method': 'Runtime.evaluate',
                                 'params': {'expression': expression, 'awaitPromise': True, 'returnByValue': True}}))
        while True:
            frame = json.loads(self.ws.recv())
            if frame.get('id') != self.counter:
                continue
            if frame.get('error'):
                raise RuntimeError(str(frame['error']))
            result = frame['result']
            if result.get('exceptionDetails'):
                raise RuntimeError(str(result['exceptionDetails']))
            return result['result'].get('value')

    def close(self):
        self.ws.close()


def targets(parents):
    result = []
    parents = set(parents)
    for folder in Path('/proc').iterdir():
        if not folder.name.isdigit():
            continue
        try:
            status = (folder / 'status').read_text()
            ppid = int(re.search(r'^PPid:\s*(\d+)', status, re.M)[1])
            if ppid not in parents:
                continue
            argv = [s.decode() for s in (folder / 'cmdline').read_bytes().split(b'\0') if s]
            if len(argv) < 6 or not argv[0].endswith('/node') or Path(argv[1]).resolve() != CLI.resolve():
                continue
            if argv[2:4] != ['--profile', 'sdk'] or argv[4] != '--patch':
                continue
            patch = Path(argv[5]).resolve()
            cwd = (folder / 'cwd').resolve()
            if not patch.is_relative_to(W / 'harness_sessions') or patch != cwd / 'controlled.patch.yml':
                continue
            expected = 'v5_' if ppid == 4020931 else 'v6_' if ppid == 2345163 else None
            if expected and not cwd.name.startswith(expected):
                continue
            result.append({'pid': int(folder.name), 'ppid': ppid, 'argv': argv,
                           'session_dir': str(cwd), 'patch': str(patch),
                           'receipt': str(cwd / 'sdk_model_drain_v1.jsonl')})
        except (OSError, ValueError, TypeError):
            continue
    return sorted(result, key=lambda r: r['pid'])


def _endpoints():
    try:
        with urllib.request.urlopen('http://127.0.0.1:9229/json/list', timeout=.5) as response:
            return json.load(response)
    except OSError:
        return []


def install(target):
    current = next((r for r in targets([target['ppid']]) if r['pid'] == target['pid']), None)
    if current != target:
        raise RuntimeError('SDK child identity changed before patch')
    endpoints = _endpoints()
    opened = not endpoints
    if opened:
        os.kill(target['pid'], signal.SIGUSR1)
        deadline = time.monotonic() + 5
        while not endpoints and time.monotonic() < deadline:
            time.sleep(.05)
            endpoints = _endpoints()
    if len(endpoints) != 1:
        raise RuntimeError('Cannot identify exactly one local inspector target')
    client = Inspector(endpoints[0]['webSocketDebuggerUrl'])
    try:
        pid = client.evaluate('process.pid')
        if pid != target['pid']:
            raise RuntimeError('Inspector belongs to another process: ' + str(pid))
        result = client.evaluate(patch_expression(target['receipt']))
        if not result.get('cached_class_confirmed') or not result.get('wait_function_unchanged'):
            raise RuntimeError('Drain guard class/wait verification failed')
        if opened:
            client.evaluate("setTimeout(()=>process.getBuiltinModule('inspector').close(),100);true")
        return {**target, 'guard': result}
    finally:
        client.close()
        if opened:
            deadline = time.monotonic() + 5
            while _endpoints() and time.monotonic() < deadline:
                time.sleep(.05)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', type=int, action='append', required=True)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args(argv)
    chosen = targets(args.parent)
    result = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'parents': args.parent,
              'targets': chosen, 'applied': [], 'errors': [], 'new_model_calls': 0}
    if args.apply:
        for target in chosen:
            try:
                result['applied'].append(install(target))
            except Exception as exc:
                result['errors'].append({'pid': target['pid'], 'error': str(exc)[:2000]})
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
