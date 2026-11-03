"""Authenticated campus-only GET relay to the existing HKUST3 arXiv exit.

No generic proxy, DNS override, IP selection, metadata crawler or model call.
Caller retains the existing global request permit, cooldown and byte budget.
"""
from pathlib import Path
import datetime,fcntl,hashlib,hmac,http.server,json,os,re,threading,time,urllib.parse
import requests
R=Path('/backup/shaoshitong/img2code_20261029');D=R/'clean/arxiv_research_figures_v1/cluster_direct_v1/source_relay_v1';AUTH=R/'conversion/private_arxiv_cluster_v1/broker.json'
LOCK=threading.Lock()
def allowed(url):
 p=urllib.parse.urlsplit(url)
 return p.scheme=='https' and p.netloc=='arxiv.org' and not p.query and not p.fragment and re.fullmatch(r'/(?:abs|src)/\d{4}\.\d{4,5}v[1-9]\d*',p.path) is not None
class Handler(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.0'
 def do_GET(self):
  if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+CONFIG['token']):self.send_error(403);return
  q=urllib.parse.urlsplit(self.path);url=urllib.parse.parse_qs(q.query).get('url',[''])[0]
  if q.path!='/source' or not allowed(url):self.send_error(400);return
  # The worker has already obtained its shared broker permit. Budget and
  # transient HTTP response handling remain in the unmodified worker transport.
  from arxiv_cluster_broker_v1 import guard
  g,_,used=guard()
  if g.get('stop') or used>=g['network_payload_limit_bytes']:self.send_error(503);return
  n=0;status=None;error=None;started=False;t=time.monotonic()
  try:
   headers={k:self.headers[k] for k in ['Range','Accept-Encoding','User-Agent'] if self.headers.get(k)}
   with requests.Session() as s:
    s.trust_env=False
    with s.get(url,headers=headers,stream=True,timeout=(12,25)) as r:
     status=r.status_code;self.send_response(status)
     for k in ['Content-Length','Content-Type','Content-Range','Content-Encoding','Accept-Ranges','ETag','Last-Modified','Retry-After']:
      if k in r.headers:self.send_header(k,r.headers[k])
     self.send_header('X-Original-Source-URL',r.url);self.end_headers();started=True
     limit=128*1024**2 if '/src/' in url else 2*1024**2
     while True:
      if time.monotonic()-t>600:raise TimeoutError('relay_stream_600s')
      b=r.raw.read(min(65536,limit-n+1),decode_content=False)
      if not b:break
      n+=len(b)
      if n>limit:raise ValueError('source_size_limit')
      self.wfile.write(b);self.wfile.flush()
  except Exception as e:
   error=type(e).__name__+':'+str(e)[:300]
   if not started:
    try:self.send_error(504)
    except (BrokenPipeError,ConnectionResetError):pass
  finally:
   with LOCK:
    with (D/'requests.jsonl').open('a') as f:f.write(json.dumps(dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),url=url,status=status,upstream_body_bytes=n,seconds=time.monotonic()-t,error=error,source_exit='HKUST3_DIRECT',consumer='HKUST4_LAN',budget_accounted_by_original_worker=True))+'\n')
 def log_message(self,*args):pass
if __name__=='__main__':
 D.mkdir(parents=True,exist_ok=True);lock=(D/'program.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);CONFIG=json.loads(AUTH.read_text());http.server.ThreadingHTTPServer(('10.120.17.122',60572),Handler).serve_forever()
