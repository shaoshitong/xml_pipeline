"""Own exactly one new case subprocess tree in an otherwise child-free slot.

Linux subreaper adoption catches escaped sessions. Every signal uses a pidfd and
checks /proc birth identity; no process group or pre-existing child is signalled.
The caller must use an exclusive slot process and must not create unrelated
children concurrently. No database, network client, or model API is used here.
"""
from __future__ import annotations
import ctypes,errno,json,math,os,signal,subprocess,sys,threading,time,uuid
from pathlib import Path

_LOCK=threading.Lock()
PR_SET_CHILD_SUBREAPER=36
PR_GET_CHILD_SUBREAPER=37


def pidfd_open(pid,flags=0):
    if hasattr(os,'pidfd_open'):return os.pidfd_open(pid,flags)
    # The bundled Python may omit Linux API bindings even when libc/kernel
    # support them. This is the same pidfd capability, never naked-PID kill.
    libc=ctypes.CDLL(None,use_errno=True)
    if not hasattr(libc,'pidfd_open'):raise OSError(errno.ENOSYS,'libc pidfd_open unavailable')
    function=libc.pidfd_open;function.argtypes=(ctypes.c_int,ctypes.c_uint);function.restype=ctypes.c_int
    ctypes.set_errno(0);fd=function(pid,flags)
    if fd<0:raise OSError(ctypes.get_errno(),'pidfd_open')
    return fd


def pidfd_send_signal(fd,signum,info=None,flags=0):
    if hasattr(signal,'pidfd_send_signal'):return signal.pidfd_send_signal(fd,signum,info,flags)
    if info is not None:raise ValueError('Only null siginfo is supported')
    libc=ctypes.CDLL(None,use_errno=True)
    if not hasattr(libc,'pidfd_send_signal'):raise OSError(errno.ENOSYS,'libc pidfd_send_signal unavailable')
    function=libc.pidfd_send_signal;function.argtypes=(ctypes.c_int,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint);function.restype=ctypes.c_int
    ctypes.set_errno(0);result=function(fd,signum,None,flags)
    if result<0:raise OSError(ctypes.get_errno(),'pidfd_send_signal')
    return None


def identity(pid):
    try:
        text=Path('/proc',str(pid),'stat').read_text();fields=text[text.rindex(')')+2:].split()
        return {'pid':int(pid),'ppid':int(fields[1]),'state':fields[0],'process_group':int(fields[2]),'session':int(fields[3]),'start_ticks':int(fields[19])}
    except (OSError,ValueError,IndexError):return None


def same_birth(record,current):
    return current is not None and current['pid']==record['pid'] and current['start_ticks']==record['start_ticks']


def children(pid):
    result=set()
    try:tasks=list(Path('/proc',str(pid),'task').iterdir())
    except OSError:return result
    for task in tasks:
        try:result.update(int(x) for x in (task/'children').read_text().split())
        except (OSError,ValueError):pass
    return result


def subreaper(value=None):
    libc=ctypes.CDLL(None,use_errno=True)
    if value is None:
        result=ctypes.c_int();rc=libc.prctl(PR_GET_CHILD_SUBREAPER,ctypes.byref(result),0,0,0)
        if rc:raise OSError(ctypes.get_errno(),'PR_GET_CHILD_SUBREAPER')
        return result.value
    if libc.prctl(PR_SET_CHILD_SUBREAPER,int(bool(value)),0,0,0):raise OSError(ctypes.get_errno(),'PR_SET_CHILD_SUBREAPER')


def safe_signal(record,signum):
    """A retained pidfd binds the kernel process even if numeric PID is reused."""
    current=identity(record['pid'])
    if not same_birth(record,current):return {'signal':signum,'sent':False,'reason':'birth_identity_absent_or_changed'}
    if current['state']=='Z':return {'signal':signum,'sent':False,'reason':'already_zombie'}
    fd=record.get('_pidfd');temporary=False
    if fd is None:
        try:fd=pidfd_open(record['pid'],0);temporary=True
        except ProcessLookupError:return {'signal':signum,'sent':False,'reason':'already_exited'}
        # Opening the descriptor and reading /proc happen in separate syscalls.
        # Check again; sending on the descriptor can never hit a later reuse.
        if not same_birth(record,identity(record['pid'])):
            os.close(fd);return {'signal':signum,'sent':False,'reason':'birth_changed_before_pidfd_bind'}
    try:
        pidfd_send_signal(fd,signum,None,0)
        return {'signal':signum,'sent':True,'identity_checked':True,'via':'pidfd'}
    except ProcessLookupError:return {'signal':signum,'sent':False,'reason':'already_exited'}
    finally:
        if temporary:os.close(fd)


class Tree:
    def __init__(self,root):
        self.self_pid=os.getpid();self.root=root;self.records={};self.foreign=[];self.errors=[];self.peak=0
        born=identity(root.pid)
        if born is None:raise RuntimeError('New root disappeared before its birth identity could be captured')
        self.root_birth=born;self.track(born,'new_Popen_root',0)
    def track(self,born,basis,depth):
        key=(born['pid'],born['start_ticks'])
        if key in self.records:return self.records[key]
        fd=None
        try:
            fd=pidfd_open(born['pid'],0)
            if not same_birth(born,identity(born['pid'])):os.close(fd);return None
        except ProcessLookupError:return None
        except OSError as error:self.errors.append({'pid':born['pid'],'stage':'pidfd_open','error':repr(error)})
        record={**born,'ownership_basis':basis,'depth':depth,'_pidfd':fd,'actions':[],'first_seen_monotonic':time.monotonic()}
        self.records[key]=record;self.peak=max(self.peak,len(self.live()));return record
    def discover(self):
        roots=[]
        for pid in children(self.self_pid):
            born=identity(pid)
            if not born:continue
            if born['start_ticks']<self.root_birth['start_ticks']:
                if born not in self.foreign:self.foreign.append(born)
                continue
            record=self.track(born,'new_root_or_subreaper_adopted_child',1)
            if record:roots.append(record)
        roots.extend(r for r in self.records.values() if same_birth(r,identity(r['pid'])))
        visited=set()
        while roots:
            parent=roots.pop();key=(parent['pid'],parent['start_ticks'])
            if key in visited or not same_birth(parent,identity(parent['pid'])):continue
            visited.add(key)
            for pid in children(parent['pid']):
                born=identity(pid)
                if not born or born['ppid']!=parent['pid']:continue
                record=self.track(born,'observed_descendant_of_owned_birth',parent['depth']+1)
                if record:roots.append(record)
        self.peak=max(self.peak,len(self.live()))
    def live(self):
        result=[]
        for record in self.records.values():
            current=identity(record['pid'])
            if same_birth(record,current) and current['state']!='Z':result.append(record)
        return result
    def reap(self):
        self.root.poll()
        for record in self.records.values():
            current=identity(record['pid'])
            if record['pid']==self.root.pid or not same_birth(record,current) or current['ppid']!=self.self_pid:continue
            try:os.waitpid(record['pid'],os.WNOHANG)
            except (ChildProcessError,ProcessLookupError):pass
    def send(self,record,signum):
        try:record['actions'].append(safe_signal(record,signum))
        except OSError as error:
            action={'signal':signum,'sent':False,'error':repr(error)};record['actions'].append(action);self.errors.append({'pid':record['pid'],**action})
    def cleanup(self,grace=.35,budget=5.0):
        started=time.monotonic();sent_term=set();self.discover();leftover_at_start=len(self.live())
        while time.monotonic()-started<grace:
            self.discover()
            for record in self.live():
                key=(record['pid'],record['start_ticks'])
                if key not in sent_term:self.send(record,signal.SIGTERM);sent_term.add(key)
            self.reap()
            if not self.live() and not children(self.self_pid):break
            time.sleep(.015)
        # Stop parents before another discovery pass, so fork/setsid cannot race
        # an indefinitely growing tree. Each subsequent child is stopped before
        # being killed; all operations remain pidfd/birth scoped.
        while time.monotonic()-started<budget:
            self.discover();live=self.live()
            for record in sorted(live,key=lambda r:r['depth']):self.send(record,signal.SIGSTOP)
            self.discover()
            for record in sorted(self.live(),key=lambda r:r['depth'],reverse=True):self.send(record,signal.SIGKILL)
            self.reap();self.discover();self.reap()
            if not self.live() and not children(self.self_pid):break
            time.sleep(.02)
        self.discover();self.reap()
        complete=not self.live() and not children(self.self_pid) and not self.foreign
        return complete,leftover_at_start
    def close(self):
        for record in self.records.values():
            if record.get('_pidfd') is not None:
                try:os.close(record['_pidfd'])
                except OSError:pass
                record['_pidfd']=None
    def public(self):
        rows=[]
        for record in self.records.values():
            current=identity(record['pid']);rows.append({k:v for k,v in record.items() if not k.startswith('_')}|{'same_birth_still_present':same_birth(record,current),'current_state':current['state'] if same_birth(record,current) else None})
        return rows


def run(command:list[str],work:Path,timeout:float,env:dict|None=None)->dict:
    started=time.monotonic();work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True);token=uuid.uuid4().hex
    stdout=work/('process.'+token+'.stdout.log');stderr=work/('process.'+token+'.stderr.log');stdout.touch();stderr.touch()
    result={'ok':False,'returncode':None,'deadline_exceeded':False,'cleanup_complete':True,'root_process':None,'tracked_processes':[],'stdout_file':str(stdout),'stderr_file':str(stderr),'seconds':0.0,'refused':False}
    acquired=False;prior=None;root=None;tree=None
    try:
        if sys.platform!='linux':raise ValueError('Linux subreaper and pidfd are required')
        if not isinstance(command,list) or not command or not all(isinstance(x,str) and x for x in command):raise ValueError('Command must be a nonempty argv list')
        if not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:raise ValueError('Positive finite deadline required')
        if env is not None and (not isinstance(env,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in env.items())):raise ValueError('Environment must be string to string')
        acquired=_LOCK.acquire(False)
        if not acquired:raise ValueError('This process already owns a case')
        existing=children(os.getpid())
        if existing:raise ValueError('Refusing a slot with preexisting children: '+','.join(map(str,sorted(existing))))
        fd=pidfd_open(os.getpid(),0)
        try:pidfd_send_signal(fd,0,None,0)
        finally:os.close(fd)
        prior=subreaper();subreaper(True)
        with stdout.open('wb') as out,stderr.open('wb') as err:
            root=subprocess.Popen(command,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True,close_fds=True)
            tree=Tree(root);result['root_process']={**tree.root_birth,'ownership_basis':'new_Popen_handle'}
            deadline=started+timeout
            while root.poll() is None:
                tree.discover();tree.reap()
                if time.monotonic()>=deadline:result['deadline_exceeded']=True;break
                time.sleep(min(.025,max(0,deadline-time.monotonic())))
            tree.discover();result['cleanup_complete'],leftovers=tree.cleanup();result['returncode']=root.poll();result['leftovers_at_cleanup_start']=leftovers
        result['tracked_processes']=tree.public();result['peak_tracked_live_processes']=tree.peak;result['tracking_errors']=tree.errors;result['foreign_children_not_touched']=tree.foreign
        result['ok']=result['returncode']==0 and not result['deadline_exceeded'] and result['cleanup_complete']
    except BaseException as error:
        result['error']=repr(error);result['refused']=root is None
        if tree is not None:
            try:result['cleanup_complete'],_=tree.cleanup();result['tracked_processes']=tree.public();result['returncode']=root.poll()
            except BaseException as cleanup_error:result['cleanup_complete']=False;result['cleanup_error']=repr(cleanup_error)
        elif root is not None:
            # Root is still our unreaped Popen child; bind its current identity
            # rather than ever signalling a naked numeric PID.
            try:
                born=identity(root.pid)
                if born:
                    safe_signal(born,signal.SIGKILL);root.wait(timeout=1)
                result['returncode']=root.poll();result['cleanup_complete']=result['returncode'] is not None and not children(os.getpid())
            except BaseException as cleanup_error:result['cleanup_complete']=False;result['cleanup_error']=repr(cleanup_error)
    finally:
        if tree is not None:tree.close()
        if prior is not None and not result['cleanup_complete']:
            result['subreaper_retained_for_incomplete_cleanup']=True
        elif prior is not None:
            try:subreaper(prior)
            except OSError as error:result['subreaper_restore_error']=repr(error);result['cleanup_complete']=False;result['ok']=False
        if acquired:_LOCK.release()
        result['seconds']=round(time.monotonic()-started,3)
    return result
