import json,uuid
from pathlib import Path
from remote_harness import SDK,ROOT,safe_text
case=ROOT/'harness_sessions'/('probe_'+uuid.uuid4().hex);case.mkdir(parents=True)
sdk=SDK(case)
try:
 ack=sdk.initialize('deepseek-flash','high',65536)
 (case/'initialize.json').write_text(json.dumps(ack,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'ok':True,'case':str(case),'initialize':ack},ensure_ascii=False),flush=True)
except Exception as e:
 print(json.dumps({'ok':False,'error':safe_text(str(e))[-3000:],'stderr':''.join(sdk.stderr)[-3000:]},ensure_ascii=False),flush=True);raise
finally:sdk.close()
