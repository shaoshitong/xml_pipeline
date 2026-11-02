#!/usr/bin/env python3
"""Render three frozen dataset gold references on HKUST; never call a model.

Run on HKUST, for example:
  PYTHONPATH=/backup/shaoshitong/img2code_20261029/env \
    /home/shaoshitong/anaconda3/bin/python3 evaluation/validate_gold_references.py \
    --root /backup/shaoshitong/img2code_20261029

All artifacts are NEW copies below evaluation/dataset_gold_validation. Existing
output directories are refused. The original cases and renderer are read only.
The XML renderer remains the cached official GraphViewer. Poster HTML uses the
same Chromium viewport and metrics, while allowing only its copied local assets.
No downloaded Python/JS source is executed except the already-cached official
draw.io viewer; poster page JavaScript is disabled. No network downloads occur.
"""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit


CASES = (
    ('framework_simple', 'drawio', 'ground_truth.drawio'),
    ('framework_complex', 'drawio', 'ground_truth.drawio'),
    ('academic_poster', 'html', 'ground_truth.html'),
)
VIEWER_SHA256 = '0c12ccf10dcaf0d0ef40ca60a5bc881ba27b57e076797ee39bce46602371f769'


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def save_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def load_renderer(path):
    spec = importlib.util.spec_from_file_location('img2code_existing_renderer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def offline_drawio_browser(blocked):
    """Keep the existing GraphViewer renderer, but block all resource requests.

    Its local add_script_tag(path=...) injects the cached viewer content without
    making a resource request. No editor/CDN or missing-bundle fallback is used.
    """
    import playwright.sync_api as api
    original_factory = api.sync_playwright

    class BrowserProxy:
        def __init__(self, browser):
            self.browser = browser

        def new_page(self, **kwargs):
            context = self.browser.new_context(service_workers='block', **kwargs)
            context.set_offline(True)

            def deny(route):
                blocked.append(route.request.url)
                route.abort()

            context.route('**/*', deny)
            return context.new_page()

        def __getattr__(self, name):
            return getattr(self.browser, name)

    class BrowserTypeProxy:
        def __init__(self, browser_type):
            self.browser_type = browser_type

        def launch(self, **kwargs):
            kwargs.pop('proxy', None)
            kwargs['args'] = list(kwargs.get('args', [])) + ['--disable-background-networking']
            return BrowserProxy(self.browser_type.launch(**kwargs))

    class PlaywrightProxy:
        def __init__(self, playwright):
            self.chromium = BrowserTypeProxy(playwright.chromium)

    @contextlib.contextmanager
    def guarded_factory():
        with original_factory() as playwright:
            yield PlaywrightProxy(playwright)

    api.sync_playwright = guarded_factory
    try:
        yield
    finally:
        api.sync_playwright = original_factory


def poster_with_assets(source, output, width, height, allowed_files):
    """Offline native HTML capture with exact copied assets, no page scripts."""
    from playwright.sync_api import sync_playwright

    installed = sorted(
        Path.home().joinpath('.cache/ms-playwright').glob('chromium-*/chrome-linux*/chrome'),
        key=lambda p: int(re.search(r'chromium-(\d+)', str(p)).group(1)), reverse=True)
    if not installed:
        raise FileNotFoundError('Installed full Chromium executable is required; no download permitted')
    options = {'headless': True, 'executable_path': str(installed[0]),
               'args': ['--disable-dev-shm-usage', '--disable-background-networking']}
    blocked, served, trace = [], set(), []
    root = source.parent.resolve()
    permitted = {Path(p).resolve() for p in allowed_files}
    permitted.add(source.resolve())
    origin = 'http://gold.invalid'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(viewport={'width': width, 'height': height},
            device_scale_factor=1, service_workers='block', java_script_enabled=False)
        context.set_offline(True)

        def local_resource(route):
            parsed = urlsplit(route.request.url)
            resource_type = route.request.resource_type
            candidate = (root / unquote(parsed.path).lstrip('/')).resolve()
            valid = (parsed.scheme == 'http' and parsed.netloc == 'gold.invalid'
                     and within(candidate, root) and candidate in permitted
                     and candidate.is_file() and resource_type in
                     {'document', 'image', 'font', 'stylesheet'})
            # Only the copied gold is a document; assets cannot navigate frames.
            if resource_type == 'document' and candidate != source.resolve():
                valid = False
            if not valid:
                blocked.append({'url': route.request.url, 'resource_type': resource_type})
                route.abort()
                return
            served.add(str(candidate.relative_to(root)))
            route.fulfill(path=str(candidate), content_type=(
                'text/html; charset=utf-8' if candidate == source.resolve()
                else mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'))

        context.route('**/*', local_resource)
        page = context.new_page()
        page.set_default_timeout(25000)
        page.on('pageerror', lambda error: trace.append({'kind': 'pageerror', 'text': str(error)[:1000]}))
        page.on('console', lambda msg: trace.append({'kind': 'console', 'text': msg.text[:1000]})
                if msg.type == 'error' else None)
        page.goto(origin + '/' + source.name, wait_until='load', timeout=25000)
        page.evaluate('document.fonts.ready')
        page.evaluate('''async()=>{await Promise.all(Array.from(document.images).map(
          image=>image.decode().catch(()=>null)))}''')
        document = page.evaluate('''()=>({
          documentWidth:document.documentElement.scrollWidth,
          documentHeight:document.documentElement.scrollHeight,
          htmlTextElements:Array.from(document.querySelectorAll('body *')).filter(e=>
            e.namespaceURI==='http://www.w3.org/1999/xhtml'&&e.childElementCount===0&&
            e.tagName!=='STYLE'&&e.textContent.trim().length>0).length,
          svgTextElements:document.querySelectorAll('svg text').length,
          svgVectorElements:document.querySelectorAll('svg path,svg rect,svg circle,svg ellipse,svg line,svg polyline,svg polygon').length,
          images:Array.from(document.images).map(e=>({src:e.getAttribute('src'),
            complete:e.complete,naturalWidth:e.naturalWidth,naturalHeight:e.naturalHeight}))
        })''')
        page.screenshot(path=str(output), full_page=False, animations='disabled', timeout=20000)
        browser.close()
    return {'renderer': 'offline headless Chromium HTML/CSS with copied gold local assets',
        'viewport': [width, height], 'page_javascript_enabled': False,
        'network_downloads_allowed': False, 'local_asset_allowlist_enforced': True,
        'served_local_files': sorted(served), 'blocked_resource_requests': blocked,
        'native_editable_elements': document, 'browser_trace': trace,
        'missing_image_count': sum(not x['complete'] or not x['naturalWidth'] for x in document['images']),
        'content_outside_viewport': document['documentWidth'] > width or document['documentHeight'] > height}


def graph_bounds_diagnostic(renderer, reference, rendered, native):
    """Separate export-view diagnostic; never replace the declared-page score."""
    from PIL import Image

    bounds = native.get('graphBounds') or {}
    try:
        x, y, width, height = (float(bounds[key]) for key in ('x', 'y', 'width', 'height'))
        if not all(math.isfinite(v) for v in (x, y, width, height)) or min(width, height) <= 0:
            raise ValueError('Non-finite or empty graph bounds')
        with Image.open(rendered) as image:
            page_width, page_height = image.size
            intersection_width = max(0.0, min(x + width, page_width) - max(0.0, x))
            intersection_height = max(0.0, min(y + height, page_height) - max(0.0, y))
            coverage = intersection_width * intersection_height / (width * height)
            inside = x >= 0 and y >= 0 and x + width <= page_width and y + height <= page_height
            diagnostic = {'ok': False, 'graph_bounds': bounds,
                'declared_page_bounds_coverage': coverage,
                'coverage_note': 'Geometric graph-bounds rectangle intersection with the declared page, not an object/ink recall score.',
                'separate_from_declared_page_metric': True}
            if inside:
                crop_box = (math.floor(x), math.floor(y), math.ceil(x + width), math.ceil(y + height))
                destination = rendered.parent / 'render.graph_bounds_crop.png'
                image.crop(crop_box).save(destination)
                diagnostic.update({'method': 'Actual declared-page PNG cropped to floor(left/top), ceil(right/bottom) of official GraphViewer graphBounds; no coordinate changes.',
                    'crop_box_xyxy': list(crop_box), 'output': str(destination)})
            else:
                destination = rendered.parent / 'render.tight.png'
                if not destination.is_file() or native.get('tight_diagnostic') != str(destination):
                    diagnostic.update({'method': 'skipped', 'error': 'Bounds extend outside page and no existing official-renderer tight diagnostic is available.'})
                    return diagnostic
                diagnostic.update({'method': 'Existing official GraphViewer render.tight.png: scale 1 and translation (2-x, 2-y), canvas ceil(bounds width/height + 4), retaining all bounded content plus 2px padding.',
                    'output': str(destination)})
        diagnostic['metrics'] = renderer.metrics(reference, destination)
        diagnostic['baseline_ssim'] = diagnostic['metrics']['ssim_resized']
        diagnostic['ok'] = True
        return diagnostic
    except Exception as exc:
        return {'ok': False, 'method': 'skipped', 'separate_from_declared_page_metric': True,
                'error': type(exc).__name__ + ': ' + str(exc)[:1500]}


def worker(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    directory = manifest_path.parent
    source, reference = directory / manifest['source'], directory / manifest['reference']
    width, height = manifest['reference_size']
    renderer = load_renderer(Path(manifest['existing_renderer']))
    result = {'ok': False, 'kind': manifest['kind'], 'source': str(source),
              'output': str(directory / 'render.png'), 'no_model_calls': True}
    started = time.monotonic()
    try:
        if manifest['kind'] == 'drawio':
            bundle = Path(manifest['existing_renderer']).parent / 'assets/viewer-static.min.js'
            if not bundle.is_file() or sha256(bundle) != VIEWER_SHA256:
                raise ValueError('Required frozen official viewer bundle is absent or hash differs; no download attempted')
            # An inherited embed setting must not select the online editor.
            os.environ.pop('IMG2CODE_DRAWIO_BACKEND', None)
            blocked = []
            with offline_drawio_browser(blocked):
                result.update(renderer.drawio_png(source, directory / 'render.png', width, height, ''))
            result['blocked_resource_requests'] = blocked
            result['network_downloads_allowed'] = False
        else:
            result.update(poster_with_assets(source, directory / 'render.png', width, height,
                [directory / entry['copy'] for entry in manifest['files'] if entry['role'] == 'asset']))
        from PIL import Image
        with Image.open(directory / 'render.png') as image:
            image.verify()
        result['metrics'] = renderer.metrics(reference, directory / 'render.png')
        if manifest['kind'] == 'drawio':
            result['graph_bounds_content_crop_diagnostic'] = graph_bounds_diagnostic(
                renderer, reference, directory / 'render.png', result)
        result['ok'] = True
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)[-5000:]
    result['seconds'] = round(time.monotonic() - started, 3)
    save_json(directory / 'render.json', result)
    return 0 if result['ok'] else 1


def copy_frozen_case(root, output_root, case_id, kind, gold_name, renderer):
    from PIL import Image

    original = root / 'cases' / case_id
    gold = original / gold_name
    references = [original / 'reference.png', original / 'reference.jpg', original / 'reference.jpeg']
    references = [p for p in references if p.is_file()]
    if len(references) != 1:
        raise ValueError(f'{case_id}: expected exactly one frozen reference image, found {len(references)}')
    reference = references[0]
    if not gold.is_file() or not within(gold, root) or not within(reference, root):
        raise ValueError(f'{case_id}: missing gold source or input outside task root')
    with Image.open(reference) as image:
        size = list(image.size)
        image.verify()
    if max(size) > 8192 or size[0] * size[1] > 64000000:
        raise ValueError('Frozen image exceeds existing renderer limits')
    originals = [(gold, 'source'), (reference, 'reference')]
    if kind == 'html':
        asset_root = original / 'assets'
        if not asset_root.is_dir():
            raise FileNotFoundError(f'{case_id}: frozen assets directory is missing')
        for path in sorted(asset_root.rglob('*')):
            if path.is_symlink() or not within(path, asset_root):
                raise ValueError('Asset symlink or path escape refused: ' + str(path))
            if path.is_file():
                originals.append((path, 'asset'))
        assets = [p for p, role in originals if role == 'asset']
        if len(assets) > 1000 or sum(p.stat().st_size for p in assets) > 512 * 1024 * 1024:
            raise ValueError('Frozen assets exceed bounded-copy limits')
    directory = output_root / case_id
    directory.mkdir()
    files = []
    for path, role in originals:
        relative = path.relative_to(original)
        destination = directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        initial_hash = sha256(path)
        shutil.copyfile(path, destination)
        if sha256(destination) != initial_hash:
            raise ValueError('Copied frozen file hash mismatch: ' + str(relative))
        files.append({'role': role, 'original': str(path), 'copy': str(relative),
                      'bytes': destination.stat().st_size, 'sha256': initial_hash})
    manifest = {'case': case_id, 'kind': kind, 'source': gold.name, 'reference': reference.name,
        'reference_size': size, 'files': files, 'asset_count': sum(f['role'] == 'asset' for f in files),
        'existing_renderer': str(renderer), 'existing_renderer_sha256': sha256(renderer),
        'created_utc': now(), 'no_model_calls': True,
        'purpose': 'Dataset supplied reconstruction/template correspondence to its frozen image; not original-author source recovery.'}
    save_json(directory / 'input_manifest.json', manifest)
    return directory, manifest


def bounded_render(directory, timeout):
    environment = dict(os.environ)
    for name in ('IMG2CODE_DRAWIO_BACKEND', 'IMG2CODE_DRAWIO_PROXY', 'HTTP_PROXY', 'HTTPS_PROXY',
                 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        environment.pop(name, None)
    environment.update({'PYTHONHASHSEED': '0', 'OMP_NUM_THREADS': '1',
                        'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
    started = time.monotonic()
    timed_out = False
    with (directory / 'worker.stdout.txt').open('wb') as stdout, \
         (directory / 'worker.stderr.txt').open('wb') as stderr:
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
            '--worker-manifest', str(directory / 'input_manifest.json')],
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            env=environment, start_new_session=True)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            # Kill the whole group even if its leader already exited, so browser
            # descendants cannot survive a timed-out worker.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)
    result_path = directory / 'render.json'
    try:
        result = json.loads(result_path.read_text()) if result_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        result = {}
    return result, {'returncode': process.returncode, 'timed_out': timed_out,
                    'timeout_seconds': timeout, 'wall_seconds': round(time.monotonic() - started, 3)}


def run(root, output_root, renderer, timeout):
    root, output_root, renderer = root.resolve(), output_root.resolve(), renderer.resolve()
    if not within(output_root, root / 'evaluation'):
        raise ValueError('Output root must be a NEW directory within task evaluation/')
    if output_root.exists():
        raise FileExistsError('Refusing to overwrite existing validation outputs: ' + str(output_root))
    if not renderer.is_file() or not within(renderer, root / 'evaluation'):
        raise ValueError('Existing trusted evaluation/remote_render.py is required')
    output_root.mkdir(parents=True)
    summary = {'schema_version': 1, 'created_utc': now(), 'root': str(root),
        'output_root': str(output_root), 'no_model_calls': True, 'original_inputs_modified': False,
        'cases': [], 'note': 'Gold-render pixel diagnostics measure supplied reconstructed/template code versus frozen reference. They are not semantic correctness, author-source verification, or model scores.'}
    for case_id, kind, gold_name in CASES:
        print(json.dumps({'event': 'gold_validation_started', 'case': case_id, 'utc': now()}), flush=True)
        item = {'case': case_id, 'kind': kind, 'ok': False}
        try:
            directory, manifest = copy_frozen_case(root, output_root, case_id, kind, gold_name, renderer)
            result, process = bounded_render(directory, timeout)
            unchanged = all(Path(f['original']).is_file() and sha256(f['original']) == f['sha256']
                            for f in manifest['files'])
            success = bool(result.get('ok')) and not process['timed_out'] and process['returncode'] == 0 and unchanged
            item.update({'ok': success, 'render_status': 'ok' if success else 'timeout' if process['timed_out'] else 'failed',
                'baseline_ssim': result.get('metrics', {}).get('ssim_resized'),
                'metrics': result.get('metrics'), 'reference_size': manifest['reference_size'],
                'canvas': result.get('canvas', result.get('viewport')),
                'content_outside_declared_canvas': result.get('content_outside_declared_canvas'),
                'content_outside_viewport': result.get('content_outside_viewport'),
                'graph_bounds': result.get('graphBounds'), 'asset_count': manifest['asset_count'],
                'graph_bounds_content_crop_diagnostic': result.get('graph_bounds_content_crop_diagnostic'),
                'missing_image_count': result.get('missing_image_count'),
                'blocked_resource_request_count': len(result.get('blocked_resource_requests', [])),
                'originals_unchanged': unchanged, 'process': process,
                'details': str(directory / 'render.json'), 'input_manifest': str(directory / 'input_manifest.json')})
            if not success:
                item['error'] = result.get('error', 'Renderer timed out or exited without successful render.json; inspect worker.stderr.txt')
        except Exception as exc:
            item.update({'render_status': 'failed', 'baseline_ssim': None,
                         'error': type(exc).__name__ + ': ' + str(exc)[-3000:]})
        summary['cases'].append(item)
        save_json(output_root / 'summary.json', summary)
        print(json.dumps({'event': 'gold_validation_case', **item}, ensure_ascii=False), flush=True)
    summary.update({'finished_utc': now(), 'ok': all(c['ok'] for c in summary['cases']),
                    'original_inputs_modified': any(c.get('originals_unchanged') is False for c in summary['cases'])})
    save_json(output_root / 'summary.json', summary)
    print(json.dumps({'summary': str(output_root / 'summary.json'), 'ok': summary['ok'],
        'no_model_calls': True, 'cases': [{key: c.get(key) for key in
        ('case', 'render_status', 'baseline_ssim', 'content_outside_declared_canvas',
         'content_outside_viewport', 'missing_image_count', 'asset_count',
         'graph_bounds_content_crop_diagnostic')} for c in summary['cases']]},
        ensure_ascii=False), flush=True)
    return 0 if summary['ok'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=Path('/backup/shaoshitong/img2code_20261029'))
    parser.add_argument('--output-root', type=Path, help='New directory inside task evaluation/; never overwrite')
    parser.add_argument('--renderer', type=Path, help='Defaults to the existing evaluation/remote_render.py')
    parser.add_argument('--timeout', type=float, default=55, help='Per-render wall timeout, 50..60 seconds (default 55)')
    parser.add_argument('--worker-manifest', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_manifest:
        return worker(args.worker_manifest.resolve())
    if not 50 <= args.timeout <= 60:
        parser.error('--timeout must be between 50 and 60 seconds')
    return run(args.root, args.output_root or args.root / 'evaluation/dataset_gold_validation',
               args.renderer or args.root / 'evaluation/remote_render.py', args.timeout)


if __name__ == '__main__':
    sys.exit(main())
