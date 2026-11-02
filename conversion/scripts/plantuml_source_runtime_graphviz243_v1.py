"""One provider-wide source runtime, verified against 100 original native PNGs.

This is an additional immutable runtime profile. It neither replaces the old
Graphviz installation nor selects a backend per sample. Java keeps its original
library environment; only the child dot process receives the private 2.43 libs.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

R = Path('/backup/shaoshitong/img2code_20261029')
W = R / 'conversion'
DIRECTORY = W / 'runtime/plantuml_dot243_v1'
DOT = DIRECTORY / 'dot'
DEPENDENCIES = W / 'runtime/graphviz_deb'
JAVA = '/usr/lib/jvm/java-11-openjdk-amd64/bin/java'
JAR = W / 'runtime/plantuml/plantuml-1.2025.7.jar'
JAR_SHA = '4edcdda164a4be2f8f954f82868795500ebd49f42306236bf88eac41f7e217a8'
PROVIDER = 'Y36521478Y--omnidiagram_train_sft'
POLICY = 'OmniDiagram_PlantUML2025_7_Java11_private_dot243_no_per_id_selection_v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def environment():
    return dict(GRAPHVIZ_DOT=str(DOT), PATH='/usr/bin:/bin',
                PLANTUML_SECURITY_PROFILE='SANDBOX')


def extra_ro():
    return [(JAR, '/runtime/plantuml.jar'), (DEPENDENCIES, DEPENDENCIES),
            (DIRECTORY, DIRECTORY), ('/etc/java-11-openjdk', '/etc/java-11-openjdk'),
            ('/etc/alternatives', '/etc/alternatives')]


def configuration(data_root=R):
    if Path(data_root).resolve() != R:
        raise ValueError('requires_registered_HKUST_root')
    manifest_path = DIRECTORY / 'manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get('policy') != POLICY:
        raise RuntimeError('infrastructure_source_dot243_manifest_policy_changed')
    for path, digest in manifest['pins'].items():
        if sha(Path(path).read_bytes()) != digest:
            raise RuntimeError('infrastructure_source_dot243_profile_changed:' + path)
    if sha(JAR.read_bytes()) != JAR_SHA:
        raise RuntimeError('infrastructure_source_PlantUML_JAR_changed')
    pins = {**manifest['pins'], str(manifest_path): sha(manifest_path.read_bytes())}
    return dict(policy=POLICY, provider=PROVIDER, pins=pins,
                dot=str(DOT), java=JAVA, jar=str(JAR), environment=environment(),
                private_dot_version='2.43.0', source_JAR_version='1.2025.7',
                source_validation=manifest['source_validation'],
                per_id_backend_selection=False, original_source_rewriting=False)


def native_png_provenance(text, original_code, provider):
    """Optional source provenance, never a replacement for full quality checks.

    Expanded macros may legitimately make metadata source differ from the input;
    that difference is reported, not used to silently discard the source.
    """
    version = re.search(r'(?m)^PlantUML version ([^\r\n]+)', text or '')
    footer = (text or '').rfind('\nPlantUML version ')
    embedded = (text or '')[:footer].strip() if footer >= 0 else None
    normalize = lambda value: value.replace('\r\n', '\n').replace('\r', '\n').strip()
    code = original_code.decode('utf-8-sig') if isinstance(original_code, bytes) else original_code
    return dict(provider_in_profile=provider == PROVIDER,
                metadata_PlantUML_version=version[1] if version else None,
                metadata_source_matches_original_code=(normalize(embedded) == normalize(code)) if embedded is not None else None,
                provenance_is_not_quality_acceptance=True)


def run(work, code, fmt):
    from sandbox_runner import command, limits
    configuration()
    if fmt not in ('png', 'svg'):
        raise ValueError('unsupported_fixed_source_export_format')
    work = Path(work).resolve(strict=True)
    if not work.is_relative_to(W):
        raise ValueError('source_runtime_work_outside_owned_root')
    argv = [JAVA, '-Xmx512m', '-XX:+UseSerialGC', '-Djava.awt.headless=true',
            '-DPLANTUML_SECURITY_PROFILE=SANDBOX', '-jar', '/runtime/plantuml.jar',
            '-charset', 'UTF-8', '-pipe', '-t' + fmt]
    process = subprocess.run(command(work, argv, extra_ro(), environment()), input=code,
            capture_output=True, timeout=100, preexec_fn=limits)
    (work / (fmt + '.stderr')).write_bytes(process.stderr)
    if process.returncode:
        raise ValueError('source_dot243_export_failed:' + process.stderr.decode(errors='replace')[-1500:])
    return process.stdout


def initialize():
    """Explicit one-time setup; never called implicitly by conversion jobs."""
    report = W / 'plantuml_source_backend_compare_v1/report.json'
    comparison = json.loads(report.read_bytes())
    actual = comparison['summary']['existing_private_graphviz243']
    if actual['cases'] != 100 or actual['exact_rgba'] != 100:
        raise ValueError('fixed_source_comparison_not_100_exact_originals')
    DIRECTORY.mkdir(parents=True, exist_ok=False)
    # Reuse exactly the independently tested dot-only environment wrapper.
    DOT.write_bytes((W / 'plantuml_source_backend_compare_v1/dot243').read_bytes())
    DOT.chmod(0o555)
    pins = {str(Path(__file__).resolve()): sha(Path(__file__).read_bytes()),
            str(DOT): sha(DOT.read_bytes()), str(JAR): sha(JAR.read_bytes()),
            str(Path(JAVA)): sha(Path(JAVA).read_bytes()), str(report): sha(report.read_bytes())}
    for path in DEPENDENCIES.rglob('*'):
        if path.is_file() and 'packages' not in path.relative_to(DEPENDENCIES).parts:
            pins[str(path)] = sha(path.read_bytes())
    from sandbox_runner import __file__ as sandbox_file
    pins[str(Path(sandbox_file).resolve())] = sha(Path(sandbox_file).read_bytes())
    source_validation = dict(file=str(report), sha256=sha(report.read_bytes()),
            original_native_PNGs=100, exact_RGBA_matches=100, original_inputs_unchanged=True,
            same_PlantUML_and_Java_and_fonts=True, profiles_declared_before_results=True)
    with (DIRECTORY / 'manifest.json').open('xb') as handle:
        handle.write(json.dumps(dict(policy=POLICY, pins=pins, source_validation=source_validation),
                                ensure_ascii=False, sort_keys=True).encode() + bytes([10]))
    (DIRECTORY / 'manifest.json').chmod(0o444)
    return configuration()
