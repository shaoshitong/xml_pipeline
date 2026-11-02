"""Development probe on an existing candidate; never publishes or qualifies it."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import sys
import time

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
sys.path.insert(0, str(W / 'scripts'))


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    from PIL import Image, ImageChops
    import compiler_svg_general_guard_v3 as guard
    from svg_source_group_nesting_v1 import nest_source_groups
    frontend = guard.frontend
    original_record = args.record.read_bytes()
    record = json.loads(original_record)
    original_xml = (R / record['code_file']).read_bytes()
    assert sha(original_xml) == record['code_sha256']
    timings = {}
    started = time.monotonic()
    xml, proof = nest_source_groups(original_xml)
    (args.work / 'nested.drawio').write_text(xml)
    timings['nest_groups'] = time.monotonic() - started
    start = time.monotonic()
    prepared = frontend.prepare_source(record)
    assert prepared['ok'], 'original_source_reproduction_failed'
    timings['fresh_original_source_observation'] = time.monotonic() - start
    results = {}
    pixels = {}
    for label, code in [('original', original_xml.decode()), ('nested', xml)]:
        start = time.monotonic()
        order = guard.paint_order(prepared['capture']['dom'], code, prepared['size'])
        timings[label + '_paint_order'] = time.monotonic() - start
        (args.work / (label + '_paint_order.json')).write_text(json.dumps(order, indent=2))
        start = time.monotonic()
        rendered = frontend._native(code, prepared['size'])
        timings[label + '_actual_native_render'] = time.monotonic() - start
        image = Image.open(io.BytesIO(rendered['png'])).convert('RGBA')
        image.load()
        pixels[label] = image
        (args.work / (label + '_actual.png')).write_bytes(rendered['png'])
        results[label] = {'paint_order_ok': order['ok'], 'paint_order_failures': order['failures'], 'canvas': list(image.size), 'PNG_sha256': sha(rendered['png'])}
    assert pixels['original'].size == pixels['nested'].size
    difference = ImageChops.difference(pixels['original'], pixels['nested'])
    equal = pixels['original'].tobytes() == pixels['nested'].tobytes()
    assert args.record.read_bytes() == original_record
    assert (R / record['code_file']).read_bytes() == original_xml
    output = {
        'id': record['id'],
        'probe': 'development_only_existing_candidate_source_group_nesting_v1',
        'old_candidate_record_unchanged': True,
        'old_candidate_XML_unchanged': True,
        'nesting': proof,
        'results': results,
        'actual_native_RGBA_exactly_equal': equal,
        'actual_native_RGBA_max_difference_by_channel': [v[1] for v in difference.getextrema()],
        'seconds': timings,
        'total_seconds': time.monotonic() - started,
        'new_normal_conversion_calls': 0,
        'new_model_calls': 0,
        'full_quality_or_publication_claimed': False,
    }
    (args.work / 'summary.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output), flush=True)
    return 0 if results['nested']['paint_order_ok'] and equal else 2


if __name__ == '__main__':
    sys.exit(main())
