"""Publish consistent current descriptors while preserving every data byte."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import uuid

R = Path('/backup/shaoshitong/img2code_20261029')
C = R / 'clean/complexity_curation_20261102T054553Z_v1'


def raw(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def asset(path):
    data = path.read_bytes()
    return dict(file=str(path.relative_to(R)), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def checked(ref):
    path = (R / ref['file']).resolve(strict=True)
    assert path.is_relative_to((R / 'clean').resolve())
    actual = asset(path)
    assert all(actual[k] == ref[k] for k in actual)
    return path


def main():
    before = (C / 'current.json').read_bytes()
    current = json.loads(before)
    parent = json.loads(checked(current['summary']).read_bytes())
    for ref in current['views'].values():
        checked(ref)
    main_ref = current['views']['paired_priority_complex']
    count = sum(bool(line.strip()) for line in checked(main_ref).read_bytes().splitlines())
    assert count == main_ref['rows'] == current['paired_priority_complex']
    now = datetime.datetime.now(datetime.timezone.utc)
    output = C / ('published_current_' + now.strftime('%Y%m%dT%H%M%S%fZ') + '_metadata_v6')
    output.mkdir()
    (output / 'previous_current_snapshot.json').write_bytes(before)
    summary = {**parent, 'schema': 'consistent_curation_summary_v6',
               'at_utc': now.isoformat(), 'root': str(output),
               'files': {**parent.get('files', {}), **current['views']},
               'files_new_in_this_snapshot': {},
               'inherited_previous_new_files': parent.get('files_new_in_this_snapshot', {}),
               'metadata_repair': 'Current view descriptors reconciled to the verified atomic pointer; pair files unchanged.',
               'new_QA_calls': 0, 'new_conversions': 0,
               'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / 'summary.json').write_bytes(raw(summary))
    (output / 'hash_inventory.json').write_bytes(raw(dict(
        views=current['views'], summary=asset(output / 'summary.json'),
        parent_pointer=asset(output / 'previous_current_snapshot.json'))))
    updated = {**current, 'schema': 'curated_current_pointer_v6',
               'at_utc': now.isoformat(), 'snapshot': str(output.relative_to(R)),
               'summary': asset(output / 'summary.json'),
               'hash_inventory': asset(output / 'hash_inventory.json'),
               'previous_current_snapshot': asset(output / 'previous_current_snapshot.json')}
    assert (C / 'current.json').read_bytes() == before
    temporary = C / ('current.' + uuid.uuid4().hex + '.tmp')
    temporary.write_bytes(raw(updated))
    os.replace(temporary, C / 'current.json')
    for path in output.iterdir():
        path.chmod(0o444)
    assert json.loads(checked(updated['summary']).read_bytes())['files']['paired_priority_complex'] == main_ref
    print(json.dumps(dict(paired_priority_complex=count, pair_file_unchanged=True,
                          summary_descriptors_consistent=True, current_pointer=asset(C / 'current.json'))))


if __name__ == '__main__':
    main()
