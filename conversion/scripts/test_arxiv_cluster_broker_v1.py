"""Real SQLite contention/once and idempotent accounting tests in a temp root."""
import concurrent.futures as cf,hashlib,json,tempfile
from pathlib import Path
import arxiv_cluster_broker_v1 as b
with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);b.R=root;b.P=root/'clean';b.D=b.P/'cluster_direct_v1';b.SOURCE=b.P/'source';b.AUTH=root/'conversion/private'
    b.P.mkdir();b.SOURCE.mkdir();b.AUTH.parent.mkdir();b.init()
    with b.connect(b.SOURCE/'once.sqlite') as c:
        c.execute('create table papers(id text primary key,status text,record text)');c.execute('create table pdfs(id text primary key,status text,record text)')
    g=b.P/'transport_performance_v3/resource_guard_v1';g.mkdir(parents=True)
    (g/'state.json').write_text(json.dumps(dict(observed_payload_bytes=1234567,network_payload_limit_bytes=549755813888,stop=None)))
    x=dict(node='hkust1',id=hashlib.sha256(b'pdf').hexdigest(),paper='2610.00001v1')
    with cf.ThreadPoolExecutor(20) as pool:out=list(pool.map(lambda _:b.action('claim_pdf',x),range(50)))
    assert sum(r['claimed'] for r in out)==1
    charge=dict(node='hkust1',id='same-reservation',bytes=1234)
    with cf.ThreadPoolExecutor(20) as pool:list(pool.map(lambda _:b.action('charge',charge),range(50)))
    assert b.guard()[1:]==(1234,1235801)
    papers=[dict(versioned_id=f'2610.{i:05d}v1') for i in range(1000)]
    assert b.action('enqueue',dict(papers=papers))['enqueued']==1000
    assert b.action('enqueue',dict(papers=papers))['enqueued']==0
    assert all(b.shard(p['versioned_id'])==b.shard(p['versioned_id'].replace('v1','v2')) for p in papers)
    counts=[]
    for node in b.NODES:
        result=b.action('next',dict(node=node));assert len(result['papers'])==16
        assert all(b.shard(p['versioned_id'])==node for p in result['papers']);counts.append(len(result['papers']))
    print(json.dumps(dict(global_once_claims=1,concurrent_claim_requests=50,idempotent_charge_bytes=1234,old_budget_used_preserved=1234567,all_five_disjoint_shards_receive_jobs=counts)))
