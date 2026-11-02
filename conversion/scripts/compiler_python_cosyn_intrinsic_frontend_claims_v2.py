"""Frozen integer-viewport source frontend with read-only legacy claim proof."""
import hashlib
import json
from pathlib import Path

import compiler_python_cosyn_intrinsic_frontend_v2 as frozen
import compiler_python_cosyn_intrinsic_claims_v2 as claims

R,W=frozen.R,frozen.W
VERSION='compiler_python_cosyn_intrinsic_frontend_claims_v2'
UNIT=frozen.UNIT
original=frozen.original
ordinary_queue_status=frozen.ordinary_queue_status
sha=lambda value:hashlib.sha256(value).hexdigest()


def configuration(data_root=R):
    original_config=frozen.configuration(data_root);pins={**original_config['pins']}
    for name in ('compiler_python_cosyn_intrinsic_frontend_claims_v2.py','compiler_python_cosyn_intrinsic_quality_ro_claims_v2.py','compiler_python_cosyn_intrinsic_claims_v2.py'):
        path=W/'scripts'/name;pins[str(path)]=sha(path.read_bytes())
    return {**original_config,'policy':VERSION+':'+sha(json.dumps(pins,sort_keys=True).encode())[:20],'pins':pins,'frozen_integer_viewport_source_frontend':original_config['policy'],'legacy_canonical_claims_read_only':True}


def static_support(given):
    result=frozen.static_support(given)
    if result['supported']:
        _,job=original(None,given);result['canonical_worker_claim']=claims.inspect(job)
    return result


def convert(record,given,work):
    _,job=original(record,given);claim=claims.inspect(job)
    if claim['blocked']:return dict(ok=False,reason='deferred_live_or_unproved_canonical_worker_claim',canonical_worker_claim=claim,normal_source_conversion_called=False,infrastructure_failure=False,model_calls=0)
    attempt=frozen.convert(record,given,work)
    return {**attempt,'canonical_worker_claim':claim,'normal_source_conversion_called':not str(attempt.get('reason','')).startswith('deferred_')}
