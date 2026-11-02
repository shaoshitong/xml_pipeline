"""Reference registration for the batch font/space/clip quality policy."""
from auto_quality_common_v3 import *
from auto_quality_common_v3 import registration_record as _previous_registration

POLICY='bounded_deterministic_font_text_layout_and_native_quality_v4'


def registration_record(record, reference, xml):
    if record.get('html_text_layout_v5'):
        from html_text_layout_registration_v5 import registration_record as layout_registration
        return layout_registration(record,reference,xml)
    return _previous_registration(record,reference,xml)
