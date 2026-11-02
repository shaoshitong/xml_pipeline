"""Finite SOURCE-only two-profile comparison on an already consumed cohort.

No candidate conversion, output selection, source rewriting, threshold changes,
canonical writes or external model calls. Both declared profiles run on every
source. All code, PNG data and comparison outputs remain on HKUST.
"""
import concurrent.futures
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
ROOT = W / 'plantuml_source_backend_compare_v1'
JAR = W / 'runtime/plantuml/plantuml-1.2025.7.jar'
JAVA = '/usr/lib/jvm/java-11-openjdk-amd64/bin/java'
G14 = W / 'runtime/graphviz'
G243 = W / 'runtime/graphviz_deb'
LEDGER = R / 'release/compiler_iterations/runs/plantuml_closed_paint_v8_unseen100_20261101_v1_C/status.sqlite'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True).encode() + bytes([10])
    with path.open('xb') as handle:
        handle.write(payload)


def one(item):
    from PIL import Image
    import numpy as np
    from sandbox_runner import command, limits
    from auto_quality_common_v4 import image_quality
    identifier, source, manifest = item
    work = ROOT / 'cases' / identifier
    work.mkdir(parents=True, exist_ok=False)
    original_code = (R / manifest['source_code']).read_bytes()
    original_image = (R / manifest['reference_image']).read_bytes()
    assert sha(original_code) == source['code_sha256']
    assert sha(original_image) == source['image_sha256']
    reference = Image.open(io.BytesIO(original_image)).convert('RGBA')
    result = dict(id=identifier, source_code_sha256=source['code_sha256'],
                  source_image_sha256=source['image_sha256'], profiles={}, model_calls=0)
    for profile, dot, extra in (
            ('existing_graphviz14', G14 / 'bin/dot', [(G14, G14)]),
            ('existing_private_graphviz243', ROOT / 'dot243', [(G243, G243), (ROOT / 'dot243', ROOT / 'dot243')])):
        directory = work / profile
        directory.mkdir()
        environment = dict(GRAPHVIZ_DOT=str(dot), PATH='/usr/bin:/bin',
                           PLANTUML_SECURITY_PROFILE='SANDBOX')
        args = [JAVA, '-Xmx512m', '-XX:+UseSerialGC', '-Djava.awt.headless=true',
                '-DPLANTUML_SECURITY_PROFILE=SANDBOX', '-jar', '/runtime/plantuml.jar',
                '-charset', 'UTF-8', '-pipe', '-tpng']
        process = subprocess.run(command(directory, args,
            [(JAR, '/runtime/plantuml.jar'), ('/etc/java-11-openjdk', '/etc/java-11-openjdk'),
             ('/etc/alternatives', '/etc/alternatives'), *extra], environment),
            input=original_code, capture_output=True, timeout=100, preexec_fn=limits)
        (directory / 'stderr.txt').write_bytes(process.stderr)
        row = dict(returncode=process.returncode, source_only=True)
        if process.returncode == 0:
            try:
                image = Image.open(io.BytesIO(process.stdout)).convert('RGBA')
                (directory / 'actual_source.png').write_bytes(process.stdout)
                same_size = image.size == reference.size
                exact = same_size and np.array_equal(np.asarray(image), np.asarray(reference))
                row.update(canvas=list(image.size), reference_canvas=list(reference.size),
                           actual_png_sha256=sha(process.stdout), same_canvas=same_size,
                           exact_rgba_pixels_equal=bool(exact))
                if same_size:
                    visual = image_quality(original_image, process.stdout, {}, [])
                    row['unregistered_full_reference_visual'] = visual
            except Exception as error:
                row.update(error_type=type(error).__name__, error=str(error)[:1200])
        else:
            row['stderr'] = process.stderr.decode(errors='replace')[-1500:]
        result['profiles'][profile] = row
    save(work / 'comparison.json', result)
    return result


def main():
    ROOT.mkdir(parents=True, exist_ok=False)
    assert sha(JAR.read_bytes()) == '4edcdda164a4be2f8f954f82868795500ebd49f42306236bf88eac41f7e217a8'
    # The older binary and all its libraries were already installed privately.
    wrapper = '#!/bin/sh\nexec env LD_LIBRARY_PATH="' + str(G243 / 'usr/lib/x86_64-linux-gnu') + '" GVBINDIR="' + str(G243 / 'usr/lib/x86_64-linux-gnu/graphviz') + '" "' + str(G243 / 'usr/bin/dot') + '" "$@"\n'
    (ROOT / 'dot243').write_text(wrapper)
    (ROOT / 'dot243').chmod(0o555)
    pins = {str(JAR): sha(JAR.read_bytes()), str(Path(JAVA)): sha(Path(JAVA).read_bytes()),
            str(ROOT / 'dot243'): sha((ROOT / 'dot243').read_bytes()),
            str(Path(__file__).resolve()): sha(Path(__file__).read_bytes())}
    for runtime in (G14, G243):
        for path in runtime.rglob('*'):
            if path.is_file() and 'packages' not in path.relative_to(runtime).parts:
                pins[str(path)] = sha(path.read_bytes())
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as database:
        identifiers = sorted(row[0] for row in database.execute('select id from samples'))
    assert len(identifiers) == 100
    with sqlite3.connect('file:' + str(W / 'jobs.sqlite') + '?mode=ro', uri=True) as database:
        inputs = []
        for identifier in identifiers:
            source, manifest = database.execute('select input_record,input_manifest from jobs where id=?', (identifier,)).fetchone()
            inputs.append((identifier, json.loads(source), json.loads(manifest)))
    save(ROOT / 'protocol.json', dict(profiles=['existing_graphviz14', 'existing_private_graphviz243'],
         cohort='all_100_already_consumed_PlantUML_v8_C_sources', ids=identifiers,
         per_sample_profile_selection=False, reference_resampling=False, candidate_conversion=False,
         graphviz_versions_other_than_these_two=False, pins=pins, model_calls=0))
    with concurrent.futures.ProcessPoolExecutor(max_workers=4,
            mp_context=multiprocessing.get_context('fork')) as pool:
        rows = list(pool.map(one, inputs))
    for path, digest in pins.items():
        assert sha(Path(path).read_bytes()) == digest, 'source_backend_changed:' + path
    summary = {}
    for name in ('existing_graphviz14', 'existing_private_graphviz243'):
        values = [row['profiles'][name] for row in rows]
        summary[name] = dict(cases=len(values), successful=sum(row.get('returncode') == 0 for row in values),
            same_canvas=sum(bool(row.get('same_canvas')) for row in values),
            exact_rgba=sum(bool(row.get('exact_rgba_pixels_equal')) for row in values),
            source_visual_pass=sum(row.get('unregistered_full_reference_visual', {}).get('ok') is True for row in values))
    save(ROOT / 'report.json', dict(summary=summary, cases=rows, model_calls=0,
         source_or_reference_changed=False, profiles_frozen_before_results=True,
         source_only=True, automatic_profile_selection=False))
    print(json.dumps(dict(directory=str(ROOT), summary=summary), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
