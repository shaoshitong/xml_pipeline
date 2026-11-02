"""Publish verified revisions with source/owner CAS and metadata rollback."""
import json
from pathlib import Path

from auto_quality_common import checked, sha
from auto_quality_dispatch_v2 import route_failure
from durable_sqlite import begin, commit
from native_worker import R, W, now

MODEL_TABLES = ('harness_queue', 'harness_queue_v2', 'harness_queue_v3')


def model_owned(db, identifier):
    for table in MODEL_TABLES:
        if not db.execute('select 1 from sqlite_master where type=\'table\' and name=?', (table,)).fetchone():
            continue
        columns = {r[1] for r in db.execute('pragma table_info(' + table + ')')}
        condition = "state='running'" + (' or worker_pid is not NULL' if 'worker_pid' in columns else '')
        if db.execute('select 1 from ' + table + ' where id=? and (' + condition + ')', (identifier,)).fetchone():
            return True
    return False


def atomic(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.quality-v3.tmp')
    temporary.write_bytes(data)
    temporary.replace(path)


def _route(report):
    reason = '; '.join(report['failures'])
    failures = report.get('checks', {}).get('source', {}).get('failures') or []
    reasons = [x.get('reason', '') if isinstance(x, dict) else str(x) for x in failures]
    if 'source_profile_not_implemented' in reason or reasons and all(x.startswith('unsupported') for x in reasons):
        return 'source_profile_extension'
    if any(x in ('source_profile_validation_error', 'source_graph_validation_error') for x in reasons):
        return 'resource_or_runtime_repair'
    if 'font_portability' in reason:
        return 'deterministic_font_embedding'
    if 'source_coverage_failure' in reason or 'raster_anomaly' in reason or 'native_marker_paint_failure' in reason:
        return 'source_geometry_or_harness'
    if any(x in reason for x in ('Native content', 'outside', 'canvas')):
        return 'deterministic_canvas_repair'
    return 'resource_or_runtime_repair'


def publish(db, item, report, out, work, enabled, policy):
    identifier, state, raw, input_raw, route = item
    previous = json.loads(raw)
    conversion = (R / previous['code_file']).parent / 'conversion.json'
    replacement = None
    original_metadata = None
    begin(db)
    try:
        current = db.execute('select state,output_record,input_record,worker_pid from jobs where id=?', (identifier,)).fetchone()
        queue_exists = db.execute("select 1 from sqlite_master where name='harness_queue_v3'").fetchone()
        if current != (state, raw, input_raw, None) or model_owned(db, identifier):
            report['state'] = 'stale_revision'
            out = None
        elif out and enabled:
            checked(R, previous['code_file'], previous['code_sha256'])
            checked(R, previous['image_file'], previous['image_sha256'])
            checked(R, out['code_file'], out['code_sha256'])
            fresh = (work / 'fresh.png').read_bytes()
            if sha(fresh) != out['image_sha256']:
                raise ValueError('Fresh native PNG changed after verification')
            for key in ('id', 'source_pair_sha256', 'source_code_sha256', 'source_image_sha256'):
                if key in previous and out.get(key) != previous[key]:
                    raise ValueError('Qualified output source identity changed: ' + key)
            archive = work / 'before'
            archive.mkdir(exist_ok=True)
            atomic(archive / 'conversion.json', raw.encode())
            atomic(archive / 'image.png', (R / previous['image_file']).read_bytes())
            # Both PNG versions remain intact across rollback or interrupted publication.
            atomic(R / out['image_file'], fresh)
            replacement = (json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode()
            original_metadata = conversion.read_bytes() if conversion.exists() else None
            atomic(conversion, replacement)
            db.execute("update auto_quality_exceptions_v1 set state='resolved_by_verified_revision',updated_at=? where id=? and state in ('pending','repaired_pending_batch_qa')", (now(), identifier))
            db.execute("update jobs set state='accepted',output_record=?,error=NULL,worker_pid=NULL,updated_at=? where id=?", (json.dumps(out, ensure_ascii=False), now(), identifier))
            if queue_exists:
                db.execute("update harness_queue_v3 set state='resolved',heartbeat=?,worker_pid=NULL,error=NULL where id=? and state!='running' and worker_pid is NULL", (now(), identifier))
            report['accepted'] = True
            report['state'] = 'accepted'
        elif current == (state, raw, input_raw, None) and enabled and report['state'] == 'repair_required':
            reason = '; '.join(report['failures'])
            repair_route = _route(report)
            db.execute('insert or replace into auto_quality_exceptions_v1 values(?,?,?,?,?,?,?,?)', (identifier, previous['code_sha256'], previous['image_sha256'], policy, repair_route, 'pending', reason, now()))
            updated = previous
            if repair_route == 'source_geometry_or_harness' and db.execute('select input_manifest from jobs where id=?', (identifier,)).fetchone()[0]:
                updated, dispatch = route_failure(db, previous, report, root=R)
                report['model_dispatch'] = dispatch
            if updated != previous:
                replacement = (json.dumps(updated, ensure_ascii=False, indent=2) + '\n').encode()
                original_metadata = conversion.read_bytes() if conversion.exists() else None
                atomic(conversion, replacement)
            target = 'needs_quality_repair' if repair_route != 'source_profile_extension' or state == 'accepted' else state
            db.execute('update jobs set state=?,output_record=?,error=?,updated_at=? where id=?', (target, json.dumps(updated, ensure_ascii=False), reason[:2500], now(), identifier))
        db.execute('insert or replace into auto_quality_audits_v1 values(?,?,?,?,?,?,?)', (identifier, previous['code_sha256'], previous['image_sha256'], policy, report['state'], json.dumps(report, ensure_ascii=False), now()))
        commit(db)
    except BaseException:
        db.rollback()
        report['accepted'] = False
        # The DB snapshot remains authoritative. Restore only our own failed write.
        if replacement is not None and conversion.exists() and conversion.read_bytes() == replacement:
            if original_metadata is None:
                conversion.unlink()
            else:
                atomic(conversion, original_metadata)
        raise
    atomic(work / 'audit.json', (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode())
