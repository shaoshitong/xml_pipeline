"""Reject hierarchy lowering that moves source paint across another peer."""
import hashlib
import json


def verify(model_root, source_objects, marker_reports=(), label_reports=()):
    source = [obj['id'] for obj in source_objects]
    if len(source) != len(set(source)):
        raise ValueError('source_paint_ID_order_not_unique')
    positions = {identifier: index for index, identifier in enumerate(source)}
    removed = set()
    marker_blocks = {}
    for role in marker_reports:
        marker, edge = role['source_object'], role['edge']
        if marker not in positions or edge not in positions or marker in removed or role['side'] not in ('start', 'end'):
            raise ValueError('source_marker_paint_role_invalid')
        removed.add(marker)
        marker_blocks.setdefault(edge, []).append(marker)
    for edge, markers in marker_blocks.items():
        block = sorted(positions[key] for key in [edge, *markers])
        if block[0] != positions[edge] or block != list(range(block[0], block[-1] + 1)):
            raise ValueError('source_marker_paint_block_interleaved_with_peer')
    expected = [identifier for identifier in source if identifier not in removed]
    elements = list(model_root)
    cells = {cell.get('id'): cell for cell in elements}
    if None in cells or len(cells) != len(elements):
        raise ValueError('native_paint_cell_ID_missing_or_duplicate')
    if any(marker in cells for marker in removed):
        raise ValueError('source_marker_role_was_not_lowered_exactly_once')
    groups = {row['label_group'] for row in label_reports}
    unknown = set(cells) - set(source) - {'0', '1'}
    if unknown != groups:
        raise ValueError('native_non_source_paint_cell_not_an_explicit_label_container')
    for identifier in groups:
        cell = cells[identifier]
        style = cell.get('style', '')
        if cell.get('value', '') or 'fillColor=none;' not in style or 'strokeColor=none;' not in style:
            raise ValueError('native_label_container_would_add_paint')
    children = {}
    for cell in elements:
        parent = cell.get('parent')
        if parent is not None:
            if parent not in cells:
                raise ValueError('native_paint_parent_missing')
            children.setdefault(parent, []).append(cell.get('id'))
    visited, active, actual = set(), set(), []

    def walk(identifier):
        if identifier in active or identifier in visited:
            raise ValueError('native_paint_hierarchy_cycle_or_duplicate_visit')
        active.add(identifier)
        visited.add(identifier)
        if identifier in positions:
            actual.append(identifier)
        for child in children.get(identifier, []):
            walk(child)
        active.remove(identifier)

    if '0' not in cells:
        raise ValueError('native_paint_root_missing')
    walk('0')
    if visited != set(cells) or actual != expected:
        raise ValueError('source_paint_order_changed_by_native_hierarchy')
    digest = lambda values: hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()
    return dict(policy='exact_SOURCE_peer_order_after_explicit_native_marker_lowering_v2',
                original_source_paint_objects=len(source), preserved_source_objects=len(actual),
                source_order_sha256=digest(expected), native_model_DFS_order_sha256=digest(actual),
                exact_source_peer_paint_order=True, lowered_marker_roles=list(marker_reports),
                model_container_count=len(groups))
