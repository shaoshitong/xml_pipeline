"""Eight direct downloads + eight unchanged official native import workers per node.

Canonical relative paths are retained for verified LAN ingest back into HKUST3.
No models, system proxy, global DNS, VPS or Mac bulk transfer is involved.
"""
from pathlib import Path
import argparse, concurrent.futures as cf, datetime, fcntl, hashlib, io, json, os
import shutil, sqlite3, sys, tarfile, threading, time, uuid
import socket
import requests

STOP = False

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''): h.update(b)
    return h.hexdigest()

def main(root, config_path):
    config=json.loads(config_path.read_text()); node=config['node']; root=root.resolve()
    work=root/'clean/arxiv_research_figures_v1/recent_ai_source_expansion_v2'
    work.mkdir(parents=True,exist_ok=True)
    lock=(root/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    local=threading.local()
    def session():
        if not hasattr(local,'session'):
            local.session=requests.Session();local.session.trust_env=False
            local.session.headers['Authorization']='Bearer '+config['token']
        return local.session
    def rpc(op, **data):
        payload=dict(node=node,**data)
        # Repeating operations has stable IDs. Never proceed with an uncertain
        # global claim, permit or central upload acknowledgement.
        while True:
            try:
                r=session().post(config['url']+'/'+op,json=payload,timeout=(8,120));r.raise_for_status(); x=r.json()
                if 'error' in x:raise RuntimeError(x['error'])
                return x
            except (requests.RequestException,ValueError) as e:
                print(json.dumps(dict(event='broker_pending_retry',operation=op,error=str(e)[:400])),flush=True);time.sleep(10)
    sys.path[:0]=[str(root/'conversion/scripts'),str(root/'runtime/packages')]
    import arxiv_oai_direct_pipeline_v1 as direct
    import arxiv_bulk_official_xml_png_v1 as render
    engine=direct.engine; native=engine.native
    engine.R=root;engine.S=root/'conversion/scripts';engine.P=root/'clean/arxiv_research_figures_v1'
    engine.CONTROL=engine.P/'transport_performance_v3';engine.CONTROL.mkdir(parents=True,exist_ok=True)
    engine.PROXY=None;engine.BUDGET=512*1024**3
    native.R=root;native.D=work;native.S=engine.P/'drawio_builtin_import_v1/official_importer'
    direct.R=root;direct.S=engine.S;direct.P=engine.P
    render.R=root;render.WAR=root/'evaluation/assets/drawio-runtime-v32.6.1/draw.war'
    render.CHROME=str(root/'runtime/chrome/chrome')
    inherited=engine.P/'new_bulk_200_v1';inherited.mkdir(exist_ok=True)
    with sqlite3.connect(inherited/'once.sqlite') as c:
        c.execute('create table if not exists papers(id text primary key,status text,record text)')
        c.execute('create table if not exists pdfs(id text primary key,status text,record text)')
        for ident in json.loads((root/'runtime/inherited_paper_ids.json').read_text()):
            c.execute('insert or ignore into papers values(?,?,?)',(ident,'inherited','{}'))
    actual_run=engine.real_run
    def node_run(args,*a,**kw):
        if isinstance(args,list) and args and args[0]=='/usr/bin/node':
            args=[str(root/'runtime/packages/playwright/driver/node'),*args[1:]]
        return actual_run(args,*a,**kw)
    engine.real_run=node_run
    original_process=engine.NativeWorker.process
    def once_process(self,path,paper,source):
        ident=engine.sha(path.read_bytes())
        if self.db.execute('select 1 from pdfs where id=?',(ident,)).fetchone():return
        with self.owner.hash_lock('claim:'+ident):
            claim=rpc('claim_pdf',id=ident,paper=paper['versioned_id'])
            if not claim['claimed']:
                self.owner.metric('global_PDF_hash_reuse',0);return
            return original_process(self,path,paper,source)
    engine.NativeWorker.process=once_process
    launched=uuid.uuid4().hex
    counters=dict(actual_source_bytes=0,source_completed=0,papers_ingested=0)
    counterlock=threading.Lock()
    class Body:
        def __init__(self,response):self.r=response
        def __getattr__(self,k):return getattr(self.r,k)
        def __enter__(self):
            self.r.__enter__()
            def abort():
                try:self.r.raw._fp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                except (AttributeError,OSError):pass
                self.r.close()
            self.timer=threading.Timer(600,abort);self.timer.daemon=True;self.timer.start()
            return self
        def __exit__(self,*a):
            self.timer.cancel()
            return self.r.__exit__(*a)
        def iter_content(self,size):
            it=self.r.iter_content(size)
            while True:
                reservation=rpc('charge',id=launched+':'+uuid.uuid4().hex,bytes=size)
                if not reservation.get('ok'):raise requests.ConnectionError('existing_resource_budget')
                try:b=next(it)
                except StopIteration:return
                with counterlock:counters['actual_source_bytes']+=len(b)
                yield b
    class State(direct.DirectState):
        allow_slow_direct=True
        def request(self,url,stream=False,headers=None,api=False):
            permit=rpc('rate');time.sleep(permit['wait_seconds'])
            response=self.session().get(url,stream=stream,headers=headers,timeout=(12,25))
            if response.status_code in [403,429,503]:rpc('cooldown',seconds=60)
            response.raise_for_status()
            return Body(response) if stream else response
        def save(self,finished=False):
            super().save(finished)
        def emit(self,event,**fields):
            if 'route' in fields:fields['route']='arxiv -> '+node+' DIRECT -> HKUST3 LAN'
            super().emit(event,**fields)
    state=State(work,'recent_AI')
    def heartbeat():
        while True:
            with counterlock:value=dict(counters)
            rpc('heartbeat',pid=os.getpid(),launch_id=launched,root=str(root),download_threads=8,native_import_threads=8,**value)
            tmp=root/'status.json.tmp';tmp.write_text(json.dumps(dict(value,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())));os.replace(tmp,root/'status.json')
            time.sleep(10)
    threading.Thread(target=heartbeat,daemon=True).start()
    def fetch_partial(paper):
        folder=work/'papers'/paper['versioned_id']
        if folder.exists():return
        response=session().get(config['url']+'/paper',params={'id':paper['versioned_id']},timeout=(8,180));response.raise_for_status()
        with tarfile.open(fileobj=io.BytesIO(response.content)) as t:
            for m in t.getmembers():
                assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts and (m.isfile() or m.isdir())
            t.extractall(work,filter='data')
    def download(paper):
        if shutil.disk_usage(root).free<8*1024**3:
            return dict(error='resource_worker_disk_below_8GiB',network_failure=True)
        try:fetch_partial(paper)
        except requests.RequestException as e:return dict(error='ConnectionError:'+str(e),network_failure=True)
        return state.download(paper)
    def upload(paper):
        ident=paper['versioned_id']; folder=work/'papers'/ident
        record=json.loads((folder/'record.json').read_text())
        pdf_records=[json.loads(raw) for raw, in state.db.execute('select record from pdfs') if json.loads(raw).get('paper')==ident]
        files={}
        for tree in [folder,*[work/'cases'/r['id'] for r in pdf_records]]:
            for path in tree.rglob('*'):
                if path.is_file():files[str(path.relative_to(work))]=digest(path)
        out=root/'outbox';out.mkdir(exist_ok=True);archive=out/(ident+'.tar')
        result=json.dumps(dict(node=node,paper_record=record,pdf_records=pdf_records,files=files)).encode()
        with tarfile.open(archive,'w') as t:
            info=tarfile.TarInfo('result.json');info.size=len(result);t.addfile(info,io.BytesIO(result))
            for name in files:t.add(work/name,arcname=name,recursive=False)
        expected=digest(archive)
        while True:
            try:
                with archive.open('rb') as f:
                    r=session().post(config['url']+'/upload',data=f,headers={'X-SHA256':expected,'Content-Type':'application/octet-stream'},timeout=(8,600))
                r.raise_for_status();ack=r.json();assert ack.get('ok'),ack
                break
            except (requests.RequestException,AssertionError) as e:
                print(json.dumps(dict(event='ingest_pending_retry',paper=ident,error=str(e)[:500])),flush=True);time.sleep(15)
        # Canonical server has verified hashes of every file and durable DB rows.
        # Source and case payload may now be removed from this worker only.
        archive.unlink();shutil.rmtree(folder)
        for rec in pdf_records:shutil.rmtree(work/'cases'/rec['id'],ignore_errors=True)
        with counterlock:
            counters['papers_ingested']+=1
            counters['source_completed']+=int(record['status']=='source_completed')
    try:
        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            while True:
                response=rpc('next',retry_delay=60)
                if response.get('blocked'):
                    print(json.dumps(response),flush=True);time.sleep(30);continue
                papers=response['papers']
                if not papers:time.sleep(5);continue
                futures=[pool.submit(download,paper) for paper in papers]
                for paper,future in zip(papers,futures):
                    result=future.result()
                    if direct.transient(result):
                        rpc('paper_pending',id=paper['versioned_id'],error=result.get('error'))
                        continue
                    terminal=state.db.execute('select status from papers where id=?',(paper['versioned_id'],)).fetchone()
                    if not terminal or terminal[0]=='attempt_started':state.process_paper(paper,result)
                    upload(paper)
    finally:state.close(finished=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--config',type=Path,required=True);a=p.parse_args();main(a.root,a.config)
