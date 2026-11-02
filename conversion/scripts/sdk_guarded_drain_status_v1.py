"""Read-only status of the eight SDK sessions protected during user-requested drain.

No prompt, API, inspector connection, signal, database transaction or file write.
Response content is hashed remotely; only sizes, timestamps and usage leave it.
"""
import argparse
import collections
import datetime
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from sdk_inflight_drain_v1 import R, W, targets


def _at(value):
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def _proc(pid, argv=None):
    folder = Path('/proc') / str(pid)
    try:
        current = [v.decode() for v in (folder/'cmdline').read_bytes().split(b'\0') if v]
        state = re.search(r'^State:\s*(.*)', (folder/'status').read_text(), re.M)[1]
        return {'live': bool(current) and (argv is None or current == argv), 'state': state,
                'pid_reused': bool(current) and argv is not None and current != argv}
    except OSError:
        return {'live': False, 'state': 'exited', 'pid_reused': False}


def _file(path):
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'modified_at': datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat()}


def status(receipt=W/'sdk_model_drain_v1_receipt.json', *, root=R):
    root = Path(root)
    work = root/'conversion'
    source = json.loads(Path(receipt).read_text())
    report = {'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'source_receipt': str(receipt), 'covered': len(source['applied']),
              'guard_install_errors': source['errors'], 'sessions': []}
    db = sqlite3.connect('file:'+str(work/'jobs.sqlite')+'?mode=ro', uri=True, timeout=2)
    try:
        for target in source['applied']:
            folder = Path(target['session_dir']).resolve()
            if not folder.is_relative_to(work/'harness_sessions'):
                raise ValueError('Drain target outside owned sessions')
            identifier = folder.name.split('_')[1]
            installed = target['guard']['installed_at']
            stamp = _at(installed)
            events = []
            parse_errors = 0
            path = Path(target['receipt'])
            if path.exists():
                for line in path.read_text().splitlines():
                    try:
                        event = json.loads(line)
                        if event.get('pid') != target['pid']:
                            raise ValueError('guard event belongs to another pid')
                        events.append(event)
                    except (ValueError, TypeError):
                        parse_errors += 1
            calls = []
            for directory in sorted(p for p in folder.iterdir() if p.is_dir() and p.name != 'sdk_home'):
                call = directory/'call.json'
                response = directory/'response.txt'
                if not call.exists() and not response.exists():
                    continue
                item = {'label': directory.name, 'response': _file(response), 'events': _file(directory/'events.jsonl'),
                        'call_present': call.exists(),
                        'response_saved_after_guard': response.exists() and response.stat().st_mtime >= stamp}
                if call.exists():
                    meta = json.loads(call.read_text())
                    item['usage'] = meta.get('usage')
                    item['message_id'] = meta.get('message_id')
                    item['seconds'] = meta.get('seconds')
                    item['finish_reasons'] = meta.get('finish_reasons')
                calls.append(item)
            summary_path = folder/'summary.json'
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
            queue = db.execute('SELECT state,worker_pid,attempts,error FROM harness_queue_v3 WHERE id=?', (identifier,)).fetchone()
            job = db.execute('SELECT state,worker_pid,error FROM jobs WHERE id=?', (identifier,)).fetchone()
            kinds = collections.Counter(event.get('kind') for event in events)
            report['sessions'].append({'id': identifier, 'node_pid': target['pid'], 'parent_pid': target['ppid'],
                'node': _proc(target['pid'], target['argv']), 'parent': _proc(target['ppid']),
                'session_dir': str(folder.relative_to(root)), 'installed_at': installed,
                'guard_receipt': str(path.relative_to(root)), 'guard_kinds': dict(kinds),
                'guard_parse_errors': parse_errors,
                'all_blocked_events_prevent_upstream': all(event.get('upstream_send_performed') is False and event.get('charged') is False for event in events if str(event.get('kind')).startswith('blocked_')),
                'saved_calls': calls, 'responses_saved_after_guard': sum(item['response_saved_after_guard'] for item in calls),
                'summary': {k:summary.get(k) for k in ['result_state','finished_at_utc','error','baseline_error']},
                'queue': dict(zip(['state','worker_pid','attempts','error'],queue)) if queue else None,
                'job': dict(zip(['state','worker_pid','error'],job)) if job else None})
    finally:
        db.close()
    known = {r['node_pid'] for r in report['sessions']}
    current = targets(source['parents'])
    report['unexpected_sdk_children'] = [r for r in current if r['pid'] not in known]
    report['remaining_node_pids'] = [r['node_pid'] for r in report['sessions'] if r['node']['live']]
    report['remaining_job_ids'] = [r['id'] for r in report['sessions'] if r['queue'] and r['queue']['state']=='running']
    report['blocked_prompts'] = sum(r['guard_kinds'].get('blocked_prompt',0) for r in report['sessions'])
    report['blocked_model_posts'] = sum(r['guard_kinds'].get('blocked_model_POST',0) for r in report['sessions'])
    report['responses_saved_after_guard'] = sum(r['responses_saved_after_guard'] for r in report['sessions'])
    report['saved_response_sessions_after_guard'] = sum(bool(r['responses_saved_after_guard']) for r in report['sessions'])
    complete = (not report['guard_install_errors'] and not report['unexpected_sdk_children']
                and all(r['guard_kinds'].get('guards_installed') == 1 and not r['guard_parse_errors'] and r['all_blocked_events_prevent_upstream'] for r in report['sessions']))
    report['new_upstream_model_posts_permitted_by_installed_guards'] = 0 if complete else None
    report['upstream_evidence_scope'] = 'All covered SDK Node processes have installed prompt and global model-fetch guards; their local refusals never invoke upstream fetch. Saved responses/usage belong to previously sent work. No provider billing API is queried.'
    report['drained'] = not report['remaining_node_pids'] and not report['remaining_job_ids'] and not report['unexpected_sdk_children']
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=R)
    p.add_argument('--receipt', type=Path)
    args = p.parse_args(argv)
    print(json.dumps(status(args.receipt or args.root/'conversion/sdk_model_drain_v1_receipt.json', root=args.root), ensure_ascii=False))


if __name__=='__main__':
    main()
