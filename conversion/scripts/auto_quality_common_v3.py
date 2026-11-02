"""Independent canvas and source-Range text-delta registration for batch QA."""
from auto_quality_common_v2 import *
from auto_quality_common_v2 import registration_record as _canvas_registration

POLICY = 'source_execution_glyph_lineage_native_render_and_local_fidelity_v3'


def registration_record(record, reference, xml):
    if record.get('html_actual_text_alignment'):
        from html_actual_text_registration import registration_record as glyph_registration
        return glyph_registration(record, reference, xml)
    return _canvas_registration(record, reference, xml)
