"""Pure typed runtime-failure classification for fixed compiler orchestration.

Never stringify a payload, scan dictionary keys, recurse into ordinary detail,
or inspect record/source/candidate data. A false infrastructure flag is simply
false. Recognized exception envelopes and standard failure records provide
positive evidence; labels, source text and ordinary diagnostic data do not.
"""
import re

VERSION='typed_runtime_failure_without_payload_key_scanning_v1'
EXCEPTIONS=frozenset(('ImportError','ModuleNotFoundError','TargetClosedError','BrowserClosedError','BrowserCrashedError','ConnectionClosedError'))
_INFRA=re.compile(r'^(?:[A-Za-z_.]+Error:\s*)?(infrastructure_[A-Za-z0-9_]+)(?::|\s*$)')
_METHOD=re.compile(r'^(?:[A-Za-z_.]+Error:\s*)?(?:Page|Browser|BrowserType|BrowserContext|Target|Connection|Driver)\.[A-Za-z_]+:')
_RUNTIME=('Target page, context or browser has been closed','Browser has been closed','Browser crashed',
          'Connection closed while reading from the driver','Unable to capture screenshot',"Executable doesn't exist at",
          'error while loading shared libraries')


def _messages(value):
    if not isinstance(value,str):return []
    lines=[line.strip()for line in value.splitlines()if line.strip()]
    if not lines:return []
    # A real traceback has a typed final line. Arbitrary multi-line source text
    # does not turn its later lines into environment diagnostics.
    return [lines[0],lines[-1]]if lines[0].startswith('Traceback (most recent call last):')else[lines[0]]


def _message(value,path,allow_exception,allow_reason=True):
    for line in _messages(value):
        match=_INFRA.match(line)
        if allow_reason and match and match[1]!='infrastructure_failure':return dict(infrastructure_failure=True,basis='explicit_infrastructure_reason',path=path,reason=match[1])
        if allow_exception and ':'in line:
            typename=line.partition(':')[0].rsplit('.',1)[-1]
            if typename in EXCEPTIONS:return dict(infrastructure_failure=True,basis='actual_exception_message',path=path,exception_type=typename)
        prefix=line.removeprefix('Error: ').removeprefix('RuntimeError: ')
        if any(prefix.startswith(message)for message in _RUNTIME)or _METHOD.match(line)and any(message in line for message in _RUNTIME):
            return dict(infrastructure_failure=True,basis='actual_runtime_message',path=path,message=line[:1500])
    return None


def _envelope(value,path):
    if not isinstance(value,dict):return None
    if value.get('infrastructure_failure')is True:return dict(infrastructure_failure=True,basis='explicit_boolean_true',path=path+'.infrastructure_failure')
    for field in ('error_type','exception_type'):
        typename=value.get(field)
        if isinstance(typename,str)and typename.rsplit('.',1)[-1]in EXCEPTIONS:
            return dict(infrastructure_failure=True,basis='typed_exception_field',path=path+'.'+field,exception_type=typename)
    for field in ('reason','error','message'):
        result=_message(value.get(field),path+'.'+field,allow_exception=field!='reason')
        if result:return result
    # detail is ordinary data, not an error envelope. A shallow string may
    # carry a definite browser/runtime message; import-like source prose and
    # all nested mappings/lists remain ordinary data.
    result=_message(value.get('detail'),path+'.detail',allow_exception=False,allow_reason=False)
    if result:return result
    return None


def diagnose(payload=None,*,exception=None):
    """Return positive typed evidence, or a stable false diagnosis.

    ``exception`` accepts an actual caught exception. ``payload`` accepts a
    result/error envelope, with optional standard ``failures`` list of error
    envelopes or runtime-message strings. Ordinary detail is never traversed.
    """
    if exception is None and isinstance(payload,BaseException):exception=payload;payload=None
    if exception is not None:
        if not isinstance(exception,BaseException):raise TypeError('exception_must_be_an_actual_caught_exception')
        if isinstance(exception,(ImportError,ModuleNotFoundError))or type(exception).__name__ in EXCEPTIONS:
            return dict(infrastructure_failure=True,basis='actual_exception_type',path='exception',exception_type=type(exception).__name__)
        result=_message(str(exception),'exception.message',allow_exception=True)
        if result:return result
    result=_envelope(payload,'result')
    if result:return result
    if isinstance(payload,dict)and isinstance(payload.get('failures'),list):
        for index,item in enumerate(payload['failures']):
            path='result.failures['+str(index)+']'
            result=_envelope(item,path)if isinstance(item,dict)else _message(item,path,allow_exception=True)
            if result:return result
    return dict(infrastructure_failure=False,basis='no_positive_typed_runtime_evidence')


def is_infrastructure(payload=None,*,exception=None):return diagnose(payload,exception=exception)['infrastructure_failure']


def diagnostic_messages(payload):
    """Controlled reason values for failure grouping, not infra inference."""
    if not isinstance(payload,dict):return []
    values=[]
    for field in ('reason','error','message'):
        if isinstance(payload.get(field),str):values.append(payload[field])
    detail=payload.get('detail')
    if isinstance(detail,str):values.append(detail)
    elif isinstance(detail,dict):
        for field in ('reason','error','message'):
            if isinstance(detail.get(field),str):values.append(detail[field])
    if isinstance(payload.get('failures'),list):
        for item in payload['failures']:
            if isinstance(item,str):values.append(item)
            elif isinstance(item,dict):
                for field in ('reason','error','message'):
                    if isinstance(item.get(field),str):values.append(item[field])
    return values
