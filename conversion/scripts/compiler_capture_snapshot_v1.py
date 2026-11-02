"""Hash-bound capture inputs. Changes after selection are infrastructure drift."""
import hashlib
import json
from pathlib import Path

R=Path('/backup/shaoshitong/img2code_20261029')
VERSION='compiler_capture_snapshot_v1'


def sha(blob):return hashlib.sha256(blob).hexdigest()


def read(locator,clean=False):
    if not isinstance(locator,str) or Path(locator).is_absolute() or '..' in Path(locator).parts:
        raise RuntimeError('infrastructure_capture_invalid_locator')
    try:path=(R/locator).resolve(strict=True)
    except OSError as error:raise RuntimeError('infrastructure_capture_payload_unreadable:'+locator) from error
    floor=(R/'clean').resolve() if clean else R.resolve()
    if not path.is_relative_to(floor):raise RuntimeError('infrastructure_capture_outside_owner')
    try:return path.read_bytes()
    except OSError as error:raise RuntimeError('infrastructure_capture_payload_unreadable:'+locator) from error


def seal_snapshot(record,selected_evidence=None):
    evidence=selected_evidence or {}
    result=dict(schema=VERSION,id=record['id'],source_code_sha256=record['source_code_sha256'],
                source_image_sha256=record['source_image_sha256'])
    for key,path_key,clean in [('source_dot','source_render_dot',True),('source_svg','source_render_svg',True),
                               ('execution_audit','execution_audit',False)]:
        locator=record[path_key];blob=read(locator,clean);digest=sha(blob)
        if evidence and evidence.get(key+'_sha256')!=digest:
            raise RuntimeError('infrastructure_capture_differs_from_selected_snapshot:'+key)
        if key=='source_svg' and record['source_render_svg_sha256']!=digest:
            raise RuntimeError('infrastructure_capture_record_svg_hash_changed')
        result[key]=locator;result[key+'_sha256']=digest
    audit=json.loads(read(result['execution_audit']))
    if (audit.get('id'),audit.get('source_code_sha256'))!=(record['id'],record['source_code_sha256']):
        raise RuntimeError('infrastructure_capture_audit_identity_changed')
    returned=str(Path(audit['directory'])/'returned_image.png')
    result.update(returned_png=returned,returned_png_sha256=sha(read(returned)))
    if record.get('original_source_data'):
        payload=read(record['original_source_data'],True);digest=sha(payload)
        if digest!=record['source_data_sha256']:
            raise RuntimeError('infrastructure_capture_source_data_changed')
        result.update(original_source_data=record['original_source_data'],source_data_sha256=digest)
    check_snapshot(record,result)
    return result


def check_snapshot(record,snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('schema')!=VERSION:
        raise RuntimeError('infrastructure_missing_frozen_capture_snapshot')
    if not all(key in snapshot for key in ('id','source_code_sha256','source_image_sha256',
            'source_dot','source_dot_sha256','source_svg','source_svg_sha256',
            'execution_audit','execution_audit_sha256','returned_png','returned_png_sha256')):
        raise RuntimeError('infrastructure_incomplete_frozen_capture_snapshot')
    for key in ('id','source_code_sha256','source_image_sha256'):
        if snapshot.get(key)!=record.get(key):
            raise RuntimeError('infrastructure_capture_source_identity_changed:'+key)
    for key,path_key,clean in [('source_dot','source_render_dot',True),('source_svg','source_render_svg',True),
                               ('execution_audit','execution_audit',False)]:
        if record.get(path_key)!=snapshot.get(key):
            raise RuntimeError('infrastructure_capture_locator_changed:'+key)
        if sha(read(snapshot[key],clean))!=snapshot.get(key+'_sha256'):
            raise RuntimeError('infrastructure_capture_payload_changed:'+key)
    if record.get('source_render_svg_sha256')!=snapshot['source_svg_sha256']:
        raise RuntimeError('infrastructure_capture_record_svg_digest_changed')
    audit=json.loads(read(snapshot['execution_audit']))
    if (audit.get('id'),audit.get('source_code_sha256'))!=(record['id'],record['source_code_sha256']):
        raise RuntimeError('infrastructure_capture_execution_identity_changed')
    returned=str(Path(audit['directory'])/'returned_image.png')
    if returned!=snapshot['returned_png'] or sha(read(returned))!=snapshot['returned_png_sha256']:
        raise RuntimeError('infrastructure_capture_returned_image_changed')
    if record.get('original_source_data'):
        if record['original_source_data']!=snapshot.get('original_source_data') or record.get('source_data_sha256')!=snapshot.get('source_data_sha256'):
            raise RuntimeError('infrastructure_capture_data_identity_changed')
        if sha(read(snapshot['original_source_data'],True))!=snapshot['source_data_sha256']:
            raise RuntimeError('infrastructure_capture_data_payload_changed')
    return dict(ok=True,schema=VERSION,source_dot_sha256=snapshot['source_dot_sha256'],
                source_svg_sha256=snapshot['source_svg_sha256'],execution_audit_sha256=snapshot['execution_audit_sha256'],
                returned_png_sha256=snapshot['returned_png_sha256'])
