"""Explicit validation identity aliases, independent of registry key kind.

Unknown family/provenance strings remain opaque clusters. Bare hashes in a
cluster are never guessed to mean an image, source file or sample identifier.
"""
import re

POLICY = 'explicit_original_identity_and_cross_kind_cluster_aliases_v1'
HASH = re.compile(r'[0-9a-fA-F]{64}\Z')
PREFIXES = {'id':'id', 'pair_sha256':'id', 'source_pair_sha256':'id',
            'code':'code', 'exact_original_code':'code', 'source_code_sha256':'code',
            'image':'image', 'exact_original_image':'image', 'source_image_sha256':'image'}


def normalize_pair(kind, value):
    if not isinstance(kind, str) or not kind or not isinstance(value, str) or not value:
        raise ValueError('validation_identity_key_not_nonempty_strings')
    original = value
    for _ in range(4):
        prefix, separator, rest = value.partition(':')
        if separator and prefix in ('hard_cluster', 'audit_cluster'):
            value = rest
        else:
            break
    prefix, separator, rest = value.partition(':')
    if separator and prefix in PREFIXES and HASH.fullmatch(rest):
        target = PREFIXES[prefix]
        if kind in ('id','code','image') and kind != target:
            raise ValueError('validation_typed_identity_alias_kind_conflict')
        return target, rest.lower()
    if kind in ('id', 'code', 'image'):
        if not HASH.fullmatch(value):
            raise ValueError('validation_typed_identity_is_not_sha256')
        return kind, value.lower()
    if kind in ('audit_cluster', 'hard_cluster', 'cluster'):
        return 'cluster', value
    return 'opaque_kind:' + kind, original


def normalize_keys(pairs):
    return frozenset(normalize_pair(kind, value) for kind, value in pairs)


def request_keys(item):
    source = item['source']
    pairs = [('id', item['id']), ('code', source['code_sha256']),
             ('image', source['image_sha256'])]
    if item.get('audit_cluster'):
        pairs.append(('audit_cluster', item['audit_cluster']))
    pairs.extend(('hard_cluster', key) for key in item.get('cluster_keys', ()))
    return normalize_keys(pairs)


def storage_keys(selected):
    """Write legacy-compatible aliases too, so old reservers also collide.

    This adds keys only to the newly created reservation. Existing reservations
    and key rows are never renamed, deleted, migrated or released.
    """
    result = set()
    for item in selected:
        result.add(('audit_cluster', item['audit_cluster']))
        result.update(('hard_cluster', key) for key in item['cluster_keys'])
        for kind, value in request_keys(item):
            if kind in ('id', 'code', 'image'):
                result.add((kind, value))
                result.add(('hard_cluster', kind + ':' + value))
                if kind in ('code', 'image'):
                    result.add(('hard_cluster', 'exact_original_' + kind + ':' + value))
            elif kind == 'cluster':
                result.add(('audit_cluster', value))
                result.add(('hard_cluster', value))
    return sorted(result)
