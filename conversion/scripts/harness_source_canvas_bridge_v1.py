"""Recover only proven reference dimensions/offset for a later Harness graph.

This never inherits an old graph's coverage, glyph alignment, execution binding,
font validation, pixel equality or acceptance. Current graph/source/render/font
checks are still required. No files, jobs, queues or model sessions are changed.
"""
import hashlib
import json
import math
import xml.etree.ElementTree as E
from pathlib import Path

R = Path('/backup/shaoshitong/img2code_20261029')
FIELD = 'source_reference_canvas_v1'
IDENTITY = ('id', 'source_code_sha256', 'source_image_sha256')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _source_provenance(record):
    from harness_source_provenance import validate_frozen
    proof = record.get('source_provenance')
    if not isinstance(proof, dict) or proof.get('version') != 1:
        raise ValueError('canvas_bridge_requires_frozen_source_provenance')
    origin = validate_frozen(proof)
    if any(origin.get(k) != record.get(k) or proof.get('identity', {}).get(k) != record.get(k) for k in IDENTITY):
        raise ValueError('canvas_bridge_source_provenance_identity_mismatch')
    return origin, proof


def _archive(relative, record, root):
    # This is a historical graph, not current source/graph acceptance evidence.
    target = (root / relative).resolve()
    if not target.is_relative_to((root / 'conversion/harness_sessions').resolve()):
        raise ValueError('canvas_bridge_baseline_outside_harness_sessions')
    raw = (target / 'conversion.json').read_bytes()
    before = json.loads(raw)
    if any(before.get(k) != record.get(k) for k in IDENTITY):
        raise ValueError('canvas_bridge_baseline_source_identity_mismatch')
    xml = (target / 'diagram.drawio').read_bytes()
    if sha(xml) != before['code_sha256']:
        raise ValueError('canvas_bridge_archived_xml_hash_changed')
    # Independently verify each original source locator, including font DOMs.
    from harness_source_provenance import validate_source_record
    validate_source_record(before)
    return before, xml.decode(), raw, str(target.relative_to(root))


def _registration(before, reference, xml):
    # This revalidates frozen renderer/pixel/geometry proof, not a stored offset.
    from auto_quality_common_v2 import registration_record
    _, contract = registration_record(before, reference, xml)
    if contract is None:
        raise ValueError('canvas_bridge_baseline_has_no_verified_registration')
    return contract


def _page(xml):
    outer = E.fromstring(xml)
    pages = list(outer.iter('mxGraphModel'))
    if len(pages) != 1 or outer.tag == 'mxfile' and len(outer.findall('diagram')) != 1:
        raise ValueError('canvas_bridge_requires_single_uncompressed_page')
    try:
        values = [float(pages[0].get(k, 'nan')) for k in ('pageWidth', 'pageHeight')]
    except (TypeError, ValueError) as exc:
        raise ValueError('canvas_bridge_invalid_current_page') from exc
    if not all(math.isfinite(x) and 0 < x <= 8192 and x.is_integer() for x in values):
        raise ValueError('canvas_bridge_invalid_current_page')
    return [int(x) for x in values]


def derive(record, reference, xml, *, root=R):
    """Recompute a minimal immutable lineage plus independently proven page."""
    root = Path(root)
    if sha(reference) != record.get('source_image_sha256'):
        raise ValueError('canvas_bridge_original_reference_changed')
    if sha(xml.encode()) != record.get('code_sha256'):
        raise ValueError('canvas_bridge_current_xml_hash_changed')
    _, provenance = _source_provenance(record)
    inherited = record.get(FIELD)
    link = inherited.get('baseline_archive') if isinstance(inherited, dict) else record.get('previous_candidate_archive')
    if not link:
        raise ValueError('canvas_bridge_no_owned_historical_baseline')
    before, oldxml, raw, locator = _archive(link, record, root)
    contract = _registration(before, reference, oldxml)
    reference_page = contract.get('reference_page')
    output_page = contract.get('output_page')
    offset = contract.get('original_page_offset')
    if (not isinstance(reference_page, list) or len(reference_page) != 2
            or not isinstance(output_page, list) or len(output_page) != 2
            or not isinstance(offset, list) or len(offset) != 2
            or not all(type(v) is int for v in reference_page + output_page + offset)
            or any(v <= 0 or v > 8192 for v in reference_page + output_page)
            or any(v < 0 for v in offset)
            or any(offset[i] + reference_page[i] > output_page[i] for i in range(2))):
        raise ValueError('canvas_bridge_invalid_verified_registration')
    if _page(xml) != output_page:
        raise ValueError('canvas_bridge_model_changed_verified_page_dimensions')
    return {'version': 1, 'identity': {k: record[k] for k in IDENTITY},
            'baseline_archive': locator, 'baseline_record_sha256': sha(raw),
            'baseline_code_sha256': sha(oldxml.encode()),
            'source_provenance_archive': provenance['archive'],
            'source_provenance_record_sha256': provenance['record_sha256'],
            'reference_page': reference_page, 'output_page': output_page,
            'original_page_offset': offset, 'accepted': False,
            'scope': 'Verified original-reference dimensions and integer placement only. Every current graph, source object, glyph, font, native render and fidelity check remains independent.'}


def attach(record, reference, xml, *, root=R):
    """Add only page lineage; do not copy any old candidate proof fields."""
    contract = derive(record, reference, xml, root=root)
    return {**record, FIELD: contract}


def validate(record, reference, xml, *, root=R):
    """Return a QA registration contract after rederiving source/pixel lineage."""
    stored = record.get(FIELD)
    if not isinstance(stored, dict) or stored != derive(record, reference, xml, root=root):
        raise ValueError('canvas_bridge_inherited_registration_changed')
    return {**stored, 'source_page_registration_verified': True,
            'current_revision_verified': False, 'current_graph_source_geometry_verified': False,
            'scale': 1, 'no_reference_crop': True}
