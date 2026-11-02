"""Bounded SQLite lock waiting without replaying producer mutations.

BEGIN/COMMIT waiting has its own budget; conversion and filesystem work are not
charged to it. This helper sets connection busy_timeout=0 and leaves it there;
only its explicit budget may wait. Producers retain receipts, CAS and intents.
"""
import math
import sqlite3
import time
from durable_sqlite import begin as durable_begin,commit as durable_commit


def is_busy(error):
    if not isinstance(error,sqlite3.OperationalError):return False
    code=getattr(error,'sqlite_errorcode',None)
    if isinstance(code,int):return (code&255) in (getattr(sqlite3,'SQLITE_BUSY',5),getattr(sqlite3,'SQLITE_LOCKED',6))
    message=str(error).lower().strip()
    return message.startswith(('database is locked','database table is locked','database schema is locked','database is busy'))


class BusyBudgetExceeded(TimeoutError):
    def __init__(self,diagnostics):
        self.diagnostics=diagnostics
        super().__init__('Bounded SQLite admission wait exhausted')


class BusyBudget:
    def __init__(self,seconds=60,step_seconds=5):
        if any(isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0 for value in [seconds,step_seconds]):raise ValueError('Positive finite SQLite wait/step budgets required')
        self.limit=float(seconds);self.step=float(step_seconds);self.waited=0.;self.begins=0;self.commits=0;self.busy_events=0;self.last_error=None
    def diagnostics(self):
        return {'begin_attempts':self.begins,'commit_attempts':self.commits,'attempts':self.begins,'busy_events':self.busy_events,'wait_seconds':round(self.waited,6),'wait_budget_seconds':self.limit,'step_seconds':self.step,'last_error':self.last_error}
    def remaining(self):return max(0.,self.limit-self.waited)
    def _ensure(self):
        if self.remaining()<=0:raise BusyBudgetExceeded(self.diagnostics())
    def _call(self,operation):
        self._ensure();started=time.monotonic()
        try:return operation(min(self.step,self.remaining()))
        finally:self.waited+=time.monotonic()-started
    def retry(self,error):
        if not is_busy(error):raise error
        self.busy_events+=1;self.last_error={'type':type(error).__name__,'sqlite_errorcode':getattr(error,'sqlite_errorcode',None),'message':str(error)[:180]};self._ensure()
        delay=min(.05*2**min(self.busy_events,4),1.,self.remaining());started=time.monotonic();time.sleep(delay);self.waited+=time.monotonic()-started;self._ensure()
    def begin(self,db):
        if db.in_transaction:raise RuntimeError('Admission cannot borrow a preexisting transaction')
        db.execute('PRAGMA busy_timeout=0')
        while True:
            self.begins+=1
            try:return self._call(lambda seconds:durable_begin(db,seconds=seconds))
            except sqlite3.OperationalError as error:
                if db.in_transaction or not is_busy(error):raise
                self.retry(error)
    def commit(self,db):
        if not db.in_transaction:raise RuntimeError('Commit requires the producer transaction')
        db.execute('PRAGMA busy_timeout=0')
        while True:
            self.commits+=1
            try:return self._call(lambda seconds:durable_commit(db,seconds=seconds))
            except sqlite3.OperationalError as error:
                # A vanished transaction needs the producer's nonce receipt
                # probe; repeating COMMIT cannot tell whether it succeeded.
                if not db.in_transaction or not is_busy(error):raise
                self.retry(error)
