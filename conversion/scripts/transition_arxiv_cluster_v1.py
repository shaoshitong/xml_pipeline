"""Drain only owned single-node collector, retain ledgers, switch to LAN queue."""
from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time
R=Path('/backup/shaoshitong/img2code_20261029');P=R/'clean/arxiv_research_figures_v1';S=R/'conversion/scripts';C=P/'transport_performance_v3';D=P/'cluster_direct_v1'
def birth(pid):
    try:
        r=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split();return r[19] if r[0]!='Z' else None
    except FileNotFoundError:return None
old=json.loads((P/'oai_direct_pipeline_v1/launch.json').read_text())
if birth(old['pid'])==old['birth_ticks']:
    cmd=Path('/proc',str(old['pid']),'cmdline').read_bytes();assert b'arxiv_oai_direct_pipeline_v1.py' in cmd
    os.kill(old['pid'],signal.SIGTERM)
    while birth(old['pid'])==old['birth_ticks']:
        print(json.dumps(dict(event='draining_existing_single_node_batch',pid=old['pid'],at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())),flush=True);time.sleep(10)
# Explicitly meter the final old-launch counter before any new-launch telemetry.
metric=json.loads((C/'recent_AI.performance.json').read_text());epoch=str(old['pid'])+':'+old['birth_ticks']+':recent_AI'
while True:
    g=json.loads((C/'resource_guard_v1/state.json').read_text())
    if g['cursors'].get(epoch,0)>=metric['new_source_network_bytes']:break
    time.sleep(3)
# Reload only this task's guard. Its original cumulative state is untouched.
for path in Path('/proc').iterdir():
    if not path.name.isdigit():continue
    try:cmd=(path/'cmdline').read_bytes().split(b'\0')
    except (FileNotFoundError,PermissionError):continue
    if str(S/'arxiv_resource_guard_v1.py').encode() in cmd and b'run' in cmd:os.kill(int(path.name),signal.SIGTERM)
subprocess.run([sys.executable,str(S/'arxiv_resource_guard_v1.py'),'launch'],check=True)
receipt=json.loads((D/'broker_launch.json').read_text())
if birth(receipt['pid'])==receipt['birth_ticks']:
    os.kill(receipt['pid'],signal.SIGTERM)
    while birth(receipt['pid'])==receipt['birth_ticks']:time.sleep(.2)
subprocess.run([sys.executable,str(S/'start_arxiv_cluster_broker_v1.py')],check=True)
sys.path.insert(0,str(S));import arxiv_cluster_broker_v1 as broker;import arxiv_oai_direct_pipeline_v1 as direct
# All cached authoritative OAI pages can seed independent work immediately.
count=0
for path in [C/'oai_recovery_v1/probe_listrecords.xml',*sorted((P/'oai_direct_pipeline_v1/metadata').glob('*/*/*.xml'))]:
    if not path.exists():continue
    papers,_=direct.parse_page(path.read_bytes());count+=broker.action('enqueue',dict(papers=papers))['enqueued']
env=dict(os.environ,ARXIV_CLUSTER_CONFIG=str(R/'conversion/private_arxiv_cluster_v1/broker.json'))
subprocess.run([sys.executable,str(S/'launch_arxiv_oai_direct_v1.py')],env=env,check=True)
put=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),old_pid=old['pid'],old_birth=old['birth_ticks'],old_launch_drained=True,seeded_jobs=count,budget_used_before=g['observed_payload_bytes'],cumulative_budget_not_reset=True,old_once_ledgers_preserved=True)
(D/'transition.json').write_text(json.dumps(put,indent=2));print(json.dumps(put),flush=True)
