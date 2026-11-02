"""Fresh, failure-only QA4b evidence in an isolated owned work directory.

No canonical claim, outcomes write, acceptance, model call or daemon exists.
Only evidence-output roots are redirected in a new child; frozen QA decisions,
source inputs, renderers, fonts and quality thresholds remain unchanged.
"""
import argparse
import copy
import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import traceback
import uuid

ROOT = Path('/backup/shaoshitong/img2code_20261029')
OWNER = Path('conversion/prototype/visual_failure_certificate_v1')
SCHEMA = 'fresh_current_program_visual_failure_certificate_v1'
VISUAL_FAILURES = frozenset(('global_fidelity_below_0.90', 'foreground_tile_p10_below_0.72',
    'foreground_coverage_below_0.90', 'local_text_line_ssim_below_0.55'))
LOADED_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def save(path, raw):
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'file': str(path), 'sha256': sha(raw), 'bytes': len(raw)}


def fingerprint(root, logical, expected=None):
    relative = Path(logical)
    require(not relative.is_absolute() and '..' not in relative.parts, 'invalid_resource_locator')
    path = Path(root) / relative
    target = path.resolve(strict=True)
    require(target.is_relative_to(Path(root).resolve()), 'resource_outside_data_root')
    stat_keys = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
    before = target.stat(); h = hashlib.sha256()
    with path.open('rb') as stream:
        require(stat_keys(os.fstat(stream.fileno())) == stat_keys(before), 'resource_changed_before_hash')
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
        require(stat_keys(os.fstat(stream.fileno())) == stat_keys(before), 'resource_changed_during_hash')
    require(path.resolve(strict=True) == target and stat_keys(target.stat()) == stat_keys(before), 'resource_path_changed_during_hash')
    require(expected is None or h.hexdigest() == expected, 'resource_hash_mismatch:' + str(relative))
    return {'logical': str(relative), 'resolved': str(target), 'identity': list(stat_keys(before)), 'sha256': h.hexdigest()}


def configuration(root=ROOT):
    root = Path(root).resolve(); scripts = root / 'conversion/scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    guard = importlib.import_module('visual_failure_route_guard_v1')
    cfg = guard.configuration(root)
    qa = importlib.import_module('auto_quality_batch_v4b')
    qa.ensure_pinned()
    require(qa.R.resolve() == root and json.loads((root / 'conversion/auto_quality_owner.json').read_text())['policy'] == qa.POLICY,
            'active_qa_or_root_mismatch')
    pins = dict(cfg['pins'])
    for module in (guard, qa, importlib.import_module('initial_conversion_process_v1')):
        path = Path(module.__file__).resolve(); pins[str(path)] = sha(path.read_bytes())
    pins[str(Path(__file__).resolve())] = LOADED_SHA
    return {'root': str(root), 'guard': cfg, 'pins': pins, 'qa_policy': qa.POLICY,
            'qa_output_original_root': str(qa.W), 'renderer': str(qa.RENDERER), 'clip_renderer': str(qa.CLIP_RENDERER)}


def ensure_pins(config):
    for path, expected in config['pins'].items():
        require(sha(Path(path).read_bytes()) == expected, 'pinned_implementation_changed:' + path)


def classify(report, observation, request):
    """Pure final classification; a low metric by itself can never propose."""
    r = request['record']; checks = report.get('checks') or {}
    require(request.get('no_reachable_current_repair') is True and re.fullmatch('[0-9a-f]{64}', request.get('route_snapshot_sha256', '')), 'fresh_no_repair_route_proof_missing')
    require(report.get('id') == r['id'] and report.get('policy') == request['qa_policy'], 'fresh_qa_identity_or_policy_mismatch')
    require((report.get('input_code_sha256'), report.get('input_image_sha256'), report.get('source_code_sha256'), report.get('source_image_sha256'))
            == (r['code_sha256'], r['image_sha256'], r['source_code_sha256'], r['source_image_sha256']), 'fresh_qa_four_hash_mismatch')
    failures = report.get('failures')
    require(report.get('state') == 'repair_required' and report.get('accepted') is False
            and isinstance(failures, list) and len(failures) == 1 and failures[0].startswith('raster_anomaly: '), 'not_sole_fresh_raster_anomaly')
    for name in ('structure', 'resources', 'source', 'render', 'text_paint', 'fonts', 'visual'):
        require(isinstance(checks.get(name), dict), 'fresh_prerequisite_not_reached:' + name)
    source = checks['source']; visual = checks['visual']; render = checks['render']; text = checks['text_paint']; fonts = checks['fonts']
    require(source.get('supported') is True and source.get('ok') is True and not source.get('failures'), 'fresh_source_not_fully_verified')
    require(checks['structure'].get('ok') is True, 'fresh_structure_not_verified')
    require(isinstance(checks['resources'].get('verified_files'), list), 'fresh_resources_not_verified')
    require(text.get('all_source_text_objects_rendered') is True and type(text.get('expected_text_objects')) is int
            and text['expected_text_objects'] >= 0 and text.get('actually_positioned_text_objects', -1) >= text['expected_text_objects'], 'fresh_text_not_fully_rendered')
    require(fonts.get('all_rendered_fonts_embedded') is True and type(fonts.get('actual_custom_font_glyphs')) is int
            and fonts['actual_custom_font_glyphs'] >= 0, 'fresh_actual_fonts_not_portable')
    require(not text['expected_text_objects'] or fonts['actual_custom_font_glyphs'] > 0, 'fresh_text_has_no_actual_custom_glyphs')
    require(observation.get('ok') is True and observation.get('kind') == 'primary_clip_render' and observation.get('code_sha256') == r['code_sha256'], 'fresh_primary_render_not_observed')
    require(render.get('code_sha256') == r['code_sha256'] and render.get('image_sha256') == observation['png']['sha256']
            and render.get('strict_outside_page_pixels') == 0 and render.get('canvas') == observation['canvas']
            and render.get('renderer_sha256') == observation['renderer_sha256'], 'fresh_strict_render_not_bound_to_observation')
    require(visual.get('ok') is False and isinstance(visual.get('failures'), list) and visual['failures']
            and set(visual['failures']) <= VISUAL_FAILURES, 'unknown_or_blank_visual_failure_keep_pending')
    require(failures[0] == 'raster_anomaly: ' + ','.join(visual['failures']), 'fresh_raster_failure_detail_mismatch')
    require(visual.get('thresholds') == {'ssim': .90, 'tile_p10': .72, 'foreground_precision_recall': .90, 'each_text_line_ssim': .55}, 'frozen_visual_thresholds_not_preserved')
    require('native_editing' not in checks, 'unexpected_native_editing_after_raster_failure')
    return {'proposal': True, 'accepted': False, 'reason': 'fresh_raster_failure_with_full_prerequisites_and_no_reachable_current_repair',
            'visual_failures': list(visual['failures']), 'native_editing': {'state': 'not_reached', 'ok': None, 'reason': 'Frozen QA4b stops at the preceding raster gate.'},
            'source_semantically_unsupported': False, 'scope': 'Current frozen verified program and current revision only; not intrinsic drawio impossibility.',
            'terminal_publication_authorized': False}


def install_write_guard(root, owned, blocked):
    """Guard Python mutations under R; renderer/source choices stay unchanged."""
    root = Path(root).resolve(); owned = Path(owned).resolve()
    def target(value, dirfd=None):
        if not isinstance(value, (str, bytes, os.PathLike)):
            return None
        path = Path(os.fsdecode(value))
        if not path.is_absolute():
            base = Path('/proc/self/fd', str(dirfd)).resolve() if isinstance(dirfd, int) and dirfd >= 0 else Path.cwd()
            path = base / path
        return path.resolve(strict=False)
    def check(value, event, dirfd=None):
        path = target(value, dirfd)
        if path is not None and path.is_relative_to(root) and not path.is_relative_to(owned):
            blocked.append({'event': event, 'path': str(path)})
            raise PermissionError('Canonical data mutation denied by evidence-only observer: ' + str(path))
    def hook(event, args):
        if event == 'open':
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            mode = args[1] if len(args) > 1 else None
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) or isinstance(mode, str) and any(c in mode for c in 'wax+'):
                check(args[0], event)
        elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod', 'os.utime', 'os.truncate'):
            check(args[0], event, args[-1] if isinstance(args[-1], int) and event in ('os.remove', 'os.rmdir', 'os.mkdir') else None)
        elif event in ('os.rename', 'os.link'):
            check(args[0], event, args[2] if len(args) > 2 else None); check(args[1], event, args[3] if len(args) > 3 else None)
        elif event == 'os.symlink':
            check(args[1], event, args[2] if len(args) > 2 else None)
        elif event == 'socket.connect' and isinstance(args[1], tuple):
            require(str(args[1][0]) in ('127.0.0.1', 'localhost', '::1'), 'nonloopback_network_connect_forbidden')
    sys.addaudithook(hook)


def child(request_path):
    request = json.loads(Path(request_path).read_bytes()); root = Path(request['root']); owned = Path(request['owned']).resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root / 'conversion/scripts'))
    qa = importlib.import_module('auto_quality_batch_v4b'); clip = importlib.import_module('clip_canvas_render_v4b')
    qa.ensure_pinned(); require(qa.POLICY == request['qa_policy'], 'child_qa_policy_mismatch')
    for path, digest in request['pins'].items():
        require(sha(Path(path).read_bytes()) == digest, 'child_pinned_file_changed')
    bindings = {'R': str(qa.R), 'renderer': str(qa.RENDERER), 'clip_renderer': str(qa.CLIP_RENDERER),
                'qa_policy': qa.POLICY, 'implementation': qa.IMPLEMENTATION}
    require(bindings['R'] == request['root'] and bindings['renderer'] == request['renderer'] and bindings['clip_renderer'] == request['clip_renderer'], 'child_input_renderer_binding_changed')
    original_w = qa.W; original_clip_owner = clip.OWNER
    qa.W = owned / 'qa_work_root'
    clip.OWNER = str((owned / 'clip_canvas_evidence').relative_to(root))
    qa.W.mkdir()
    observations = []; observer_errors = []; blocked = []; source_redirections = []
    glyph = importlib.import_module('html_actual_text_alignment')
    original_capture_source = glyph.capture_source
    def capture_source_to_owned(record, work, *args, **kwargs):
        requested = Path(work).resolve()
        redirected = owned / 'html_source_capture' / uuid.uuid4().hex
        source_redirections.append({'field': 'html_actual_text_alignment.capture_source.work',
                                    'original': str(requested), 'redirected': str(redirected),
                                    'purpose': 'Fresh HTML source evidence output only; record and source inputs unchanged'})
        return original_capture_source(record, redirected, *args, **kwargs)
    glyph.capture_source = capture_source_to_owned
    observe_dir = owned / 'render_observations'; observe_dir.mkdir()
    original_render = clip.render
    def observed(*args, **kwargs):
        result = original_render(*args, **kwargs)
        try:
            index = len(observations); stem = f'{index:03d}'
            native = result.get('native_render')
            info = save(observe_dir / (stem + '.native_info.json'), canonical(native)) if native is not None else None
            png = save(observe_dir / (stem + '.png'), result['png']) if isinstance(result.get('png'), bytes) else None
            observations.append({'kind': 'primary_clip_render', 'ok': result.get('ok') is True, 'code_sha256': sha(args[0].encode()),
                'canvas': [args[1], args[2]], 'renderer': str(args[4]), 'renderer_sha256': sha(Path(args[4]).read_bytes()),
                'native_info': info, 'png': png, 'returned_original_result_object': True})
        except Exception as error:
            observer_errors.append(repr(error))
        return result
    clip.render = observed
    install_write_guard(root, owned, blocked)
    item, report, out, work = qa.verify(tuple(request['item']))
    require(Path(work).resolve().is_relative_to(owned), 'qa_work_not_owned')
    qa.ensure_pinned()
    result = {'report': report, 'qa_returned_out': out is not None, 'qa_work': str(work), 'observations': observations,
              'observer_errors': observer_errors, 'blocked_mutation_attempts': blocked,
              'unchanged_bindings': bindings, 'redirections': [
                  {'field': 'auto_quality_batch_v4b.W', 'original': str(original_w), 'redirected': str(qa.W), 'purpose': 'QA evidence output only'},
                  {'field': 'clip_canvas_render_v4b.OWNER', 'original': original_clip_owner, 'redirected': clip.OWNER, 'purpose': 'Clip strict-proof evidence output only'}] + source_redirections,
              'same_render_result_objects_returned': True, 'model_api_calls': 0, 'canonical_publication_called': False}
    save(owned / 'child_result.json', canonical(result))
    return 0


def prepare(db, identifier, config, timeout=360, work=None):
    import visual_failure_route_guard_v1 as guard
    from initial_conversion_process_v1 import run as run_process
    qa = importlib.import_module('auto_quality_batch_v4b')
    root = Path(config['root']); ensure_pins(config)
    context = guard.capture(db, identifier, config['guard'])
    owned = Path(work).resolve() if work is not None else root / OWNER / identifier / uuid.uuid4().hex
    require(owned.is_relative_to((root / OWNER).resolve()), 'evidence_work_outside_owned_namespace')
    owned.mkdir(parents=True, exist_ok=False)
    report = {'schema': SCHEMA, 'id': identifier, 'at': now(), 'proposal': False, 'accepted': False,
              'canonical_mutations': 0, 'models_called': 0, 'terminal_publication_authorized': False,
              'native_editing': {'state': 'not_reached', 'ok': None}, 'evidence_directory': str(owned)}
    try:
        require(context.get('eligible') is True, 'route_admission_refused:' + str(context.get('reason')))
        r = context['record']; job = context['job']
        require(r.get('original_source_code') and r.get('original_reference'), 'missing_source_locators_requires_metadata_repair')
        xml = qa.checked(root, r['code_file'], r['code_sha256']).decode(); reference = qa.checked(root, r['original_reference'], r['source_image_sha256'])
        resources = qa.resource_checks(root, r, xml, reference)
        paths = set(resources['verified_files']) | {r[k] for k in ('code_file', 'image_file', 'original_source_code', 'original_reference')}
        expected = {r[k]: r[h] for k,h in (('code_file','code_sha256'),('image_file','image_sha256'),('original_source_code','source_code_sha256'),('original_reference','source_image_sha256'))}
        manifest = context['input_manifest']
        for key, digest in (('source_code','code_sha256'),('reference_image','image_sha256')):
            if manifest.get(key): paths.add(manifest[key]); expected[manifest[key]] = manifest[digest]
        before = {path: fingerprint(root, path, expected.get(path)) for path in sorted(paths)}
        prior_audit = root / 'conversion/auto_quality_v4b' / identifier / (r['code_sha256'] + '_' + r['image_sha256'][:16]) / config['qa_policy'].rsplit(':',1)[-1] / 'audit.json'
        prior = sha(prior_audit.read_bytes()) if prior_audit.exists() else None
        request = {'root': str(root), 'owned': str(owned), 'qa_policy': config['qa_policy'], 'pins': config['pins'],
                   'renderer': config['renderer'], 'clip_renderer': config['clip_renderer'], 'record': r,
                   'item': context['item'], 'no_reachable_current_repair': True, 'route_snapshot_sha256': sha(canonical(context['snapshot']))}
        report['evidence_files'] = {'context': save(owned / 'context.json', canonical(context)), 'request': save(owned / 'request.json', canonical(request))}
        execution = run_process([sys.executable, str(Path(__file__).resolve()), '--child', str(owned / 'request.json')], owned / 'process', timeout,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        report['execution'] = execution
        require(execution.get('ok') is True and execution.get('cleanup_complete') is True, 'fresh_qa_process_runtime_or_cleanup_failure')
        child_raw = (owned / 'child_result.json').read_bytes(); result = json.loads(child_raw); report['fresh_qa'] = result
        report['evidence_files']['child_result'] = {'file':str(owned/'child_result.json'),'sha256':sha(child_raw)}
        audit_file = Path(result['qa_work'])/'audit.json'; audit_raw = audit_file.read_bytes()
        require(canonical(json.loads(audit_raw)) == canonical(result['report']), 'fresh_frozen_qa_audit_differs_from_returned_report')
        report['evidence_files']['frozen_qa_audit'] = {'file':str(audit_file),'sha256':sha(audit_raw)}
        require(not result['observer_errors'] and not result['blocked_mutation_attempts'], 'observation_or_canonical_write_attempt_keep_pending')
        require((sha(prior_audit.read_bytes()) if prior_audit.exists() else None) == prior, 'original_live_audit_changed_during_probe_keep_pending')
        after = {path: fingerprint(root, path, expected.get(path)) for path in sorted(paths)}
        require(before == after and qa.resource_checks(root, r, xml, reference) == resources, 'source_resource_or_candidate_changed_during_probe')
        current = guard.revalidate(db, context, config['guard']); report['fresh_admission_recheck'] = current
        require(current.get('eligible') is True, 'fresh_route_or_revision_changed_keep_pending:' + str(current.get('reason')))
        observations = result['observations']
        require(len(observations) == 1, 'fresh_primary_render_not_unique')
        observation = observations[0]
        require(observation.get('native_info') and observation.get('png'), 'fresh_png_or_native_info_missing')
        native_file = Path(observation['native_info']['file']); png_file = Path(observation['png']['file'])
        require(sha(native_file.read_bytes()) == observation['native_info']['sha256'] and sha(png_file.read_bytes()) == observation['png']['sha256'], 'fresh_render_evidence_hash_changed')
        info = json.loads(native_file.read_bytes()); qa.require_declared_page(info, *observation['canvas'])
        from PIL import Image
        require(list(Image.open(png_file).size) == observation['canvas'], 'fresh_png_declared_canvas_mismatch')
        require(not result['qa_returned_out'], 'fresh_qa_now_qualifies_not_a_visual_negative')
        report.update(classify(result['report'], observation, request), current_four_hashes={k:r[k] for k in ('source_code_sha256','source_image_sha256','code_sha256','image_sha256')},
                      files_before_and_after=before, original_live_audit={'file':str(prior_audit),'sha256_before_and_after':prior,'unchanged':True},
                      pins=config['pins'], qa_policy=config['qa_policy'], route_verdicts=context['route_verdicts'])
    except Exception as error:
        report.update(proposal=False, reason='retain_pending', deferred_reason=repr(error))
    try:
        ensure_pins(config)
    except Exception as error:
        report.update(proposal=False, reason='retain_pending', deferred_reason='post_probe_implementation_changed:' + repr(error))
    report['finished_at'] = now(); report['certificate_sha256'] = sha(canonical(report))
    save(owned / 'report.json', canonical(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path); parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--id', action='append', default=[]); parser.add_argument('--timeout', type=int, default=360)
    args = parser.parse_args(argv)
    if args.child:
        return child(args.child)
    require(1 <= len(args.id) <= 16 and len(set(args.id)) == len(args.id), 'explicit_finite_unique_ids_required')
    require(30 <= args.timeout <= 900, 'bounded_timeout_required')
    config = configuration(args.root)
    db = sqlite3.connect('file:' + str(args.root / 'conversion/jobs.sqlite') + '?mode=ro', uri=True, timeout=0)
    db.execute('pragma query_only=on')
    try:
        for identifier in args.id:
            require(re.fullmatch('[0-9a-f]{64}', identifier), 'invalid_original_id')
            result = prepare(db, identifier, config, args.timeout)
            print(json.dumps({key: result.get(key) for key in ('id','proposal','reason','deferred_reason','evidence_directory','certificate_sha256')}, ensure_ascii=False), flush=True)
    finally:
        db.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
