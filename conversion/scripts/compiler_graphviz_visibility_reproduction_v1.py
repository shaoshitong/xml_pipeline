"""Bounded fresh Graphviz source-image reproduction, separate from target QA.

Python is not rerun.  A single, identity-bound Python capture supplies the DOT;
the pinned Graphviz engine is freshly run in bwrap.  Its fresh PNG is compared
both with the historical returned-image pixels and with the immutable reference.
Neither a cache agreement nor a source-image pass qualifies a drawio candidate.
"""
from __future__ import annotations

import io
import json
import math
import time
import uuid
from pathlib import Path

from compiler_graphviz_visibility_scene_v1 import R, W, DOT, GRAPHVIZ_VERSION, _read, _save, _source_scene, raw, sha, static_support

POLICY = 'fresh_graphviz_png_source_reference_uniform_fit_visibility_v1'


def canvas_mapping(source_size, reference_size):
    """One predeclared proportional downscale and integer rounding, no search."""
    sw, sh = map(int, source_size)
    rw, rh = map(int, reference_size)
    if min(sw, sh, rw, rh) <= 0:
        raise ValueError('source_reference_invalid_canvas')
    scale = min(rw/sw, rh/sh)
    if not math.isfinite(scale) or scale > 1 + 1e-12:
        raise ValueError('source_reference_upscale_not_supported')
    expected = (round(sw*scale), round(sh*scale))
    errors = [abs(sw*scale-rw), abs(sh*scale-rh)]
    if max(errors) > 1 or expected != (rw, rh):
        raise ValueError('source_reference_canvas_mismatch')
    return {'policy': 'single_uniform_fit_downscale_round_v1', 'source_canvas': [sw, sh],
            'reference_canvas': [rw, rh], 'scale': scale, 'rounded_output_canvas': list(expected),
            'rounding_error_px': errors, 'resampling': 'PIL.Image.Resampling.LANCZOS',
            'crop': False, 'padding': False, 'translation': [0, 0], 'parameter_search': False}


def _asset(path):
    path = Path(path).resolve(strict=True)
    if not path.is_relative_to((R/'clean').resolve()):
        raise ValueError('source_reproduction_asset_outside_clean')
    blob = path.read_bytes()
    return {'file': str(path.relative_to(R)), 'sha256': sha(blob), 'bytes': len(blob)}


def _text_positions(dom):
    """Feed each source SVG text run's complete line box to unchanged local gate.

    This is a full-run box rather than fake per-character measurements.  The
    original gate uses the union of those boxes to crop the corresponding line.
    Source text/shape completeness remains the separate scene profile's duty.
    """
    positions = []
    for obj in dom['objects']:
        if obj.get('type') != 'text' or not obj.get('text', '').strip():
            continue
        box = obj['bbox']
        if box['w'] <= 0 or box['h'] <= 0:
            continue
        positions.append({'cell': 'source:'+obj['id'], 'runs': [{'chars': [{
            'text': obj['text'], 'x': box['x'], 'y': box['y'],
            'width': box['w'], 'height': box['h']}]}]})
    return positions


def check(record, work=None):
    """Return a source-stage diagnostic; never edits a record or qualifies XML."""
    started = time.monotonic()
    report = {'policy': POLICY, 'id': record.get('id'), 'stage': 'source_reference',
              'supported': False, 'ok': False, 'infrastructure_failure': False,
              'python_reexecuted': False, 'graphviz_reexecuted': False,
              'model_calls': 0, 'full_target_qa_executed': False, 'assets': {}}
    dest = None
    output_work = None
    try:
        predicate = static_support(record)
        if not predicate['supported']:
            raise ValueError('source_profile_unsupported:'+json.dumps(predicate['reasons']))
        work = Path(work or (W/'compiler_graphviz_visibility_reproduction_v1/checks'/record['id']/uuid.uuid4().hex)).resolve()
        if not work.is_relative_to(W.resolve()):
            raise ValueError('source_reproduction_work_outside_conversion')
        work.mkdir(parents=True, exist_ok=True)
        output_work = work
        scene = _source_scene(record, work/'source_ir')
        report['supported'] = True
        report['source_chain'] = scene['source']
        report['runtime'] = scene['frontend']
        dest = R/'clean/compiler_graphviz_visibility_reproduction_v1'/record['id'][:2]/record['id']/uuid.uuid4().hex
        dest.mkdir(parents=True, exist_ok=False)
        dot_blob = _read(record['source_render_dot'], predicate['source_dot_sha256'])
        svg_blob = _read(record['source_render_svg'], record['source_render_svg_sha256'])
        audit_blob = _read(record['execution_audit'], predicate['execution_audit_sha256'], clean=False)
        audit = json.loads(audit_blob)
        capture_png = str(Path(audit['directory'])/'returned_image.png')
        cached_png = _read(capture_png, clean=False)
        _save(dest/'source.dot', dot_blob)
        _save(dest/'source.svg', svg_blob)
        _save(dest/'cached_execution_audit.json', audit_blob)
        _save(dest/'cached_returned_image.png', cached_png)
        _save(dest/'source_scene.json', raw(scene))
        for key, name in [('source_dot', 'source.dot'), ('source_svg', 'source.svg'),
                          ('cached_execution_audit', 'cached_execution_audit.json'),
                          ('cached_returned_png', 'cached_returned_image.png'), ('source_scene', 'source_scene.json')]:
            report['assets'][key] = _asset(dest/name)
        report['cache_provenance'] = {
            'original_execution_audit': record['execution_audit'],
            'original_cached_returned_png': capture_png,
            'historical_png_was_not_hash_bound_in_original_audit': True,
            'historical_png_is_not_fresh_execution_evidence': True,
            'python_capture_scope': 'The preserved execution identity/source/data hashes bind the cached DOT capture; this check does not rerun Python.'}

        from sandbox_runner import run
        runtime = W/'runtime/graphviz'
        process = run(work/'source_ir', [str(DOT), '-Tpng', '-o', '/work/fresh_source.png', '/work/input.dot'],
                      timeout=45, extra_ro=[(runtime, runtime)],
                      extra_env={'LD_LIBRARY_PATH': str(runtime/'lib'), 'GVBINDIR': str(runtime/'lib/graphviz')})
        _save(work/'fresh_png.stdout.log', process.stdout.encode())
        _save(work/'fresh_png.stderr.log', process.stderr.encode())
        if process.returncode:
            infrastructure = any(message in process.stderr for message in (
                'error while loading shared libraries', 'bwrap: ', 'Could not load ', 'not recognized. Use one of:'))
            if infrastructure:
                raise RuntimeError('infrastructure_graphviz_png_runtime_failed:'+process.stderr[-2000:])
            raise ValueError('source_png_execution_failed:'+process.stderr[-2000:])
        fresh_blob = (work/'source_ir/fresh_source.png').read_bytes()
        _save(dest/'fresh_source_engine.png', fresh_blob)
        report['assets']['fresh_source_engine_png'] = _asset(dest/'fresh_source_engine.png')
        report['graphviz_reexecuted'] = True
        from PIL import Image
        import numpy as np
        fresh = Image.open(io.BytesIO(fresh_blob)).convert('RGBA')
        cached = Image.open(io.BytesIO(cached_png)).convert('RGBA')
        equal = fresh.size == cached.size and np.array_equal(np.asarray(fresh), np.asarray(cached))
        report['fresh_vs_cache'] = {'comparison': 'full RGBA pixels, no registration or resampling',
                                   'same_canvas': fresh.size == cached.size,
                                   'fresh_canvas': list(fresh.size), 'cached_canvas': list(cached.size),
                                   'exact_rgba_pixels_equal': bool(equal)}
        if not equal:
            raise ValueError('fresh_source_png_disagrees_with_cached_python_returned_image')

        reference_blob = _read(record['original_reference'], record['source_image_sha256'])
        reference = Image.open(io.BytesIO(reference_blob))
        mapping = canvas_mapping(fresh.size, reference.size)
        report['source_reference_mapping'] = mapping
        mapped = fresh if fresh.size == reference.size else fresh.resize(reference.size, Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        mapped.save(stream, format='PNG')
        mapped_blob = stream.getvalue()
        _save(dest/'fresh_source_reference_canvas.png', mapped_blob)
        report['assets']['fresh_source_reference_canvas_png'] = _asset(dest/'fresh_source_reference_canvas.png')
        report['reference'] = {'file': record['original_reference'], 'sha256': record['source_image_sha256'], 'canvas': list(reference.size)}
        from auto_quality_source_vector_v2 import _capture
        dom, _ = _capture(record, svg_blob, reference.width, reference.height, 'svg')
        if dom.get('issues'):
            raise ValueError('source_svg_text_geometry_unsupported:'+json.dumps(dom['issues'])[:1000])
        text_positions = _text_positions(dom)
        _save(dest/'source_text_line_boxes.json', raw(text_positions))
        report['assets']['source_text_line_boxes'] = _asset(dest/'source_text_line_boxes.json')
        from auto_quality_common import image_quality
        visual = image_quality(reference_blob, mapped_blob, {}, text_positions)
        report['source_reference_visual'] = visual
        report['source_reference_text_scope'] = 'Every nonblank fresh source SVG DOM text run supplies a whole-line crop to the unchanged local-text SSIM gate; source pixel content is the freshly executed Graphviz PNG.'
        report['ok'] = bool(visual['ok'])
        report['reason'] = 'source_reference_reproduced' if report['ok'] else 'source_reference_mismatch'
    except Exception as exc:
        report['reason'] = str(exc).split(':', 1)[0]
        report['detail'] = str(exc)[:4000]
        report['exception_type'] = type(exc).__name__
        report['infrastructure_failure'] = isinstance(exc, (ImportError, ModuleNotFoundError)) or str(exc).startswith('infrastructure_')
    report['seconds'] = time.monotonic()-started
    report['scope'] = 'Source-stage reproduction only. It does not prove Python was rerun or drawio completeness, portability, fidelity or editing behavior.'
    if dest is not None:
        _save(dest/'source_reproduction.json', raw(report))
        report['evidence'] = _asset(dest/'source_reproduction.json')
    if output_work is not None:
        _save(output_work/'result.json', raw(report))
    return report
