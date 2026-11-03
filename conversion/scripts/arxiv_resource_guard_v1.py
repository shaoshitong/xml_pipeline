"""Persistent task resource guard; fail closed by stopping only its SSH relay.

No PDF/importer process is killed: bounded download failures trip the existing
transport circuit breaker while in-flight native validation is allowed to drain.
"""
from pathlib import Path
import datetime,fcntl,json,os,shutil,signal,subprocess,sys,tempfile,time

R=Path('/backup/shaoshitong/img2code_20261029')
P=R/'clean/arxiv_research_figures_v1'
T=R/'conversion/private_arxiv_transport_v3'
D=P/'transport_performance_v3/resource_guard_v1'
LIMIT=512*1024**3
MIN_FREE=250*1024**3

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,value):
    q=path.with_name(path.name+'.tmp')
    with q.open('w') as f:
        json.dump(value,f,ensure_ascii=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(q,path)
def birth(pid):
    try:
        x=Path('/proc',str(pid),'stat').read_text().split(') ',1)[1].split()
        return x[19] if x[0]!='Z' else None
    except FileNotFoundError:return None
def owned_signal(receipt,sig):
    if birth(receipt['pid'])!=receipt['birth_ticks']:return False
    os.kill(receipt['pid'],sig);return True
def read(path):
    try:return json.loads(path.read_text())
    except FileNotFoundError:return None
def accumulate(state,epoch,counter):
    assert isinstance(counter,int) and counter>=0
    old=state['cursors'].get(epoch)
    if old is None:delta=counter
    elif counter>=old:delta=counter-old
    else:
        # A reset is a new measured segment, never a fresh overall budget.
        delta=counter
        state['counter_reset_segments']=state.get('counter_reset_segments',0)+1
    state['observed_payload_bytes']+=delta
    state['cursors'][epoch]=counter
    return delta
def resource_reason(state,free):
    if free<MIN_FREE:return 'free_disk_below_250_GiB'
    if state['observed_payload_bytes']>=LIMIT:return 'persistent_observed_source_payload_reached_512_GiB'
    return None
def retained_payload_bytes():
    total=0
    for name in ['new_bulk_200_v1','recent_ai_source_expansion_v2']:
        folder=P/name/'papers'
        if folder.exists():
            for paper in folder.iterdir():
                for basename in ['source.archive','source.archive.part']:
                    q=paper/basename
                    try:total+=q.stat().st_size
                    except FileNotFoundError:pass
    return total
def stop_task_transport():
    receipt=read(T/'launch.json');status=read(T/'status.json');actions=[]
    if receipt:
        actions.append({'target':'task_tunnel_supervisor','pid':receipt['pid'],
                        'signalled':owned_signal(receipt,signal.SIGTERM)})
    # Fallback only after the supervisor has had time for its own finally block.
    deadline=time.monotonic()+12
    if receipt:
        while birth(receipt['pid'])==receipt['birth_ticks'] and time.monotonic()<deadline:time.sleep(.2)
    if status and status.get('child_birth_ticks'):
        child={'pid':status['child_pid'],'birth_ticks':status['child_birth_ticks']}
        actions.append({'target':'task_tunnel_SSH_child','pid':child['pid'],
                        'signalled':owned_signal(child,signal.SIGTERM)})
    return actions
def run():
    D.mkdir(parents=True,exist_ok=True)
    lock=(D/'guard.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state=read(D/'state.json')
    if state is None:
        state={'schema':'arxiv_resource_guard_v1','installed_at_utc':now(),
               'observed_payload_bytes':0,'cursors':{},'initial_retained_payload_bytes':retained_payload_bytes(),
               'historical_wire_bytes_exact':False,
               'meter_note':'Retained payload is an initial floor; subsequent monotonic HTTP body counters accumulate across launches. Historical discarded/retransmitted bytes before installation are not reconstructible; unflushed in-flight bytes may lag metrics.',
               'stop':None}
    while True:
        launch=read(P/'transport_performance_v3/launch.json')
        if launch:
            launched=datetime.datetime.fromisoformat(launch['at_utc'].replace('Z','+00:00'))
            for profile in ['initial_200','recent_AI']:
                metric=read(P/'transport_performance_v3'/(profile+'.performance.json'))
                if not metric:continue
                recorded=datetime.datetime.fromisoformat(metric['at_utc'].replace('Z','+00:00'))
                if recorded<launched:continue
                epoch=str(launch['pid'])+':'+launch['birth_ticks']+':'+profile
                accumulate(state,epoch,metric['new_source_network_bytes'])
        state['observed_payload_bytes']=max(state['observed_payload_bytes'],state['initial_retained_payload_bytes'])
        cluster=read(P/'cluster_direct_v1/network_bytes.json')
        if cluster:
            # Persistent reservations cover all five nodes and interrupted reads.
            # The old cumulative budget and every prior launch cursor remain.
            accumulate(state,'cluster_direct_v1:persistent_reservations',cluster['bytes'])
            state['cluster_charged_bytes_included']=cluster['bytes']
        free=shutil.disk_usage(R).free
        reason=resource_reason(state,free)
        if reason and not state['stop']:
            state['stop']={'at_utc':now(),'reason':reason,'native_workers_killed':False,
                           'partial_archives_preserved':True,'automatic_budget_reset':False}
            atomic(D/'STOP.json',state['stop']);atomic(D/'state.json',state)
        if state['stop']:
            state['last_transport_stop_actions']=stop_task_transport()
        state.update(at_utc=now(),free_disk_bytes=free,network_payload_limit_bytes=LIMIT,
                     minimum_free_disk_bytes=MIN_FREE,agent_required=False,external_models=0)
        atomic(D/'state.json',state)
        time.sleep(15)
def selftest():
    s={'observed_payload_bytes':0,'cursors':{}}
    assert accumulate(s,'A',100)==100
    assert accumulate(s,'A',150)==50
    assert accumulate(s,'A',150)==0
    assert accumulate(s,'B',20)==20
    assert accumulate(s,'A',5)==5 and s['observed_payload_bytes']==175
    assert resource_reason(s,MIN_FREE+1) is None
    assert resource_reason(s,MIN_FREE-1)=='free_disk_below_250_GiB'
    s['observed_payload_bytes']=LIMIT
    assert resource_reason(s,MIN_FREE+1)=='persistent_observed_source_payload_reached_512_GiB'
    p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
    try:
        assert not owned_signal({'pid':p.pid,'birth_ticks':'wrong-owner'},signal.SIGTERM)
        assert p.poll() is None
        assert owned_signal({'pid':p.pid,'birth_ticks':birth(p.pid)},signal.SIGTERM)
        assert p.wait(timeout=5)==-signal.SIGTERM
    finally:
        if p.poll() is None:p.terminate();p.wait(timeout=5)
    print(json.dumps({'persistent_meter_and_reset_controls':True,'budget_and_disk_controls':True,
                      'actual_owned_signal_control':True,'wrong_birth_not_signalled':True,
                      'production_tunnel_or_worker_stopped':False,'external_models':0}))
def launch():
    D.mkdir(parents=True,exist_ok=True)
    old=read(D/'launch.json')
    if old and birth(old['pid'])==old['birth_ticks']:
        print(json.dumps({'already_running':True,**old}));return
    with (D/'program.log').open('ab') as log:
        p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],
                           stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    receipt={'at_utc':now(),'pid':p.pid,'birth_ticks':birth(p.pid),
             'program':str(Path(__file__).resolve()),'agent_required':False}
    atomic(D/'launch.json',receipt);print(json.dumps(receipt))
if __name__=='__main__':
    {'run':run,'launch':launch,'selftest':selftest}[sys.argv[1]]()
