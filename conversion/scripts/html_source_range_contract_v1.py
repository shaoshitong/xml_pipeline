"""Separate logical selection slots from physical glyph paint at run boundaries.

This contract never accepts an image or declares visual equivalence. Boundary
slot exceptions require a separate, bit-exact full SOURCE/native text-paint
comparison. Interior glyph placement, every baseline, fonts and source clipping
remain independently checked. No target-image parameter is used.
"""
import math
import statistics


def evaluate(residuals, font_size, tolerance=.08, maximum_translation=8.):
    result = dict(ok=False, aligned=False, errors=[], boundary_slot_exceptions=[],
                  requires_exact_source_native_ink=True,
                  does_not_prove_paint_equality=True)
    if not residuals or not math.isfinite(font_size) or font_size <= 0:
        result['errors'].append('missing_finite_source_glyph_metrics')
        return result
    if not all(all(isinstance(r.get(k), (int, float)) and math.isfinite(r[k])
                   for k in ('dx', 'dy', 'dw', 'dh')) for r in residuals):
        result['errors'].append('nonfinite_or_missing_range_residual')
        return result
    # Interior cursors determine the common run placement. A first character's
    # selection slot may include kerning allocated outside this source fragment.
    stable = residuals[1:-1] if len(residuals) > 2 else residuals[-1:]
    dx = statistics.median(r['dx'] for r in stable)
    dy = statistics.median(r['dy'] for r in residuals)
    result['translation'] = dict(dx=dx, dy=dy)
    if max(abs(dx), abs(dy)) > maximum_translation:
        result['errors'].append('source_translation_exceeds_finite_contract')
    for index, row in enumerate(residuals):
        xerr, yerr = abs(row['dx'] - dx), abs(row['dy'] - dy)
        if yerr > tolerance or abs(row['dh']) > tolerance:
            result['errors'].append(dict(index=index, reason='baseline_or_range_height_changed'))
            continue
        if max(xerr, abs(row['dw'])) <= tolerance:
            continue
        if (len(residuals) > 1 and index == 0 and
                abs(row['dx'] - dx + row['dw']) <= tolerance and
                abs(row['dw']) <= font_size):
            result['boundary_slot_exceptions'].append(dict(
                index=index, kind='leading_slot_right_edge_congruent',
                dx=row['dx'], dw=row['dw']))
        elif index == len(residuals) - 1 and xerr <= tolerance and abs(row['dw']) <= font_size:
            result['boundary_slot_exceptions'].append(dict(
                index=index, kind='unused_trailing_selection_advance',
                dx=row['dx'], dw=row['dw']))
        else:
            result['errors'].append(dict(index=index, reason='interior_or_unexplained_range_change'))
    result['ok'] = not result['errors']
    result['aligned'] = result['ok'] and max(abs(dx), abs(dy)) <= tolerance
    result['all_baselines_and_interior_cursors_checked'] = True
    result['maximum_original_slot_position_residual'] = max(
        max(abs(r['dx']), abs(r['dy'])) for r in residuals)
    return result


def from_analysis(row, **kwargs):
    return evaluate(row.get('residuals', []), row.get('source_font_size', 0), **kwargs)
