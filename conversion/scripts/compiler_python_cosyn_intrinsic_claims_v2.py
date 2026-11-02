"""Read-only legacy canonical worker claims; never erase or acquire a claim."""
import datetime
import os
from pathlib import Path


def inspect(job,process_identity=None,boot_time=None,ticks_per_second=None):
    stored=job[12]
    result=dict(stored_worker_pid=stored,canonical_claim_changed=False,read_only=True,blocked=False)
    if stored is None:return {**result,'disposition':'no_canonical_worker_claim'}
    try:pid=int(stored)
    except (TypeError,ValueError):return {**result,'blocked':True,'disposition':'unproved_malformed_canonical_worker_claim'}
    if pid<=0:return {**result,'disposition':'nonpositive_stale_canonical_worker_claim'}
    if process_identity is None:
        from initial_conversion_process_v1 import identity
        process_identity=identity
    current=process_identity(pid)
    result['current_process_identity']=current
    if not current or current.get('state')=='Z':return {**result,'disposition':'dead_canonical_worker_claim_preserved'}
    try:
        timestamp=datetime.datetime.fromisoformat(str(job[8]).replace('Z','+00:00'))
        if timestamp.tzinfo is None:raise ValueError('claim_timestamp_has_no_timezone')
        if boot_time is None:boot_time=int(next(line.split()[1]for line in Path('/proc/stat').read_text().splitlines()if line.startswith('btime ')))
        ticks_per_second=ticks_per_second or os.sysconf('SC_CLK_TCK')
        birth=float(boot_time)+int(current['start_ticks'])/ticks_per_second
        result.update(current_process_birth_epoch=birth,stored_claim_updated_epoch=timestamp.timestamp())
        # btime is integer seconds; leave a full second safety margin. A newer
        # process cannot own this older unmodified canonical row's PID claim.
        if birth>timestamp.timestamp()+1:return {**result,'disposition':'time_proved_reused_PID_claim_preserved'}
    except (OSError,ValueError,TypeError,KeyError,StopIteration):
        return {**result,'blocked':True,'disposition':'live_process_without_provable_legacy_claim_birth_binding'}
    return {**result,'blocked':True,'disposition':'potentially_live_canonical_worker_claim'}
