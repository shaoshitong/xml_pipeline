"""Validate the strict renderer's actual padded-pixel and DOM-bound evidence."""
def validate(info, width, height):
    def need(value, message):
        if not value:
            raise ValueError('strict_native_canvas_evidence:' + message)
    need(info.get('selected_image') == 'declared_first_page', 'wrong_selected_page')
    need(info.get('output_size') == [width, height], 'wrong_canvas')
    need(info.get('content_outside_declared_canvas') is False, 'content_outside_page')
    need(info.get('probe_includes_actual_dom_paint_bounds') is True, 'DOM_paint_not_covered')
    boundary = info.get('outside_page_pixel_audit') or {}
    need(boundary.get('audit_always_performed') is True, 'missing_unconditional_pixel_audit')
    need(boundary.get('white_threshold') == 255, 'nonexact_white_threshold')
    need(boundary.get('nonwhite_outside_pixels') == 0, 'visible_pixels_outside_page')
    need(boundary.get('minimum_probe_margin') == 32, 'wrong_minimum_margin')
    offset = boundary.get('offset')
    padded = boundary.get('padded_native_render_size')
    need(isinstance(offset, list) and isinstance(padded, list) and len(offset) == len(padded) == 2, 'missing_probe_geometry')
    need(all(type(value) is int for value in offset + padded), 'noninteger_probe_geometry')
    need(min(offset) >= 32 and padded[0] >= width + offset[0] + 32 and padded[1] >= height + offset[1] + 32, 'incomplete_padded_coverage')
    return True
