"""LAN-only durable five-node source queue, global PDF once claims and rate/budget gate.

One SQLite writer host; no SQLite file is shared over a network filesystem.
Workers retain local artifacts until a hashed, idempotent central ingest succeeds.
"""
from pathlib import Path
import argparse, contextlib, datetime, fcntl, hashlib, hmac, http.server, io, json, os
import secrets, shutil, sqlite3, tarfile, threading, time, urllib.parse, uuid

R = Path('/backup/shaoshitong/img2code_20261029')
P = R / 'clean/arxiv_research_figures_v1'
D = P / 'cluster_direct_v1'
SOURCE = P / 'recent_ai_source_expansion_v2'
AUTH = R / 'conversion/private_arxiv_cluster_v1'
LOCK = threading.RLock()
RATE = threading.Lock()
NEXT = 0.0
NODES = ['hkust1', 'hkust2', 'hkust3', 'hkust4', 'hkust5']
PREFIX = 'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2/'

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def put(p, x):
    q = p.with_name(p.name + '.' + uuid.uuid4().hex + '.tmp')
    q.write_text(json.dumps(x, ensure_ascii=True, indent=2) + '\n'); os.replace(q, p)
def connect(p):
    c = sqlite3.connect(p, timeout=60); c.execute('pragma busy_timeout=60000'); return c

def shard(ident):
    # Five contiguous, non-overlapping SHA256 intervals; all versions share owner.
    return NODES[min(4, int(sha(ident.split('v')[0].encode()), 16) * 5 // (1 << 256))]

def init():
    D.mkdir(exist_ok=True); AUTH.mkdir(mode=0o700, exist_ok=True)
    config = AUTH / 'broker.json'
    if not config.exists():
        put(config, dict(url='http://10.120.17.122:60571', token=secrets.token_hex(32)))
        config.chmod(0o600)
    with connect(D / 'queue.sqlite') as c:
        c.execute('pragma journal_mode=WAL')
        c.executescript('''
        create table if not exists jobs(id text primary key,node text,status text,paper text,updated real,error text);
        create table if not exists pdf_claims(id text primary key,node text,paper text,at_utc text);
        create table if not exists charges(id text primary key,node text,bytes integer);
        create table if not exists uploads(id text primary key,sha text,at_utc text);
        create table if not exists heartbeats(node text primary key,record text);
        create table if not exists actual_network(launch text primary key,node text,bytes integer);
        ''')
    if not (D / 'policy.json').exists():
        put(D / 'policy.json', dict(at_utc=now(), nodes=NODES, sharding='contiguous SHA256(arxiv_id) intervals [i/5,(i+1)/5)', download_threads_per_node=8, native_import_threads_per_node=8, global_request_spacing_seconds=.34, metadata_serial=True, source_budget_not_reset=True, VPS_used=False, importer_changed=False))
    return json.loads(config.read_text())

def guard():
    g = json.loads((P / 'transport_performance_v3/resource_guard_v1/state.json').read_text())
    with connect(D / 'queue.sqlite') as c:
        total = c.execute('select coalesce(sum(bytes),0) from charges').fetchone()[0]
    # Guard includes cluster bytes once observed. Pending charges are added here,
    # so a delayed guard tick can never grant a fresh budget on another node.
    observed_cluster = g.get('cluster_charged_bytes_included', 0)
    used = g['observed_payload_bytes'] + max(0, total - observed_cluster)
    return g, total, used

def checkpoint():
    with LOCK, connect(D / 'queue.sqlite') as c:
        counts = {}
        for node, status, count in c.execute('select node,status,count(*) from jobs group by node,status'):
            counts.setdefault(node, {})[status] = count
        heartbeats = {n:json.loads(r) for n,r in c.execute('select node,record from heartbeats')}
        total = c.execute('select coalesce(sum(bytes),0) from charges').fetchone()[0]
        pdf = c.execute('select count(*) from pdf_claims').fetchone()[0]
        actual = c.execute('select coalesce(sum(bytes),0) from actual_network').fetchone()[0]
        put(D / 'progress.json', dict(at_utc=now(), jobs=counts, source_bytes_reserved_conservatively=total, source_bytes_actually_received=actual, new_PDF_once_claims=pdf, workers=heartbeats, goal_complete=False))
        put(D / 'network_bytes.json', dict(bytes=total))

def action(op, x):
    global NEXT
    node = x.get('node')
    if op == 'rate':
        with RATE:
            wait = max(0, NEXT - time.monotonic()); NEXT = max(NEXT, time.monotonic()) + .34
        return dict(wait_seconds=wait)
    if op == 'cooldown':
        with RATE: NEXT = max(NEXT, time.monotonic() + min(900, max(60, x.get('seconds',60))))
        return dict(ok=True)
    with LOCK, connect(D / 'queue.sqlite') as q, connect(SOURCE / 'once.sqlite') as old:
        if op == 'enqueue':
            count = 0
            for paper in x['papers']:
                ident = paper['versioned_id']
                row = old.execute('select status from papers where id=?',(ident,)).fetchone()
                if row and row[0] != 'attempt_started': continue
                count += q.execute('insert or ignore into jobs values(?,?,?,?,?,?)',(ident,shard(ident),'pending',json.dumps(paper),time.time(),None)).rowcount
            return dict(enqueued=count)
        assert node in NODES, 'unknown_node'
        if op == 'next':
            g,total,used = guard()
            if g.get('stop') or used >= g['network_payload_limit_bytes']:
                return dict(blocked='existing_resource_budget', used=used)
            # Sticky claims survive worker restart on the same node. A worker
            # only calls next after its prior batch's terminal reports complete.
            rows = q.execute("select id,paper from jobs where node=? and status in ('pending','claimed','pending_network_retry') and updated<? order by case status when 'claimed' then 0 else 1 end,updated limit 16",(node,time.time()-x.get('retry_delay',0))).fetchall()
            for ident,_ in rows:
                q.execute("update jobs set status='claimed',updated=? where id=?",(time.time(),ident))
            return dict(papers=[json.loads(r) for _,r in rows])
        if op == 'paper_pending':
            q.execute("update jobs set status='pending_network_retry',updated=?,error=? where id=? and node=?",(time.time(),x.get('error','')[:2000],x['id'],node))
            return dict(ok=True)
        if op == 'claim_pdf':
            ident=x['id']; row=old.execute('select status from pdfs where id=?',(ident,)).fetchone()
            if row: return dict(claimed=False, prior_status=row[0])
            rec=dict(id=ident,status='distributed_claim_reserved',node=node,paper=x['paper'],at_utc=now(),official_calls=0,reason='Committed before any official invocation; never reassigned automatically')
            old.execute('insert into pdfs values(?,?,?)',(ident,rec['status'],json.dumps(rec))); old.commit()
            q.execute('insert into pdf_claims values(?,?,?,?)',(ident,node,x['paper'],now()))
            return dict(claimed=True)
        if op == 'charge':
            amount=x['bytes']; assert 0 <= amount <= 256*1024
            existing=q.execute('select bytes from charges where id=?',(x['id'],)).fetchone()
            if existing: return dict(ok=True)
            g,total,used=guard()
            if g.get('stop') or used+amount>g['network_payload_limit_bytes']:
                return dict(ok=False,blocked='existing_resource_budget')
            # Reservation before reading covers interrupted/short reads
            # conservatively, never refunds or resets historical budget.
            q.execute('insert into charges values(?,?,?)',(x['id'],node,amount))
            return dict(ok=True)
        if op == 'heartbeat':
            q.execute('insert or replace into heartbeats values(?,?)',(node,json.dumps(dict(x,at_utc=now()))))
            q.execute('insert into actual_network values(?,?,?) on conflict(launch) do update set bytes=max(bytes,excluded.bytes)',(x['launch_id'],node,x['actual_source_bytes']))
            return dict(ok=True)
    raise ValueError('unknown_operation')

def pack_paper(ident):
    assert ident and all(c in '0123456789.v' for c in ident)
    folder=SOURCE/'papers'/ident
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz') as t:
        if folder.exists(): t.add(folder,arcname='papers/'+ident,recursive=True)
    return out.getvalue()

def ingest(path, expected):
    assert sha(path.read_bytes()) == expected
    with tarfile.open(path) as t:
        members=t.getmembers()
        assert sum(m.size for m in members)<=2*1024**3 and len(members)<=25000
        for m in members:
            p=Path(m.name)
            assert not p.is_absolute() and '..' not in p.parts and (m.isfile() or m.isdir())
            assert m.name=='result.json' or m.name.startswith(('papers/','cases/'))
        staging=D/'ingest'/expected; staging.mkdir(parents=True,exist_ok=True)
        t.extractall(staging, members=members, filter='data')
    result=json.loads((staging/'result.json').read_text()); node=result['node']; ident=result['paper_record']['id']
    assert node in NODES and shard(ident)==node
    # Verify every file against the manifest before publishing any DB rows.
    entries=result['files']; assert len(entries)==len([m for m in members if m.isfile()])-1
    for name,digest in entries.items():
        source=staging/name; assert sha(source.read_bytes())==digest, name
    with LOCK, connect(D/'queue.sqlite') as q, connect(SOURCE/'once.sqlite') as old:
        job=q.execute('select node from jobs where id=?',(ident,)).fetchone(); assert job and job[0]==node
        if q.execute('select 1 from uploads where id=?',(ident,)).fetchone(): return dict(ok=True,already_ingested=True)
        for name,digest in entries.items():
            source=staging/name; target=SOURCE/name; target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if sha(target.read_bytes())==digest: continue
                # Only resume journals/partial metadata may change. Immutable
                # author payloads and accepted assets cannot be overwritten.
                assert name.startswith('papers/') and target.name in ['download_attempts.v3.jsonl','record.json','source.archive.part'], 'immutable_collision:'+name
            temporary=target.with_name(target.name+'.cluster.'+uuid.uuid4().hex)
            shutil.copyfile(source,temporary); os.replace(temporary,target)
        for record in result['pdf_records']:
            claim=q.execute('select node from pdf_claims where id=?',(record['id'],)).fetchone(); assert claim and claim[0]==node
            current=old.execute('select status from pdfs where id=?',(record['id'],)).fetchone()
            if current and current[0]!='distributed_claim_reserved':
                prior=json.loads(old.execute('select record from pdfs where id=?',(record['id'],)).fetchone()[0]); assert prior==record
            else: old.execute('update pdfs set status=?,record=? where id=?',(record['status'],json.dumps(record),record['id']))
        rec=result['paper_record']; old.execute('insert or replace into papers values(?,?,?)',(ident,rec['status'],json.dumps(rec)));old.commit()
        q.execute('insert into uploads values(?,?,?)',(ident,expected,now()))
        q.execute("update jobs set status='ingested',updated=?,error=null where id=?",(time.time(),ident))
        # Existing cold-replay collector sees canonical paths/rows, untouched QA.
        rows=old.execute("select record from pdfs where status='qualified_native_xml_png_pair' order by id").fetchall()
        tmp=SOURCE/'manifest.jsonl.cluster.tmp';tmp.write_text(''.join(r[0]+'\n' for r in rows));os.replace(tmp,SOURCE/'manifest.jsonl')
    shutil.rmtree(staging); path.unlink()
    return dict(ok=True,files=len(entries),paper=ident)

class Handler(http.server.BaseHTTPRequestHandler):
    def authorized(self):
        return hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+CONFIG['token'])
    def respond(self,obj,status=200):
        body=json.dumps(obj).encode(); self.send_response(status);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_POST(self):
        if not self.authorized(): return self.respond({'error':'unauthorized'},403)
        try:
            size=int(self.headers.get('Content-Length','0')); op=urllib.parse.urlparse(self.path).path.lstrip('/')
            if op=='upload':
                assert 0<size<=2*1024**3
                folder=D/'uploads';folder.mkdir(exist_ok=True);path=folder/(uuid.uuid4().hex+'.tar')
                with path.open('wb') as f:
                    remaining=size
                    while remaining:
                        b=self.rfile.read(min(1024**2,remaining)); assert b; f.write(b); remaining-=len(b)
                out=ingest(path,self.headers['X-SHA256'])
            else:
                assert size<=8*1024**2
                out=action(op,json.loads(self.rfile.read(size)))
            self.respond(out)
        except Exception as e:
            self.respond(dict(error=type(e).__name__+':'+str(e)),500)
    def do_GET(self):
        if not self.authorized(): return self.respond({'error':'unauthorized'},403)
        try:
            parsed=urllib.parse.urlparse(self.path)
            if parsed.path=='/runtime':
                path=D/'runtime.tar.gz'; self.send_response(200);self.send_header('Content-Length',str(path.stat().st_size));self.send_header('X-SHA256',sha(path.read_bytes()));self.end_headers()
                with path.open('rb') as f: shutil.copyfileobj(f,self.wfile)
            elif parsed.path=='/paper':
                b=pack_paper(urllib.parse.parse_qs(parsed.query)['id'][0]); self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            else: self.respond(dict(error='unknown'),404)
        except (BrokenPipeError,ConnectionResetError): pass
    def log_message(self,*args): pass

def main():
    global CONFIG
    CONFIG=init();lock=(D/'broker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def monitor():
        while True:
            try:checkpoint()
            except Exception as e: print(json.dumps({'monitor_error':str(e)}),flush=True)
            time.sleep(10)
    threading.Thread(target=monitor,daemon=True).start()
    http.server.ThreadingHTTPServer(('10.120.17.122',60571),Handler).serve_forever()
if __name__=='__main__': main()
