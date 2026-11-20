"""Account for provider replies completed after their DSH turn timed out."""

import json
from hashlib import sha256
from pathlib import Path


def interrupted_replies(root, store, episode, missing):
    if not missing:
        return []
    records = store.db.execute("""select id,stage,started,ended,request,response from calls
        where episode=? and role='generator' and completed=1 and status=200 and error is null
        order by id""", (episode,)).fetchall()
    proofs = []
    for record in records:
        number, stage, started, ended, request, response = record
        reply = store.get(response)
        tools = {t['id'] for t in reply['choices'][0]['message'].get('tool_calls', [])}
        if not tools or not tools <= missing:
            continue
        status = timeout_status(root, episode, stage, started, ended)
        origin = None
        if status is None:
            status, origin = deferred_request_timeout(root, store, episode, record, records)
        if status is None:
            status, origin = logged_timeout(root, store, episode, record, records)
        if status is None or consumed_later(store, records, number, tools):
            continue
        proofs.append({'call_id': number, 'request_ref': request, 'response_ref': response,
                       'supervision_eligible': False, 'tool_ids': sorted(tools),
                       'reason': 'reply_completed_after_turn_timeout_without_execution',
                       'timeout_status': str(status), 'timeout_written_at': status.stat().st_mtime,
                       'provider_started': started, 'provider_ended': ended,
                       'consumed_by_later_generator_requests': False})
        if origin is not None:
            proofs[-1]['request_origin'] = origin
            if origin['reason'] == 'timeout_status_preserved_in_collector_stdout':
                proofs[-1]['reason'] = 'reply_not_consumed_by_timed_out_turn'
                proofs[-1]['timeout_written_at'] = None
    return proofs


def logged_timeout(root, store, episode, record, records):
    """Recover overwritten status evidence from the actual collector stdout."""
    messages = store.get(record[4])['messages']
    resumed = resumed_turn_request(store, records, record, messages)
    if resumed is None:
        return None, None
    folder = Path(root) / 'episodes' / episode / 'generator' / f'round{record[1]}'
    events = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()
              if line.startswith('{') and line.endswith('}')]
    session = next((e['sessionId'] for e in events if e.get('type') == 'session'), None)
    calls = sum(e.get('type') == 'tool_call' for e in events)
    if session is None or any(e.get('type') == 'final' for e in events):
        return None, None
    for path in sorted(Path(root).parent.glob('main*.log')):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            try:
                state = json.loads(line)
            except ValueError:
                continue
            if not isinstance(state, dict) or not state.get('timed_out'):
                continue
            if (state.get('role'), state.get('round'), state.get('session_id'), state.get('log_dir'),
                state.get('exit'), state.get('completed'), state.get('tool_calls')) != (
                    'generator', record[1], session, folder.name, 124, False, calls):
                continue
            return path, {'reason': 'timeout_status_preserved_in_collector_stdout',
                          'line': number, 'line_sha256': sha256(line.encode()).hexdigest(),
                          'status': state, 'continuation_call_id': resumed[0],
                          'continuation_request_ref': resumed[4], 'pending_request_ref': record[4],
                          'exact_pending_prefix_retained': True,
                          'new_timeout_recovery_prompt_appended': True}
    return None, None


def timeout_paths(folder, stage):
    return list(folder.glob(f'round{stage}*/turn-status.json')) + list(folder.glob(f'round{stage}*/status.json'))


def stage_prompt(message, stage):
    if message.get('role') != 'user':
        return ''
    content = message.get('content', '')
    text = content if isinstance(content, str) else '\n'.join(
        part.get('text', '') for part in content if isinstance(part, dict))
    marker = f'Workspace paths: /case/reference.png; /case/round{stage}.drawio; /case/round{stage}.png.'
    return text if marker in text else ''


def deferred_request_timeout(root, store, episode, record, records):
    number, stage, started, ended, request, _ = record
    messages = store.get(request)['messages']
    folder = Path(root) / 'episodes' / episode / 'generator'
    for path in timeout_paths(folder, stage):
        state = json.loads(path.read_text())
        cutoff = path.stat().st_mtime
        if not state.get('timed_out') or not cutoff < started < ended:
            continue
        prior = prior_turn_request(store, records, record, messages, cutoff, state['seconds'])
        resumed = resumed_turn_request(store, records, record, messages)
        if prior is not None and resumed is not None:
            return path, {'reason': 'request_archived_after_timeout_from_the_expired_turn',
                          'prior_call_id': prior[0], 'prior_request_ref': prior[4],
                          'continuation_call_id': resumed[0], 'continuation_request_ref': resumed[4],
                          'pending_request_ref': request, 'pending_message_count': len(messages),
                          'exact_pending_prefix_retained': True,
                          'new_timeout_recovery_prompt_appended': True}
    return None, None


def prior_turn_request(store, records, record, messages, cutoff, seconds):
    for prior in reversed(records):
        if prior[0] >= record[0] or prior[1] != record[1] or not cutoff - seconds - 5 <= prior[2] <= prior[3] <= cutoff:
            continue
        earlier = store.get(prior[4])['messages']
        if not any(stage_prompt(message, record[1]) for message in earlier):
            continue
        if messages[:len(earlier)] != earlier:
            continue
        if not any(stage_prompt(message, record[1]) for message in messages[len(earlier):]):
            return prior
    return None


def resumed_turn_request(store, records, record, messages):
    for later in records:
        if later[0] <= record[0] or later[1] != record[1] or later[2] < record[3]:
            continue
        current = store.get(later[4])['messages']
        if len(current) <= len(messages) or current[:len(messages)] != messages:
            continue
        text = stage_prompt(current[len(messages)], record[1])
        if 'Host runtime recovery note:' in text and 'The previous turn reached its wall-clock limit.' in text:
            return later
    return None


def timeout_status(root, episode, stage, started, ended):
    folder = Path(root) / 'episodes' / episode / 'generator'
    for path in timeout_paths(folder, stage):
        state = json.loads(path.read_text())
        cutoff = path.stat().st_mtime
        if state.get('timed_out') and cutoff - state['seconds'] - 5 <= started <= cutoff < ended:
            return path
    return None


def consumed_later(store, records, number, tools):
    for later, _, _, _, request, _ in records:
        if later <= number:
            continue
        messages = store.get(request)['messages']
        referenced = {t['id'] for m in messages for t in m.get('tool_calls', [])}
        referenced.update(m.get('tool_call_id') for m in messages)
        if tools & referenced:
            return True
    return False


def write_annotations(root, proofs):
    folder = Path(root) / 'annotations'
    folder.mkdir(exist_ok=True)
    for proof in proofs:
        path = folder / f"{proof['call_id']}.json"
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(proof, indent=2) + '\n')
        temporary.replace(path)


def annotation(store, row):
    path = Path(store.root).parent / 'annotations' / f"{row['call_id']}.json"
    if not path.exists():
        return {'supervision_eligible': True}
    proof = json.loads(path.read_text())
    if any(proof[key] != row[key] for key in ('call_id', 'request_ref', 'response_ref')):
        raise ValueError('Interruption annotation does not match its archived call')
    return {'supervision_eligible': False, 'execution_annotation': proof}
