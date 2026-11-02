"""Use the installed real SDK class with fake agents/fetch; zero network APIs."""
import json
import select
import subprocess
import tempfile
from pathlib import Path

from sdk_inflight_drain_v1 import MODULE, Inspector, patch_expression


def main():
    with tempfile.TemporaryDirectory(prefix='sdk_zero_api_drain_') as folder:
        root = Path(folder)
        fixture = root / 'fixture.mjs'
        fixture.write_text('''
          const {HarnessSdkJsonRpcServer}=await import(MODULE);
          globalThis.stubNetworkCalls=0;globalThis.activeFetchDone=false;globalThis.activeWaitDone=false;
          globalThis.fetch=()=>{globalThis.stubNetworkCalls++;return new Promise(resolve=>globalThis.finishExistingFetch=()=>resolve({ok:true}));};
          globalThis.activeFetch=fetch('https://zero-network.invalid/v1/messages',{method:'POST'}).then(()=>globalThis.activeFetchDone=true);
          const agent={id:'agent',session:{id:'session',seq:0},status:'busy',whenIdle:()=>new Promise(resolve=>globalThis.finishExistingWait=()=>{agent.status='idle';resolve();})};
          const ctx={on:()=>()=>{},agents:new Map([['agent',agent]]),get:()=>undefined};
          globalThis.server=new HarnessSdkJsonRpcServer(ctx,{notify:()=>{}});server.initialized=true;
          server.sessions.set('session',{handle:{agent}});
          globalThis.activeWait=server.wait({sessionId:'session'}).then(()=>globalThis.activeWaitDone=true);
          process.stdout.write('READY\\n');setInterval(()=>{},1000);
        '''.replace('MODULE', json.dumps(MODULE.as_uri())))
        proc = subprocess.Popen(['/usr/bin/node', '--inspect=127.0.0.1:0', str(fixture)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            import re
            url = None
            for _ in range(4):
                line = proc.stderr.readline()
                match = re.search(r'ws://\S+', line)
                if match:
                    url = match[0]
                    break
            if not url or not select.select([proc.stdout], [], [], 10)[0] or proc.stdout.readline().strip() != 'READY':
                raise RuntimeError('Sandbox failed to become ready')
            client = Inspector(url)
            try:
                before = client.evaluate('({pid:process.pid,stubNetworkCalls,activeFetchDone,activeWaitDone})')
                receipt = root / 'guard.jsonl'
                installed = client.evaluate(patch_expression(receipt))
                result = client.evaluate('''(async()=>{
                  let promptBlocked=false,fetchBlocked=false;
                  try{await server.prompt({sessionId:'new-forbidden-session',contentBlocks:[]});}catch(e){promptBlocked=String(e).includes('blocked locally');}
                  try{await fetch('https://zero-network.invalid/v1/messages',{method:'POST'});}catch(e){fetchBlocked=String(e).includes('blocked locally');}
                  finishExistingFetch();finishExistingWait();await activeFetch;await activeWait;
                  return {promptBlocked,fetchBlocked,stubNetworkCalls,activeFetchDone,activeWaitDone};
                })()''')
                assert before['stubNetworkCalls'] == 1 and not before['activeFetchDone'] and not before['activeWaitDone'], before
                assert installed['cached_class_confirmed'] and installed['wait_function_unchanged'], installed
                assert result == {'promptBlocked': True, 'fetchBlocked': True, 'stubNetworkCalls': 1, 'activeFetchDone': True, 'activeWaitDone': True}, result
                records = [json.loads(line) for line in receipt.read_text().splitlines()]
                assert [r['kind'] for r in records] == ['guards_installed', 'blocked_prompt', 'blocked_model_POST']
                assert all(r['upstream_send_performed'] is False and r['charged'] is False for r in records)
                print(json.dumps({'ok': True, 'actual_api_calls': 0, 'before': before, 'installed': installed,
                                  'result': result, 'receipt_kinds': [r['kind'] for r in records]}))
            finally:
                client.close()
        finally:
            proc.terminate()
            proc.communicate(timeout=10)


if __name__ == '__main__':
    main()
