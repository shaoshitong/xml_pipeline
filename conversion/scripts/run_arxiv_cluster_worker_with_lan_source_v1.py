"""Keep the exact node worker/once protocol; route only arXiv source GET via LAN."""
from pathlib import Path
import argparse,json,urllib.parse
import requests
from arxiv_lan_source_relay_v1 import allowed
from arxiv_cluster_worker_v1 import main
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--config',type=Path,required=True);a=p.parse_args();config=json.loads(a.config.read_text());assert config['node']=='hkust4' and config['source_transport']=='HKUST3_DIRECT_LAN_RELAY'
endpoint='http://10.120.17.122:60572/source';original=requests.Session.get
def get(self,url,**kwargs):
 if url.startswith('https://arxiv.org/'):
  assert allowed(url),'unsupported_relay_source_URL'
  headers=dict(kwargs.pop('headers',None) or {});headers['Authorization']='Bearer '+config['token'];kwargs['headers']=headers
  kwargs['params']={'url':url};response=original(self,endpoint,**kwargs);response.url=response.headers.get('X-Original-Source-URL',url);return response
 return original(self,url,**kwargs)
requests.Session.get=get
print(json.dumps(dict(source_transport="arxiv -> HKUST3 DIRECT -> HKUST4 campus LAN",PDF_once_protocol_unchanged=True,global_broker_rate_and_budget_preserved=True)),flush=True)
main(a.root,a.config)
