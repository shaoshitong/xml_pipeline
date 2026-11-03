"""Baseline-preserving admission: a duplicate code OR exact RGBA is not new.

Callers must supply already verified payload hashes and dimension-prefixed RGBA
hashes. This module performs no rendering, source validation or acceptance by
itself; it only filters identities after the caller's strict QA gates.
"""
from collections import defaultdict

def identity(row):
    image = row['image_pixels']
    code = row['code_sha256']
    rgba = image['rgba_sha256']
    width, height = image['width'], image['height']
    if not isinstance(width, int) or not isinstance(height, int) or min(width, height) <= 0:
        raise ValueError('invalid_verified_image_dimensions')
    for value in (code, rgba):
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('invalid_verified_identity_SHA256')
    return code, (width, height, rgba)

def admit_unique(baseline, candidates):
    """Keep baseline untouched; deterministically admit disjoint new identities.

    Candidates must already be in deterministic priority order. Rejected rows do
    not reserve their *other* identity: an A/P duplicate cannot suppress a later
    distinct B/P result when A/P was rejected only for baseline code A.
    """
    codes, images = defaultdict(list), defaultdict(list)
    def label(row, index, origin):
        return row.get('goal500_pair_id') or row.get('id') or f'{origin}:{index}'
    def remember(row, index, origin):
        code, pixels = identity(row)
        name = label(row, index, origin)
        codes[code].append(name)
        images[pixels].append(name)
    for i, row in enumerate(baseline):
        remember(row, i, 'baseline')
    admitted, rejected = [], []
    for i, row in enumerate(candidates):
        code, pixels = identity(row)
        reasons = {}
        if code in codes:
            reasons['duplicate_code_SHA256'] = list(codes[code])
        if pixels in images:
            reasons['duplicate_dimensions_prefixed_RGBA_SHA256'] = list(images[pixels])
        if reasons:
            rejected.append(dict(candidate=label(row, i, 'candidate'), reasons=reasons))
        else:
            admitted.append(row)
            remember(row, i, 'candidate')
    return admitted, rejected
