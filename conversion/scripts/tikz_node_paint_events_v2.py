"""Read PGF node-to-driver-paint provenance without evaluating TeX."""
import collections
import re

from tikz_execution_graph import ARITY as LEGACY_ARITY, parse_events as parse_legacy

EXTRA_ARITY = {'nodeowner': 3, 'nodepaint': 6, 'ownershipcomplete': 2}
ARITY = {**LEGACY_ARITY, **EXTRA_ARITY}


def parse_events(data):
    events = []
    position = 0
    while position < len(data):
        while position < len(data) and data[position].isspace():
            position += 1
        if position == len(data):
            break
        match = re.match(r'\\IIC([A-Za-z]+)', data[position:])
        if not match or match[1] not in ARITY:
            raise ValueError('Unknown or corrupt source ownership event')
        kind = match[1]
        position += match.end()
        fields = []
        for _ in range(ARITY[kind]):
            while position < len(data) and data[position].isspace():
                position += 1
            if position == len(data) or data[position] != '{':
                raise ValueError('Missing source ownership field:' + kind)
            start = position + 1
            position += 1
            depth = 1
            while position < len(data) and depth:
                if data[position] == '\\' and position + 1 < len(data) and not data[position + 1].isalpha():
                    position += 2
                    continue
                if data[position] == '{':
                    depth += 1
                if data[position] == '}':
                    depth -= 1
                position += 1
            if depth:
                raise ValueError('Truncated source ownership field:' + kind)
            fields.append(data[start:position - 1])
        events.append({'kind': kind, 'fields': fields})
    # Apply the existing strict session/header/trailer checks as well.
    legacy = legacy_events(events)
    encoded = ''.join('\\IIC' + event['kind'] + ''.join('{' + x + '}' for x in event['fields'])
                      for event in legacy)
    if parse_legacy(encoded) != legacy:
        raise ValueError('Legacy execution event reconstruction changed')
    return events


def legacy_events(events):
    return [event for event in events if event['kind'] not in EXTRA_ARITY]


def ownership(events):
    nodes = {(event['fields'][0], event['fields'][2]): event for event in events
             if event['kind'] == 'node'}
    if len(nodes) != sum(event['kind'] == 'node' for event in events):
        raise ValueError('Duplicate executed node serial in source ownership trace')
    owners = {}
    serials = {}
    paints = []
    complete = []
    for event in events:
        fields = event['fields']
        if event['kind'] == 'nodeowner':
            picture, serial, owner = fields
            if (picture, serial) not in nodes or (picture, serial) in serials or owner in owners:
                raise ValueError('Source node ownership is not bijective')
            if not owner.isdecimal() or int(owner) <= 0:
                raise ValueError('Invalid source node ownership identity')
            owners[owner] = (picture, serial)
            serials[(picture, serial)] = owner
        elif event['kind'] == 'nodepaint':
            picture, owner, sequence, mode, current, processed = fields
            if mode not in ('fill', 'stroke', 'fillstroke') or not sequence.isdecimal() or int(sequence) <= 0:
                raise ValueError('Invalid actual source driver paint event')
            paints.append(dict(picture=picture, owner=owner, sequence=int(sequence), mode=mode,
                               current_softpath=current, processed_softpath=processed))
        elif event['kind'] == 'ownershipcomplete':
            complete.append(fields)
    if len(complete) != 1 or any(not value.isdecimal() for value in complete[0]):
        raise ValueError('Source node ownership completion is missing or corrupt')
    count, paint_count = map(int, complete[0])
    if len(serials) != len(nodes) or count != len(nodes) or set(owners) != {str(x) for x in range(1, count + 1)}:
        raise ValueError('Source node ownership does not cover every executed node')
    if len(paints) != paint_count or [paint['sequence'] for paint in paints] != list(range(1, paint_count + 1)):
        raise ValueError('Actual source driver paint sequence is incomplete')
    by_serial = collections.defaultdict(list)
    for paint in paints:
        if paint['owner'] not in owners or owners[paint['owner']][0] != paint['picture']:
            raise ValueError('Actual source driver paint has no matching node owner')
        picture, serial = owners[paint['owner']]
        by_serial[picture + ':' + serial].append(paint)
    return dict(schema='PGF_executed_node_actual_driver_paint_ownership_v2',
                executed_nodes=len(nodes), driver_paints=len(paints),
                owners={picture + ':' + serial: owner for (picture, serial), owner in serials.items()},
                by_node=dict(by_serial), complete=True)
