"""Loopback contract test: byte identity, Range, auth, URL restriction and budget."""
from pathlib import Path
import gzip,io,json,tempfile,threading,urllib.request,urllib.error
import arxiv_lan_source_relay_v1 as relay
import arxiv_cluster_broker_v1 as broker
calls=[];blocked=False
class Response:
 def __init__(self,headers,url):
  self.url=url
  if 'Range' in headers:self.status_code=206;body=b'56789';self.headers={'Content-Length':'5','Content-Range':'bytes 5-9/10'}
  else:self.status_code=200;body=gzip.compress(b'unchanged source bytes');self.headers={'Content-Length':str(len(body)),'Content-Encoding':'gzip','Content-Type':'application/octet-stream'}
  self.raw=Raw(body)
 def __enter__(self):return self
 def __exit__(self,*a):pass
class Raw(io.BytesIO):
 def read(self,n=-1,decode_content=False):assert decode_content is False;return super().read(n)
class Session:
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def get(self,url,**kw):calls.append((url,kw));assert 'Authorization' not in kw['headers'];return Response(kw['headers'],url)
relay.requests.Session=Session;broker.guard=lambda:({'stop':blocked,'network_payload_limit_bytes':1024},0,0)
relay.CONFIG={'token':'fixture-not-real'}
with tempfile.TemporaryDirectory() as td:
 relay.D=Path(td);server=relay.http.server.ThreadingHTTPServer(('127.0.0.1',0),relay.Handler);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)+'/source?url='
 def req(url,auth=True,**headers):
  h={'Authorization':'Bearer fixture-not-real'} if auth else {};h.update(headers)
  try:
   with urllib.request.urlopen(urllib.request.Request(base+urllib.parse.quote(url,safe=''),headers=h)) as r:return r.status,dict(r.headers),r.read()
  except urllib.error.HTTPError as e:return e.code,{},e.read()
 u='https://arxiv.org/src/2610.00001v1';status,h,b=req(u);assert status==200 and gzip.decompress(b)==b'unchanged source bytes' and h['Content-Encoding']=='gzip'
 status,h,b=req(u,Range='bytes=5-9');assert status==206 and b==b'56789' and h['Content-Range']=='bytes 5-9/10' and calls[-1][1]['headers']['Range']=='bytes=5-9'
 assert req(u,auth=False)[0]==403
 for bad in ['https://evil.invalid/src/2610.00001v1','https://arxiv.org@evil.invalid/src/2610.00001v1','http://arxiv.org/src/2610.00001v1','https://arxiv.org/src/2610.00001v1?next=evil','https://arxiv.org/admin']:
  assert req(bad)[0]==400
 blocked=True;assert req(u)[0]==503;assert len(calls)==2
 server.shutdown();server.server_close()
 print(json.dumps(dict(raw_bytes_and_content_encoding_preserved=True,range_resume_preserved=True,auth_and_URL_restrictions_passed=True,budget_stop_respected=True,external_requests=0,fixture_upstream_calls=len(calls))))
